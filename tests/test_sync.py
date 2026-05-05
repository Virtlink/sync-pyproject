import tempfile
import textwrap
import unittest
from pathlib import Path

import tomllib
from typer.testing import CliRunner

from syncpyproject import app


class SyncCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def _write_project(self, root: Path, pyproject_text: str, uv_lock_text: str) -> None:
        (root / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")
        (root / "uv.lock").write_text(uv_lock_text, encoding="utf-8")

    def test_updates_direct_and_optional_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_project(
                root,
                textwrap.dedent(
                    """
                    [project]
                    name = "demo"
                    version = "0.1.0"
                    dependencies = [
                        "tomlkit>=0.1.0",
                        "typer>=0.2.0",
                    ]

                    [project.optional-dependencies]
                    dev = [
                        "rich>=10.0.0",
                    ]
                    """
                ).strip()
                + "\n",
                textwrap.dedent(
                    """
                    version = 1
                    revision = 3

                    [[package]]
                    name = "tomlkit"
                    version = "0.14.0"

                    [[package]]
                    name = "typer"
                    version = "0.25.1"

                    [[package]]
                    name = "rich"
                    version = "15.0.0"
                    """
                ).strip()
                + "\n",
            )

            result = self.runner.invoke(app, [str(root)])
            self.assertEqual(0, result.exit_code, msg=result.output)

            updated = (root / "pyproject.toml").read_text(encoding="utf-8")
            self.assertIn('"tomlkit>=0.14.0"', updated)
            self.assertIn('"typer>=0.25.1"', updated)
            self.assertIn('"rich>=15.0.0"', updated)

    def test_multi_specifier_updates_only_primary_comparator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_project(
                root,
                textwrap.dedent(
                    """
                    [project]
                    name = "demo"
                    version = "0.1.0"
                    dependencies = [
                        "typer>=0.2.0,<0.9.0",
                    ]
                    """
                ).strip()
                + "\n",
                textwrap.dedent(
                    """
                    version = 1
                    revision = 3

                    [[package]]
                    name = "typer"
                    version = "0.25.1"
                    """
                ).strip()
                + "\n",
            )

            result = self.runner.invoke(app, [str(root)])
            self.assertEqual(0, result.exit_code, msg=result.output)
            updated = (root / "pyproject.toml").read_text(encoding="utf-8")
            self.assertIn('"typer>=0.25.1,<0.9.0"', updated)

    def test_unconstrained_dependency_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_project(
                root,
                textwrap.dedent(
                    """
                    [project]
                    name = "demo"
                    version = "0.1.0"
                    dependencies = [
                        "typer",
                    ]
                    """
                ).strip()
                + "\n",
                textwrap.dedent(
                    """
                    version = 1
                    revision = 3

                    [[package]]
                    name = "typer"
                    version = "0.25.1"
                    """
                ).strip()
                + "\n",
            )

            result = self.runner.invoke(app, [str(root)])
            self.assertEqual(0, result.exit_code, msg=result.output)
            updated = (root / "pyproject.toml").read_text(encoding="utf-8")
            self.assertIn('"typer"', updated)

    def test_complex_constraint_emits_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_project(
                root,
                textwrap.dedent(
                    """
                    [project]
                    name = "demo"
                    version = "0.1.0"
                    dependencies = [
                        "typer @ https://example.invalid/pkg.whl",
                    ]
                    """
                ).strip()
                + "\n",
                textwrap.dedent(
                    """
                    version = 1
                    revision = 3

                    [[package]]
                    name = "typer"
                    version = "0.25.1"
                    """
                ).strip()
                + "\n",
            )

            result = self.runner.invoke(app, [str(root)])
            self.assertEqual(0, result.exit_code, msg=result.output)
            self.assertIn("warning: left unchanged complex constraint", result.output)

    def test_quiet_suppresses_warning_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_project(
                root,
                textwrap.dedent(
                    """
                    [project]
                    name = "demo"
                    version = "0.1.0"
                    dependencies = [
                        "typer @ https://example.invalid/pkg.whl",
                    ]
                    """
                ).strip()
                + "\n",
                textwrap.dedent(
                    """
                    version = 1
                    revision = 3

                    [[package]]
                    name = "typer"
                    version = "0.25.1"
                    """
                ).strip()
                + "\n",
            )

            result = self.runner.invoke(app, ["--quiet", str(root)])
            self.assertEqual(0, result.exit_code, msg=result.output)
            self.assertNotIn("warning:", result.output)
            self.assertNotIn("done:", result.output)

    def test_verbose_prints_each_updated_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_project(
                root,
                textwrap.dedent(
                    """
                    [project]
                    name = "demo"
                    version = "0.1.0"
                    dependencies = [
                        "typer>=0.1.0",
                        "tomlkit>=0.1.0",
                    ]
                    """
                ).strip()
                + "\n",
                textwrap.dedent(
                    """
                    version = 1
                    revision = 3

                    [[package]]
                    name = "typer"
                    version = "0.25.1"

                    [[package]]
                    name = "tomlkit"
                    version = "0.14.0"
                    """
                ).strip()
                + "\n",
            )

            result = self.runner.invoke(app, ["--verbose", str(root)])
            self.assertEqual(0, result.exit_code, msg=result.output)
            self.assertIn("updated: typer>=0.1.0 -> typer>=0.25.1", result.output)
            self.assertIn("updated: tomlkit>=0.1.0 -> tomlkit>=0.14.0", result.output)

    def test_preserves_extras_and_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_project(
                root,
                textwrap.dedent(
                    """
                    [project]
                    name = "demo"
                    version = "0.1.0"
                    dependencies = [
                        "typer[all]>=0.1.0 ; python_version >= '3.10'",
                    ]
                    """
                ).strip()
                + "\n",
                textwrap.dedent(
                    """
                    version = 1
                    revision = 3

                    [[package]]
                    name = "typer"
                    version = "0.25.1"
                    """
                ).strip()
                + "\n",
            )

            result = self.runner.invoke(app, [str(root)])
            self.assertEqual(0, result.exit_code, msg=result.output)

            updated = (root / "pyproject.toml").read_text(encoding="utf-8")
            self.assertIn(
                '"typer[all]>=0.25.1; python_version >= \'3.10\'"',
                updated,
            )


if __name__ == "__main__":
    unittest.main()


