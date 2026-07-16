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

```bash
python -m unittest discover -s tests -v
```

## License
Copyright (C) 2026 Daniel A. A. Pelsmaeker

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but **without any warranty**; without even the implied warranty of **merchantability** or **fitness for a particular purpose**.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.  If not, see <https://www.gnu.org/licenses/>.