"""Release policy protects app updates while leaving documentation unreleased."""

import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "check_version", Path(__file__).parent / ".github" / "scripts" / "check_version.py",
)
version_policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version_policy)


class VersionPolicyTests(unittest.TestCase):
    def check(self, current="V8.5", paths=("README.md",), readme=None):
        return version_policy.check_version(
            'APP_VERSION = "V8.5"', f'APP_VERSION = "{current}"', paths,
            readme if readme is not None else f"Current application version: **{current}**",
        )

    def test_documentation_tests_and_tooling_do_not_release(self):
        result = self.check(paths=("README.md", "AGENTS.md", "test_guardrail_ui.py", ".github/workflows/ci.yml"))
        self.assertEqual(result["changed"], "false")

    def test_patch_feature_and_major_bumps_release(self):
        for version in ("V8.5.1", "V8.6.0", "V9.0.0"):
            with self.subTest(version=version):
                result = self.check(version, ("guardrail_ui.py", "guardrail_design.py"))
                self.assertEqual(result, {"changed": "true", "version": version, "tag": version.lower()})

    def test_application_and_packaging_changes_require_bump(self):
        for path in ("guardrail_ui.py", "guardrail_alignment.py", "guardrail.spec", "requirements.txt",
                     "gr manual.pdf", "GR-4.pdf", "GR-4a.pdf"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "require an APP_VERSION bump"):
                self.check(paths=(path,))

    def test_reused_lower_and_short_new_versions_are_rejected(self):
        for version in ("V8.5.0", "V8.4.9", "V8.6"):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "Increase APP_VERSION"):
                self.check(version)

    def test_readme_must_match_version(self):
        with self.assertRaisesRegex(ValueError, "README.md"):
            self.check("V8.5.1", readme="Current application version: **V8.5**")

    def test_malformed_or_executable_versions_are_rejected(self):
        for source in ('APP_VERSION = "beta"', 'APP_VERSION = "V8.5\\nchanged=true"',
                       'APP_VERSION = str("V8.5")', 'OTHER = "V8.5"'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                version_policy.read_version(source)


if __name__ == "__main__":
    unittest.main()
