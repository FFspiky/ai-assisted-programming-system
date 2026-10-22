"""Exercise installer control flow without installing software on the test host."""

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import prerequisites as pre
from tests.test_launchers import BASH, ROOT


class PrerequisitesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(patch.dict(os.environ))

    def test_decline_and_noninteractive_never_silently_consent(self):
        with (
            patch.object(pre.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", return_value="n"),
        ):
            with self.assertRaises(pre.PrerequisiteError):
                pre.confirm("Install?")
        with (
            patch.object(pre.sys.stdin, "isatty", return_value=False),
            patch("builtins.input") as prompt,
        ):
            with self.assertRaises(pre.PrerequisiteError):
                pre.confirm("Install?")
            prompt.assert_not_called()

    def test_ready_engine_does_not_install_or_launch_anything(self):
        with (
            patch.object(pre, "refresh_docker_path"),
            patch.object(pre, "engine_ready", return_value=True),
            patch.object(pre, "confirm") as consent,
            patch.object(pre, "start_desktop") as start,
        ):
            pre.ensure_docker()
            consent.assert_not_called()
            start.assert_not_called()

    def test_download_error_has_network_recovery_message(self):
        with patch.object(pre.urllib.request, "urlopen", side_effect=OSError("offline")):
            with self.assertRaisesRegex(pre.PrerequisiteError, "网络"):
                pre.download("https://desktop.docker.com/test", self.root / "installer")

    def test_new_install_continues_only_after_engine_is_ready(self):
        for system, installer in (
            ("win32", "install_windows_docker"),
            ("darwin", "install_macos_docker"),
        ):
            with (
                self.subTest(system=system),
                patch.object(pre.sys, "platform", system),
                patch.object(pre, "desktop_paths", return_value=[]),
                patch.object(pre, "refresh_docker_path"),
                patch.object(pre, "confirm") as consent,
                patch.object(pre, installer) as install,
                patch.object(pre, "start_desktop", return_value=True),
                patch.object(pre, "engine_ready", side_effect=[False, False, True]),
                patch.object(pre.time, "sleep"),
            ):
                pre.ensure_docker()
                consent.assert_called_once()
                install.assert_called_once()

    def test_existing_desktop_is_started_without_reinstallation(self):
        with (
            patch.object(pre, "desktop_paths", return_value=[self.root]),
            patch.object(pre, "refresh_docker_path"),
            patch.object(pre.sys, "platform", "darwin"),
            patch.object(pre, "engine_ready", side_effect=[False, True]),
            patch.object(pre, "confirm") as consent,
            patch.object(pre, "start_desktop", return_value=True) as start,
        ):
            pre.ensure_docker()
            consent.assert_not_called()
            start.assert_called_once()

    def test_engine_timeout_fails_with_recovery_instructions(self):
        with (
            patch.object(pre, "desktop_paths", return_value=[self.root]),
            patch.object(pre, "refresh_docker_path"),
            patch.object(pre.sys, "platform", "darwin"),
            patch.object(pre, "engine_ready", return_value=False),
            patch.object(pre, "start_desktop", return_value=True),
            patch.object(pre.time, "monotonic", side_effect=[0, 301]),
        ):
            with self.assertRaisesRegex(pre.PrerequisiteError, "重启"):
                pre.ensure_docker()

    def test_new_docker_cli_is_added_to_current_process_path(self):
        binaries = self.root / "Contents/Resources/bin"
        binaries.mkdir(parents=True)
        with (
            patch.object(pre.sys, "platform", "darwin"),
            patch.object(pre, "desktop_paths", return_value=[self.root]),
        ):
            pre.refresh_docker_path()
            pre.refresh_docker_path()
            self.assertEqual(os.environ["PATH"].split(os.pathsep).count(str(binaries)), 1)

    def test_wsl_decodes_localized_utf16_and_rejects_old_version(self):
        for version, expected in (("2.6.1", True), ("1.0.0", False)):
            result = Mock(returncode=0, stdout=f"WSL 版本： {version}\n".encode("utf-16-le"))
            with patch.object(pre.subprocess, "run", return_value=result):
                self.assertEqual(pre.wsl_ready(), expected)

    def test_wsl_installs_without_a_distribution_or_updates_existing_wsl(self):
        for version, first in ((None, "--no-distribution"), ((1, 0, 0), "--update")):
            with (
                patch.object(pre, "wsl_ready", side_effect=[False, True]),
                patch.object(pre, "wsl_version", return_value=version),
                patch.object(pre, "confirm"),
                patch.object(pre, "powershell") as ps,
            ):
                pre.ensure_wsl()
                command = ps.call_args.args[0]
                self.assertIn(first, command)
                self.assertIn("-Verb RunAs", command)
                self.assertNotIn("Restart-Computer", command)

    def test_wsl_restart_stops_before_docker_download(self):
        with (
            patch.object(pre, "wsl_ready", return_value=False),
            patch.object(pre, "wsl_version", return_value=None),
            patch.object(pre, "confirm"),
            patch.object(pre, "powershell", side_effect=subprocess.CalledProcessError(3010, "wsl")),
            patch.object(pre, "download") as download,
        ):
            with self.assertRaisesRegex(pre.PrerequisiteError, "重启"):
                pre.install_windows_docker(self.root)
            download.assert_not_called()

    def test_invalid_windows_publisher_stops_before_execution(self):
        with (
            patch.object(pre, "ensure_wsl"),
            patch.object(pre, "docker_architecture", return_value="amd64"),
            patch.object(pre, "download"),
            patch.object(
                pre, "powershell", side_effect=subprocess.CalledProcessError(1, "signature")
            ),
            patch.object(pre.subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(pre.PrerequisiteError, "发布者"):
                pre.install_windows_docker(self.root)
            run.assert_not_called()

    def test_windows_installer_exit_codes_and_no_silent_license_acceptance(self):
        for code in (0, 3010, 1602):
            with (
                self.subTest(code=code),
                patch.object(pre, "ensure_wsl"),
                patch.object(pre, "docker_architecture", return_value="amd64"),
                patch.object(pre, "download") as download,
                patch.object(pre, "powershell"),
                patch.object(pre.subprocess, "run", return_value=Mock(returncode=code)) as run,
            ):
                if code:
                    with self.assertRaises(pre.PrerequisiteError):
                        pre.install_windows_docker(self.root)
                else:
                    pre.install_windows_docker(self.root)
                self.assertIn("desktop.docker.com/win/main/amd64/", download.call_args.args[0])
                self.assertIn("--user", run.call_args.args[0])
                self.assertNotIn("--accept-license", run.call_args.args[0])

    def test_macos_arm_detection_including_rosetta(self):
        with (
            patch.object(pre.sys, "platform", "darwin"),
            patch.object(pre.platform, "machine", return_value="x86_64"),
            patch.object(pre.subprocess, "run", return_value=Mock(returncode=0, stdout=b"1\n")),
        ):
            self.assertEqual(pre.docker_architecture(), "arm64")

    def test_macos_signature_failure_unmounts_without_installing(self):
        with (
            patch.object(pre, "download"),
            patch.object(pre, "docker_architecture", return_value="arm64"),
            patch.object(
                pre.subprocess,
                "run",
                return_value=Mock(returncode=0, stderr=b"TeamIdentifier=WRONG\n"),
            ) as run,
        ):
            with self.assertRaisesRegex(pre.PrerequisiteError, "发布者"):
                pre.install_macos_docker(self.root)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[-1][:2], ["hdiutil", "detach"])
            self.assertFalse(any(command[0] == "sudo" for command in commands))

    def test_macos_valid_installer_uses_native_install_and_unmounts(self):
        with (
            patch.object(pre, "download") as download,
            patch.object(pre, "docker_architecture", return_value="arm64"),
            patch.object(
                pre.subprocess,
                "run",
                return_value=Mock(returncode=0, stderr=b"TeamIdentifier=9BNSXJN65R\n"),
            ) as run,
        ):
            pre.install_macos_docker(self.root)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn("mac/main/arm64/Docker.dmg", download.call_args.args[0])
            self.assertEqual(commands[-2][0], "sudo")
            self.assertEqual(commands[-1][:2], ["hdiutil", "detach"])

    @unittest.skipUnless(os.name == "nt", "Requires native Windows PowerShell")
    def test_windows_python_installer_success_failure_and_checksum(self):
        script = self.root / "installer-test.ps1"
        script.write_text(
            "$ErrorActionPreference = 'Stop'\n"
            ". '" + str(ROOT / "scripts/bootstrap-windows.ps1").replace("'", "''") + "'\n"
            "$env:PROCESSOR_ARCHITECTURE = 'AMD64'\n"
            "$env:PROCESSOR_ARCHITEW6432 = ''\n"
            "function Confirm-CodeLabPython {}\n"
            "function Invoke-WebRequest { param($Uri, $OutFile, [switch]$UseBasicParsing) [IO.File]::WriteAllText($OutFile, 'fake') }\n"
            "function Get-FileHash { param($LiteralPath, $Algorithm) [pscustomobject]@{Hash=$script:Hash} }\n"
            "function Start-Process { param($FilePath, $ArgumentList, [switch]$PassThru, [switch]$Wait) $script:Invoked=$true; [pscustomobject]@{ExitCode=$script:Code} }\n"
            "$script:Hash = '5da012101ba2e17113a9a1cd901e9ce1441086f2b7ecb5de06ec94163899a190'\n"
            "foreach ($code in @(0, 3010, 1602)) {\n"
            "  $script:Code=$code; $script:Invoked=$false; $failed=$false\n"
            "  try { Install-CodeLabPython } catch { $failed=$true }\n"
            "  if (!$script:Invoked -or ($failed -ne ($code -ne 0))) { throw 'Installer exit handling failed' }\n"
            "}\n"
            "$script:Hash='invalid'; $script:Invoked=$false; $failed=$false\n"
            "try { Install-CodeLabPython } catch { $failed=$true }\n"
            "if (!$failed -or $script:Invoked) { throw 'Invalid checksum executed' }\n"
            "function Confirm-CodeLabPython { throw 'declined' }\n"
            "$script:Invoked=$false; $failed=$false\n"
            "try { Install-CodeLabPython } catch { $failed=$true }\n"
            "if (!$failed -or $script:Invoked) { throw 'Decline ignored' }\n",
            encoding="utf-8-sig",
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(BASH, "Requires Bash")
    def test_macos_python_installer_checks_hash_and_stops_on_failure(self):
        bootstrap = (ROOT / "scripts/bootstrap-macos.sh").as_posix()
        for mode in ("ok", "bad-hash", "install-failed", "declined", "network-failed"):
            with self.subTest(mode=mode):
                log = self.root / (mode + ".log")
                script = self.root / (mode + ".sh")
                script.write_text(
                    'source "$BOOTSTRAP"\n'
                    'codelab_confirm_python() { [ "$MODE" != declined ]; }\n'
                    "uname() { echo Darwin; }\n"
                    'curl() { [ "$MODE" != network-failed ]; }\n'
                    'shasum() { if [ "$MODE" = bad-hash ]; then echo bad; else echo "3053592af66128269efab37fe7851a4894920b27c442aeec99ce4d34d17c07e3  fake.pkg"; fi; }\n'
                    'sudo() { echo install >> "$LOG"; [ "$MODE" != install-failed ]; }\n'
                    'codelab_install_certificates() { echo certificates >> "$LOG"; }\n'
                    "codelab_install_python\n",
                    encoding="utf-8",
                    newline="\n",
                )
                result = subprocess.run(
                    [BASH, str(script)],
                    env={**os.environ, "BOOTSTRAP": bootstrap, "MODE": mode, "LOG": log.as_posix()},
                    capture_output=True,
                    timeout=20,
                )
                entries = log.read_text().splitlines() if log.exists() else []
                self.assertEqual(
                    result.returncode == 0, mode == "ok", result.stdout + result.stderr
                )
                self.assertEqual(
                    entries,
                    (
                        ["install", "certificates"]
                        if mode == "ok"
                        else ["install"] if mode == "install-failed" else []
                    ),
                )


if __name__ == "__main__":
    unittest.main()
