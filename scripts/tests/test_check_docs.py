"""Checker regression tests use disposable synthetic documents, never paper data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("check_docs", Path(__file__).parents[1] / "check_docs.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

class MarkdownChecks(unittest.TestCase):
    def check(self, files):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, body in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
            return checker.check_markdown(root, [root / n for n in files if n.endswith(".md")])[0]

    def test_duplicate_and_unicode_anchors(self):
        self.assertEqual([], self.check({"a.md": "# 中文 标题\n# 中文 标题\n[ok](#中文-标题-1)\n[space](<my file.md#hello>)", "my file.md": "# Hello"}))

    def test_broken_link_and_anchor(self):
        errors = self.check({"a.md": "# A\n[x](missing.md)\n[y](#missing)"})
        self.assertEqual(2, len(errors))

    def test_invalid_json_and_unclosed_fence(self):
        self.assertTrue(self.check({"a.md": '```json\n{"a": }\n```'}))
        self.assertTrue(self.check({"a.md": '```json\n{}'}))

    def test_duplicate_keys_and_nan_rejected(self):
        for value in ['{"a":1,"a":2}', '{"a":NaN}']:
            self.assertTrue(self.check({"a.md": "```json\n" + value + "\n```"}))

    def test_fenced_fake_link_ignored(self):
        self.assertEqual([], self.check({"a.md": "```text\n[not a link](missing.md)\n```"}))

class ContractChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parents[2]
        cls.docs = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in root.glob("docs/*.md")}

    def mutate(self, name, old, new):
        docs = self.docs.copy()
        self.assertIn(old, docs[name])
        docs[name] = docs[name].replace(old, new)
        return checker.check_contracts(docs)[0]

    def test_current_contract(self):
        self.assertEqual([], checker.check_contracts(self.docs)[0])

    def test_budget_drift(self):
        self.assertTrue(self.mutate("docs/glossary.md", '"main_requests": 3', '"main_requests": 4'))

    def test_missing_packet_field(self):
        self.assertTrue(self.mutate("docs/glossary.md", '"accounting": {', '"wrong_accounting": {'))

    def test_cancelled_with_decision(self):
        self.assertTrue(self.mutate("docs/architecture.md", '"decision": null, "error_code": null}', '"decision": {}, "error_code": null}'))

    def test_unregistered_error_code(self):
        docs = self.docs.copy()
        docs["docs/architecture.md"] += "\nUPSTREAM_NEW_FAILURE\n"
        self.assertTrue(checker.check_contracts(docs)[0])

    def test_version_drift(self):
        self.assertTrue(self.mutate("docs/prd.md", "版本：0.6", "版本：0.5"))

    def test_field_table_drift(self):
        self.assertTrue(self.mutate("docs/glossary.md", "| `accounting` |", "| `wrong_accounting` |"))

    def test_missing_evidence_field(self):
        self.assertTrue(self.mutate("docs/glossary.md", '"quote": "<redacted>"', '"wrong_quote": "<redacted>"'))

    def test_attempt_accounting_drift(self):
        self.assertTrue(self.mutate("docs/glossary.md", '"observed_upstream_attempts": 2', '"observed_upstream_attempts": 1'))

if __name__ == "__main__":
    unittest.main()
