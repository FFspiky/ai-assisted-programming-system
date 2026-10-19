"""Real Docker checks, without Flask/user databases or any AI request.

Run: python -m modules.task_room.verify_languages --languages python cpp
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from services.execute_runner import run_code

from .catalog import build_contract, get_scenario, reference_code
from .languages import compiled_harness
from .service import build_harness, same_json


def score_code(language, rules):
    threshold = int(rules["threshold"])
    compare = ">=" if rules["boundary"] == "inclusive" else ">"
    if language == "python":
        return reference_code("score_summary", rules)
    if language == "cpp":
        return f"""Json solve(const Json& data) {{
    long long total=0,highest=0,passed=0;
    for(const Json& value:data["scores"].array_items()) {{
        long long score=value.as_int();total+=score;highest=max(highest,score);
        if(score {compare} {threshold})passed++;
    }}
    Json result=Json::object();result["count"]=data["scores"].size();result["total"]=total;
    result["highest"]=highest;result["passed"]=passed;return result;
}}"""
    raise ValueError("Unsupported language")


def verify(language, label, code, inputs, expected):
    source = build_harness() if language == "python" else compiled_harness(code, language)
    payload = {"code": code, "inputs": inputs} if language == "python" else inputs
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if label == "json_unicode_types_and_debug_capture":
        # Exercise raw UTF-8 and escaped Unicode/surrogate pairs together.
        text = inputs[0]["text"]
        encoded = encoded.replace(
            json.dumps(text, ensure_ascii=False), json.dumps(text, ensure_ascii=True), 1
        )
    execution = run_code(source, language, input_text=encoded)
    results = []
    if execution.get("success") and execution.get("execution_backend") == "docker":
        try:
            results = json.loads(execution["output"])["results"]
        except (ValueError, KeyError, TypeError):
            pass
    success = len(results) == len(expected) and all(
        row.get("index") == i and row.get("error") is None and same_json(row.get("actual"), answer)
        for i, (row, answer) in enumerate(zip(results, expected, strict=True))
    )
    return {
        "language": language,
        "test": label,
        "success": success,
        "total": len(expected),
        "execution": {k: v for k, v in execution.items() if k not in {"output"}},
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--languages",
        nargs="+",
        choices=("python", "cpp"),
        default=["python", "cpp"],
    )
    parser.add_argument(
        "--output", type=Path, default=Path("tmp/task-room-multilang/docker-verification.json")
    )
    args = parser.parse_args()
    scenario = get_scenario("score_summary")
    rules = {group["key"]: group["recommended"] for group in scenario["rule_groups"]}
    contract = build_contract("score_summary", rules)
    records = []
    for language in args.languages:
        record = verify(
            language,
            "score_summary_acceptance",
            score_code(language, rules),
            [c["input"] for c in contract["cases"]],
            [c["expected"] for c in contract["cases"]],
        )
        records.append(record)
        print(language, "score_summary", record["success"], flush=True)
        code = {
            "python": "def solve(data):\n    print('debug')\n    return data\n",
            "cpp": 'Json solve(const Json& data) { cout << "debug"; return data; }',
        }[language]
        inputs = [
            {
                "text": '中文😀\n\t"\\',
                "raw": "保持中文😀",
                "nested": [None, True, False, 0, -1, 1.5, {"empty": []}],
                "large": 1000000000,
            },
            [],
            {},
        ]
        record = verify(language, "json_unicode_types_and_debug_capture", code, inputs, inputs)
        records.append(record)
        print(language, "JSON roundtrip", record["success"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"at": datetime.now(timezone.utc).isoformat(), "records": records},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if all(record["success"] for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
