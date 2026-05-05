#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#    "tomlkit>=0.14.0",
#    "typer>=0.25.1",
# ]
# ///

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import typer
import tomlkit

app = typer.Typer(help="Sync pyproject dependency versions from uv.lock")

NAME_RE = re.compile(r"[-_.]+")
BASE_REQ_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]+\])?\s*(.*?)\s*$"
)
COMPARATOR_RE = re.compile(
    r"^(\s*)(~=|==|!=|<=|>=|<|>|===)(\s*)([^,\s]+)(\s*)$"
)


def normalize_name(name: str) -> str:
    # Match UV/PEP 503 style normalization for distribution names.
    return NAME_RE.sub("-", name).lower()


def parse_uv_lock_versions(lock_path: Path) -> dict[str, str]:
    with lock_path.open("rb") as fh:
        data = tomllib.load(fh)

    versions: dict[str, str] = {}
    for pkg in data.get("package", []):
        name = pkg.get("name")
        version = pkg.get("version")
        if isinstance(name, str) and isinstance(version, str):
            versions[normalize_name(name)] = version
    return versions


def split_marker(dep: str) -> tuple[str, str]:
    if ";" not in dep:
        return dep, ""
    base, marker = dep.split(";", 1)
    return base, ";" + marker


def update_dependency_string(dep: str, versions: dict[str, str]) -> tuple[str, str, str]:
    """
    Returns: (updated_dependency, status, package_name)
    status in {"updated", "unchanged-unconstrained", "unchanged-complex", "unchanged-no-lock"}
    """
    base, marker = split_marker(dep)
    match = BASE_REQ_RE.match(base)
    if not match:
        return dep, "unchanged-complex", dep

    raw_name, extras, specifier = match.groups()
    package_name = raw_name
    locked_version = versions.get(normalize_name(raw_name))
    if locked_version is None:
        return dep, "unchanged-no-lock", package_name

    extras = extras or ""
    specifier = specifier.strip()
    if not specifier:
        return dep, "unchanged-unconstrained", package_name

    if "@" in specifier:
        return dep, "unchanged-complex", package_name

    parts = [part.strip() for part in specifier.split(",")]
    if any(not part for part in parts):
        return dep, "unchanged-complex", package_name

    primary_index: int | None = None
    updated_parts = parts[:]

    for idx, part in enumerate(parts):
        comp = COMPARATOR_RE.match(part)
        if comp is None:
            return dep, "unchanged-complex", package_name
        if primary_index is None:
            primary_index = idx
            prefix, operator, spacing, _old_version, suffix = comp.groups()
            updated_parts[idx] = f"{prefix}{operator}{spacing}{locked_version}{suffix}"

    if primary_index is None:
        return dep, "unchanged-complex", package_name

    new_base = f"{raw_name}{extras}{','.join(updated_parts)}"
    updated = f"{new_base}{marker}"
    return updated, "updated", package_name


def update_dependency_array(
    dep_array: list,
    versions: dict[str, str],
    *,
    quiet: bool,
    verbose: bool,
) -> tuple[int, int]:
    updates = 0
    warnings = 0

    for idx, value in enumerate(dep_array):
        if not isinstance(value, str):
            continue

        updated, status, package_name = update_dependency_string(value, versions)
        if status == "updated":
            if updated != value:
                dep_array[idx] = updated
                updates += 1
                if verbose and not quiet:
                    typer.echo(f"updated: {value} -> {updated}")
        elif status == "unchanged-complex":
            warnings += 1
            if not quiet:
                typer.echo(
                    f"warning: left unchanged complex constraint for '{package_name}': {value}",
                    err=True,
                )

    return updates, warnings


@app.command()
def sync(
    directory: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress warnings and info output."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Print each dependency update."),
) -> None:
    """Sync pyproject dependency versions from uv.lock for a project directory."""
    uv_lock_path = directory / "uv.lock"
    pyproject_path = directory / "pyproject.toml"

    if not uv_lock_path.exists():
        raise typer.BadParameter(f"Missing file: {uv_lock_path}")
    if not pyproject_path.exists():
        raise typer.BadParameter(f"Missing file: {pyproject_path}")

    versions = parse_uv_lock_versions(uv_lock_path)

    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    doc = tomlkit.parse(pyproject_text)

    project = doc.get("project")
    if not isinstance(project, dict):
        raise typer.BadParameter("Missing [project] table in pyproject.toml")

    updates = 0
    warnings = 0

    dependencies = project.get("dependencies")
    if isinstance(dependencies, list):
        up, warn = update_dependency_array(
            dependencies, versions, quiet=quiet, verbose=verbose
        )
        updates += up
        warnings += warn

    optional_deps = project.get("optional-dependencies")
    if isinstance(optional_deps, dict):
        for _group_name, dep_array in optional_deps.items():
            if isinstance(dep_array, list):
                up, warn = update_dependency_array(
                    dep_array, versions, quiet=quiet, verbose=verbose
                )
                updates += up
                warnings += warn

    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    if not quiet:
        typer.echo(f"done: updated={updates}, warnings={warnings}")


if __name__ == "__main__":
    app()
