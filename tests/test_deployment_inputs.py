"""Verify deployment preflight refuses partial, dirty, and mismatched generator checkouts."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from script.check_deployment_inputs import REQUIRED, SUBMODULE, validate


class DeploymentInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / SUBMODULE
        for name in REQUIRED:
            path = self.checkout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}" if name.endswith(".json") else "", encoding="utf-8")

    def verify(self, actual="abc", dirty=""):
        with patch("script.check_deployment_inputs.subprocess.check_output", side_effect=[
            f"160000 commit abc\t{SUBMODULE}\n", actual + "\n", dirty
        ]):
            return validate(self.root)

    def test_complete_pinned_inputs_pass(self):
        self.assertEqual(self.verify(), [])

    def test_stale_directories_and_missing_config_fail(self):
        for name in REQUIRED:
            (self.checkout / name).unlink()
        self.assertEqual(sum("Missing generator input" in e for e in self.verify()), len(REQUIRED))

    def test_malformed_present_configuration_fails(self):
        (self.checkout / REQUIRED[-1]).write_text("{broken", encoding="utf-8")
        self.assertTrue(any("Invalid toy" in e for e in self.verify()))

    def test_wrong_revision_and_dirty_sources_fail(self):
        self.assertTrue(any("Git link" in e for e in self.verify("different")))
        self.assertTrue(any("modified tracked" in e for e in self.verify(dirty=" M configuration.py")))

    def snapshot(self, pin="abc", parent="160000 commit abc", dirty=""):
        with patch("script.check_deployment_inputs.subprocess.check_output", side_effect=[
            f"040000 tree def\t{SUBMODULE}\n", f"{parent}\t{SUBMODULE}\n",
            f"snapshot: materialize submodules\n\nPinned submodule commits:\n  {SUBMODULE} {pin}\n",
            "\n".join(REQUIRED), dirty,
        ]):
            return validate(self.root)

    def test_materialized_snapshot_requires_parent_pin_and_clean_inputs(self):
        self.assertEqual(self.snapshot(), [])
        self.assertTrue(any("recorded Git pin" in e for e in self.snapshot(pin="different")))
        self.assertTrue(any("recorded Git pin" in e for e in self.snapshot(parent="040000 tree def")))
        self.assertTrue(any("modified tracked" in e for e in self.snapshot(dirty=" M configuration.py")))


if __name__ == "__main__":
    unittest.main()
