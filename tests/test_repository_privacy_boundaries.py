from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
PRIVATE_ARTIFACT_NAMES = {
    "collection_backup_before_reimport.json",
    "collection_backup_encoding.json",
    "numista_export.xlsx",
}


class RepositoryPrivacyBoundaryTests(unittest.TestCase):
    def test_uncertain_images_are_documented_as_local_only(self):
        policy = (ROOT / "test_coins" / "README.md").read_text(encoding="utf-8")

        self.assertIn("UNCERTAIN /", policy)
        self.assertIn("LOCAL-ONLY", policy)
        self.assertIn("must not be uploaded", policy)

    def test_ci_checkout_excludes_uncertain_images_and_uploads_no_artifacts(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("!/test_coins/*", workflow)
        self.assertIn("/test_coins/README.md", workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("test_coins/IMG_", workflow)

    def test_public_benchmark_manifests_do_not_reference_uncertain_images(self):
        for manifest in sorted((ROOT / "benchmarks").glob("*/manifest.json")):
            with self.subTest(manifest=manifest):
                text = manifest.read_text(encoding="utf-8")
                self.assertNotIn("test_coins/", text)
                self.assertNotIn("IMG_346", text)

    def test_known_private_exports_are_not_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()

        self.assertTrue(PRIVATE_ARTIFACT_NAMES.isdisjoint(Path(name).name for name in tracked))

    def test_known_private_exports_are_ignored_at_repository_root(self):
        rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertTrue({f"/{name}" for name in PRIVATE_ARTIFACT_NAMES}.issubset(rules))


if __name__ == "__main__":
    unittest.main()
