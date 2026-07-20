#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#    "typer>=0.25.1",
#    "pytest>=8.0.0",
# ]
# ///
"""Create a release for this action.

Bumps the version references in README.md to the given (full) version,
rotates the changelog's [Unreleased] section to the new version (and starts a
fresh [Unreleased] section), commits both changes, creates an annotated tag whose
message combines "Release <version>" with the unreleased changelog notes, and
pushes the commit and the tag to the remote.

Usage:

    uv run --locked release.py v1.0.1

The working tree must be clean and the current branch must be up to date
with its remote before the script will run.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import NoReturn

import pytest
import typer
from typer.testing import CliRunner

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


def fail(message: str, code: int = 1) -> NoReturn:
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
    res = git(
        "rev-parse", "-q", "--verify", f"refs/tags/{tag}", capture=True, check=False
    )
    return res.returncode == 0


def update_readme(version: str) -> tuple[int, bool]:
    """Rewrite action refs in README.md to the given version. Returns (count, changed)."""
    text = README_PATH.read_text(encoding="utf-8")
    new_text, count = ACTION_REF_RE.subn(lambda m: f"{REPOSITORY}@{version}", text)
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


def rotate_changelog(tag: str) -> bool:
    """Rename the [Unreleased] section to [version] and start a fresh, empty
    [Unreleased] heading above it. Returns True if the file was modified.

    Before:
        ## [Unreleased]
        ### Added
        - New thing.

    After:
        ## [Unreleased]

        ## [1.0.1] - 2026-07-20
        ### Added
        - New thing.
    """
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    match = re.search(r"^## \[Unreleased\][ \t]*$", text, re.MULTILINE)
    if not match:
        fail(f"no '## [Unreleased]' section found in {CHANGELOG_PATH.name}.")
    bare_version = tag.lstrip("v")
    today = date.today().isoformat()
    new_heading = f"## [Unreleased]\n\n## [{bare_version}] - {today}"
    new_text = text[: match.start()] + new_heading + text[match.end() :]
    changed = new_text != text
    if changed:
        CHANGELOG_PATH.write_text(new_text, encoding="utf-8")
    return changed


@app.command()
def release(
    version: str = typer.Argument(..., help="The version to release, e.g. 'v1.0.1'."),
) -> None:
    """Bump the README version, rotate the changelog, create an annotated tag, and push both."""
    tag, major_tag, is_prerelease = parse_version(version)
    typer.echo(f"Releasing {tag}...")

    check_clean_state()

    if tag_exists(tag):
        fail(f"tag {tag} already exists.")

    # Capture the unreleased notes before rotating the changelog, so they can
    # be used as the body of the annotated tag.
    body = extract_changelog_unreleased()

    count, readme_changed = update_readme(tag)
    if readme_changed:
        typer.echo(f"Updated {count} version reference(s) in README.md.")

    changelog_changed = rotate_changelog(tag)
    if changelog_changed:
        typer.echo(f"Rotated changelog: [Unreleased] -> [{tag.lstrip('v')}].")

    if readme_changed or changelog_changed:
        git("add", str(README_PATH), str(CHANGELOG_PATH))
        git("commit", "-m", f"Release {tag}")
    else:
        typer.echo(
            "README.md and CHANGELOG.md are already up to date; "
            "tagging the current commit."
        )

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# A fixed repository identifier used by the tests, independent of the real
# ``REPOSITORY`` constant so the suite stays portable across repos.
_TEST_REPOSITORY = "example/release-action"


def _init_git_repo(work: Path, remote: Path) -> None:
    """Create a git repository at ``work`` with an initial commit and a bare
    ``origin`` remote, so branch-tracking checks can be exercised."""
    subprocess.run(
        ["git", "init", "-b", "main", str(work)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(work), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "config", "commit.gpgsign", "false"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "config", "tag.gpgsign", "false"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    (work / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(work), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(work), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "remote", "add", "origin", str(remote)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "push", "-u", "origin", "main"],
        check=True,
        capture_output=True,
    )


def _patch_paths(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Point the module's README/CHANGELOG/repository globals at ``root``."""
    mod = sys.modules[__name__]
    monkeypatch.setattr(mod, "REPOSITORY", _TEST_REPOSITORY)
    monkeypatch.setattr(
        mod, "ACTION_REF_RE", re.compile(rf"{_TEST_REPOSITORY}@v[0-9A-Za-z._+-]*")
    )
    monkeypatch.setattr(mod, "README_PATH", root / "README.md")
    monkeypatch.setattr(mod, "CHANGELOG_PATH", root / "CHANGELOG.md")


# --- parse_version --------------------------------------------------------


def test_parse_version_strips_leading_v() -> None:
    # Arrange
    raw = "v1.2.3"

    # Act
    tag, major_tag, is_prerelease = parse_version(raw)

    # Assert
    assert tag == "v1.2.3"
    assert major_tag == "v1"
    assert is_prerelease is False


def test_parse_version_accepts_no_leading_v() -> None:
    # Arrange
    raw = "1.2.3"

    # Act
    tag, major_tag, is_prerelease = parse_version(raw)

    # Assert
    assert tag == "v1.2.3"
    assert major_tag == "v1"
    assert is_prerelease is False


def test_parse_version_flags_prerelease() -> None:
    # Arrange
    raw = "v1.0.0-beta.1"

    # Act
    tag, major_tag, is_prerelease = parse_version(raw)

    # Assert
    assert tag == "v1.0.0-beta.1"
    assert major_tag == "v1"
    assert is_prerelease is True


def test_parse_version_preserves_build_metadata() -> None:
    # Arrange
    raw = "v1.0.0+build.7"

    # Act
    tag, major_tag, is_prerelease = parse_version(raw)

    # Assert
    assert tag == "v1.0.0+build.7"
    assert major_tag == "v1"
    assert is_prerelease is False


def test_parse_version_rejects_short_version() -> None:
    # Arrange
    raw = "v1.0"

    # Act
    with pytest.raises(typer.Exit):
        parse_version(raw)

    # Assert -- an invalid version aborts with typer.Exit.


def test_parse_version_rejects_garbage() -> None:
    # Arrange
    raw = "not-a-version"

    # Act
    with pytest.raises(typer.Exit):
        parse_version(raw)

    # Assert -- an invalid version aborts with typer.Exit.


# --- update_readme --------------------------------------------------------


def test_update_readme_rewrites_action_refs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "README.md").write_text(
        f"uses {_TEST_REPOSITORY}@v1.0.0 here\n", encoding="utf-8"
    )

    # Act
    count, changed = update_readme("v1.2.3")

    # Assert
    assert changed is True
    assert count == 1
    assert (tmp_path / "README.md").read_text(
        encoding="utf-8"
    ) == f"uses {_TEST_REPOSITORY}@v1.2.3 here\n"


def test_update_readme_reports_unchanged_when_already_at_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "README.md").write_text(
        f"uses {_TEST_REPOSITORY}@v1.2.3 here\n", encoding="utf-8"
    )

    # Act
    count, changed = update_readme("v1.2.3")

    # Assert
    assert changed is False
    assert count == 1


def test_update_readme_fails_when_no_refs_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "README.md").write_text("no action refs here\n", encoding="utf-8")

    # Act
    with pytest.raises(typer.Exit):
        update_readme("v1.2.3")

    # Assert -- missing references abort with typer.Exit.


# --- extract_changelog_unreleased -----------------------------------------


def test_extract_changelog_unreleased_returns_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n### Added\n- New thing.\n\n## [1.0.0] - 2026-01-01\n### Fixed\n- Old.\n",
        encoding="utf-8",
    )

    # Act
    body = extract_changelog_unreleased()

    # Assert
    assert body == "### Added\n- New thing."


def test_extract_changelog_unreleased_fails_without_section(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - 2026-01-01\n", encoding="utf-8"
    )

    # Act
    with pytest.raises(typer.Exit):
        extract_changelog_unreleased()

    # Assert -- a missing [Unreleased] section aborts with typer.Exit.


# --- rotate_changelog -----------------------------------------------------


def test_rotate_changelog_renames_unreleased_section(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n### Added\n- New thing.\n", encoding="utf-8"
    )
    today = date.today().isoformat()

    # Act
    changed = rotate_changelog("v1.2.3")

    # Assert
    assert changed is True
    result = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [Unreleased]\n\n## [1.2.3] - {today}\n" in result
    assert "### Added\n- New thing." in result


def test_rotate_changelog_fails_without_unreleased(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - 2026-01-01\n", encoding="utf-8"
    )

    # Act
    with pytest.raises(typer.Exit):
        rotate_changelog("v1.2.3")

    # Assert -- a missing [Unreleased] section aborts with typer.Exit.


# --- tag_exists -----------------------------------------------------------


def test_tag_exists_true_for_existing_tag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    work = tmp_path / "work"
    _init_git_repo(work, tmp_path / "remote.git")
    subprocess.run(
        ["git", "-C", str(work), "tag", "v1.0.0"], check=True, capture_output=True
    )
    monkeypatch.chdir(work)

    # Act
    exists = tag_exists("v1.0.0")

    # Assert
    assert exists is True


def test_tag_exists_false_for_missing_tag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    work = tmp_path / "work"
    _init_git_repo(work, tmp_path / "remote.git")
    monkeypatch.chdir(work)

    # Act
    exists = tag_exists("v9.9.9")

    # Assert
    assert exists is False


# --- check_clean_state ----------------------------------------------------


def test_check_clean_state_passes_when_clean_and_in_sync(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    work = tmp_path / "work"
    _init_git_repo(work, tmp_path / "remote.git")
    monkeypatch.chdir(work)

    # Act
    result = check_clean_state()

    # Assert
    assert result is None


def test_check_clean_state_fails_when_dirty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    work = tmp_path / "work"
    _init_git_repo(work, tmp_path / "remote.git")
    (work / "README.md").write_text("dirty\n", encoding="utf-8")
    monkeypatch.chdir(work)

    # Act
    with pytest.raises(typer.Exit):
        check_clean_state()

    # Assert -- a dirty working tree aborts with typer.Exit.


def test_check_clean_state_fails_when_ahead_of_remote(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    work = tmp_path / "work"
    _init_git_repo(work, tmp_path / "remote.git")
    (work / "README.md").write_text("more\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(work), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(work), "commit", "-m", "ahead"],
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(work)

    # Act
    with pytest.raises(typer.Exit):
        check_clean_state()

    # Assert -- unpushed commits abort with typer.Exit.


# --- release command (end to end) ----------------------------------------


def test_release_command_updates_files_commits_tags_and_pushes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    work = tmp_path / "work"
    remote = tmp_path / "remote.git"
    _init_git_repo(work, remote)
    (work / "README.md").write_text(
        f"uses {_TEST_REPOSITORY}@v1.0.0\n", encoding="utf-8"
    )
    (work / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n### Added\n- New.\n", encoding="utf-8"
    )
    subprocess.run(
        ["git", "-C", str(work), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(work), "commit", "-m", "setup"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(work), "push"], check=True, capture_output=True)
    monkeypatch.chdir(work)
    _patch_paths(monkeypatch, work)
    runner = CliRunner()

    # Act
    result = runner.invoke(app, ["v1.2.3"])

    # Assert
    assert result.exit_code == 0, result.output
    assert (work / "README.md").read_text(
        encoding="utf-8"
    ) == f"uses {_TEST_REPOSITORY}@v1.2.3\n"
    changelog = (work / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]\n\n## [1.2.3] -" in changelog
    assert "### Added\n- New." in changelog
    tags = subprocess.run(
        ["git", "-C", str(remote), "tag", "-l"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert "v1.2.3" in tags


if __name__ == "__main__":
    app()
