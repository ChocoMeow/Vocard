from flask import Flask, redirect, url_for, session, request, render_template, abort, Response, stream_with_context
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms, disconnect
from ipc import IPCClient
from objects import User
from dotenv import load_dotenv
from datetime import timedelta

import requests
import json
import os
import asyncio
import functools

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SERCET_KEY")
socketio = SocketIO(app)

# Discord OAuth2 credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET_ID")
REDIRECT_URI = 'http://127.0.0.1:5000/callback'
DISCORD_API_BASE_URL = 'https://discord.com/api'

USERS = {}

def get_user(user_id: int):
    for user in USERS.values():
        if user.id == user_id:
            return user    
    return None

def user_join_room(guild_id: int, user: User) -> None:
    if not user.sid:
        return
    join_room(guild_id, sid=user.sid)
    user.guild_id = guild_id

def user_leave_room(guild_id: int, user: User) -> None:
    if not user.sid:
        return
    leave_room(guild_id, sid=user.sid)
    user.guild_id = None

def message_handler(data: dict):
    op = data.get("op")

    user_id = data.get("user_id", None)
    if user_id:
        user: User = get_user(user_id)
    else:
        user = None

    guild_id = data.get("guild_id", None)
            
    if op == "updateGuild":
        user_id = data.get("user", {}).get("user_id", None)
        is_joined = data.get("is_joined")

        user: User = get_user(user_id)
        if user and guild_id:
            user_join_room(guild_id, user) if is_joined else user_leave_room(guild_id, user)

    elif op == "createPlayer":
        members_id = data.get("members_id", [])
        for member_id in members_id:
            user: User = get_user(member_id)
            if user:
                user_join_room(guild_id, user)
                emit('message', {
                    "op": "updateGuild",
                    "user": {
                        "user_id": user.id,
                        "avatar_url": user.avatar.url,
                        "name": user.username
                    },
                    "is_joined": True
                }, to=user.sid)
        return
    
    if user:
        if guild_id and user.sid:
            join_room(guild_id, sid=user.sid)
        elif guild_id in rooms(user.sid):
            pass
        else:
            emit('message', data, to=user.sid)
        
        if op == "initPlayer":
            return emit('message', data, to=user.sid)
    
    if guild_id:
        skip_sids = []
        if skip_users := data.get("skip_users"):
            for user_id in skip_users:
                if user := get_user(user_id):
                    skip_sids.append(user.sid)

        emit('message', data, room=guild_id, skip_sid=skip_sids)

ipc_client = IPCClient(secret_key=app.secret_key, callback=message_handler)

def login_required(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        token = session.get("discord_token", None)
        if not token:
            return redirect(url_for('login'))

        if token not in USERS:
            resp = requests_api(f'{DISCORD_API_BASE_URL}/users/@me', headers={'Authorization': f'Bearer {token}'})
            if resp:
                user = USERS[token] = User(resp)
            else:
                return redirect(url_for('login'))
        else:
            user = USERS[token]

        return func(user, *args, **kwargs)
    return wrapper


def requests_api(url: str, headers=None):
    resp = requests.get(url=url, headers=headers)
    if not resp:
        return False

    return resp.json()

@app.route('/<path:url>', methods=["GET"])
@login_required
def proxy(user: User, url):
    request = requests.get(url, stream=True)
    response = Response(
        stream_with_context(request.iter_content()),
        content_type=request.headers['content-type'],
        status=request.status_code
    )
    response.headers['Access-Control-Allow-Origin'] = "*"
    return response

# home page
@app.route('/')
@login_required
def home(user: User):
    return render_template("index.html", user=user)

# login page
@app.route('/login')
def login():
    # redirect to Discord OAuth2 login page
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': 'identify'
    }
    return redirect(f'{DISCORD_API_BASE_URL}/oauth2/authorize?{"&".join([f"{k}={v}" for k, v in params.items()])}')

# Logout page
@app.route('/logout')
@login_required
def logout(user: User):
    session.pop("discord_token", None)
    
    return redirect(url_for("home"))

# callback page
@app.route('/callback')
def callback():
    # fetch user token from Discord OAuth2
    code = request.args.get('code')
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'scope': 'identify'
    }
    response = requests.post(f'{DISCORD_API_BASE_URL}/oauth2/token', data=data)
    token_data = json.loads(response.content.decode('utf-8'))
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=30)
    session['discord_token'] = token_data.get("access_token")

    return redirect(url_for("home"))


@socketio.on("connect")
@login_required
def handle_connect(user: User):
    if user.sid:
        disconnect(sid=user.sid)
    user.sid = request.sid
    asyncio.run(ipc_client.send('{"op": "initPlayer"}', user))

@socketio.on("disconnect")
@login_required
def handle_disconnect(user: User):
    user.sid = None

@socketio.on("message")
@login_required
def handle_message(user: User, msg):
    asyncio.run(ipc_client.send(msg, user))

if __name__ == '__main__':
    socketio.run(app, host="127.0.0.1", port=5000)
