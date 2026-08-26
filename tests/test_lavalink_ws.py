import asyncio
import json
import logging
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import WSMessage, WSMsgType

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voicelink.enums import ReconnectStrategy
from voicelink.pool import Node, interpret_lavalink_ws_message


def _msg(msg_type, data=None, extra=None):
    return WSMessage(type=msg_type, data=data, extra=extra)


class InterpretLavalinkWsTests(unittest.TestCase):
    def test_text_json_dispatches_payload(self):
        decision = interpret_lavalink_ws_message(_msg(WSMsgType.TEXT, '{"op":"stats","players":1}'))
        self.assertEqual(decision.action, "dispatch")
        self.assertEqual(decision.payload["op"], "stats")
        self.assertEqual(decision.payload["players"], 1)

    def test_close_with_integer_code_does_not_call_json(self):
        msg = _msg(WSMsgType.CLOSE, 1001, "going away")
        with self.assertRaises(TypeError):
            json.loads(msg.data)
        decision = interpret_lavalink_ws_message(msg)
        self.assertEqual(decision.action, "reconnect")
        self.assertEqual(decision.close_code, 1001)
        self.assertEqual(decision.close_reason, "going away")

    def test_closed_reconnects(self):
        decision = interpret_lavalink_ws_message(_msg(WSMsgType.CLOSED, None, None))
        self.assertEqual(decision.action, "reconnect")

    def test_error_reconnects_with_exception(self):
        err = RuntimeError("socket boom")
        decision = interpret_lavalink_ws_message(_msg(WSMsgType.ERROR, err, None))
        self.assertEqual(decision.action, "reconnect")
        self.assertIs(decision.error, err)

    def test_ping_and_pong_are_ignored(self):
        self.assertEqual(interpret_lavalink_ws_message(_msg(WSMsgType.PING, b"", None)).action, "ignore")
        self.assertEqual(interpret_lavalink_ws_message(_msg(WSMsgType.PONG, b"", None)).action, "ignore")

    def test_binary_is_ignored(self):
        self.assertEqual(interpret_lavalink_ws_message(_msg(WSMsgType.BINARY, b"{}", None)).action, "ignore")

    def test_non_object_text_json_is_ignored(self):
        self.assertEqual(interpret_lavalink_ws_message(_msg(WSMsgType.TEXT, "[1,2]")).action, "ignore")
        self.assertEqual(interpret_lavalink_ws_message(_msg(WSMsgType.TEXT, "not-json")).action, "ignore")


class FakeWebSocket:
    def __init__(self, messages):
        self._messages = list(messages)
        self.receive_calls = 0

    async def receive(self):
        self.receive_calls += 1
        if not self._messages:
            await asyncio.sleep(60)
            raise asyncio.TimeoutError("receive hung")
        return self._messages.pop(0)


class ListenStub:
    def __init__(self, messages):
        self._websocket = FakeWebSocket(messages)
        self._available = True
        self._identifier = "test-node"
        self._session_id = "session-1"
        self._logger = logging.getLogger("vocard.test.lavalink")
        self._players = {}
        self._payloads = []
        self._reconnect_strategy = ReconnectStrategy.RECONNECT_ON_DROP
        loop = asyncio.get_running_loop()
        self._bot = SimpleNamespace(loop=loop)
        self._reconnects = 0

    async def _handle_payload(self, data):
        self._payloads.append(data)

    async def connect(self):
        self._reconnects += 1
        self._available = True

    async def _listen(self):
        await Node._listen(self)


class LavalinkListenTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backoff_patch = patch("voicelink.pool.ExponentialBackoff.delay", return_value=0)
        self.backoff_patch.start()

    async def asyncTearDown(self):
        self.backoff_patch.stop()

    async def test_listen_text_then_close_does_not_raise(self):
        stub = ListenStub(
            [
                _msg(WSMsgType.TEXT, '{"op":"ready","sessionId":"abc"}'),
                _msg(WSMsgType.CLOSE, 1000, "normal"),
            ]
        )
        await asyncio.wait_for(stub._listen(), timeout=2)
        self.assertEqual(stub._payloads[0]["op"], "ready")
        self.assertGreaterEqual(stub._reconnects, 1)

    async def test_listen_close_integer_does_not_typeerror(self):
        stub = ListenStub([_msg(WSMsgType.CLOSE, 1006, "abnormal")])
        await asyncio.wait_for(stub._listen(), timeout=2)
        self.assertGreaterEqual(stub._reconnects, 1)

    async def test_listen_closed_reconnects(self):
        stub = ListenStub([_msg(WSMsgType.CLOSED, None, None)])
        await asyncio.wait_for(stub._listen(), timeout=2)
        self.assertGreaterEqual(stub._reconnects, 1)

    async def test_listen_error_reconnects(self):
        stub = ListenStub([_msg(WSMsgType.ERROR, RuntimeError("ws"), None)])
        await asyncio.wait_for(stub._listen(), timeout=2)
        self.assertGreaterEqual(stub._reconnects, 1)

    async def test_listen_ping_pong_then_close(self):
        stub = ListenStub(
            [
                _msg(WSMsgType.PING, b"", None),
                _msg(WSMsgType.PONG, b"", None),
                _msg(WSMsgType.TEXT, '{"op":"stats"}'),
                _msg(WSMsgType.CLOSED, 1000, ""),
            ]
        )
        await asyncio.wait_for(stub._listen(), timeout=2)
        self.assertEqual(stub._payloads[0]["op"], "stats")
        self.assertGreaterEqual(stub._reconnects, 1)


NAME = "Lavalink websocket frames"
DESCRIPTION = (
    "Vocard does not JSON-decode CLOSE integer codes; CLOSE/ERROR reconnect "
    "without crashing, and PING/PONG/BINARY are ignored."
)


def run() -> bool:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(InterpretLavalinkWsTests))
    suite.addTests(loader.loadTestsFromTestCase(LavalinkListenTests))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    unittest.main()
