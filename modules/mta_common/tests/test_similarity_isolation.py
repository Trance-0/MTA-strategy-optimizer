"""Tests proving SimilarityReference is isolated from the core data model.

Covers both directions of isolation: no module under modules/mta_common/src/
(outside the presentation subpackage) imports SimilarityReference or the
presentation package at all, and no core, model-facing dataclass has a field
type-hinted to accept a SimilarityReference.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import re
import subprocess
import sys
import typing
import unittest
from pathlib import Path

_PRESENTATION_WORD = re.compile(r"\bpresentation\b")

from modules.mta_common.src.presentation.similarity import SimilarityReference

import modules.mta_common.src as core_package

_CORE_SRC_DIR = Path(core_package.__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _core_module_files() -> list[Path]:
    files = []
    for path in _CORE_SRC_DIR.rglob("*.py"):
        if "presentation" in path.relative_to(_CORE_SRC_DIR).parts:
            continue
        files.append(path)
    return files


def _core_module_names() -> list[str]:
    # Deliberately non-recursive (glob, not rglob): every core class lives in
    # a top-level module under src/; the only nested package is
    # presentation/, which must never be imported as a side effect of
    # importing core modules, so it is never named here.
    names = []
    for path in sorted(_CORE_SRC_DIR.glob("*.py")):
        if path.stem == "__init__":
            continue
        names.append(f"{core_package.__name__}.{path.stem}")
    return names


class NoCoreModuleImportsPresentationTests(unittest.TestCase):
    def test_no_core_source_file_references_presentation_by_name(self) -> None:
        # Word-boundary match, not plain substring: "representation" (as in
        # "independent of platform or product count") legitimately contains
        # "presentation" as a substring without referencing the package.
        for path in _core_module_files():
            source = path.read_text(encoding="utf-8")
            self.assertIsNone(
                _PRESENTATION_WORD.search(source),
                msg=f"{path} references the presentation package",
            )

    def test_no_core_source_file_parses_to_an_import_of_presentation(self) -> None:
        for path in _core_module_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    self.assertNotIn("presentation", module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn("presentation", alias.name)

    def test_importing_every_core_module_does_not_load_presentation(self) -> None:
        # Run in a fresh interpreter rather than checking sys.modules in-process:
        # by the time any test body runs, unittest discovery has already
        # imported every test_*.py file in this directory (including this one,
        # which itself imports SimilarityReference at module scope), so
        # sys.modules is polluted with "...presentation..." entries regardless
        # of what the core modules themselves do. A subprocess gives a clean
        # sys.modules that reflects only the imports below.
        script = "\n".join(
            ["import sys"]
            + [f"import {name}" for name in _core_module_names()]
            + [
                "leaked = [m for m in sys.modules "
                "if '.presentation' in m and m.startswith('modules.mta_common')]",
                "print('|'.join(leaked))",
            ]
        )
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", "-c", script],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        leaked = [name for name in result.stdout.strip().split("|") if name]
        self.assertEqual(leaked, [])


class NoCoreDataclassAcceptsSimilarityReferenceTests(unittest.TestCase):
    def test_no_core_dataclass_field_is_typed_as_similarity_reference(self) -> None:
        for name in _core_module_names():
            module = importlib.import_module(name)
            for attribute_name in dir(module):
                candidate = getattr(module, attribute_name)
                if not (isinstance(candidate, type) and dataclasses.is_dataclass(candidate)):
                    continue
                hints = typing.get_type_hints(candidate)
                for field in dataclasses.fields(candidate):
                    hint = hints.get(field.name)
                    self.assertNotEqual(
                        hint,
                        SimilarityReference,
                        msg=(
                            f"{candidate.__module__}.{candidate.__qualname__}."
                            f"{field.name} accepts SimilarityReference"
                        ),
                    )


class SimilarityReferenceValidationTests(unittest.TestCase):
    def test_valid_reference_is_constructible(self) -> None:
        reference = SimilarityReference(
            subject_type="PRODUCT",
            subject_id="SKU-001",
            comparable_id="SKU-002",
            similarity_score=0.87,
        )
        self.assertEqual(reference.subject_id, "SKU-001")

    def test_score_outside_unit_interval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SimilarityReference(
                subject_type="PRODUCT",
                subject_id="SKU-001",
                comparable_id="SKU-002",
                similarity_score=1.5,
            )

    def test_subject_cannot_be_its_own_comparable(self) -> None:
        with self.assertRaises(ValueError):
            SimilarityReference(
                subject_type="PRODUCT",
                subject_id="SKU-001",
                comparable_id="SKU-001",
                similarity_score=1.0,
            )


if __name__ == "__main__":
    unittest.main()
