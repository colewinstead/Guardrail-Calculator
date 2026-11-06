"""Require intentional application version bumps without executing application code."""

import argparse
import ast
from pathlib import Path
import re
import subprocess


def read_version(source):
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "APP_VERSION"
            for target in node.targets
        ):
            version = ast.literal_eval(node.value)
            if isinstance(version, str) and re.fullmatch(r"V\d+\.\d+(?:\.\d+)?", version):
                parts = tuple(int(part) for part in version[1:].split("."))
                return version, parts + (0,) * (3 - len(parts))
            break
    raise ValueError("APP_VERSION must be a literal VMAJOR.MINOR.PATCH version.")


def check_version(base_source, current_source, changed_paths, readme):
    previous, previous_parts = read_version(base_source)
    current, current_parts = read_version(current_source)
    changed = current != previous
    if changed and (current_parts <= previous_parts or current.count(".") != 2):
        raise ValueError("Increase APP_VERSION using VMAJOR.MINOR.PATCH; never reuse or lower a version.")
    application_changed = any(
        ("/" not in path and path.startswith("guardrail_") and path.endswith(".py"))
        or path in {"guardrail.spec", "requirements.txt", "gr manual.pdf", "GR-4.pdf", "GR-4a.pdf"}
        for path in changed_paths
    )
    if application_changed and not changed:
        raise ValueError("Application changes require an APP_VERSION bump and README version update.")
    if f"Current application version: **{current}**" not in readme:
        raise ValueError("README.md current application version must match APP_VERSION.")
    return {"changed": str(changed).lower(), "version": current, "tag": current.lower()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    base = args.base
    if set(base) == {"0"}:
        base = subprocess.check_output(["git", "merge-base", "HEAD", "origin/main"], text=True).strip()
    base_source = subprocess.check_output(["git", "show", f"{base}:guardrail_design.py"], text=True)
    changed_paths = subprocess.check_output(
        ["git", "diff", "--name-only", "-z", base, "HEAD"], text=True,
    ).split("\0")
    result = check_version(
        base_source, Path("guardrail_design.py").read_text(encoding="utf-8"),
        changed_paths, Path("README.md").read_text(encoding="utf-8"),
    )
    tag = result["tag"]
    if result["changed"] == "true":
        existing_tag = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
            capture_output=True, text=True,
        )
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if existing_tag.returncode == 0 and existing_tag.stdout.strip() != head:
            raise ValueError(f"Release tag {tag} already belongs to another commit; choose a new version.")
    with open(args.output, "a", encoding="utf-8") as output:
        for key, value in result.items():
            output.write(f"{key}={value}\n")
    print(f"Version policy passed: {result['version']}; version changed: {result['changed']}.")


if __name__ == "__main__":
    main()
