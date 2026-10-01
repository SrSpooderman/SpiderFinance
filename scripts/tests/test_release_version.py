import sys
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_version import calculate, next_tag, parse_tag  # noqa: E402


class ReleaseVersionTests(unittest.TestCase):
    def test_first_release(self) -> None:
        self.assertEqual(next_tag(None, ["feat: primera versión"]), "v0.1.0")

    def test_patch_minor_and_major(self) -> None:
        self.assertEqual(next_tag("v0.1.0", ["fix: saldo"]), "v0.1.1")
        self.assertEqual(next_tag("v0.1.1", ["feat(accounts): filtros"]), "v0.2.0")
        self.assertEqual(next_tag("v0.2.0", ["feat!: esquema nuevo"]), "v1.0.0")
        self.assertEqual(next_tag("v1.0.0", ["chore: mantenimiento\n\nBREAKING CHANGE: API nueva"]), "v2.0.0")
        self.assertEqual(next_tag("v2.0.0", ["fix: esquema\n\nBREAKING-CHANGE: API nueva"]), "v3.0.0")

    def test_tag_validation(self) -> None:
        self.assertEqual(parse_tag("v12.3.40"), (12, 3, 40))
        self.assertIsNone(parse_tag("v01.2.3"))
        self.assertIsNone(parse_tag("v1.2"))
        self.assertIsNone(parse_tag("latest"))

    def test_calculate_from_git_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            def git(*args: str) -> None:
                subprocess.run(["git", *args], cwd=directory, check=True, capture_output=True)

            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            git("commit", "--allow-empty", "-qm", "feat: inicio")
            previous = os.getcwd()
            try:
                os.chdir(directory)
                self.assertEqual(calculate(), ("v0.1.0", False))
                git("tag", "v0.1.0")
                self.assertEqual(calculate(), ("v0.1.0", True))
                git("commit", "--allow-empty", "-qm", "feat: cuentas")
                self.assertEqual(calculate(), ("v0.2.0", False))
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
