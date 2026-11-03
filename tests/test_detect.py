"""detect.py の単体テスト。gh は呼ばず、gh_json を差し替えて試す。

実行: python3 -m unittest discover -s tests
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "skills/pr-review-sessions/scripts/detect.py"


def load_detect(folder):
    spec = importlib.util.spec_from_file_location("detect", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("STATE", "PENDING", "TEST_EVENTS", "INCLUDE_SELF", "INCLUDE_BOTS"):
        setattr(mod, name, os.path.join(folder, os.path.basename(getattr(mod, name))))
    return mod


def review(rid, login, state, bot=False):
    return {"id": rid, "state": state, "user": {"login": login, "type": "Bot" if bot else "User"}}


class FakeGitHub:
    """gh_json の代わり。requested と mine は PR の一覧、reviews は PR ごとのレビュー。"""

    def __init__(self):
        self.requested, self.mine, self.reviews = [], [], {}

    def pr(self, repo, number, title="title"):
        return {"repository": {"nameWithOwner": repo}, "number": number, "title": title,
                "url": f"https://github.com/{repo}/pull/{number}"}

    def __call__(self, args):
        if args[:2] == ["api", "user"]:
            return {"login": "me"}
        if args[:2] == ["search", "prs"]:
            return self.requested if "--review-requested=@me" in args else self.mine
        if args[0] == "api":
            repo, number = args[-1].split("/pulls/")[0].removeprefix("repos/"), int(args[-1].split("/")[-2])
            return [self.reviews.get((repo, number), [])]
        raise AssertionError(args)


class DetectTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.mod = load_detect(self.dir.name)
        self.gh = FakeGitHub()
        self.mod.gh_json = self.gh

    def tearDown(self):
        self.dir.cleanup()

    def detect(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.mod.detect()
        return json.loads(out.getvalue())

    def commit(self, ids):
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.commit(set(ids))

    def state(self):
        with open(self.mod.STATE, encoding="utf-8") as f:
            return json.load(f)

    def test_first_run_marks_existing_reviews_read(self):
        self.gh.mine = [self.gh.pr("o/r", 1)]
        self.gh.reviews[("o/r", 1)] = [review(10, "alice", "COMMENTED")]
        result = self.detect()
        self.assertTrue(result["first_run"])
        self.assertEqual(result["events"], [])
        self.commit([])
        self.assertTrue(self.state()["initialized"])
        self.assertEqual(self.detect()["events"], [])

    def test_bind_before_first_commit_keeps_first_run(self):
        self.gh.mine = [self.gh.pr("o/r", 1)]
        self.gh.reviews[("o/r", 1)] = [review(10, "alice", "COMMENTED")]
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.bind("author:o/r#1", "local_x")
        self.assertTrue(self.detect()["first_run"])

    def test_new_comment_and_approve(self):
        self.gh.mine = [self.gh.pr("o/r", 1)]
        self.detect()
        self.commit([])
        self.gh.reviews[("o/r", 1)] = [review(11, "alice", "CHANGES_REQUESTED")]
        events = self.detect()["events"]
        self.assertEqual([e["kind"] for e in events], ["comment"])
        self.commit([events[0]["id"]])
        self.gh.reviews[("o/r", 1)].append(review(12, "bob", "APPROVED"))
        self.assertEqual([e["kind"] for e in self.detect()["events"]], ["approve"])

    def test_bots_and_dismissed_are_ignored(self):
        self.gh.mine = [self.gh.pr("o/r", 1)]
        self.detect()
        self.commit([])
        self.gh.reviews[("o/r", 1)] = [review(11, "copilot", "COMMENTED", bot=True),
                                       review(12, "alice", "DISMISSED")]
        self.assertEqual(self.detect()["events"], [])

    def test_failed_event_is_retried(self):
        self.gh.requested = [self.gh.pr("o/r", 2)]
        events = self.detect()["events"]
        self.assertEqual([e["kind"] for e in events], ["request"])
        self.commit([])
        self.assertEqual([e["id"] for e in self.detect()["events"]], [events[0]["id"]])

    def test_events_over_limit_are_deferred(self):
        self.gh.requested = [self.gh.pr("o/r", n) for n in range(1, 13)]
        result = self.detect()
        self.assertEqual(len(result["events"]), self.mod.MAX_EVENTS)
        self.assertEqual(result["deferred"], 2)
        self.commit([e["id"] for e in result["events"]])
        self.assertEqual(len(self.detect()["events"]), 2)

    def test_output_hides_raw_title_and_url(self):
        self.gh.requested = [self.gh.pr("o/r", 3, title="悪い\nタイトル" + "あ" * 50)]
        event = self.detect()["events"][0]
        self.assertNotIn("title", event)
        self.assertNotIn("url", event)
        self.assertNotIn("\n", event["name"])

    def test_skip_existing(self):
        self.gh.requested = [self.gh.pr("o/r", 4)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.skip_existing()
        self.assertEqual(self.detect()["events"], [])

    def test_test_event_without_colon_does_not_crash(self):
        with open(self.mod.TEST_EVENTS, "w", encoding="utf-8") as f:
            json.dump([{"id": "plain", "kind": "approve", "label": "Approve", "repo": "o/r",
                        "number": 5, "title": "t", "url": "u"}], f)
        self.detect()
        self.commit([])

    def test_overlapping_run_is_busy(self):
        self.gh.requested = [self.gh.pr("o/r", 6)]
        first = self.detect()
        self.assertEqual(len(first["events"]), 1)
        second = self.detect()  # 1回目の commit の前に、もう1つの実行が来た
        self.assertTrue(second["busy"])
        self.assertEqual(second["events"], [])
        self.commit([first["events"][0]["id"]])
        self.assertEqual(self.detect()["events"], [])

    def test_stale_pending_is_overwritten(self):
        self.gh.requested = [self.gh.pr("o/r", 7)]
        self.detect()
        old = os.path.getmtime(self.mod.PENDING) - self.mod.BUSY_SECONDS - 1
        os.utime(self.mod.PENDING, (old, old))  # 途中で止まった実行の残り
        result = self.detect()
        self.assertNotIn("busy", result)
        self.assertEqual(len(result["events"]), 1)

    def test_dry_run_does_not_block_next_run(self):
        self.gh.requested = [self.gh.pr("o/r", 8)]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.mod.detect(dry_run=True)
        self.assertEqual(len(json.loads(out.getvalue())["events"]), 1)
        self.assertFalse(os.path.exists(self.mod.PENDING))
        self.assertEqual(len(self.detect()["events"]), 1)


if __name__ == "__main__":
    unittest.main()
