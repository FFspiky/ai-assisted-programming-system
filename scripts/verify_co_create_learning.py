"""Two real Docker learning journeys in a fresh, isolated SQLite database.

This does not test live AI generation. Programs are explicitly authored verifier
fixtures, all in-process HTTP provider requests are forbidden, and the production
database is never selected. One source run and six formal target cases per language.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "tmp" / "learning-journey-check"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
RUN_ID = uuid.uuid4().hex
DATABASE = ARTIFACTS / f"docker-smoke-{RUN_ID}.db"
REPORT = ARTIFACTS / "docker-smoke.json"
os.environ.update(
    DATABASE_URL="sqlite:///" + DATABASE.as_posix(),
    AUTO_CREATE_DATABASE="0",
    FLASK_SECRET_KEY="isolated-learning-journey-verifier",
    SILICONFLOW_API_KEY="",
    SUPPORTED_LANGUAGES="python,cpp",
    RATE_LIMIT_REDIS_URL="",
    REDIS_URL="",
    ADMIN_USERNAME="",
    ADMIN_PASSWORD="",
    ADMIN_EMAIL="",
)
DOCKER_DIRECTORY = Path(os.getenv("LOCALAPPDATA", "")) / "Programs/DockerDesktop/resources/bin"
if (DOCKER_DIRECTORY / "docker.exe").exists():
    os.environ["PATH"] = str(DOCKER_DIRECTORY) + os.pathsep + os.environ.get("PATH", "")

from app import app  # noqa: E402
from config import API_KEY  # noqa: E402
from models import PracticeEvent, Problem, Submission, TestCase, User, db  # noqa: E402
from services.execute_runner import run_code  # noqa: E402
from services.problem_library import load_library  # noqa: E402

BASE = "/api/co-create/sessions"
SOURCE = "CL-BASICS-01"
TARGET = "CL-BASICS-02"
SOURCE_PROGRAMS = {
    "python": "t = int(input())\nprint(t // 3600, t // 60 % 60, t % 60)\n",
    "cpp": (
        "#include <iostream>\nint main(){ long long t; std::cin >> t;\n"
        "std::cout << t/3600 << ' ' << t/60%60 << ' ' << t%60 << '\\n'; }\n"
    ),
}
TARGET_PROGRAMS = {
    "python": "n = abs(int(input()))\ns = 0\nwhile n:\n    s += n % 10\n    n //= 10\nprint(s)\n",
    "cpp": (
        "#include <iostream>\nint main(){ long long n; std::cin >> n;\n"
        "if(n<0)n=-n; int s=0; while(n){s+=n%10;n/=10;} std::cout << s << '\\n'; }\n"
    ),
}
executions = []
stage = {"language": None, "name": None}


def checked(response, status=200):
    packet = response.get_json()
    assert response.status_code == status, (response.status_code, packet)
    assert packet["success"] is True, packet
    return packet["data"]


def counts():
    with app.app_context():
        return {
            "submissions": Submission.query.count(),
            "points": User.query.filter_by(username="learning-smoke-verifier").one().points,
            "transfer_events": PracticeEvent.query.filter_by(kind="transfer_submission").count(),
        }


def tracked_runner(*args, **kwargs):
    result = run_code(*args, **kwargs)
    executions.append(
        {
            "language": stage["language"],
            "stage": stage["name"],
            **{
                key: result.get(key)
                for key in (
                    "success",
                    "status",
                    "execution_backend",
                    "time",
                    "compile_time",
                    "run_time",
                )
            },
        }
    )
    assert result.get("execution_backend") == "docker", result
    assert result.get("success") is True, result
    return result


def assert_no_mastery(value):
    if isinstance(value, dict):
        assert not any("mastery" in key.lower() for key in value), value
        for child in value.values():
            assert_no_mastery(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_mastery(child)


def assert_hidden_redacted(cases):
    hidden = [item for item in cases if not item["is_public"]]
    assert len(hidden) == 4, cases
    for item in hidden:
        assert not set(item) & {
            "input",
            "expected",
            "expected_output",
            "actual",
            "actual_output",
            "output",
            "error",
        }, item


def main():
    started = time.monotonic()
    assert not API_KEY, "The verifier must not inherit a paid provider credential"
    docker = shutil.which("docker")
    assert docker, "Docker CLI was not found"
    image = subprocess.run(
        [
            docker,
            "image",
            "inspect",
            os.getenv("CODE_SANDBOX_IMAGE", "codelab-runner:local"),
            "--format",
            "{{.Id}}",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.strip()
    app.config.update(TESTING=True, SESSION_COOKIE_NAME="isolated_learning_smoke")
    with app.app_context():
        assert Path(db.engine.url.database).resolve() == DATABASE.resolve()
        assert not DATABASE.exists(), "Every verifier run must use a fresh database"
        db.create_all()
        user = User(username="learning-smoke-verifier", email="learning-smoke@example.test")
        user.set_password("isolated-learning-smoke-password")
        db.session.add(user)
        for record in load_library():
            if record["id"] not in {SOURCE, TARGET}:
                continue
            db.session.add(
                Problem(
                    **{
                        key: record[key]
                        for key in (
                            "id",
                            "title",
                            "description",
                            "difficulty",
                            "category",
                            "tags",
                            "source",
                            "judge_mode",
                        )
                    }
                )
            )
            for case in record["cases"]:
                db.session.add(
                    TestCase(
                        problem_id=record["id"],
                        input_data=case["input"],
                        expected_output=case["output"],
                        is_public=case["public"],
                    )
                )
        db.session.commit()
    client = app.test_client()
    login = client.post(
        "/api/login",
        json={
            "username": "learning-smoke-verifier",
            "password": "isolated-learning-smoke-password",
        },
    )
    checked(login)
    headers = {"X-CSRF-Token": login.get_json()["csrf_token"]}
    evidence = []

    def post(row, action, **body):
        return checked(
            client.post(
                f'{BASE}/{row["id"]}/{action}',
                json={"revision": row["revision"], **body},
                headers=headers,
            )
        )

    with (
        patch("modules.co_create.service.run_code", side_effect=tracked_runner),
        patch("routes.solution_checker.run_code", side_effect=tracked_runner),
        patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError(
                "Any HTTP provider request is forbidden in this isolated Docker verifier"
            ),
        ) as network,
    ):
        for language in SOURCE_PROGRAMS:
            stage.update(language=language, name="source-single-official-input")
            before = counts()
            row = checked(
                client.post(
                    BASE,
                    json={
                        "mode": "review",
                        "problem_id": SOURCE,
                        "language": language,
                        "code": SOURCE_PROGRAMS[language],
                        "input_text": "3661\n",
                    },
                    headers=headers,
                ),
                201,
            )["session"]
            run_result = post(row, "review-run", input="3661\n")
            row, run = run_result["session"], run_result["run"]
            assert run["passed"] is True and run["expected_source"] == "official", run
            assert run["prediction_matched"] is None
            reflected = post(
                row,
                "learning/reflection",
                candidate_id="review",
                judgment="unsure",
                reason="校验者本人记录：分钟使用整除后取余。",
                boundary="校验者本人记录：检查零值和整小时边界。",
                next_check="校验者本人记录：继续检查范围上界。",
            )
            row = reflected["session"]
            assert reflected["learning"]["reflection"]["stale"] is False
            assert run["id"] in reflected["learning"]["reflection"]["run_ids"]
            assert [item["problem_id"] for item in reflected["related"]] == [TARGET]
            opened = post(row, "learning/transfer", problem_id=TARGET)
            row, attempt = opened["session"], opened["attempt"]
            attempt_url = f'{BASE}/{row["id"]}/learning/transfer/{attempt["id"]}'
            context = checked(client.get(attempt_url))
            assert context["attempt"]["problem_id"] == TARGET
            assert context["attempt"]["language"] == language
            assert counts() == before, "Learning-only actions must not create submissions or points"

            stage["name"] = "target-six-official-cases"
            body = {
                "problem_id": TARGET,
                "language": language,
                "code": TARGET_PROGRAMS[language],
                "operation_id": uuid.uuid4().hex,
            }
            formal = checked(client.post("/api/check-solution", json=body, headers=headers))
            assert formal["status"] == "Accepted", formal
            assert formal["evidence"]["executed"] == 6
            assert_hidden_redacted(formal["evidence"]["cases"])
            formal_counts = counts()
            assert formal_counts["submissions"] == before["submissions"] + 1
            assert (
                formal_counts["points"] == 10
            ), "Same target earns its existing first-pass award only"
            executed = len(executions)
            replay = checked(client.post("/api/check-solution", json=body, headers=headers))
            assert replay["submission_id"] == formal["submission_id"]
            assert len(executions) == executed and counts() == formal_counts

            attached = post(
                row,
                f'learning/transfer/{attempt["id"]}/submission',
                submission_id=formal["submission_id"],
                help_usage="unspecified",
            )
            row = attached["session"]
            saved = attached["attempt"]["submissions"][0]
            assert saved["help_usage"] == "unspecified"
            assert saved["help_usage_source"] == "student_self_report"
            assert saved["submission"]["status"] == "Accepted"
            assert saved["recorded_help"] == []
            assert counts() == {**formal_counts, "transfer_events": before["transfer_events"] + 1}
            current_counts = counts()
            repeated = post(
                row,
                f'learning/transfer/{attempt["id"]}/submission',
                submission_id=formal["submission_id"],
                help_usage="unspecified",
            )
            assert repeated["revision"] == row["revision"] and counts() == current_counts
            changed = post(
                row,
                f'learning/transfer/{attempt["id"]}/submission',
                submission_id=formal["submission_id"],
                help_usage="none",
            )
            row = changed["session"]
            assert changed["attempt"]["submissions"][0]["help_usage"] == "none"
            assert counts() == current_counts
            recap = checked(client.get(f'{BASE}/{row["id"]}/learning'))
            assert_no_mastery(recap)
            assert recap["learning"]["stage"] == "transfer"
            assert len(recap["recap"]["transfer_attempts"]) == 1
            assert recap["recap"]["reflection"]["judgment"] == "unsure"
            assert len(executions) - (len(evidence) * 7) == 7
            evidence.append(
                {
                    "language": language,
                    "session_id": row["id"],
                    "attempt_id": attempt["id"],
                    "practice_url": opened["practice_url"],
                    "source_run": run,
                    "source_full_verification": "Not run; single official input only, to limit smoke cost",
                    "target_submission_id": formal["submission_id"],
                    "target_status": formal["status"],
                    "target_executed_cases": formal["evidence"]["executed"],
                    "formal_replay_idempotent": True,
                    "association_idempotent": True,
                    "help_usage_transition": ["unspecified", "none"],
                    "help_usage_source": "student_self_report",
                    "no_mastery_score": True,
                    "counts_before": before,
                    "counts_after": counts(),
                    "recap": recap["recap"],
                }
            )
            print(
                json.dumps(
                    {"language": language, "passed": True, "docker_executions": len(executions)}
                ),
                flush=True,
            )
        network.assert_not_called()
    assert counts() == {"submissions": 2, "points": 10, "transfer_events": 2}
    assert len(executions) == 14
    report = {
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "run_id": RUN_ID,
        "database": str(DATABASE),
        "production_database_selected": False,
        "image_id": image,
        "source_problem_id": SOURCE,
        "target_problem_id": TARGET,
        "program_source": "Explicitly authored verifier fixtures; no AI generation",
        "paid_ai_requests": 0,
        "in_process_http_requests": 0,
        "docker_executions": len(executions),
        "execution_languages": dict(Counter(item["language"] for item in executions)),
        "execution_metadata": executions,
        "formal_submission_count": 2,
        "points_after_two_languages_same_target": 10,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "passed": True,
        "evidence": evidence,
    }
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    REPORT.write_text(output, encoding="utf-8")
    (ARTIFACTS / f"docker-smoke-{RUN_ID}.json").write_text(output, encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": True,
                "report": str(REPORT),
                "docker_executions": len(executions),
                "formal_submissions": len(evidence),
                "paid_ai_requests": 0,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
