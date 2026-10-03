import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from cco.budget import evaluate
from cco.config import load, validate
from cco.inventory import collect, model_class, render
from cco.providers.base import Model, Provider, Usage, Window, timestamp
from cco.providers.codex import Codex
from cco.providers.claude import Claude
from cco.providers.generic import Generic

FIXTURES = Path(__file__).parent / "fixtures"
NOW = timestamp("2026-01-01T00:00:00Z")


class BudgetTests(unittest.TestCase):
    def test_states_and_boundaries(self):
        for used, ahead, projected, reached, age, expected in (
            (20, False, None, False, 0, "ok"),
            (20, True, None, False, 0, "tight"),
            (71, False, None, False, 0, "tight"),
            (70, False, None, False, 0, "ok"),
            (90, False, None, False, 0, "tight"),
            (91, False, None, False, 0, "critical"),
            (20, False, NOW + 100, False, 0, "critical"),
            (20, False, None, True, 0, "exhausted"),
            (20, False, None, True, 3601, "unknown"),
        ):
            with self.subTest(expected=expected, used=used, age=age):
                usage = Usage([Window("primary", used, 300, NOW + 1000,
                                      ahead_of_pace=ahead, projected_exhaustion_at=projected)], NOW - age, reached)
                self.assertEqual(evaluate(usage, now=NOW)["state"], expected)
        self.assertEqual(evaluate(Usage(), now=NOW)["state"], "unknown")

    def test_configured_thresholds_and_missing_pace(self):
        usage = Usage([Window("primary", 85, ahead_of_pace=False)], NOW)
        self.assertEqual(evaluate(usage, {"critical_remaining_percent": 20}, NOW)["state"], "critical")
        usage.windows[0] = Window("primary", 5)
        self.assertEqual(evaluate(usage, now=NOW)["state"], "unknown")
        usage.windows[0] = Window("primary", 5, 300, NOW - 1)
        self.assertEqual(evaluate(usage, now=NOW)["state"], "unknown")


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        shutil.copyfile(FIXTURES / "models.json", self.home / "models_cache.json")
        (self.home / "sessions").mkdir()
        shutil.copyfile(FIXTURES / "rollout-example.jsonl", self.home / "sessions/rollout-example.jsonl")
        self.codex = Codex(home=self.home)

    def test_codex_shapes_and_age(self):
        models = self.codex.models()
        self.assertEqual(models[0].efforts, ["low", "high"])
        usage = self.codex.usage()
        self.assertEqual(usage.plan_type, "pro")
        self.assertEqual(len(usage.windows), 2)
        self.assertEqual(evaluate(usage, now=NOW + 15)["age_seconds"], 15)
        self.assertEqual(evaluate(usage, now=NOW + 4000)["state"], "unknown")

    def test_newest_rollout_and_partial_line(self):
        older = self.home / "sessions/rollout-example.jsonl"
        os.utime(older, (1, 1))
        latest = self.home / "sessions/rollout-new.jsonl"
        row = {"timestamp": NOW, "payload": {"rate_limits": {"primary": {"used_percent": 12}, "secondary": None}}}
        latest.write_text(json.dumps(row) + '\n{"partial":', encoding="utf-8")
        self.assertEqual(self.codex.usage().windows[0].used_percent, 12)
        latest.write_text('{}\n', encoding="utf-8")
        self.assertEqual(self.codex.usage().windows, [])

    def test_claude_both_windows_worst_governs(self):
        data = json.loads((FIXTURES / "accounts.json").read_text())
        def run(*args):
            return subprocess.CompletedProcess([], 0, json.dumps(data), '')
        with patch("cco.providers.claude.shutil.which", return_value="cswap"), patch("cco.providers.claude.run", side_effect=run):
            usage = Claude().usage()
            self.assertEqual([w.used_percent for w in usage.windows], [20, 95])
            self.assertEqual(evaluate(usage, now=NOW)["state"], "critical")
            data["accounts"][1]["usage"]["fiveHour"]["pct"] = 96
            data["accounts"][1]["usage"]["sevenDay"] = {"pct": 5, "expectedPct": 50, "resetsAt": "2026-01-04T00:00:00Z"}
            self.assertEqual(evaluate(Claude().usage(), now=NOW)["state"], "critical")
            data["accounts"][1]["usageFetchedAt"] = "2025-12-01T00:00:00Z"
            self.assertEqual(evaluate(Claude().usage(), now=NOW)["state"], "unknown")

    def test_class_order_and_unusable_model(self):
        model = Model("sonnet", description="frontier")
        cfg = {"classes": {"claude": {"sonnet": "fast"}}}
        self.assertEqual(model_class("claude", model, cfg), "fast")
        self.assertEqual(model_class("claude", model, {}), "frontier")
        model.description = "General purpose"
        self.assertEqual(model_class("claude", model, {}), "workhorse")
        with patch.object(self.codex, "installed", return_value=False), patch.object(self.codex, "signed_in", return_value=None):
            models = collect({}, [self.codex])["providers"][0]["models"]
        self.assertFalse(models[1]["usable"])

    def test_only_one_provider_or_none(self):
        providers = [Generic("aider"), Generic("gemini")]
        for available in (None, "aider"):
            with patch("cco.providers.base.shutil.which", side_effect=lambda name: name if name == available else None):
                data = collect({}, providers)
            self.assertEqual(sum(p["installed"] for p in data["providers"]), int(available is not None))
            self.assertTrue(all(p["signed_in"] is None for p in data["providers"]))

    def test_unknowns_and_local_usage(self):
        with patch("cco.providers.base.shutil.which", return_value=None):
            self.assertIsNone(Claude().usage().observed_at)
            self.assertIsNone(Generic("aider").models())
        with patch("cco.providers.base.shutil.which", return_value="ollama"):
            self.assertEqual(evaluate(Generic("ollama").usage())["state"], "ok")
        self.assertFalse(Claude().can_launch)
        self.assertIsNone(Claude().command("example", "opus", "high"))

    def test_privacy_in_all_renderings(self):
        account_data = (FIXTURES / "accounts.json").read_text()
        providers = [self.codex, Claude()]
        with patch.object(Provider, "installed", return_value=False), patch.object(Codex, "signed_in", return_value=None), \
                patch.object(Claude, "signed_in", return_value=None), \
                patch("cco.providers.claude.shutil.which", return_value="cswap"), \
                patch("cco.providers.claude.run", return_value=subprocess.CompletedProcess([], 0, account_data, '')):
            for usage in (False, True):
                for as_json in (False, True):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                        render(collect({}, providers, usage=usage, now=NOW), usage=usage, as_json=as_json)
                    for private in ("fixture@example.com", "inactive@example.com", "Invented Workshop", "Invented Operator"):
                        self.assertNotIn(private, output.getvalue())

    def test_auth_status_never_returns_identity(self):
        with patch.object(Codex, "executable", return_value="codex"), \
                patch("cco.providers.codex.run", return_value=subprocess.CompletedProcess([], 0, "Logged in fixture@example.com", "")):
            self.assertIs(self.codex.signed_in(), True)
        with patch.object(Claude, "executable", return_value="claude"), \
                patch("cco.providers.claude.run", return_value=subprocess.CompletedProcess([], 0, '{"loggedIn":false,"email":"fixture@example.com"}', "")):
            self.assertIs(Claude().signed_in(), False)

    def test_configured_models_and_efforts(self):
        self.assertEqual(Claude({"efforts": ["low", "high"]}).models()[0].efforts, ["low", "high"])
        provider = Generic("aider", {"models": [{"name": "example", "description": "fast", "efforts": ["low"]}]})
        self.assertEqual(provider.models()[0].efforts, ["low"])
        self.assertEqual(model_class("aider", provider.models()[0], {}), "fast")

    def test_cli_without_orca_and_config_thresholds(self):
        from cco.cli import main
        with patch("cco.cli.Orca", side_effect=AssertionError("must not touch Orca")), \
                patch("cco.inventory.adapters", return_value=[Generic("aider")]), \
                patch("cco.providers.base.shutil.which", return_value=None):
            for command in ("inventory", "usage"):
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main([command, "--json"]), 0)
                self.assertEqual(json.loads(output.getvalue())["providers"][0]["provider"], "aider")
