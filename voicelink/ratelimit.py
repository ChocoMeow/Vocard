"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .pool import Node

class YTToken:
    def __init__(self, token: str):
        self.token: str = token
        self.allow_retry_time: float = 0.0
        self.requested_times: int = 0
        self.is_flagged: bool = False
        self.flagged_time: float = 0.0

    @property
    def allow_retry(self) -> bool:
        """Determine if the token can be used again."""
        return time.time() >= self.allow_retry_time

class YTRatelimit(ABC):
    """
    Abstract base class for YouTube rate limit strategies.
    """
    def __init__(self, node: "Node", tokens: List[str]) -> None:
        self.node: "Node" = node
        self.tokens: List[YTToken] = [YTToken(token) for token in tokens]
        self.active_token: Optional[YTToken] = self.tokens[0] if self.tokens else None

    @abstractmethod
    async def flag_active_token(self) -> None:
        """
        Mark the current active token as flagged when a rate-limit is encountered.
        """
        pass

    @abstractmethod
    async def handle_request(self) -> None:
        """
        Update usage count or perform any necessary pre-request operations.
        """
        pass

    async def swap_token(self) -> Optional[YTToken]:
        """
        Swap the active token with another token that is either not flagged or ready to retry.
        If a new token is found, update it via the node and return it.
        """
        for token in self.tokens:
            if token != self.active_token and (not token.is_flagged or token.allow_retry):
                try:
                    await self.node.update_refresh_yt_access_token(token)
                    self.active_token = token
                    return token
                except Exception as e:
                    self.node._logger.error("Something wrong while updating the youtube access token.", exc_info=e)
        
        self.node._logger.warning("No active token available for processing the request.")
        return None

class LoadBalance(YTRatelimit):
    """
    A rate limiting strategy that load balances requests across tokens.
    """
    def __init__(self, node: "Node", config: Dict[str, Any]):
        super().__init__(node, tokens=config.get("tokens", []))
        self._config: Dict[str, Any] = config.get("config", {})
        self._retry_time: int = self._config.get("retry_time", 10_800)
        self._max_requests: int = self._config.get("max_requests", 30)

    async def flag_active_token(self) -> None:
        """
        Flag the active token and set a delay (e.g., 3 hours) until it can be retried.
        """
        if self.active_token:
            self.active_token.is_flagged = True
            self.active_token.flagged_time = time.time()
            self.active_token.allow_retry_time = self.active_token.flagged_time + self._retry_time
            await self.swap_token()

    async def handle_request(self) -> None:
        """
        Increment the active token's usage counter and swap tokens if a threshold is reached.
        """
        if not self.active_token:
            return await self.swap_token()

        self.active_token.requested_times += 1
        if self.active_token.requested_times >= self._max_requests:
            self.active_token.requested_times = 0
            swapped_token = await self.swap_token()
            if swapped_token is None:
                return self.node._logger.warning("No available token found after swapping.")

STRATEGY = {
    "LoadBalance": LoadBalance
}