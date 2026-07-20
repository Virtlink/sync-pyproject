# Update pyproject.toml
Script and action to update dependencies in your `pyproject.toml` to match the version numbers from the accompanying `uv.lock` file.


## GitHub Action
The most basic usage is to check out the repository you want to modify, run `uv lock --upgrade`, and then run this action to sync the version changes to the project's `pyproject.toml`.

```yaml
- uses: actions/checkout@v6
- uses: astral-sh/setup-uv@v8.1.0
- run: uv lock --upgrade
- uses: virtlink/sync-pyproject@v1
```

If your `pyproject.toml` and `uv.lock` files live in a subdirectory, pass the optional `directory` input. If omitted, the action uses the current directory (`.`).

```yaml
- uses: virtlink/sync-pyproject@v1
  with:
    directory: packages/example
```

### Input

| Name        | Required | Default | Description                                               |
|-------------|----------|---------|-----------------------------------------------------------|
| `directory` | No       | `.`     | Directory containing both `pyproject.toml` and `uv.lock`. |

The action installs its own Python dependencies and runs on Python 3.11+.


## Technical details
This script reads the `uv.lock` file and changes the dependency versions in the `pyproject.toml` file to match. It updates:

- `project.dependencies`
- `project.optional-dependencies.<group>`

For each dependency with a simple version comparator (for example, `>=1.2.0`, `~=2.1`, `==3.0.0`), the tool preserves the existing operator (`>=`, `~=`, `==`, etc.) and replaces only the version token with the lockfile version. Extras and environment markers are preserved. For multi-specifier constraints (for example, `>=1.0,<2.0`), only the first comparator segment that includes both an operator and a version token is updated.

Dependencies without explicit version constraints, complex constraints that cannot be safely rewritten, and dependencies missing in `uv.lock` are not changed. Dependency names are matched using UV-compatible normalization, which means that matching is case-insensitive and treats `-`, `_`, and `.` equivalently for distribution names.

Formatting and comments of your `pyproject.toml` is preserved.


## Local CLI usage
To run the script and see help information:

```shell
uv run syncpyproject.py --help
```

### Prerequisites
- Python
- UV ([how to install](https://docs.astral.sh/uv/getting-started/installation/))


### Usage
1.  First, use UV to update the `uv.lock` file for your project:

    ```shell
    uv lock --upgrade --script syncpyproject.py
    ```

2.  Then, run the script. Either specify the directory where your `pyproject.toml` and `uv.lock` files live,
    or specify nothing and the script will assume the current directory.

    ```shell
    uv run syncpyproject.py 
    ```
    
By default, the script will warn when a dependency version constraint could not be updated. Use `--quiet` (`-q`) to suppress warnings and informational output, or `--verbose` (`-v`) to prints each dependency that is updated, including old and new version token.

On error, the script exits with a non-zero error code and doesn't change `pyproject.toml`.

### Run tests
 
The test suite is run through the dedicated test script, which provides its own isolated environment (including `pytest`) so that the main script does not need `pytest` installed:

```bash
uv run --locked syncpyproject_test.py
```

Arguments after the script name are forwarded to pytest, for example to run a single test or increase verbosity:

```bash
uv run syncpyproject_test.py -v
uv run syncpyproject_test.py tests/test_sync.py::SyncCommandTests
```

## Releasing

Releases are cut from `main` with the `release.py` helper and the [`Release`](.github/workflows/release.yaml) GitHub Actions workflow.

Before releasing, list every notable change since the last release under the `## [Unreleased]` heading in [`CHANGELOG.md`](CHANGELOG.md). This section is used as the body of the Git tag. Your working tree must be clean and `main` must be in sync with `origin/main`; the script enforces this and aborts otherwise.

To cut a release, run:

```bash
uv run --locked release.py v1.0.1
```

The script verifies a clean, pushed working tree, updates every `virtlink/sync-pyproject@v…` reference in `README.md` to the new version (e.g. `@v1.0.1`), rotates the changelog's `## [Unreleased]` section to `## [1.0.1] - YYYY-MM-DD` and starts a fresh `## [Unreleased]` heading, commits both changes, creates an annotated tag `v1.0.1` whose message combines `Release v1.0.1` with the unreleased changelog notes, and pushes the commit and the tag to `origin`.

Pushing the tag triggers the `Release` workflow, which re-runs the tests and yamllint, creates a GitHub Release with auto-generated notes, and moves the `v1` tag to the same commit so that both `@v1` and `@v1.0.1` resolve for consumers.

Pre-release versions such as `v1.0.1-beta.1` create a GitHub pre-release but do **not** move the `v1` tag, so `@v1` keeps pointing at the last stable release.

## License
Copyright (C) 2026 Daniel A. A. Pelsmaeker

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but **without any warranty**; without even the implied warranty of **merchantability** or **fitness for a particular purpose**.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.  If not, see <https://www.gnu.org/licenses/>.