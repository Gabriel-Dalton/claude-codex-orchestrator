import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cco.app import App
from cco import codex
from cco.config import load
from cco.orca import Orca, OrcaError, TerminalGone
from cco.state import State


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / "example-app"
        self.folder.mkdir()
        (self.folder / "task.md").write_text("One invented task.", encoding="utf-8")
        self.fake = self.root / "fake.json"
        self.fake.write_text(json.dumps({"repo": str(self.root), "terminals": []}), encoding="utf-8")
        self.env = patch.dict(os.environ, {"CCO_FAKE_STATE": str(self.fake)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.orca = Orca([sys.executable, str(Path(__file__).with_name("fake_orca.py"))])
        self.app = App(self.orca, State(self.root / "state"), load())
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def data(self):
        return json.loads(self.fake.read_text(encoding="utf-8"))

    def update(self, **values):
        data = self.data()
        data.update(values)
        self.fake.write_text(json.dumps(data), encoding="utf-8")

    def launch(self, **kwargs):
        return self.app.launch(self.folder, "task.md", "standard", **kwargs)

    def test_duplicate_restored_foreign_terminal(self):
        self.update(terminals=[{"handle": "term_foreign", "worktreePath": str(self.folder)}])
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.launch()
        self.assertEqual(len(self.data()["calls"]), 1)

    def test_duplicate_fallback_displayed_folder(self):
        self.update(terminals=[{"handle": "term_foreign", "worktreePath": str(self.root),
                               "preview": "gpt-6-astra medium · " + str(self.folder)}])
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.launch()

    def test_unknown_folder_falls_back(self):
        self.update(fallback=True)
        agent = self.launch()
        creates = [c for c in self.data()["calls"] if c[:2] == ["terminal", "create"]]
        self.assertEqual(len(creates), 2)
        self.assertIn("path:" + str(self.root), creates[1])
        self.assertIn("-C", creates[1][creates[1].index("--command") + 1])
        self.assertEqual(self.app.owned(agent)["folder"], str(self.folder))

    def test_draft_retry_sends_only_enter(self):
        self.update(retry=True)
        self.launch()
        sends = [c for c in self.data()["calls"] if c[:2] == ["terminal", "send"]]
        self.assertEqual(len(sends), 2)
        self.assertNotIn("--text", sends[1])
        prompt = sends[0][sends[0].index("--text") + 1]
        self.assertNotIn("\n", prompt)
        self.assertIn("task.md", prompt)
        self.assertNotIn("One invented task", prompt)

    def test_clean_start_placeholder_is_not_a_draft(self):
        self.update(draft="Ask Codex to do anything")
        self.launch()
        sends = [c for c in self.data()["calls"] if c[:2] == ["terminal", "send"]]
        self.assertEqual(len(sends), 1)
        self.assertIn("task.md", sends[0][sends[0].index("--text") + 1])

    def test_real_draft_still_blocks_submission(self):
        self.update(draft="Do another task")
        with self.assertRaisesRegex(ValueError, "has a draft"):
            self.launch()
        self.assertFalse(any(c[:2] == ["terminal", "send"] for c in self.data()["calls"]))

    def test_shell_exit_is_reported(self):
        self.update(screen="Agent failed to start\nC:\\code\\example-app>")
        with self.assertRaisesRegex(ValueError, "exited back to a shell prompt"):
            self.launch()
        self.assertEqual(len(self.app.state.read()), 1)

    def test_send_queues_during_work(self):
        agent = self.launch()
        self.update(calls=[])
        self.app.send(agent, "Read FOLLOWUP.md")
        sends = [c for c in self.data()["calls"] if c[:2] == ["terminal", "send"]]
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0][sends[0].index("--text") + 1], "Read FOLLOWUP.md")

    def test_peek_with_limited_console_encoding(self):
        from cco.cli import main
        agent = self.launch()
        self.update(screen="\u203a \u2603 \U0001f680")
        buffer = io.BytesIO()
        output = io.TextIOWrapper(buffer, encoding="ascii")
        with patch("cco.cli.Orca", return_value=self.orca), patch("cco.cli.State", return_value=self.app.state), \
                patch("sys.stdout", output):
            self.assertEqual(main(["peek", agent]), 0)
            output.flush()
            self.assertIn("\u2603", buffer.getvalue().decode("utf-8"))
        output.detach()

    def test_queue_no_turn_start_retries_only_enter(self):
        agent = self.launch()
        self.update(calls=[], retry=True)
        self.app.send(agent, "Read FOLLOWUP.md")
        sends = [c for c in self.data()["calls"] if c[:2] == ["terminal", "send"]]
        self.assertEqual(len(sends), 2)
        self.assertNotIn("--text", sends[1])

    def test_launch_refuses_hostile_identifiers_before_orca(self):
        for key in ("model", "effort"):
            with self.assertRaisesRegex(ValueError, "must match"):
                self.launch(**{key: ""})
        for char in ";&|` ":
            for key in ("model", "effort"):
                with self.subTest(char=char, key=key), self.assertRaisesRegex(ValueError, "must match"):
                    self.launch(**{key: "example" + char + "bad"})
        self.assertNotIn("calls", self.data())

    def test_launch_refuses_unsafe_paths_and_title_before_orca(self):
        for key in ("folder", "task", "title"):
            values = {"folder": self.folder, "task": "task.md", "title": "example"}
            values[key] = str(values[key]) + "$"
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "character"):
                self.app.launch(tier="easy", **values)
        self.assertNotIn("calls", self.data())

    def test_trust_prompt_before_task(self):
        self.update(trust=True, screen="Do you trust this folder?\n1. Yes, proceed\n2. No, exit")
        self.launch()
        sends = [c for c in self.data()["calls"] if c[:2] == ["terminal", "send"]]
        self.assertEqual(sends[0][sends[0].index("--text") + 1], "1")
        self.assertIn("task.md", sends[1][sends[1].index("--text") + 1])

    def test_wait_exit_codes(self):
        agent = self.launch()
        self.update(screen="Worked for 5m 21s\n› Ask Codex to do anything")
        self.assertEqual(self.app.wait([agent], "idle", timeout=0), 0)
        self.update(screen="Working (1m 02s)")
        self.assertEqual(self.app.wait([agent], "idle", timeout=0), 2)
        self.update(gone=True)
        self.assertEqual(self.app.wait([agent], "idle", timeout=0), 3)
        self.update(gone=False, terminals=[])
        self.assertEqual(self.app.wait([agent], "idle", timeout=0), 4)

    def test_wait_report_and_multiple_ids(self):
        first = self.launch()
        # An independently recorded owned terminal, with a unique handle.
        records = self.app.state.read()
        records["second"] = dict(records[first], terminal="term_second")
        self.app.state.save(records)
        self.update(terminals=self.data()["terminals"] + [{"handle": "term_second", "incarnationId": "process_one"}])
        (self.folder / "task.report.md").write_text("Done", encoding="utf-8")
        self.assertEqual(self.app.wait([first, "second"], "report:task.report.md", timeout=0), 0)

    def test_wait_pr_missing_and_present(self):
        agent = self.launch()
        with patch("cco.app.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "gh"):
                self.app.wait([agent], "pr:feature/example")
        real_run = subprocess.run
        def run(args, **kwargs):
            if args[0] == "gh":
                return subprocess.CompletedProcess(args, 0, '[{"number": 7}]', '')
            return real_run(args, **kwargs)
        with patch("cco.app.shutil.which", return_value="gh"), patch("cco.app.subprocess.run", side_effect=run):
            self.assertEqual(self.app.wait([agent], "pr:feature/example", timeout=0), 0)

    def test_tier_defaults_and_overrides(self):
        cfg = load()
        self.assertEqual([cfg["tiers"][t]["model"] for t in ("easy", "standard", "hard")],
                         ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-6-astra"])
        agent = self.launch(model="example-model", effort="high")
        self.assertEqual(self.app.owned(agent)["model"], "example-model")
        self.assertEqual(self.app.owned(agent)["effort"], "high")

    def test_stop_refuses_foreign(self):
        with self.assertRaisesRegex(ValueError, "did not launch"):
            self.app.stop("term_foreign")
        self.assertNotIn("calls", self.data())

    def test_stop_all_only_owned(self):
        agent = self.launch()
        self.update(terminals=self.data()["terminals"] + [{"handle": "term_foreign"}])
        self.app.stop(all_mine=True)
        self.assertEqual(self.data()["terminals"], [{"handle": "term_foreign"}])
        self.assertTrue(self.app.owned(agent)["stopped"])

    def test_incarnation_change_is_not_owned(self):
        agent = self.launch()
        self.update(terminals=[{"handle": "term_owned", "incarnationId": "replacement"}])
        with self.assertRaises(TerminalGone):
            self.app.send(agent, "Do another task")
        self.app.stop(agent)
        self.assertEqual(len(self.data()["terminals"]), 1)

    def test_incomplete_listing_blocks_creation(self):
        self.update(truncated=True)
        with self.assertRaises(OrcaError):
            self.launch()

    def test_dry_run_no_terminal_or_agent(self):
        self.launch(dry_run=True)
        self.assertEqual(self.app.state.read(), {})
        self.assertEqual(len(self.data()["calls"]), 1)

    def test_task_outside_folder_refused(self):
        outside = self.root / "outside.md"
        outside.write_text("Example", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.app.launch(self.folder, outside, "easy")

    def test_orca_open_recovers_unavailable_runtime(self):
        self.update(gone=True)
        self.orca.start()
        self.assertEqual(self.orca.terminals(), [])

    def test_screen_unavailable_not_idle(self):
        self.update(screen="› Ask Codex to do anything", source="screen-unavailable")
        self.assertEqual(codex.classify(self.orca.read("term_owned")), "needs-input")

    def test_ambiguous_creation_never_retries(self):
        self.update(fallback=True, ambiguous=True)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.launch()
        creates = [c for c in self.data()["calls"] if c[:2] == ["terminal", "create"]]
        self.assertEqual(len(creates), 1)
        self.assertEqual(self.app.state.read(), {})

    def test_unconfirmed_submission_keeps_owned_record(self):
        self.update(stalled=True)
        submit = codex.submit
        with patch("cco.app.codex.submit", side_effect=lambda *a: submit(*a, timeout=0, interval=0)):
            with self.assertRaisesRegex(ValueError, "not confirmed"):
                self.launch()
        self.assertEqual(len(self.app.state.read()), 1)
        sends = [c for c in self.data()["calls"] if c[:2] == ["terminal", "send"]]
        self.assertEqual(len(sends), 1)

    def test_multiple_wait_does_not_finish_after_one_report(self):
        first = self.launch()
        other = self.root / "other-worktree"
        other.mkdir()
        records = self.app.state.read()
        records["second"] = dict(records[first], terminal="term_second", folder=str(other))
        self.app.state.save(records)
        self.update(terminals=self.data()["terminals"] + [{"handle": "term_second", "incarnationId": "process_one"}])
        (self.folder / "task.report.md").write_text("Done", encoding="utf-8")
        self.assertEqual(self.app.wait([first, "second"], "report:task.report.md", timeout=0), 2)

    def test_list_all_does_not_read_foreign_screens(self):
        self.launch()
        self.update(terminals=self.data()["terminals"] + [{"handle": "term_foreign"}], calls=[])
        self.app.listing(all_terminals=True)
        reads = [c for c in self.data()["calls"] if c[:2] == ["terminal", "read"]]
        self.assertEqual(len(reads), 1)
        self.assertIn("term_owned", reads[0])

    def test_terminal_disappearing_during_read(self):
        agent = self.launch()
        self.update(read_gone=True)
        self.assertEqual(self.app.wait([agent], "idle", timeout=0), 4)

    def test_cli_routing_and_task_no_overwrite(self):
        from cco.cli import main
        with patch("cco.cli.Orca", return_value=self.orca), patch("cco.cli.State", return_value=self.app.state):
            self.assertEqual(main(["doctor"]), 0)
            self.assertEqual(main(["launch", "--dir", str(self.folder), "--task", "task.md", "--tier", "easy"]), 0)
            agent = next(iter(self.app.state.read()))
            self.assertEqual(main(["list", "--all"]), 0)
            self.assertEqual(main(["peek", agent, "--lines", "1"]), 0)
            self.update(screen="› Ask Codex to do anything")
            self.assertEqual(main(["send", agent, "Follow up"]), 0)
            self.assertEqual(main(["stop", "--all-mine"]), 0)
            target = str(self.folder / "new-task.md")
            self.assertEqual(main(["task", "new", "--kind", "fix", "--out", target]), 0)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["task", "new", "--kind", "fix", "--out", target]), 1)

    def test_user_config_and_explicit_local_selection(self):
        user = self.root / "config"
        user.mkdir()
        (user / "cco.toml").write_text('[tiers.easy]\nmodel="example-user-model"\n', encoding="utf-8")
        with patch("cco.config.Path.cwd", return_value=self.folder), patch("cco.config.user_folder", return_value=user):
            self.assertEqual(load()["tiers"]["easy"]["model"], "example-user-model")
            (self.folder / "cco.toml").write_text('[tiers.easy]\nmodel="example-local-model"\n', encoding="utf-8")
            self.assertEqual(load()["tiers"]["easy"]["model"], "example-user-model")
            self.assertEqual(load(self.folder / "cco.toml")["tiers"]["easy"]["model"], "example-local-model")
            self.assertEqual(load()["tiers"]["hard"]["model"], "gpt-6-astra")


class PackagingTests(unittest.TestCase):
    def test_dependency_free_wheel_and_sdist(self):
        import tarfile
        import zipfile
        from cco.build import build_sdist, build_wheel
        with tempfile.TemporaryDirectory() as folder:
            wheel = Path(folder) / build_wheel(folder)
            with zipfile.ZipFile(wheel) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn("cco/templates/fix.md", archive.namelist())
                self.assertIn("cco/providers/codex.py", archive.namelist())
                self.assertIn(b"cco = cco.cli:main", archive.read("cco-0.1.0.dist-info/entry_points.txt"))
                archive.extractall(Path(folder) / "unpacked")
            env = dict(os.environ, PYTHONPATH=str(Path(folder) / "unpacked"))
            result = subprocess.run([sys.executable, "-m", "cco", "task", "new", "--kind", "review", "--out", "review.md"],
                                    cwd=folder, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Review task", (Path(folder) / "review.md").read_text(encoding="utf-8"))
            source = Path(folder) / build_sdist(folder)
            with tarfile.open(source) as archive:
                self.assertIn("cco-0.1.0/pyproject.toml", archive.getnames())


class ScreenTests(unittest.TestCase):
    def test_states(self):
        for text, state in [
            ("Working (1m 02s)", "working"),
            ("Working (1m 02s)\n› Ask Codex to do anything", "working"),
            ("Working (1m 02s)\nWorked for 5m 21s\n› Ask Codex to do anything", "idle"),
            ("Would you like to run this command?", "needs-input"),
            ("Do you trust this folder?", "needs-input"),
            ("Unrecognized screen", "needs-input"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(codex.classify({"text": text}), state)


if __name__ == "__main__":
    unittest.main()
