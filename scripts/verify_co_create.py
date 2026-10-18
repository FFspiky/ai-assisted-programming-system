"""Verify both learning flows against real Docker, without making AI requests."""

import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "tmp" / "co-create-check"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
DATABASE = ARTIFACTS / ("verification-" + uuid.uuid4().hex + ".db")
os.environ["DATABASE_URL"] = "sqlite:///" + DATABASE.as_posix()
os.environ["AUTO_CREATE_DATABASE"] = "0"
os.environ["FLASK_SECRET_KEY"] = "co-create-docker-verification-only"
os.environ["SILICONFLOW_API_KEY"] = ""

from app import app  # noqa: E402
from models import User, db  # noqa: E402
from modules.co_create.catalog import (  # noqa: E402
    IMPLEMENTATIONS,
    evaluate,
    list_catalog,
)
from services.execute_runner import run_code  # noqa: E402

BASE = "/api/co-create/sessions"
executions = []


def tracked_runner(*args, **kwargs):
    result = run_code(*args, **kwargs)
    executions.append(
        {key: result.get(key) for key in ("success", "status", "execution_backend", "time")}
    )
    return result


def checked(response, status=200):
    packet = response.get_json()
    assert response.status_code == status, (response.status_code, packet)
    assert packet["success"], packet
    return packet["data"]


def main():
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        user = User(username="co-create-verifier", email="co-create-verify@example.test")
        user.set_password("verification-password")
        db.session.add(user)
        db.session.commit()
    client = app.test_client()
    login = checked(
        client.post(
            "/api/login",
            json={
                "username": "co-create-verifier",
                "password": "verification-password",
            },
        )
    )
    headers = {"X-CSRF-Token": login["csrf_token"]}
    evidence = []

    def post(row, action, **fields):
        return checked(
            client.post(
                BASE + "/" + row["id"] + "/" + action,
                json={"revision": row["revision"], **fields},
                headers=headers,
            )
        )

    with (
        patch("modules.co_create.service.run_code", side_effect=tracked_runner),
        patch(
            "modules.co_create.ai.generate",
            side_effect=AssertionError("AI is disabled"),
        ),
    ):
        for scenario in list_catalog():
            create = {"mode": "examples", "scenario_id": scenario["id"]}
            row = checked(client.post(BASE, json=create, headers=headers), 201)["session"]
            row = post(row, "generate", source="teaching")["session"]
            generation = row["state"]["generations"][-1]
            assert generation["status"] == "verified", generation
            assert len(generation["candidates"]) == 2
            assert generation["behavior_difference"]["different"] is True
            for candidate in generation["candidates"]:
                assert candidate["verified"]
                assert candidate["verification"]["execution"]["execution_backend"] == "docker"
            compared = post(row, "compare", input=scenario["probe"])
            row, comparison = compared["session"], compared["run"]
            assert comparison["different"] is True, comparison
            rule = scenario["rule_options"][0]["id"]
            expected = evaluate(scenario["id"], rule, scenario["probe"])
            row = checked(
                client.patch(
                    BASE + "/" + row["id"],
                    json={
                        "revision": row["revision"],
                        "action": "upsert_example",
                        "example": {"input": scenario["probe"], "expected": expected},
                    },
                    headers=headers,
                )
            )["session"]
            assert row["state"]["current_generation_id"] is None
            row = post(row, "generate", source="teaching")["session"]
            narrowed = row["state"]["generations"][-1]
            assert narrowed["status"] == "verified"
            assert len(narrowed["candidates"]) == 1
            row = post(
                row,
                "select",
                generation_id=narrowed["id"],
                candidate_id=narrowed["candidates"][0]["id"],
            )["session"]
            restored = checked(client.get(BASE + "/" + row["id"]))["session"]
            assert restored["state"]["selected"] == row["state"]["selected"]
            assert len(restored["state"]["generations"]) == 2

            review = checked(
                client.post(
                    BASE,
                    json={"mode": "review", "scenario_id": scenario["id"]},
                    headers=headers,
                ),
                201,
            )["session"]
            right = scenario["review_rule"]["id"]
            other = next(r["id"] for r in scenario["rule_options"] if r["id"] != right)
            prediction = evaluate(scenario["id"], other, scenario["probe"])
            review = post(
                review,
                "review",
                judgment="incorrect",
                prediction=prediction,
                prediction_input=scenario["probe"],
                reflection="先检查能区分两条规则的输入。",
            )["session"]
            challenged = post(review, "review-run", input=scenario["probe"])
            review, failing = challenged["session"], challenged["run"]
            assert failing["success"] is True and failing["passed"] is False, failing
            assert failing["prediction_matched"] is True
            assert failing["execution"]["execution_backend"] == "docker"
            correct_prediction = evaluate(scenario["id"], right, scenario["probe"])
            review = post(
                review,
                "review",
                code=IMPLEMENTATIONS[(scenario["id"], right)],
                judgment="correct",
                prediction=correct_prediction,
                prediction_input=scenario["probe"],
                reflection="修订后再次验证同一个反例。",
            )["session"]
            revised = post(review, "review-run", input=scenario["probe"])
            review, passing = revised["session"], revised["run"]
            assert passing["passed"] is True and passing["prediction_matched"] is True
            assert passing["code_revision"] != failing["code_revision"]
            restored_review = checked(client.get(BASE + "/" + review["id"]))["session"]
            assert len(restored_review["state"]["review"]["evidence"]) == 2
            evidence.append(
                {
                    "scenario": scenario["id"],
                    "source": "teaching",
                    "comparison": comparison,
                    "selected": restored["state"]["selected"],
                    "initial_review": failing,
                    "revised_review": passing,
                }
            )
    assert executions and all(e["execution_backend"] == "docker" for e in executions)
    output = {
        "ai_requests": 0,
        "scenarios_verified": len(evidence),
        "docker_executions": len(executions),
        "execution_metadata": executions,
        "database": str(DATABASE),
        "evidence": evidence,
    }
    (ARTIFACTS / "docker-verification.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: output[k] for k in ("ai_requests", "scenarios_verified", "docker_executions")}
        )
    )


if __name__ == "__main__":
    main()
