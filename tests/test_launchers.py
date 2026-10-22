"""Execute each platform wrapper in isolation; no real credentials or model calls."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
if os.name == "nt":
    git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
    BASH = str(git_bash) if git_bash.is_file() else None

PROBE = """import json, os, sys
from pathlib import Path
Path('invocation.json').write_text(json.dumps({
    'args': sys.argv[1:], 'cwd': os.getcwd(),
    'utf8': os.environ.get('PYTHONUTF8'),
    'encoding': os.environ.get('PYTHONIOENCODING'),
    'bytecode': os.environ.get('PYTHONDONTWRITEBYTECODE'),
}), encoding='utf-8')
sys.exit(int(os.environ.get('CODELAB_TEST_EXIT', '0')))
"""


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "评审 代码 with spaces"
        (self.project / "scripts").mkdir(parents=True)
        (self.project / "scripts/quickstart.py").write_text(PROBE, encoding="utf-8")
        for name in (
            "setup-windows.cmd",
            "start-windows.cmd",
            "setup-macos.command",
            "start-macos.command",
            "scripts/launch-windows.cmd",
            "scripts/launch-macos.sh",
        ):
            shutil.copyfile(ROOT / name, self.project / name)
        self.env = {
            **os.environ,
            "CODELAB_NO_PAUSE": "1",
            "PYTHONUTF8": "1",
            "CODELAB_TEST_PYTHON": sys.executable,
        }
        self.env.pop("CODELAB_TEST_EXIT", None)

    def check_invocation(self, action):
        packet = json.loads((self.project / "invocation.json").read_text(encoding="utf-8"))
        self.assertEqual(packet["args"], [action, "--reviewer-key", "skip", "--no-browser", "a b"])
        self.assertEqual(Path(packet["cwd"]).resolve(), self.project.resolve())
        self.assertEqual(packet["utf8"], "1")
        self.assertEqual(packet["encoding"], "utf-8")
        self.assertEqual(packet["bytecode"], "1")

    @unittest.skipUnless(os.name == "nt", "Requires native Windows cmd.exe")
    def test_windows_setup_and_start_independently_from_other_directory(self):
        venv.EnvBuilder(with_pip=False).create(self.project / ".venv")
        command = str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe")
        for action in ("setup", "start"):
            for status in (0, 17):
                with self.subTest(action=action, status=status):
                    args = f'call "{self.project / (action + "-windows.cmd")}" --reviewer-key skip --no-browser "a b"'
                    result = subprocess.run(
                        f'"{command}" /d /c {args}',
                        cwd=self.base,
                        env={**self.env, "CODELAB_TEST_EXIT": str(status)},
                        capture_output=True,
                        timeout=20,
                    )
                    self.assertEqual(result.returncode, status, result.stdout + result.stderr)
                    self.check_invocation(action)

    def shell_python(self, path, supports_version=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        check = "exit 0" if supports_version else "exit 1"
        path.write_text(
            "#!/bin/bash\n"
            f'if [ "$1" = "-c" ]; then {check}; fi\n'
            'exec "$CODELAB_TEST_PYTHON" "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        path.chmod(0o755)

    def run_macos(self, action, env=None):
        return subprocess.run(
            [
                BASH,
                str(self.project / f"{action}-macos.command"),
                "--reviewer-key",
                "skip",
                "--no-browser",
                "a b",
            ],
            cwd=self.base,
            env=env or self.env,
            capture_output=True,
            timeout=20,
        )

    @unittest.skipUnless(BASH, "Requires Bash (native macOS/Linux or Git Bash)")
    def test_macos_setup_and_start_use_venv_and_preserve_failure(self):
        self.shell_python(self.project / ".venv/bin/python")
        for action in ("setup", "start"):
            for status in (0, 17):
                with self.subTest(action=action, status=status):
                    result = self.run_macos(action, {**self.env, "CODELAB_TEST_EXIT": str(status)})
                    self.assertEqual(result.returncode, status, result.stdout + result.stderr)
                    self.check_invocation(action)

    def controlled_shell_path(self):
        binaries = self.base / "bin"
        binaries.mkdir()
        # Only Bash and dirname are exposed, so host Python cannot affect fallback tests.
        for name in ("bash", "dirname"):
            if os.name == "nt":
                candidate = Path(BASH).parents[1] / "usr/bin" / f"{name}.exe"
            else:
                candidate = Path(shutil.which(name))
            wrapper = binaries / name
            wrapper.write_text(
                '#!/bin/bash\nexec "' + candidate.as_posix() + '" "$@"\n',
                encoding="utf-8",
                newline="\n",
            )
            wrapper.chmod(0o755)
        # Windows PATH is converted by Git Bash; POSIX shells use the directory directly.
        return binaries, {**self.env, "PATH": str(binaries)}

    @unittest.skipUnless(BASH, "Requires Bash")
    def test_macos_falls_back_from_old_python_to_python311(self):
        binaries, env = self.controlled_shell_path()
        self.shell_python(binaries / "python3", supports_version=False)
        self.shell_python(binaries / "python3.11")
        for action in ("setup", "start"):
            with self.subTest(action=action):
                result = self.run_macos(action, env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.check_invocation(action)

    @unittest.skipUnless(BASH, "Requires Bash")
    def test_macos_missing_python_fails_without_invoking_bootstrap(self):
        _, env = self.controlled_shell_path()
        for action in ("setup", "start"):
            with self.subTest(action=action):
                result = self.run_macos(action, env)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(b"Python 3.11+ was not found", result.stdout)
                self.assertFalse((self.project / "invocation.json").exists())


if __name__ == "__main__":
    unittest.main()
