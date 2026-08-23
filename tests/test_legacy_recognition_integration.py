import ast
from pathlib import Path
import tempfile
import unittest

from coin_collection import CoinCollection, CoinCollectionApp
from legacy_recognition_orchestration import (
    LEGACY_COIN_RECOGNITION,
    RecognitionCapabilityResult,
    RecognitionState,
)


class InjectedOrchestrator:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, image_reference):
        self.calls.append(image_reference)
        return RecognitionState(
            scan_id="scan_test",
            image_reference=image_reference,
            results=[self.result],
        )


class LegacyRecognitionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.collection = CoinCollection(
            str(Path(self.temp_directory.name) / "collection.json")
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_app_delegates_and_preserves_historical_dictionary(self):
        result = RecognitionCapabilityResult(
            capability=LEGACY_COIN_RECOGNITION,
            success=True,
            findings={"country": "Canada", "denomination": "Quarter", "year": "2023"},
            confidence=None,
            source_metadata={"denomination_confidence": 72, "year_confidence": 63},
        )
        orchestrator = InjectedOrchestrator(result)
        app = CoinCollectionApp(
            collection=self.collection,
            recognition_orchestrator=orchestrator,
        )
        app.current_image_path = "fixture.jpg"

        actual = app.run_denomination_detector()

        self.assertEqual(["fixture.jpg"], orchestrator.calls)
        self.assertEqual(
            {
                "success": True,
                "country": "Canada",
                "denomination": "Quarter",
                "year": "2023",
                "confidence": 72,
                "year_confidence": 63,
                "method": "coin_recognition",
            },
            actual,
        )
        self.assertIs(actual, app.current_detection_result)

    def test_no_image_contract_is_unchanged_and_does_not_delegate(self):
        orchestrator = InjectedOrchestrator(
            RecognitionCapabilityResult(LEGACY_COIN_RECOGNITION, False)
        )
        app = CoinCollectionApp(
            collection=self.collection,
            recognition_orchestrator=orchestrator,
        )

        self.assertEqual(
            {"success": False, "error": "No image uploaded"},
            app.run_denomination_detector(),
        )
        self.assertEqual([], orchestrator.calls)

    def test_gui_composition_uses_existing_runtime_event_bus(self):
        from coin_collection_gui import CoinCollectionGUI
        from platform_core import Platform
        from platform_integration import PlatformIntegration

        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.platform = Platform()
        gui.platform_integration = PlatformIntegration(gui.platform)
        orchestrator = gui._build_default_legacy_recognition_orchestrator()

        orchestrator.run("")

        history = gui.platform_integration.event_bus.get_history()
        self.assertEqual(
            ["recognition.started", "recognition.routed", "recognition.needs_input"],
            [entry.event.name for entry in history],
        )
        self.assertTrue(
            all(entry.event.source == "legacy_recognition_orchestrator" for entry in history)
        )

    def test_capture_import_does_not_depend_on_legacy_shell(self):
        forbidden = {
            "legacy_recognition_orchestration",
            "legacy_coin_recognition_capability",
        }
        for path in sorted(Path("capture_import").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module or "")
            with self.subTest(path=path):
                self.assertTrue(forbidden.isdisjoint(imports))

    def test_legacy_core_and_adapter_have_no_authority_dependencies(self):
        forbidden_fragments = (
            "coin_collection_gui",
            "coin_collection",
            "confirmed_observations",
            "persistence",
            "capture_import",
            "cv2",
            "pytesseract",
            "openai",
        )
        for filename in (
            "legacy_recognition_orchestration.py",
            "legacy_coin_recognition_capability.py",
        ):
            tree = ast.parse(Path(filename).read_text(encoding="utf-8"), filename=filename)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")
            with self.subTest(filename=filename):
                self.assertFalse(
                    any(fragment in name for fragment in forbidden_fragments for name in imports)
                )


if __name__ == "__main__":
    unittest.main()
