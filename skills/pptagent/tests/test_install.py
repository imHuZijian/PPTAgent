"""Registration must be discoverable without exposing nested dependency skills."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="pptagent-install-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()

    def install(self, client: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/install.py"),
                "--client",
                client,
                "--home",
                str(self.directory),
                "--skip-runtime",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_opencode_registration_is_repeatable_and_excludes_dependencies(
        self,
    ) -> None:
        for _ in range(2):
            result = self.install("opencode")
            self.assertEqual(result.returncode, 0, result.stderr)
        target = self.directory / ".config/opencode/skills/pptagent"
        self.assertFalse(target.is_symlink())
        self.assertEqual(list(target.rglob("SKILL.md")), [target / "SKILL.md"])
        self.assertIn(str(ROOT / "SKILL.md"), (target / "SKILL.md").read_text())
        self.assertIn(sys.executable, (target / "SKILL.md").read_text())

    def test_does_not_overwrite_an_existing_skill(self) -> None:
        target = self.directory / ".config/opencode/skills/pptagent"
        target.mkdir(parents=True)
        source = target / "SKILL.md"
        source.write_text("user-owned skill")
        self.assertEqual(self.install("opencode").returncode, 2)
        self.assertEqual(source.read_text(), "user-owned skill")

    def test_existing_clients_keep_their_registration_paths(self) -> None:
        for client, folder in (("claude", ".claude"), ("codex", ".agents")):
            self.assertEqual(self.install(client).returncode, 0)
            self.assertEqual(
                (self.directory / folder / "skills/pptagent").resolve(), ROOT
            )


if __name__ == "__main__":
    unittest.main()
