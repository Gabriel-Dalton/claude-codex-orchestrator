import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cco.app import quote
from cco.config import load, validate, COMMAND
from cco.providers.base import require_identifier


class SecurityTests(unittest.TestCase):
    def test_windows_double_quotes_and_posix_quotes(self):
        with patch("cco.app.os.name", "nt"):
            self.assertEqual(quote(r"C:\code\example app"), '"C:/code/example app"')
            self.assertEqual(quote(r"C:\code\example-app"), "C:/code/example-app")
        with patch("cco.app.os.name", "posix"):
            self.assertEqual(quote("~/code/example app"), "'~/code/example app'")

    def test_unsafe_characters_rejected_on_every_platform(self):
        for system in ("nt", "posix"):
            for char in "$%`&|^;\"'\n":
                with self.subTest(system=system, char=char), patch("cco.app.os.name", system):
                    with self.assertRaises(ValueError) as caught:
                        quote("example" + char + "path")
                    self.assertIn(repr(char), str(caught.exception))

    def test_identifier_validation(self):
        for char in ";&|` $%\n/\\\u00e9":
            with self.subTest(char=char), self.assertRaises(ValueError):
                require_identifier("example" + char + "model")
        self.assertEqual(require_identifier("example-model:v1.0"), "example-model:v1.0")
        for section in ({"providers": {"bad;provider": {}}},
                        {"tiers": {"easy": {"model": "bad&model"}}},
                        {"tiers": {"easy": {"effort": "bad effort"}}},
                        {"classes": {"bad|provider": {}}}):
            with self.assertRaises(ValueError):
                validate({"tiers": {}, **section})

    def test_untrusted_working_config_and_explicit_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            user = root / "config"
            user.mkdir()
            hostile = root / "cco.toml"
            hostile.write_text('agent_command="echo hostile-command"\n[tiers.easy]\nmodel="hostile-model"\n', encoding="utf-8")
            with patch("cco.config.Path.cwd", return_value=root), patch("cco.config.user_folder", return_value=user), \
                    patch.dict(os.environ, {"CCO_CONFIG": ""}):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    cfg = load()
                self.assertEqual(cfg["agent_command"], COMMAND)
                self.assertNotEqual(cfg["tiers"]["easy"]["model"], "hostile-model")
                self.assertEqual(len(err.getvalue().splitlines()), 1)
                self.assertEqual(load(hostile)["agent_command"], "echo hostile-command")
                trusted = user / "cco.toml"
                trusted.write_text('agent_command="echo trusted-command"\n[budget]\nmax_age_seconds=17\n', encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(load()["agent_command"], "echo trusted-command")
                    self.assertEqual(load()["budget"]["max_age_seconds"], 17)
                with patch.dict(os.environ, {"CCO_CONFIG": str(hostile)}):
                    self.assertEqual(load()["agent_command"], "echo hostile-command")
                    self.assertEqual(load(trusted)["agent_command"], "echo trusted-command")

    def test_config_flag_before_and_after_subcommand(self):
        from cco.cli import parser
        for args in (["--config", "example.toml", "inventory"], ["inventory", "--config", "example.toml"]):
            self.assertEqual(parser().parse_args(args).config, "example.toml")
