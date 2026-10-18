"""Check every expected answer against private references in the Docker sandbox."""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def verify():
    from services.execute_runner import run_code

    problems = json.loads((ROOT / "data/problem_library.json").read_text(encoding="utf-8"))
    references = json.loads((ROOT / "data/reference_solutions.json").read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    for p in problems:
        compile(references[p["id"]], p["id"], "exec")
        grouped[p["category"]].append(
            {"id": p["id"], "cases": p["cases"], "source": references[p["id"]]}
        )
    count = 0
    for category, batch in grouped.items():
        code = "import io,sys,json,contextlib\ntasks=json.loads(" + repr(json.dumps(batch)) + ")\n"
        code += """count=0
for task in tasks:
 for case in task['cases']:
  sys.stdin=io.StringIO(case['input']);out=io.StringIO()
  with contextlib.redirect_stdout(out):exec(compile(task['source'],task['id'],'exec'),{})
  assert out.getvalue().strip()==case['output'].strip(),(task['id'],case['input'],out.getvalue(),case['output'])
  count+=1
print(count)
"""
        result = run_code(code, "python")
        if not result.get("success"):
            raise RuntimeError(category + ": " + str(result))
        n = int(result["output"].strip())
        count += n
        print(category, n, "cases PASS", flush=True)
    assert count == 360
    print("TOTAL: 60 problems / 360 cases PASS")


if __name__ == "__main__":
    verify()
