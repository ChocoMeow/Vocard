import unittest

from voicelink.health import (
    Classification,
    DEGRADED_CLEAR_SECONDS,
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

    def test_one_track_unavailable_keeps_source_healthy(self):
        classification, changed = self.store.record_exception(
            source="youtube",
            exception={"message": "private video"},
            item_id=1,
            encoded="enc",
            title="secret",
            guild_id=1,
            now=self.now,
        )
        self.assertEqual(classification, Classification("TRACK_UNAVAILABLE", "track"))
        self.assertFalse(changed)
        youtube = self.store.components["source:youtube"]
        self.assertEqual(youtube.status, "ok")
        self.assertEqual(self.store.guild_failure(1)["code"], "TRACK_UNAVAILABLE")

    def test_one_auth_required_degrades_youtube_immediately(self):
        classification, changed = self.store.record_exception(
            source="youtube",
            exception={"message": "Sign in", "cause": "AllClientsFailedException: oauth / no valid PO token"},
            item_id=1,
            encoded="enc",
            title="Stateside",
            guild_id=1,
            now=self.now,
        )
        self.assertEqual(classification, Classification("SOURCE_AUTH_REQUIRED", "source"))
        self.assertTrue(changed)
        youtube = self.store.components["source:youtube"]
        self.assertEqual(youtube.status, "degraded")
        self.assertNotEqual(youtube.status, "unavailable")
        self.assertEqual(youtube.last_error["code"], "SOURCE_AUTH_REQUIRED")
        self.assertNotIn("repeated", youtube.message or "")

    def test_one_youtube_source_failed_degrades_immediately(self):
        classification, changed = self._fail(1)
        self.assertEqual(classification.code, "YOUTUBE_SOURCE_FAILED")
        self.assertTrue(changed)
        youtube = self.store.components["source:youtube"]
        self.assertEqual(youtube.status, "degraded")
        self.assertNotEqual(youtube.status, "unavailable")

        _, changed = self.store.record_exception(
            source="youtube",
            exception={"cause": "AllClientsFailedException"},
            item_id=1,
            encoded="enc",
            now=self.now + 10,
        )
        self.assertFalse(changed)
        self.assertEqual(self.store.components["source:youtube"].status, "degraded")

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

    def test_repeated_source_failures_stay_degraded_and_persist(self):
        self.store.record_node(
            "DEFAULT",
            available=True,
            version="4.0.0",
            plugins=[Plugin({"name": "youtube-plugin", "version": "1.18.0"})],
            now=self.now,
        )
        _, changed = self._fail(1, encoded=None)
        self.assertTrue(changed)
        youtube = self.store.components["source:youtube"]
        self.assertEqual(youtube.status, "degraded")
        self.assertIn("1.18.0", youtube.message)
        self.assertFalse(youtube.persistent)

        self._fail(2, encoded=None)
        _, changed = self._fail(3, encoded=None)
        self.assertTrue(changed)
        self.assertEqual(youtube.status, "degraded")
        self.assertTrue(youtube.persistent)
        self.assertIn("repeated", youtube.message)
        self.assertIsNone(youtube.available_version)
        self.assertNotIn("1.18.2", youtube.message or "")

        recovered = self.store.expire_degraded(now=self.now + DEGRADED_CLEAR_SECONDS + 1)
        self.assertFalse(recovered)
        self.assertEqual(youtube.status, "degraded")

    def test_two_encoded_tracks_mark_source_persistent(self):
        self.store.record_node(
            "DEFAULT",
            available=True,
            plugins=[Plugin({"name": "youtube-plugin", "version": "1.18.0"})],
            now=self.now,
        )
        self._fail(1, encoded="aaa")
        _, changed = self._fail(2, encoded="bbb")
        self.assertTrue(changed)
        youtube = self.store.components["source:youtube"]
        self.assertEqual(youtube.status, "degraded")
        self.assertTrue(youtube.persistent)

    def test_rate_limit_threshold_uses_distinct_items(self):
        self.store.record_node(
            "DEFAULT",
            available=True,
            plugins=[Plugin({"name": "youtube-plugin", "version": "1.18.0"})],
            now=self.now,
        )
        exc = {"message": "This content isn’t available."}
        _, changed = self.store.record_exception(source="youtube", exception=exc, item_id=1, encoded="a", now=self.now)
        self.assertFalse(changed)
        self.assertEqual(self.store.components["source:youtube"].status, "ok")
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
        self.assertTrue(self.store.record_track_start("youtube", now=self.now + 5))
        youtube = self.store.components["source:youtube"]
        self.assertEqual(youtube.status, "ok")
        self.assertFalse(youtube.persistent)

    def test_first_source_failure_can_timeout_without_playback(self):
        self._fail(1)
        youtube = self.store.components["source:youtube"]
        self.assertEqual(youtube.status, "degraded")
        changed = self.store.expire_degraded(now=self.now + DEGRADED_CLEAR_SECONDS + 1)
        self.assertTrue(changed)
        self.assertEqual(youtube.status, "ok")

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
