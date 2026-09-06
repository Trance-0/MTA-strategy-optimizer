"""Verify compact-spec routing and coverage defects using isolated documentation trees."""

from pathlib import Path
import tempfile
import unittest

from script.spec_docs import check, records, search


class SpecDocsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = []

    def put(self, name, text):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.files.append(name)

    def page(self, name="docs/en/history.md", source="backend/history.py"):
        self.put(name, f'''---
title: History
compact: "Windowed history resources."
source_files: {source}
test_files: backend/tests/test_history.py
---
# History
## Source Files
### History loader
Source: `{source}`

Inputs and outputs are windowed history.
## Verification
- **Scope:** History range.
- **Cases:** Empty and bounded.
- **Command:** python -m unittest
- **Limitations:** No database.
''')

    def test_valid_coverage_and_compact_only_retrieval(self):
        self.page()
        self.put("backend/history.py", "")
        self.put("backend/tests/test_history.py", "")
        self.assertEqual(check(self.root, self.files)["errors"], [])
        item = records(self.root, self.files)[0]
        self.assertEqual(set(item), {"path", "title", "compact", "source_files", "test_files"})
        self.assertEqual(search([item], "backend/history.py"), [item])
        self.assertEqual(search([item], "unrelated"), [])

    def test_missing_duplicate_stale_and_body_ownership_are_reported(self):
        self.page()
        self.page("docs/en/duplicate.md")
        self.put("backend/missing.py", "")
        errors = "\n".join(check(self.root, self.files)["errors"])
        self.assertIn("2 source_files owners", errors)
        self.assertIn("2 test_files owners", errors)
        self.assertIn("backend/missing.py: 0 source_files owners", errors)
        self.assertIn("invalid or missing", errors)

    def test_bad_structure_cannot_pass_a_file_mention(self):
        self.put("docs/en/bad.md", "---\ncompact: >\nsource_files: backend/a.py\ntest_files: backend/tests/test_a.py\n---\nSource: `backend/a.py`\n<<<<<<< ours\n" + "line\n" * 500)
        errors = "\n".join(check(self.root, self.files)["errors"])
        for phrase in ["compact", "500 lines", "merge marker", "Source Files section", "Verification section"]:
            self.assertIn(phrase, errors)

    def test_reference_notes_are_opt_in_and_ties_are_deterministic(self):
        self.put("docs/en/reference.md", '---\ntitle: History\ncompact: "History source note"\ndocument_role: reference\n---\n')
        self.page()
        self.assertEqual(len(records(self.root, self.files)), 1)
        items = records(self.root, self.files, True)
        self.assertEqual(len(items), 2)
        self.assertEqual(search(items, "history", 1)[0]["path"], "docs/en/history.md")
        self.assertEqual(search(items, "backend\\history.py", 1)[0]["path"], "docs/en/history.md")

    def test_contributor_scope_does_not_impose_new_metadata_on_excluded_work(self):
        self.page()
        self.put("backend/history.py", "")
        self.put("backend/tests/test_history.py", "")
        for name in ("docs/en/strategy-evaluation/index.md", "docs/worklog/YayuYu.md",
                     "dashboard/src/views/KnowledgeBase.vue",
                     "dashboard/tests/willow_gmv_model.test.js"):
            self.put(name, "outside this adoption\n")
        result = check(self.root, self.files)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["scope"]["name"], "Trance-0")
        self.assertEqual(len(records(self.root, self.files)), 1)
        self.put("dashboard/src/NewView.vue", "")
        self.assertTrue(any("NewView.vue: 0 source_files owners" in error
                            for error in check(self.root, self.files)["errors"]))


if __name__ == "__main__":
    unittest.main()
