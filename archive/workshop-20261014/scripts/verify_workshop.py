"""Run built-in scenes in Docker and optionally freeze honest example recordings."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.execute_runner import run_code
from services.workshop import fingerprint, parse_trace
from services.workshop_catalog import SCENES, normalize_params


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-previews", action="store_true")
    args = parser.parse_args()
    previews = {}
    for scene, spec in SCENES.items():
        defaults = normalize_params(scene, {})
        variants = {
            "ocean": {"count": 18, "speed": 6, "spread": 100, "seed": 0},
            "sorting": {"count": 16, "algorithm": "insertion", "seed": 7},
            "route": {"density": 0.4, "algorithm": "astar", "seed": 7},
        }
        for index, params in enumerate([defaults, normalize_params(scene, variants[scene])]):
            result = run_code(spec["code"], "python", json.dumps(params))
            if not result.get("success"):
                raise RuntimeError(f"{scene}: {result.get('status')} {result.get('error')}")
            trace = parse_trace(scene, result["output"])
            if scene == "sorting":
                assert trace["frames"][-1]["values"] == sorted(trace["frames"][0]["values"])
            if scene == "route":
                assert trace["path"], "Built-in scene guarantees a reachable goal"
            if index == 0:
                previews[scene] = {
                    "fingerprint": fingerprint(scene, spec["code"], params),
                    "trace": trace,
                    "execution_backend": result["execution_backend"],
                }
            print(
                f"{scene} {'default' if index == 0 else 'variant'}: Docker passed, {len(result['output'])} output characters"
            )
    if args.write_previews:
        target = Path(__file__).resolve().parents[1] / "data" / "workshop_previews.json"
        target.write_text(
            json.dumps(previews, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        print("Example recordings saved from the verified Docker runs.")


if __name__ == "__main__":
    main()
