"""Setup consent, configuration preservation and database safety."""

import contextlib
import io
import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import quickstart as setup
from scripts.reviewer_config import read_reviewer_key


class QuickstartTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "代码 with spaces"
        self.root.mkdir()
        (self.root / ".env.example").write_text(
            "FLASK_SECRET_KEY=change-me\nDEEPSEEK_API_KEY=placeholder\n"
            "REVIEWER_TEST_KEY_ENABLED=0\nDATABASE_URL=sqlite:///app.db\n",
            encoding="utf-8",
        )
        self.output = io.StringIO()
        self.capture = contextlib.redirect_stdout(self.output)
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)

    def bundle(self):
        path = self.root.parent / "runtime/reviewer-key.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            json.dumps({"api_key": "sk-fake-reviewer-test-only", "budget_cny": "10.00"})
        )
        return path

    def test_new_config_generates_secret_and_repeated_setup_preserves_file(self):
        first = setup.ensure_environment(self.root)
        content = (self.root / ".env").read_bytes()
        self.assertEqual(len(first["FLASK_SECRET_KEY"]), 64)
        self.assertEqual(first["DEEPSEEK_API_KEY"], "")
        self.assertEqual(first["DATABASE_URL"], "sqlite:///competition.db")
        self.assertEqual(setup.ensure_environment(self.root), first)
        self.assertEqual((self.root / ".env").read_bytes(), content)

    def test_invalid_existing_secret_is_not_overwritten(self):
        path = self.root / ".env"
        path.write_text("FLASK_SECRET_KEY=change-me\n")
        with self.assertRaises(setup.SetupError):
            setup.ensure_environment(self.root)
        self.assertEqual(path.read_text(), "FLASK_SECRET_KEY=change-me\n")

    def test_yes_enables_key_without_printing_it(self):
        self.bundle()
        before = setup.ensure_environment(self.root)
        with patch.object(setup, "ask_reviewer_key", return_value=True) as dialog:
            after = setup.configure_reviewer_key(self.root, before)
        dialog.assert_called_once()
        self.assertEqual(after["DEEPSEEK_API_KEY"], "sk-fake-reviewer-test-only")
        self.assertEqual(after["REVIEWER_TEST_KEY_ENABLED"], "1")
        self.assertEqual(after["FLASK_SECRET_KEY"], before["FLASK_SECRET_KEY"])
        self.assertNotIn(after["DEEPSEEK_API_KEY"], self.output.getvalue())

    def test_no_and_skip_preserve_existing_personal_config(self):
        self.bundle()
        path = self.root / ".env"
        path.write_text("FLASK_SECRET_KEY=already-configured\nDEEPSEEK_API_KEY=personal-key\n")
        settings = setup.ensure_environment(self.root)
        before = path.read_bytes()
        with patch.object(setup, "ask_reviewer_key", return_value=False) as dialog:
            setup.configure_reviewer_key(self.root, settings)
            dialog.assert_called_once_with(True)
        with patch.object(setup, "ask_reviewer_key") as dialog:
            setup.configure_reviewer_key(self.root, settings, "skip")
            dialog.assert_not_called()
        self.assertEqual(path.read_bytes(), before)

    def test_bundle_absent_skips_prompt_but_explicit_use_fails(self):
        settings = setup.ensure_environment(self.root)
        with patch.object(setup, "ask_reviewer_key") as dialog:
            self.assertEqual(setup.configure_reviewer_key(self.root, settings), settings)
            dialog.assert_not_called()
        with self.assertRaises(setup.SetupError):
            setup.configure_reviewer_key(self.root, settings, "use")

    def test_invalid_bundle_never_changes_env_or_echoes_content(self):
        bundle = self.bundle()
        bundle.write_text('{"api_key":"secret invalid value", "budget_cny":"20.00"}')
        settings = setup.ensure_environment(self.root)
        before = (self.root / ".env").read_bytes()
        with self.assertRaises(ValueError) as raised:
            setup.configure_reviewer_key(self.root, settings, "use")
        self.assertNotIn("secret", str(raised.exception))
        self.assertEqual((self.root / ".env").read_bytes(), before)
        for content in ("[]", "null", "not-json"):
            bundle.write_text(content)
            with self.assertRaises(ValueError):
                read_reviewer_key(bundle)

    def test_macos_dialog_accept_and_cancel(self):
        with (
            patch.object(setup.sys, "platform", "darwin"),
            patch.object(setup.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            run.return_value.stdout = "使用\n"
            self.assertTrue(setup.ask_reviewer_key())
            self.assertEqual(run.call_args.args[0][0], "osascript")
            run.return_value.returncode = 1
            self.assertFalse(setup.ask_reviewer_key())

    def test_windows_dialog_yes_and_no_default_to_no(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        message = MagicMock(return_value=6)
        native = SimpleNamespace(user32=SimpleNamespace(MessageBoxW=message))
        with (
            patch.object(setup.sys, "platform", "win32"),
            patch("ctypes.windll", native, create=True),
        ):
            self.assertTrue(setup.ask_reviewer_key())
            self.assertEqual(message.call_args.args[-1], 0x124)
            message.return_value = 7
            self.assertFalse(setup.ask_reviewer_key())

    @unittest.skipUnless(sys.platform == "darwin", "Requires the native macOS AppleScript compiler")
    def test_macos_dialog_compiles_without_opening_a_window(self):
        with patch.object(setup.subprocess, "run") as dialog:
            dialog.return_value.returncode = 1
            setup.ask_reviewer_key()
            script = dialog.call_args.args[0][2]
        result = subprocess.run(
            ["osacompile", "-o", str(self.root / "reviewer-dialog.scpt"), "-e", script],
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def test_database_path_confined_to_project(self):
        self.assertEqual(
            setup.database_path(self.root, {}), (self.root / "instance/competition.db").resolve()
        )
        for url in (
            "sqlite:///../../outside.db",
            "sqlite:///:memory:",
            "postgresql://localhost/db",
        ):
            with self.subTest(url=url), self.assertRaises(setup.SetupError):
                setup.database_path(self.root, {"DATABASE_URL": url})

    def test_migrated_database_backed_up_with_records_intact(self):
        path = self.root / "saved.db"
        with contextlib.closing(sqlite3.connect(path)) as db:
            db.executescript(
                "CREATE TABLE alembic_version(version_num TEXT); CREATE TABLE users(name TEXT); INSERT INTO users VALUES('existing');"
            )
        backup = setup.backup_database(path)
        with contextlib.closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT name FROM users").fetchone()[0], "existing")
        self.assertNotEqual(path, backup)

    def test_unmigrated_database_refused_without_modification(self):
        path = self.root / "old.db"
        with contextlib.closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE users(name TEXT)")
        before = path.read_bytes()
        with self.assertRaises(setup.SetupError):
            setup.backup_database(path)
        self.assertEqual(path.read_bytes(), before)

    def test_arm_and_intel_runner_selection(self):
        self.assertEqual(setup.runner_action("linux/amd64", "linux/amd64", ""), "load")
        self.assertEqual(setup.runner_action("linux/arm64", "linux/amd64", ""), "build")
        self.assertEqual(setup.runner_action("linux/arm64", "linux/amd64", "linux/arm64"), "check")
        self.assertEqual(setup.runner_action("linux/amd64", "", ""), "build")

    def test_docker_missing_and_architecture_detection(self):
        with (
            patch.object(setup.shutil, "which", return_value=None),
            self.assertRaises(setup.SetupError),
        ):
            setup.docker_platform()
        with (
            patch.object(setup.shutil, "which", return_value="docker"),
            patch.object(setup.subprocess, "check_output", return_value="linux/aarch64\n"),
        ):
            self.assertEqual(setup.docker_platform(), "linux/arm64")

    def test_busy_port_uses_next_available_port(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            selected = setup.choose_port(port)
            self.assertGreater(selected, port)
            self.assertLess(selected, port + 20)


if __name__ == "__main__":
    unittest.main()
