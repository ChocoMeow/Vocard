import json

from websockets.server import serve, WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed
from discord.ext import commands

from typing import (
    Optional,
    Dict,
    Any
)

class IPCServer:
    def __init__(
        self, 
        bot: commands.Bot,
        host: str = "127.0.0.1",
        port: int = 8000,
        sercet_key: Optional[str] = None
    ):
        self.bot = bot
        self.host = host
        self.port = port
        self.sercet_key = sercet_key

        self.user = {}
        self.connections = set()
    
    def is_secure(self, data: dict) -> bool:
        if (key := data.get("sercet")):
            return str(key) == str(self.sercet_key)
        return bool(self.sercet_key is None)
    
    async def start(self):
        try:
            print("Starting IPC")
            await serve(self.handle_ipc_connection, self.host, self.port)
        except Exception as e:
            print(e)

    async def handle_ipc_connection(self, websocket: WebSocketServerProtocol):
        from .methods import process_methods
        
        client_id = websocket.request_headers.get("Client-ID", None)
        if not client_id:
            return
        
        self.connections.add(websocket)
        try:
            async for message in websocket:
                data: Dict[str, Any] = json.loads(message)
                if self.is_secure(data):
                    action = data.get("data")
                    await process_methods(websocket, self.bot, action)                    

        except ConnectionClosed:
            pass

        self.connections.remove(websocket)
    
    async def send(self, payload):
        for conn in self.connections:
            try:
                await conn.send(json.dumps(payload))
            except:
                await conn.close()
                self.connections.remove(conn)