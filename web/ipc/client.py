import websockets, json, asyncio
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
        self.is_connected = False

    async def connect_and_reconnect(self):
        while True:
            if not self.is_connected:
                await self.connect()
                print("Reconnect in next 10s!")
                await asyncio.sleep(10)

    async def connect(self):
        try:
            self.websocket = await websockets.connect(f"ws://{self.host}:{self.port}", extra_headers={"Client-Id": str(self.id)})
            await self.start_receiver()
        except:
            self.is_connected = False
            pass
            
    async def send(self, message, user):
        if not self.is_connected:
            await self.connect_and_reconnect()
        
        data = json.loads(message)

        payload = {
            "sercet": self.secret_key,
            "data": data | {"user_id": user.id, "guild_id": user.guild_id}
        }

        await self.websocket.send(json.dumps(payload))

    async def receive(self):
        print("Connected ipc server!")
        self.is_connected = True
        async for message in self.websocket:
            if self.callback:
                data = json.loads(message)
                self.callback(data)

    async def start_receiver(self):
        await self.receive()