"""Check, export or load the isolated runner without contacting a registry."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = "codelab-runner:local"


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def docker(*args, timeout=60):
    return subprocess.check_output(["docker", *args], timeout=timeout)


def inspect_and_check(image):
    info = json.loads(docker("image", "inspect", image))[0]
    image_id = info["Id"]
    config = info["Config"]
    if info["Os"] != "linux" or config["User"] != "65534:65534":
        raise ValueError("Expected a Linux runner with the unprivileged runner user")
    if config["Entrypoint"] != ["python3", "-I", "/usr/local/bin/run_submission.py"]:
        raise ValueError("Unexpected runner entrypoint")
    source = docker(
        "run",
        "--rm",
        "--pull=never",
        "--network=none",
        "--read-only",
        "--entrypoint",
        "cat",
        image_id,
        "/usr/local/bin/run_submission.py",
    )
    local_source = (ROOT / "sandbox" / "run_submission.py").read_bytes()
    if source.replace(b"\r\n", b"\n") != local_source.replace(b"\r\n", b"\n"):
        raise ValueError("Image runner differs from sandbox/run_submission.py; rebuild it first")
    # Import only after selecting the verified image. Do not read local AI settings.
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["CODE_SANDBOX_IMAGE"] = image_id
    os.environ["SUPPORTED_LANGUAGES"] = "python,cpp"
    sys.path.insert(0, str(ROOT))
    from services.execute_runner import run_code

    examples = {
        "python": "print(sum(map(int, input().split())))",
        "cpp": '#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b<<"\\n";}',
    }
    for language, code in examples.items():
        result = run_code(code, language, "2 3\n")
        if not result.get("success") or result.get("output", "").strip() != "5":
            raise RuntimeError(f"{language} runner check failed: {result}")
        print(f"{language}: PASS")
    return {
        "image_id": image_id,
        "tag": TAG,
        "platform": f"{info['Os']}/{info['Architecture']}",
        "runner_sha256": hashlib.sha256(source).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("--image", default=TAG)
    export = commands.add_parser("export")
    export.add_argument("directory", type=Path)
    load = commands.add_parser("load")
    load.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "check":
        print(json.dumps(inspect_and_check(args.image), indent=2))
        return
    directory = args.directory.resolve()
    metadata_path = directory / "runner-image.json"
    if args.command == "export":
        metadata = inspect_and_check(TAG)
        directory.mkdir(parents=True, exist_ok=True)
        filename = "codelab-runner-" + metadata["platform"].replace("/", "-") + ".tar"
        archive = directory / filename
        if archive.exists() or metadata_path.exists():
            raise FileExistsError("Use an empty destination; existing delivery files are preserved")
        subprocess.run(["docker", "save", "--output", str(archive), TAG], check=True, timeout=300)
        metadata.update(file=filename, sha256=sha256(archive), size=archive.stat().st_size)
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print(f"Exported {filename}; SHA-256: {metadata['sha256']}")
    else:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        filename = metadata["file"]
        if Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise ValueError("Invalid image filename")
        archive = directory / filename
        if sha256(archive) != metadata["sha256"]:
            raise ValueError("Image checksum mismatch; do not load a damaged delivery")
        subprocess.run(["docker", "load", "--input", str(archive)], check=True, timeout=300)
        actual = inspect_and_check(metadata["image_id"])
        if (
            actual["platform"] != metadata["platform"]
            or actual["runner_sha256"] != metadata["runner_sha256"]
        ):
            raise ValueError("Loaded image metadata mismatch")
        subprocess.run(["docker", "tag", metadata["image_id"], TAG], check=True)
        print("Loaded and verified " + TAG + " (" + metadata["platform"] + ")")


if __name__ == "__main__":
    main()
