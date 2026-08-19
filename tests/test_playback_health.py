import unittest

from voicelink.health import (
    Classification,
    PlaybackHealthStore,
    classify_track_exception,
)
from voicelink.utils import NodeInfo, Plugin


class ClassifyTrackExceptionTests(unittest.TestCase):
    def test_all_clients_failed_is_youtube_source(self):
        result = classify_track_exception(
            "youtube",
            {"message": "Something failed", "cause": "AllClientsFailedException: clients exhausted"},
        )
        self.assertEqual(result, Classification("YOUTUBE_SOURCE_FAILED", "source"))

    def test_age_restricted_is_track_specific(self):
        result = classify_track_exception(
            "youtube",
            {"message": "This video is age-restricted", "cause": ""},
        )
        self.assertEqual(result, Classification("TRACK_UNAVAILABLE", "track"))

    def test_token_message_is_rate_limited_track_scope(self):
        result = classify_track_exception(
            "youtube",
            {"message": "This content isn’t available.", "severity": "common", "cause": ""},
        )
        self.assertEqual(result, Classification("SOURCE_RATE_LIMITED", "track"))

    def test_oauth_is_auth_required(self):
        result = classify_track_exception("youtube", {"message": "Sign in to confirm your age", "cause": "oauth"})
        self.assertEqual(result.code, "SOURCE_AUTH_REQUIRED")
        self.assertEqual(result.scope, "source")

    def test_unknown_fallback(self):
        result = classify_track_exception("soundcloud", {"message": "nope", "cause": "mystery"})
        self.assertEqual(result, Classification("UNKNOWN_PLAYBACK_ERROR", "track"))


class PlaybackHealthStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = PlaybackHealthStore()
        self.now = 1_000_000.0

    def _fail(self, item_id, encoded="enc", source="youtube", exception=None, now=None):
        return self.store.record_exception(
            source=source,
            exception=exception or {"cause": "AllClientsFailedException"},
            item_id=item_id,
            encoded=encoded,
            title=f"song-{item_id}",
            guild_id=1,
            now=now if now is not None else self.now,
        )

    def test_one_bad_track_does_not_degrade_source(self):
        classification, changed = self._fail(1)
        self.assertEqual(classification.code, "YOUTUBE_SOURCE_FAILED")
        self.assertFalse(changed)
        self.assertEqual(self.store.components["source:youtube"].status, "ok")

        classification, changed = self.store.record_exception(
            source="youtube",
            exception={"cause": "AllClientsFailedException"},
            item_id=1,
            encoded="enc",
            now=self.now + 10,
        )
        self.assertFalse(changed)

    def test_age_restricted_never_degrades_source(self):
        for item_id in (1, 2, 3, 4):
            self.store.record_exception(
                source="youtube",
                exception={"message": "This video is age-restricted"},
                item_id=item_id,
                encoded=f"e{item_id}",
                now=self.now + item_id,
            )
        youtube = self.store.components.get("source:youtube")
        self.assertTrue(youtube is None or youtube.status == "ok")

    def test_three_distinct_items_degrade_youtube(self):
        self.store.record_node(
            "DEFAULT",
            available=True,
            version="4.0.0",
            plugins=[Plugin({"name": "youtube-plugin", "version": "1.18.0"})],
            now=self.now,
        )
        self._fail(1, encoded=None)
        self._fail(2, encoded=None)
        classification, changed = self._fail(3, encoded=None)
        self.assertTrue(changed)
        youtube = self.store.components["source:youtube"]
        self.assertEqual(youtube.status, "degraded")
        self.assertIn("1.18.0", youtube.message)
        self.assertIsNone(youtube.available_version)
        self.assertNotIn("1.18.2", youtube.message or "")

    def test_two_encoded_tracks_degrade_youtube(self):
        self.store.record_node(
            "DEFAULT",
            available=True,
            plugins=[Plugin({"name": "youtube-plugin", "version": "1.18.0"})],
            now=self.now,
        )
        self._fail(1, encoded="aaa")
        _, changed = self._fail(2, encoded="bbb")
        self.assertTrue(changed)
        self.assertEqual(self.store.components["source:youtube"].status, "degraded")

    def test_rate_limit_threshold_uses_distinct_items(self):
        self.store.record_node(
            "DEFAULT",
            available=True,
            plugins=[Plugin({"name": "youtube-plugin", "version": "1.18.0"})],
            now=self.now,
        )
        exc = {"message": "This content isn’t available."}
        self.store.record_exception(source="youtube", exception=exc, item_id=1, encoded="a", now=self.now)
        self.store.record_exception(source="youtube", exception=exc, item_id=2, encoded="b", now=self.now)
        _, changed = self.store.record_exception(source="youtube", exception=exc, item_id=3, encoded="c", now=self.now)
        self.assertTrue(changed)
        self.assertEqual(self.store.components["source:youtube"].status, "degraded")

    def test_ipc_payload_has_no_stack_traces_or_available_version(self):
        self.store.record_node(
            "DEFAULT",
            available=True,
            plugins=[Plugin({"name": "youtube-plugin", "version": "1.18.0"})],
            now=self.now,
        )
        self._fail(1, encoded="a", exception={"cause": "AllClientsFailedException\n" + ("line\n" * 80)})
        self._fail(2, encoded="b", exception={"cause": "AllClientsFailedException"})
        payload = self.store.ipc_payload(guild_id=1, voice_connected=True, now=self.now)
        self.assertEqual(payload["op"], "playbackHealth")
        self.assertEqual(payload["guildId"], "1")
        dumped = str(payload)
        self.assertNotIn("line\nline", dumped)
        for component in payload["components"]:
            self.assertIsNone(component["available_version"])
            if component.get("last_error"):
                self.assertLessEqual(len(component["last_error"].get("detail") or ""), 120)
        self.assertEqual(payload["playbackFailure"]["code"], "YOUTUBE_SOURCE_FAILED")
        self.assertNotIn("causeStackTrace", dumped)

    def test_node_disconnect_is_unavailable(self):
        self.store.record_node("DEFAULT", available=True, version="4.0.8", now=self.now)
        changed = self.store.record_node("DEFAULT", available=False, version="4.0.8", now=self.now + 1)
        self.assertTrue(changed)
        node = self.store.components["node:DEFAULT"]
        self.assertEqual(node.status, "unavailable")
        self.assertEqual(node.last_error["code"], "NODE_UNAVAILABLE")

    def test_successful_start_clears_degraded_youtube(self):
        self.store.record_node(
            "DEFAULT",
            available=True,
            plugins=[Plugin({"name": "youtube-plugin", "version": "1.18.0"})],
            now=self.now,
        )
        self._fail(1, encoded="a")
        self._fail(2, encoded="b")
        self.assertTrue(self.store.record_track_start("youtube", now=self.now + 5))
        self.assertEqual(self.store.components["source:youtube"].status, "ok")

    def test_nodeinfo_parses_source_managers(self):
        info = NodeInfo({
            "version": {"semver": "4.0.8", "major": 4, "minor": 0, "patch": 8},
            "plugins": [{"name": "youtube-plugin", "version": "1.18.0"}],
            "sourceManagers": ["youtube", "soundcloud"],
        })
        self.assertEqual(info.source_managers, ["youtube", "soundcloud"])
        self.assertEqual(info.plugins[0].name, "youtube-plugin")


if __name__ == "__main__":
    unittest.main()
