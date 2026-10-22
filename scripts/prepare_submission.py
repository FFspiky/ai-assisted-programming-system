"""Assemble an uncompressed code delivery directory from the working tree."""

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .reviewer_config import read_reviewer_key
except ImportError:
    from reviewer_config import read_reviewer_key

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".env.example",
    ".gitignore",
    ".gitattributes",
    "README.md",
    "CHANGELOG.md",
    "app.py",
    "models.py",
    "config.py",
    "requirements.txt",
    "requirements-dev.txt",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "Makefile",
    "setup-windows.cmd",
    "setup-macos.command",
    "start-windows.cmd",
    "start-macos.command",
}
DIRECTORIES = {
    ".github",
    "data",
    "migrations",
    "modules",
    "routes",
    "sandbox",
    "scripts",
    "services",
    "static",
    "templates",
    "tests",
}
DOCUMENTS = {
    "AI_PROMPTS.md",
    "CODE_DELIVERY.md",
    "COMPETITION_PREVIEW.md",
    "CO_CREATE.md",
    "CO_CREATE_LEARNING.md",
    "DEPLOYMENT.md",
    "EVIDENCE_DEMO.md",
    "LANGUAGES.md",
    "LEARNING_PLAN.md",
    "PROBLEM_LIBRARY.md",
    "TASK_ROOM.md",
    "SUBMISSION_START.md",
}


def source_files():
    listing = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    for name in sorted(set(listing.decode("utf-8").split("\0")) - {""}):
        relative = Path(name)
        if not (
            name in ROOT_FILES
            or relative.parts[0] in DIRECTORIES
            or (relative.parts[0] == "docs" and relative.name in DOCUMENTS)
            or (
                relative.parts[:2] == ("docs", "images")
                and relative.name in {"home.png", "library.png", "practice.png", "task-room.png"}
            )
        ):
            continue
        source = ROOT / relative
        if not source.exists():
            continue  # A tracked file deleted in the current working tree.
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError(f"Refusing linked/outside file: {relative}")
        if relative.suffix.lower() in {
            ".db",
            ".sqlite",
            ".sqlite3",
            ".key",
            ".pem",
            ".pyc",
            ".log",
        }:
            raise ValueError(f"Unexpected local data in source list: {relative}")
        if relative.name.startswith(".env") and name != ".env.example":
            raise ValueError(f"Unexpected environment file: {relative}")
        yield relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--reviewer-key-file",
        type=Path,
        help="Explicit private reviewer JSON; copied only into runtime/",
    )
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.exists() or destination.is_relative_to(ROOT):
        parser.error("Use a new directory outside the source repository")
    files = list(source_files())
    if args.reviewer_key_file:
        read_reviewer_key(args.reviewer_key_file)
    destination.mkdir(parents=True)
    code = destination / "CodeLab"
    for relative in files:
        target = code / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    subprocess.run(
        [
            sys.executable,
            "-B",
            str(code / "scripts/runner_image.py"),
            "export",
            str(destination / "runtime"),
        ],
        check=True,
    )
    if args.reviewer_key_file:
        target = destination / "runtime/reviewer-key.json"
        shutil.copyfile(args.reviewer_key_file, target)
        if sys.platform != "win32":
            target.chmod(0o600)
    guide = (ROOT / "docs/SUBMISSION_START.md").read_text(encoding="utf-8")
    guide = guide.replace("](CODE_DELIVERY.md)", "](CodeLab/docs/CODE_DELIVERY.md)")
    guide = guide.replace("](COMPETITION_PREVIEW.md)", "](CodeLab/docs/COMPETITION_PREVIEW.md)")
    guide = guide.replace("](../static/", "](CodeLab/static/")
    (destination / "开始使用.md").write_text(guide, encoding="utf-8")
    checksums = []
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            checksums.append(f"{digest}  {path.relative_to(destination).as_posix()}")
    (destination / "文件清单.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(f"Prepared {len(files)} source files: {destination}")


if __name__ == "__main__":
    main()
