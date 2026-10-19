"""Real Docker regression checks; no application imports or database writes."""

import json
import subprocess
import unittest
from unittest.mock import patch

from services import execute_runner as runner
from services.language_support import LANGUAGE_IDS, starter_code


class ExecuteRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", runner.CODE_SANDBOX_IMAGE],
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise unittest.SkipTest("Docker execution image unavailable") from exc
        if result.returncode:
            raise unittest.SkipTest("Docker execution image unavailable")

    def test_python_input_and_unicode_output(self):
        result = runner.run_code("print('结果', int(input()) + 1)", "python", "5\n")
        self.assertEqual(result["status"], "Accepted", result)
        self.assertEqual(result["output"].strip(), "结果 6")

    def test_cpp_input_and_compile_error(self):
        code = "#include <iostream>\nint main(){int n;std::cin>>n;std::cout<<n+1;}"
        result = runner.run_code(code, "cpp", "5\n")
        self.assertEqual(result["status"], "Accepted", result)
        self.assertEqual(result["output"].strip(), "6")
        result = runner.run_code("this is not C++", "cpp")
        self.assertEqual(result["status"], "Compile Error", result)

    def test_two_language_starters_execute_in_same_bounded_container(self):
        for language in LANGUAGE_IDS:
            with self.subTest(language=language):
                result = runner.run_code(starter_code(language), language, "hello\n")
                self.assertEqual(result["status"], "Accepted", result)
                self.assertEqual(result["output"].strip(), "hello")
                self.assertEqual(result["execution_backend"], "docker")
                self.assertEqual(result["language"], language)

    def test_source_larger_than_windows_command_limit_and_input_eof(self):
        # Base64 command arguments used to exceed Windows' 32 KiB process limit.
        comment = "中" * 18000
        sources = {
            "python": "#" + comment + "\nimport sys; print(sys.stdin.read(), end='')\n",
            "cpp": "//"
            + comment
            + "\n#include <iostream>\nint main(){std::cout<<std::cin.rdbuf();}",
        }
        for language, code in sources.items():
            with self.subTest(language=language):
                result = runner.run_code(code, language, "line1\nline2\n")
                self.assertEqual(result["status"], "Accepted", result)
                self.assertEqual(result["output"], "line1\nline2\n")

    def test_compilation_budget_does_not_increase_submission_file_hard_limit(self):
        code = "import resource\nprint(resource.getrlimit(resource.RLIMIT_FSIZE))\ntry:\n    with open('/work/too-large.bin','wb') as f:\n        f.write(b'x'*(2*1024*1024))\nexcept OSError as exc:\n    print(exc.errno)\n"
        with patch.object(runner, "CODE_RUN_FILE_SIZE_MB", 1):
            result = runner.run_code(code, "python")
        self.assertEqual(result["status"], "Accepted", result)
        self.assertEqual(result["output"].splitlines(), ["(1048576, 1048576)", "27"])

    def test_inflight_stdin_envelope_without_file_limit_remains_compatible(self):
        original_dumps = json.dumps

        def legacy_envelope(payload, **kwargs):
            return original_dumps(
                {key: value for key, value in payload.items() if key != "file_size_limit"},
                **kwargs,
            )

        with patch("services.execute_runner.json.dumps", side_effect=legacy_envelope):
            result = runner.run_code("print(input())", "python", "legacy request\n")
        self.assertEqual(result["status"], "Accepted", result)
        self.assertEqual(result["output"].strip(), "legacy request")

    def test_input_and_error_stream_are_drained_concurrently(self):
        code = "import sys; sys.stderr.write('e'*8192); print(len(sys.stdin.read()))"
        result = runner.run_code(code, "python", "x" * 131072)
        self.assertEqual(result["status"], "Accepted", result)
        self.assertEqual(result["output"].strip(), "131072")
        self.assertEqual(len(result["error"]), 8192)

    def test_both_streams_have_output_limits(self):
        for stream, field in [("stdout", "output"), ("stderr", "error")]:
            with (
                self.subTest(stream=stream),
                patch.object(runner, "CODE_RUN_MAX_OUTPUT_CHARS", 1024),
            ):
                result = runner.run_code(f"import sys; sys.{stream}.write('x'*1000000)", "python")
                self.assertEqual(result["status"], "Output Limit Exceeded", result)
                self.assertTrue(result[field + "_truncated"])
                if field == "output":
                    self.assertLessEqual(len(result[field]), 1100)

    def test_timeout_removes_container(self):
        names = []
        original_remove = runner._remove_container

        def remove(name):
            names.append(name)
            original_remove(name)

        with (
            patch.object(runner, "CODE_RUN_TIMEOUT_SECONDS", 2),
            patch.object(runner, "_remove_container", side_effect=remove),
        ):
            result = runner.run_code("import time; time.sleep(30)", "python")
        self.assertEqual(result["status"], "Time Limit Exceeded", result)
        self.assertTrue(names)
        inspect = subprocess.run(
            ["docker", "container", "inspect", names[-1]], capture_output=True, timeout=5
        )
        self.assertNotEqual(inspect.returncode, 0)

    def test_runtime_error_and_missing_image(self):
        result = runner.run_code("raise ValueError('test')", "python")
        self.assertEqual(result["status"], "Runtime Error", result)
        with patch.object(runner, "CODE_SANDBOX_IMAGE", "codelab-missing-test:never-pull"):
            result = runner.run_code("print(1)", "python")
        self.assertEqual(result["status"], "Environment Error", result)


if __name__ == "__main__":
    unittest.main()
