# Update pyproject.toml
Updates dependencies in your `pyproject.toml` to match the version numbers from the accompanying `uv.lock` file.

## Prerequisites
- Python
- UV ([how to install](https://docs.astral.sh/uv/getting-started/installation/))


## Running
To run the script and see help information:

```shell
uv run syncpyproject.py --help
```


## Usage
1.  First, use UV to update the `uv.lock` file for your project:

    ```shell
    uv lock --upgrade
    ```

2.  Then, run the script. Either specify the directory where your `pyproject.toml` and `uv.lock` files live,
    or specify nothing and the script will assume the current directory.

    ```shell
    uv run syncpyproject.py 
    ```
    
By default, the script will warn when a dependency version constraint could not be updated. Use `--quiet` (`-q`) to suppress warnings and informational output, or `--verbose` (`-v`) to prints each dependency that is updated, including old and new version token.

On error, the script exits with a non-zero error code and doesn't change `pyproject.toml`.


## Technical details
This script reads the `uv.lock` file and changes the dependency versions in the `pyproject.toml` file to match. It updates:

- `project.dependencies`
- `project.optional-dependencies.<group>`

For each dependency with a simple version comparator (for example, `>=1.2.0`, `~=2.1`, `==3.0.0`), the tool preserves the existing operator (`>=`, `~=`, `==`, etc.) and replaces only the version token with the lockfile version. Extras and environment markers are preserved. For multi-specifier constraints (for example, `>=1.0,<2.0`), only the first comparator segment that includes both an operator and a version token is updated.

Dependencies without explicit version constraints, complex constraints that cannot be safely rewritten, and dependencies missing in `uv.lock` are not changed. Dependency names are matched using UV-compatible normalization, which means that matching is case-insensitive and treats `-`, `_`, and `.` equivalently for distribution names.

Formatting and comments of your `pyproject.toml` is preserved.

## Run tests

```bash
python -m unittest discover -s tests -v
```

