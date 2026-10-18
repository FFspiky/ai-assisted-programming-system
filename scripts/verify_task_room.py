"""Replay trusted task-room references in Docker without Flask, a database or AI.

This script imports model definitions through service.py only to share the actual
production harness and JSON comparator. It never imports app.py, creates a Flask
application, queries SQLAlchemy, or executes reference code on the host.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.task_room.catalog import build_contract, list_catalog, reference_code  # noqa: E402
from modules.task_room.service import build_harness, same_json  # noqa: E402
from services.execute_runner import run_code  # noqa: E402


def variants(scenario, all_rules=False):
    groups = scenario["rule_groups"]
    recommended = {group["key"]: group["recommended"] for group in groups}
    if all_rules:
        options = itertools.product(*(group["options"] for group in groups))
        candidates = [
            (
                f"combination-{index}",
                {
                    group["key"]: option["value"]
                    for group, option in zip(groups, combination, strict=True)
                },
            )
            for index, combination in enumerate(options, 1)
        ]
    else:
        candidates = [("recommended", recommended)] + [
            (change["id"], {**recommended, **change["patch"]}) for change in scenario["changes"]
        ]
    seen = set()
    for name, rules in candidates:
        signature = json.dumps(rules, sort_keys=True)
        if signature not in seen:
            seen.add(signature)
            yield name, rules


def short_json(value, maximum=600):
    text = json.dumps(value, ensure_ascii=False, allow_nan=False)
    return text if len(text) <= maximum else text[:maximum] + "…"


def verify(scenario, variant, rules):
    contract = build_contract(scenario["id"], rules)
    cases = contract["cases"]
    payload = {
        "code": reference_code(scenario["id"], rules),
        "inputs": [case["input"] for case in cases],
    }
    record = {
        "scenario_id": scenario["id"],
        "variant": variant,
        "rules": rules,
        "total": len(cases),
        "passed": 0,
        "success": False,
        "execution": {},
        "failures": [],
    }
    try:
        execution = run_code(
            build_harness(),
            "python",
            input_text=json.dumps(payload, ensure_ascii=False, allow_nan=False),
        )
        fields = (
            "success",
            "status",
            "execution_backend",
            "time",
            "compile_time",
            "run_time",
            "output_truncated",
            "error_truncated",
        )
        record["execution"] = {key: execution[key] for key in fields if key in execution}
        if execution.get("error"):
            record["execution"]["error"] = str(execution["error"])[:1200]
        if (
            execution.get("success") is not True
            or execution.get("status") != "Accepted"
            or execution.get("execution_backend") != "docker"
        ):
            record["failures"].append({"error": "未取得成功的真实 Docker 执行记录"})
            return record
        packet = json.loads(execution.get("output", ""))
        rows = packet["results"]
        if not isinstance(rows, list) or len(rows) != len(cases):
            raise ValueError("验收返回数量不符合合同")
        for index, (case, row) in enumerate(zip(cases, rows, strict=True)):
            if (
                not isinstance(row, dict)
                or type(row.get("index")) is not int
                or row["index"] != index
                or "actual" not in row
                or "error" not in row
            ):
                raise ValueError("验收返回的案例序号或结构无效")
            if row["error"] is None and same_json(row["actual"], case["expected"]):
                record["passed"] += 1
            elif len(record["failures"]) < 4:
                record["failures"].append(
                    {
                        "case_id": case["id"],
                        "case_name": case["name"],
                        "error": (
                            str(row["error"])[:600]
                            if row["error"] is not None
                            else "返回值不符合合同"
                        ),
                        "expected": short_json(case["expected"]),
                        "actual": short_json(row["actual"]),
                    }
                )
        record["success"] = record["passed"] == record["total"]
    except Exception as exc:
        record["failures"].append({"error": f"{type(exc).__name__}: {str(exc)[:1200]}"})
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="在真实 Docker 隔离环境回放任务室参考实现；不调用 AI、不访问用户数据库。"
    )
    parser.add_argument(
        "--all-rules",
        action="store_true",
        help="回放全部规则组合；默认回放推荐规则及每项有效客户变更。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tmp/task-room-check/docker-results.json",
        help="JSON 验证报告路径。",
    )
    args = parser.parse_args(argv)
    records = []
    for scenario in list_catalog():
        for variant, rules in variants(scenario, args.all_rules):
            record = verify(scenario, variant, rules)
            records.append(record)
            print(
                f"{scenario['id']} / {variant}: {record['passed']}/{record['total']} {'PASS' if record['success'] else 'FAIL'}",
                flush=True,
            )
    passed = sum(record["passed"] for record in records)
    total = sum(record["total"] for record in records)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "all_rules" if args.all_rules else "recommended_and_changes",
        "success": bool(records) and all(record["success"] for record in records),
        "scenarios": len({record["scenario_id"] for record in records}),
        "contracts": len(records),
        "passed_cases": passed,
        "total_cases": total,
        "runs": records,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(f"{passed}/{total} cases; {len(records)} Docker runs. Report: {output}")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
