#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#    "typer>=0.25.1",
# ]
# ///
"""Create a release for this action.

Bumps the version references in README.md to the given (full) version,
commits the change, creates an annotated tag whose message combines
"Release <version>" with the relevant section of the changelog, and pushes
both the commit and the tag to the remote.

Usage:

    uv run --locked release.py v1.0.1

The working tree must be clean and the current branch must be up to date
with its remote before the script will run.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import typer

HERE = Path(__file__).resolve().parent
README_PATH = HERE / "README.md"
CHANGELOG_PATH = HERE / "CHANGELOG.md"

REPOSITORY = "virtlink/sync-pyproject"

# Semver with an optional leading "v". Captures major/minor/patch, an optional
# pre-release identifier, and optional build metadata.
VERSION_RE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z._+]+))?(?:\+([0-9A-Za-z._+]+))?$"
)
# Matches the action ref `{REPOSITORY}@v<version>` (any version token).
ACTION_REF_RE = re.compile(rf"{REPOSITORY}@v[0-9A-Za-z._+-]*")

app = typer.Typer(help="Create a release for this action.")


def git(
    *args: str,
    capture: bool = False,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a git command, exiting cleanly on failure when ``check`` is set."""
    result = subprocess.run(
        ["git", *args],
        capture_output=capture,
        text=True,
        input=input_text,
        check=False,
    )
    if check and result.returncode != 0:
        if capture and result.stderr.strip():
            typer.echo(result.stderr.strip(), err=True)
        typer.echo(
            f"error: `git {' '.join(args)}` failed with exit code {result.returncode}.",
            err=True,
        )
        raise typer.Exit(code=1)
    return result


def fail(message: str, code: int = 1) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code=code)


def parse_version(raw: str) -> tuple[str, str, bool]:
    """Return ``(tag, major_tag, is_prerelease)`` for a version like ``v1.0.1``."""
    match = VERSION_RE.match(raw.strip())
    if not match:
        fail(f"invalid version number: {raw!r}. Expected something like 'v1.0.1'.")
    major, minor, patch, pre, build = match.groups()
    tag = f"v{major}.{minor}.{patch}"
    if pre:
        tag += f"-{pre}"
    if build:
        tag += f"+{build}"
    return tag, f"v{major}", pre is not None


def check_clean_state() -> None:
    """Abort if the working tree is dirty or the branch is out of sync."""
    status = git("status", "--porcelain", capture=True)
    if status.stdout.strip():
        fail("working tree has uncommitted changes. Commit or stash them first.")

    ahead = git("rev-list", "--count", "@{u}..HEAD", capture=True, check=False)
    if ahead.returncode != 0:
        fail("no upstream tracking branch is configured for the current branch.")
    if int(ahead.stdout.strip() or "0") > 0:
        fail("there are unpushed commits on the current branch. Push them first.")

    behind = git("rev-list", "--count", "HEAD..@{u}", capture=True, check=False)
    if behind.returncode == 0 and int(behind.stdout.strip() or "0") > 0:
        fail("the remote is ahead of the local branch. Pull first.")


def tag_exists(tag: str) -> bool:
    res = git("rev-parse", "-q", "--verify", f"refs/tags/{tag}", capture=True, check=False)
    return res.returncode == 0


def update_readme(version: str) -> tuple[int, bool]:
    """Rewrite action refs in README.md to the given version. Returns (count, changed)."""
    text = README_PATH.read_text(encoding="utf-8")
    new_text, count = ACTION_REF_RE.subn(
        lambda m: f"{REPOSITORY}@{version}", text
    )
    if count == 0:
        fail(f"no '{REPOSITORY}@v...' references found in {README_PATH.name}.")
    changed = new_text != text
    if changed:
        README_PATH.write_text(new_text, encoding="utf-8")
    return count, changed


def extract_changelog_unreleased() -> str:
    """Return the body of the '## [Unreleased]' section of the changelog."""
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## [Unreleased]":
            start = i + 1
            break
    if start is None:
        fail(f"no '## [Unreleased]' section found in {CHANGELOG_PATH.name}.")

    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body).strip()


@app.command()
def release(
    version: str = typer.Argument(..., help="The version to release, e.g. 'v1.0.1'."),
) -> None:
    """Bump the README version, create an annotated tag, and push both."""
    tag, major_tag, is_prerelease = parse_version(version)
    typer.echo(f"Releasing {tag}...")

    check_clean_state()

    if tag_exists(tag):
        fail(f"tag {tag} already exists.")

    count, changed = update_readme(tag)
    if changed:
        typer.echo(f"Updated {count} version reference(s) in README.md.")
        git("add", str(README_PATH))
        git("commit", "-m", f"Release {tag}")
    else:
        typer.echo(
            "README.md already references this version; tagging the current commit."
        )

    body = extract_changelog_unreleased()
    message = f"Release {tag}"
    if body:
        message += f"\n\n{body}"

    git("tag", "-a", tag, "-F", "-", input_text=message)

    typer.echo(f"Pushing commit and tag {tag}...")
    try:
        git("push")
        git("push", "origin", tag)
    except typer.Exit:
        typer.echo(
            f"Push failed. The commit and tag {tag} are local. Re-run:\n"
            f"  git push\n  git push origin {tag}",
            err=True,
        )
        raise

    if is_prerelease:
        typer.echo(
            f"Done. Tag {tag} pushed (pre-release). The release workflow will "
            f"create a pre-release GitHub Release; the {major_tag} tag is not moved."
        )
    else:
        typer.echo(
            f"Done. Tag {tag} pushed. The release workflow will create the GitHub "
            f"Release and update the {major_tag} tag."
        )


if __name__ == "__main__":
    app()
