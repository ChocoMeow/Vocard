import websockets, json
from uuid import uuid4

class IPCClient:
    def __init__(
        self,
        host = "127.0.0.1", 
        port = 8000, 
        secret_key = None,
        callback = None
    ):
        
        self.host = host
        self.port = port
        self.websocket = None
        self.secret_key = secret_key
        self.callback = callback
        self.id = uuid4()

    async def connect(self):
        self.websocket = await websockets.connect(f"ws://{self.host}:{self.port}", extra_headers={"Client-Id": str(self.id)})
        await self.start_receiver()

    async def send(self, message, user):
        if not self.websocket:
            await self.connect()
        data = json.loads(message)

        payload = {
            "sercet": self.secret_key,
            "data": data | {"user_id": user.id, "guild_id": user.guild_id}
        }

        await self.websocket.send(json.dumps(payload))

    async def receive(self):
        async for message in self.websocket:
            if self.callback:
                data = json.loads(message)
                self.callback(data)

    async def start_receiver(self):
        await self.receive()