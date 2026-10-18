"""Real Docker verification of problem co-creation and practice handoff.

Run from the repository with its virtualenv. Each run creates its own SQLite
database under tmp/problem-co-create-check. No paid AI request is permitted:
generate_problem is replaced with an explicitly named test-stub candidate.
All student and reference programs still compile/execute in the real sandbox.
"""

import json
import os
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
ARTIFACTS = ROOT / "tmp" / "problem-co-create-check"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
RUN_ID = uuid.uuid4().hex
DATABASE = ARTIFACTS / f"verification-{RUN_ID}.db"
REPORT = ARTIFACTS / f"docker-verification-{RUN_ID}.json"
os.environ.update(
    DATABASE_URL="sqlite:///" + DATABASE.as_posix(),
    AUTO_CREATE_DATABASE="0",
    FLASK_SECRET_KEY="isolated-problem-docker-verification",
    SILICONFLOW_API_KEY="",
    SUPPORTED_LANGUAGES="python,cpp,java",
    RATE_LIMIT_REDIS_URL="",
    REDIS_URL="",
    ADMIN_USERNAME="",
    ADMIN_PASSWORD="",
    ADMIN_EMAIL="",
)

from app import app  # noqa: E402
from models import (  # noqa: E402
    PracticeEvent,
    Problem,
    Submission,
    TestCase,
    User,
    db,
)
from services.execute_runner import run_code  # noqa: E402
from services.problem_library import load_library  # noqa: E402

PID = "CL-BASICS-01"
BASE = "/api/co-create/sessions"
PROGRAMS = {
    "python": "t = int(input())\nprint(t // 3600, t // 60 % 60, t % 60)\n",
    "cpp": (
        "#include <iostream>\n"
        "int main() { long long t; if (!(std::cin >> t)) return 1;\n"
        "std::cout << t / 3600 << ' ' << t / 60 % 60 << ' ' << t % 60 << '\\n'; }\n"
    ),
    "java": (
        "import java.util.Scanner;\n"
        "public class Main { public static void main(String[] args) {\n"
        "Scanner scanner = new Scanner(System.in); long t = scanner.nextLong();\n"
        'System.out.println(t / 3600 + " " + t / 60 % 60 + " " + t % 60); } }\n'
    ),
}
WRONG = {
    "python": PROGRAMS["python"].replace("t // 60 % 60", "t // 60"),
    "cpp": PROGRAMS["cpp"].replace("t / 60 % 60", "t / 60"),
    "java": PROGRAMS["java"].replace("t / 60 % 60", "t / 60"),
}
executions = []
stage = {"language": None, "name": None}


def tracked_runner(*args, **kwargs):
    result = run_code(*args, **kwargs)
    executions.append(
        {
            "requested_language": stage["language"],
            "execution_language": args[1] if len(args) > 1 else kwargs.get("language", "python"),
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


def checked(response, status=200):
    packet = response.get_json()
    assert response.status_code == status, (response.status_code, packet)
    assert packet["success"] is True, packet
    return packet["data"]


def counts():
    with app.app_context():
        return {
            "submissions": Submission.query.count(),
            "points": User.query.filter_by(username="problem-docker-verifier").one().points,
        }


def check_hidden(cases):
    hidden = [case for case in cases if not case["is_public"]]
    assert len(hidden) == 4, cases
    for case in hidden:
        assert set(case) <= {
            "id",
            "index",
            "is_public",
            "status",
            "passed",
            "time",
            "compile_time",
            "run_time",
        }, case
        assert not (
            set(case)
            & {"input", "expected", "expected_output", "actual", "actual_output", "output", "error"}
        ), case
    return True


def main():
    started = time.monotonic()
    image = subprocess.run(
        [
            "docker",
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
    record = next(item for item in load_library() if item["id"] == PID)
    app.config["TESTING"] = True
    app.config["SESSION_COOKIE_NAME"] = "isolated_problem_verification"
    with app.app_context():
        assert Path(db.engine.url.database).resolve() == DATABASE.resolve()
        db.create_all()
        user = User(username="problem-docker-verifier", email="problem-verifier@example.test")
        user.set_password("isolated-verification-password")
        db.session.add(user)
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
                    problem_id=PID,
                    input_data=case["input"],
                    expected_output=case["output"],
                    is_public=case["public"],
                )
            )
        db.session.commit()
    client = app.test_client()
    login_response = client.post(
        "/api/login",
        json={"username": "problem-docker-verifier", "password": "isolated-verification-password"},
    )
    checked(login_response)
    headers = {"X-CSRF-Token": login_response.get_json()["csrf_token"]}
    evidence = []

    def post(row, action, **fields):
        stage["name"] = action
        return checked(
            client.post(
                f'{BASE}/{row["id"]}/{action}',
                json={"revision": row["revision"], **fields},
                headers=headers,
            )
        )

    def act(proposal, action, code, language):
        return checked(
            client.post(
                f'/api/proposals/{proposal["id"]}/actions',
                json={
                    "revision": proposal["revision"],
                    "action": action,
                    "code": code,
                    "language": language,
                    "operation_id": uuid.uuid4().hex,
                },
                headers=headers,
            )
        )

    with (
        patch("modules.co_create.service.run_code", side_effect=tracked_runner),
        patch("routes.solution_checker.run_code", side_effect=tracked_runner),
        patch(
            "modules.co_create.ai.chat_completion",
            side_effect=AssertionError("Paid AI is forbidden in this verifier"),
        ) as provider,
    ):
        for language, correct in PROGRAMS.items():
            stage["language"] = language
            before = counts()
            row = checked(
                client.post(
                    BASE,
                    json={
                        "mode": "examples",
                        "problem_id": PID,
                        "language": language,
                        "code": WRONG[language],
                        "input_text": "7385\n",
                    },
                    headers=headers,
                ),
                201,
            )["session"]
            assert row["language"] == language and row["problem_id"] == PID
            assert row["state"]["baseline"]["source"] == "student"
            assert len(row["problem"]["public_examples"]) == 2
            assert row["problem"]["reference_available"] is True

            row = checked(
                client.patch(
                    f'{BASE}/{row["id"]}',
                    json={
                        "revision": row["revision"],
                        "action": "upsert_example",
                        "example": {"input": "7385\n"},
                    },
                    headers=headers,
                )
            )["session"]
            assert row["state"]["examples"][-1]["expected"] is None
            assert row["state"]["examples"][-1]["source"] == "unknown"
            with patch(
                "modules.co_create.ai.generate_problem",
                return_value=(
                    [
                        {
                            "code": correct,
                            "label": "Explicit test-stub candidate",
                            "explanation": "Verification fixture; no real AI request.",
                        }
                    ],
                    "test-stub",
                ),
            ) as generator:
                row = post(row, "generate", source="ai")["session"]
                assert generator.call_args.args[1] == language
                assert generator.call_args.kwargs["count"] == 1
            generation = row["state"]["generations"][-1]
            assert (
                generation["status"] == "ready" and generation["model"] == "test-stub"
            ), generation
            baseline, candidate = generation["candidates"]
            assert baseline["source"] == "student" and baseline["model"] is None
            assert candidate["source"] == "ai" and candidate["model"] == "test-stub"
            assert baseline["verified"] is False and candidate["verified"] is True
            for item in generation["candidates"]:
                unknown = item["verification"]["cases"][-1]
                assert unknown["passed"] is None and unknown["verdict"] == "unverified"

            compared = post(row, "compare", input="7385\n")
            row, comparison = compared["session"], compared["run"]
            assert comparison["different"] is True and comparison["correctness_verified"] is False
            assert comparison["expected_source"] == "unknown" and comparison["expected"] is None
            assert all(
                result["passed"] is None and result["verdict"] == "unverified"
                for result in comparison["results"]
            )

            verified = post(row, "verify", candidate_id=candidate["id"])
            row, verification = verified["session"], verified["run"]
            assert verification["passed"] is True and verification["passed_count"] == 6
            assert verification["hidden_total"] == verification["hidden_passed"] == 4
            check_hidden(verification["cases"])
            row = post(row, "select", generation_id=generation["id"], candidate_id=candidate["id"])[
                "session"
            ]
            handoff = post(row, "handoff", candidate_id=candidate["id"])
            proposal = handoff["proposal"]
            assert proposal["source"] == "co_create" and proposal["language"] == language
            assert proposal["state"] == "pending" and proposal["base_code"] == WRONG[language]
            assert proposal["candidate_code"] == correct and proposal["diff"]
            assert (
                counts() == before
            ), "Co-creation/handoff must not create official submissions or points"

            accepted = act(proposal, "accept", WRONG[language], language)
            assert accepted["editor_code"] == correct
            undone = act(accepted["proposal"], "undo", correct, language)
            assert undone["editor_code"] == WRONG[language]
            accepted = act(undone["proposal"], "accept", WRONG[language], language)
            proposal = accepted["proposal"]
            assert accepted["editor_code"] == correct and proposal["state"] == "accepted"
            assert counts() == before

            stage["name"] = "official-retest"
            body = {
                "problem_id": PID,
                "language": language,
                "code": correct,
                "proposal_id": proposal["id"],
                "proposal_revision": proposal["revision"],
                "operation_id": uuid.uuid4().hex,
            }
            formal_response = client.post("/api/check-solution", json=body, headers=headers)
            formal = checked(formal_response)
            assert formal["status"] == "Accepted" and formal["evidence"]["executed"] == 6, formal
            check_hidden(formal["evidence"]["cases"])
            after_formal = counts()
            assert after_formal["submissions"] == before["submissions"] + 1
            assert after_formal["points"] == 10, after_formal
            execution_count = len(executions)
            replay = checked(client.post("/api/check-solution", json=body, headers=headers))
            assert replay["submission_id"] == formal["submission_id"]
            assert len(executions) == execution_count and counts() == after_formal
            with app.app_context():
                saved = db.session.get(Submission, formal["submission_id"])
                assert saved.language == language and saved.problem_id == PID
                assert (
                    PracticeEvent.query.filter_by(
                        submission_id=saved.id, kind="retest", language=language
                    ).count()
                    == 1
                )

            review = checked(
                client.post(
                    BASE,
                    json={
                        "mode": "review",
                        "problem_id": PID,
                        "language": language,
                        "code": WRONG[language],
                    },
                    headers=headers,
                ),
                201,
            )["session"]
            review = post(
                review,
                "review",
                judgment="incorrect",
                prediction="2 123 5",
                prediction_input="7385\n",
            )["session"]
            challenged = post(review, "review-run", input="7385\n", input_validated=True)
            review, wrong_run = challenged["session"], challenged["run"]
            assert wrong_run["expected_source"] == "reference" and wrong_run["passed"] is False
            assert wrong_run["prediction_matched"] is True
            assert wrong_run["expected"].strip() == "2 3 5"
            review = post(
                review,
                "review",
                code=correct,
                judgment="correct",
                reflection="Corrected minutes modulo; optional prediction intentionally omitted.",
            )["session"]
            assert review["state"]["review"]["prediction_saved"] is False
            revised = post(review, "review-run", input="3661\n")
            review, correct_run = revised["session"], revised["run"]
            assert correct_run["expected_source"] == "official" and correct_run["passed"] is True
            assert correct_run["prediction_matched"] is None
            assert correct_run["code_revision"] != wrong_run["code_revision"]
            assert len(review["state"]["review"]["evidence"]) == 2
            assert counts() == after_formal
            restored = checked(client.get(f'{BASE}/{review["id"]}'))["session"]
            assert restored["state"]["review"]["code"] == correct
            assert restored["language"] == language
            history = checked(
                client.get(f"/api/problems/{PID}/practice-history?language={language}")
            )
            assert len(history["submissions"]) == 1
            latest = next(item for item in history["proposals"] if item["id"] == proposal["id"])
            assert latest["latest_test"]["status"] == "Accepted"
            assert latest["latest_test"]["submission_id"] == formal["submission_id"]
            evidence.append(
                {
                    "language": language,
                    "session_id": row["id"],
                    "review_session_id": review["id"],
                    "source": "test-stub (AI replaced; not a real AI invocation)",
                    "unknown_comparison": comparison,
                    "full_verification": verification,
                    "handoff_proposal": proposal["id"],
                    "practice_actions": ["accept", "undo", "accept"],
                    "formal_submission": {
                        "id": formal["submission_id"],
                        "status": formal["status"],
                        "language": language,
                        "executed": formal["evidence"]["executed"],
                    },
                    "idempotent_formal_replay": True,
                    "review_before": wrong_run,
                    "review_after": correct_run,
                    "hidden_evidence_redacted": True,
                    "only_formal_retest_created_submission": True,
                }
            )
            print(
                json.dumps(
                    {
                        "language": language,
                        "passed": True,
                        "docker_executions_so_far": len(executions),
                    }
                ),
                flush=True,
            )
        provider.assert_not_called()
    assert counts() == {"submissions": 3, "points": 10}
    report = {
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "run_id": RUN_ID,
        "database": str(DATABASE),
        "image_id": image,
        "problem_id": PID,
        "paid_ai_requests": 0,
        "ai_replacement": "generate_problem replaced with explicit test-stub model; this does not test live AI generation",
        "languages": list(PROGRAMS),
        "docker_executions": len(executions),
        "execution_languages": dict(Counter(item["execution_language"] for item in executions)),
        "execution_metadata": executions,
        "formal_submission_count": 3,
        "points_after_three_languages_same_problem": 10,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "passed": True,
        "evidence": evidence,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (ARTIFACTS / "docker-verification-latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": True,
                "paid_ai_requests": 0,
                "docker_executions": len(executions),
                "report": str(REPORT),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
