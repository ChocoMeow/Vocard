import aiohttp
import asyncio
import logging
import function as func

from discord.ext import commands
from typing import Optional

from .methods import process_methods

class IPCClient:
    def __init__(
        self,
        bot: commands.Bot,
        host: str,
        port: int,
        password: str,
        heartbeat: int = 30,
        secure: bool = False,
        *arg,
        **kwargs
    ) -> None:
        
        self._bot: commands.Bot = bot
        self._host: str = host
        self._port: int = port
        self._password: str = password
        self._heartbeat: int = heartbeat
        self._is_secure: bool = secure
        self._is_connected: bool = False
        self._is_connecting: bool = False
        self._logger: logging.Logger = logging.getLogger("ipc_client")
        
        self._websocket_url: str = f"{'wss' if self._is_secure else 'ws'}://{self._host}:{self._port}/ws_bot"
        self._session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._task: Optional[asyncio.Task] = None

        self._heanders = {
            "Authorization": self._password,
            "User-Id": str(bot.user.id),
            "Client-Version": func.settings.version
        }

    async def _listen(self) -> None:
        while True:
            try:
                msg = await self._websocket.receive()
                self._logger.debug(f"Receive Message: {msg}")
            except:
                break
            
            if msg.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]:
                self._is_connected = False

                self._logger.info("Trying to reconnect dashboard in 10s")
                await asyncio.sleep(10)
                if not self._is_connected:
                    try:
                        await self.connect()
                    except:
                        pass
            else:
                self._bot.loop.create_task(process_methods(self, self._bot, msg.json()))

    async def send(self, data: dict):
        if self._is_connected:
            self._logger.debug(f"Send Message: {data}")
            await self._websocket.send_json(data)

    async def connect(self):    
        try:
            if not self._session:
                self._session = aiohttp.ClientSession()

            if self._is_connecting:
                return
            
            self._is_connecting = True
            self._websocket = await self._session.ws_connect(
                self._websocket_url, headers=self._heanders, heartbeat=self._heartbeat
            )
        
            self._task = self._bot.loop.create_task(self._listen())
            self._is_connected = True
            
            self._logger.info("Connected to dashboard!")
        
        except aiohttp.ClientConnectorError:
            raise Exception("The connection is failed.")
        
        except aiohttp.WSServerHandshakeError:
            raise Exception("The password is invalid.")
        
        except Exception as e:
            self._logger.error("Error occured while connecting to dashboard!", exc_info=e)
        
        finally:
            self._is_connecting = False
            
        return self

    async def disconnect(self) -> None:
        self._is_connected = False
        self._task.cancel()
        self._logger.info("Disconnected to dashboard!")