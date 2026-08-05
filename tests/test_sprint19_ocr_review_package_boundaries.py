"""Sprint 19 OCR review package-boundary enforcement tests.

This suite enforces the frozen boundary policy using AST-only import analysis.
It never imports production modules.
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_POLICY_PATH = _REPO_ROOT / "docs" / "SPRINT_19_PACKAGE_BOUNDARY_ENFORCEMENT_POLICY.md"

_LAYER_A_MODULES = frozenset(
    {
        "capture_import.workflow_ocr_models",
        "capture_import.workflow_ocr_review_models",
        "capture_import.workflow_ocr_review_service",
        "capture_import.workflow_ocr_review_session",
        "capture_import.workflow_ocr_review_presenter",
        "capture_import.workflow_ocr_review_controller",
    }
)
_LAYER_B_MODULES = frozenset(
    {
        "capture_import.workflow_ocr_review_persistence_models",
        "capture_import.workflow_ocr_review_persistence_service",
        "capture_import.workflow_ocr_review_local_repository",
    }
)
_LAYER_C_MODULES = frozenset(
    {
        "capture_import.desktop_ocr_review_composition",
        "capture_import.desktop_ocr_review_handoff",
        "capture_import.desktop_ocr_candidate_review",
        "capture_import.desktop_ocr_conflict_review",
        "capture_import.desktop_ocr_review_persistence",
        "capture_import.desktop_ocr_review_persistence_controls",
    }
)

_ENFORCED_SCOPE_BY_LAYER = {
    "Layer A": _LAYER_A_MODULES,
    "Layer B": _LAYER_B_MODULES,
    "Layer C": _LAYER_C_MODULES,
}

_ENFORCED_MODULES = frozenset().union(*_ENFORCED_SCOPE_BY_LAYER.values())

_IMPORT_ALLOWLISTS = {
    "capture_import.workflow_ocr_models": {
        "stdlib": {
            "__future__",
            "dataclasses",
            "enum",
            "math",
            "typing",
            "unicodedata",
        },
        "third_party": set(),
        "project": {"capture_import.workflow_models"},
    },
    "capture_import.workflow_ocr_review_models": {
        "stdlib": {"__future__", "dataclasses", "enum", "typing"},
        "third_party": set(),
        "project": {"capture_import.workflow_ocr_models"},
    },
    "capture_import.workflow_ocr_review_service": {
        "stdlib": {"__future__", "dataclasses", "enum", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_models",
        },
    },
    "capture_import.workflow_ocr_review_session": {
        "stdlib": {"__future__", "dataclasses", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_conflict_resolution",
            "capture_import.workflow_ocr_consolidation",
            "capture_import.workflow_ocr_final_projection",
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_service",
        },
    },
    "capture_import.workflow_ocr_review_presenter": {
        "stdlib": {"__future__", "dataclasses", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_conflict_resolution",
            "capture_import.workflow_ocr_consolidation",
            "capture_import.workflow_ocr_final_projection",
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_service",
            "capture_import.workflow_ocr_review_session",
        },
    },
    "capture_import.workflow_ocr_review_controller": {
        "stdlib": {"__future__", "dataclasses", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_presenter",
            "capture_import.workflow_ocr_review_service",
            "capture_import.workflow_ocr_review_session",
        },
    },
    "capture_import.workflow_ocr_review_persistence_models": {
        "stdlib": {
            "__future__",
            "collections.abc",
            "dataclasses",
            "enum",
            "typing",
        },
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_conflict_resolution",
            "capture_import.workflow_ocr_consolidation",
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_service",
            "capture_import.workflow_ocr_review_session",
        },
    },
    "capture_import.workflow_ocr_review_persistence_service": {
        "stdlib": {"__future__", "dataclasses"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_persistence_models",
            "capture_import.workflow_ocr_review_service",
            "capture_import.workflow_ocr_review_session",
        },
    },
    "capture_import.workflow_ocr_review_local_repository": {
        "stdlib": {
            "__future__",
            "hashlib",
            "os",
            "pathlib",
            "stat",
            "tempfile",
            "typing",
        },
        "third_party": set(),
        "project": {
            "capture_import._json",
            "capture_import.limits",
            "capture_import.workflow_ocr_review_persistence_models",
        },
    },
    "capture_import.desktop_ocr_review_composition": {
        "stdlib": {"__future__", "dataclasses", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.manifest",
            "capture_import.package",
            "capture_import.workflow_ocr_composition",
            "capture_import.workflow_ocr_review_controller",
            "capture_import.workflow_ocr_runtime",
            "capture_import.workflow_ocr_stage",
            "capture_import.workflow_pipeline",
        },
    },
    "capture_import.desktop_ocr_review_handoff": {
        "stdlib": {"__future__", "collections.abc", "dataclasses", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_execution",
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_controller",
            "capture_import.workflow_pipeline",
        },
    },
    "capture_import.desktop_ocr_candidate_review": {
        "stdlib": {"__future__", "dataclasses", "math", "tkinter", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_controller",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_presenter",
            "capture_import.workflow_ocr_review_service",
        },
    },
    "capture_import.desktop_ocr_conflict_review": {
        "stdlib": {"__future__", "dataclasses", "tkinter", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_conflict_resolution",
            "capture_import.workflow_ocr_consolidation",
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_controller",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_presenter",
            "capture_import.workflow_ocr_review_service",
            "capture_import.workflow_ocr_review_session",
        },
    },
    "capture_import.desktop_ocr_review_persistence": {
        "stdlib": {"__future__", "dataclasses"},
        "third_party": set(),
        "project": {
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_controller",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_persistence_models",
            "capture_import.workflow_ocr_review_persistence_service",
            "capture_import.workflow_ocr_review_service",
            "capture_import.workflow_ocr_review_session",
        },
    },
    "capture_import.desktop_ocr_review_persistence_controls": {
        "stdlib": {"__future__", "dataclasses", "enum", "tkinter", "typing"},
        "third_party": set(),
        "project": {
            "capture_import.desktop_ocr_review_persistence",
            "capture_import.workflow_ocr_models",
            "capture_import.workflow_ocr_review_local_repository",
            "capture_import.workflow_ocr_review_models",
            "capture_import.workflow_ocr_review_persistence_models",
            "capture_import.workflow_ocr_review_persistence_service",
            "capture_import.workflow_ocr_review_service",
            "capture_import.workflow_ocr_review_session",
        },
    },
}

_STDLIB_ROOTS = set(sys.stdlib_module_names) | {"__future__"}

_LAYER_B_FORBIDDEN_PROJECT_PREFIXES = (
    "capture_import.desktop_",
    "capture_import.collection",
    "capture_import.workflow_confirmed_observation",
)
_LAYER_C_FORBIDDEN_PROJECT_PREFIXES = (
    "capture_import.collection",
    "capture_import.workflow_confirmed_observation",
)


def _module_path(module_name: str) -> Path:
    return _REPO_ROOT / (module_name.replace(".", "/") + ".py")


def _resolve_imports(tree: ast.AST, package: tuple[str, ...]) -> set[str]:
    names: set[str] = set()

    def _resolve_from(node: ast.ImportFrom) -> tuple[str, ...]:
        if any(alias.name == "*" for alias in node.names):
            raise ValueError("unresolvable import form: wildcard import")
        if node.level == 0:
            if node.module is None:
                raise ValueError(
                    "unresolvable import form: ImportFrom without module"
                )
            return (node.module,)
        remaining = len(package) - (node.level - 1)
        if remaining < 1:
            raise ValueError(
                f"relative import escapes package: level {node.level}"
            )
        base = package[:remaining]
        if node.module is not None:
            return (".".join([*base, node.module]),)
        resolved = []
        for alias in node.names:
            if not alias.name:
                raise ValueError("unresolvable import form: empty alias")
            resolved.append(".".join([*base, alias.name]))
        return tuple(resolved)

    def _visit(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
            return
        if isinstance(node, ast.ImportFrom):
            names.update(_resolve_from(node))
            return
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Name)
                and test.id == "TYPE_CHECKING"
                or isinstance(test, ast.Attribute)
                and test.attr == "TYPE_CHECKING"
            ):
                for statement in node.orelse:
                    _visit(statement)
                return
        for child in ast.iter_child_nodes(node):
            _visit(child)

    _visit(tree)
    return names


def _runtime_import_modules(module_name: str) -> set[str]:
    module_path = _module_path(module_name)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    return _resolve_imports(tree, ("capture_import",))


def _import_category(name: str) -> str:
    if name.startswith("capture_import."):
        return "project"
    if name.split(".", 1)[0] in _STDLIB_ROOTS:
        return "stdlib"
    return "third_party"


def _assert_module_allowlist(
    test_case: unittest.TestCase, module_name: str
) -> set[str]:
    resolved = _runtime_import_modules(module_name)
    expected = _IMPORT_ALLOWLISTS[module_name]
    categorized = {"stdlib": set(), "third_party": set(), "project": set()}
    for name in resolved:
        categorized[_import_category(name)].add(name)

    for category in ("stdlib", "third_party", "project"):
        test_case.assertEqual(
            categorized[category],
            set(expected[category]),
            f"{module_name}: {category} import allowlist mismatch",
        )
    return resolved


def _extract_policy_scope_by_layer() -> dict[str, set[str]]:
    text = _POLICY_PATH.read_text(encoding="utf-8")
    scope = {"Layer A": set(), "Layer B": set(), "Layer C": set()}
    current_layer: str | None = None
    layer_heading = re.compile(r"^###\s+(Layer [ABC])\s+-\s+")
    module_bullet = re.compile(r"^-\s+`(capture_import\.[^`]+)`\s*$")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        heading_match = layer_heading.match(line)
        if heading_match:
            current_layer = heading_match.group(1)
            continue
        module_match = module_bullet.match(line)
        if module_match and current_layer in scope:
            scope[current_layer].add(module_match.group(1))
    return scope


class Sprint19OCRReviewPackageBoundaryTests(unittest.TestCase):
    def test_layer_a_runtime_import_boundaries(self) -> None:
        for module_name in sorted(_LAYER_A_MODULES):
            resolved = _assert_module_allowlist(self, module_name)
            self.assertFalse(
                any(name.startswith("capture_import.desktop_") for name in resolved),
                f"{module_name}: Layer A must not import desktop modules",
            )
            self.assertFalse(
                any(name == "tkinter" or name.startswith("tkinter.") for name in resolved),
                f"{module_name}: Layer A must not import tkinter",
            )

    def test_layer_b_runtime_import_boundaries(self) -> None:
        for module_name in sorted(_LAYER_B_MODULES):
            resolved = _assert_module_allowlist(self, module_name)
            self.assertFalse(
                any(name.startswith("capture_import.desktop_") for name in resolved),
                f"{module_name}: Layer B must not import desktop modules",
            )
            self.assertFalse(
                any(
                    name.startswith(prefix)
                    for name in resolved
                    for prefix in _LAYER_B_FORBIDDEN_PROJECT_PREFIXES
                ),
                f"{module_name}: Layer B imports forbidden project modules",
            )

    def test_layer_c_runtime_import_boundaries(self) -> None:
        for module_name in sorted(_LAYER_C_MODULES):
            resolved = _assert_module_allowlist(self, module_name)
            self.assertFalse(
                any(
                    name.startswith(prefix)
                    for name in resolved
                    for prefix in _LAYER_C_FORBIDDEN_PROJECT_PREFIXES
                ),
                f"{module_name}: Layer C imports forbidden project modules",
            )

    def test_type_checking_imports_are_excluded(self) -> None:
        tree = ast.parse(
            "import typing\n"
            "if typing.TYPE_CHECKING:\n"
            "    from . import workflow_confirmed_observation_models\n"
            "else:\n"
            "    from . import workflow_ocr_models\n"
        )
        self.assertEqual(
            _resolve_imports(tree, ("capture_import",)),
            {"typing", "capture_import.workflow_ocr_models"},
        )

    def test_function_local_runtime_imports_are_included(self) -> None:
        resolved = _runtime_import_modules(
            "capture_import.desktop_ocr_review_composition"
        )
        self.assertIn("capture_import.workflow_ocr_runtime", resolved)

    def test_relative_import_resolution_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            _resolve_imports(ast.parse("from ....x import y\n"), ("a", "b"))
        with self.assertRaises(ValueError):
            _resolve_imports(ast.parse("from ..sibling import x\n"), ("capture_import",))
        node = ast.ImportFrom(module=None, names=[ast.alias(name="x")], level=0)
        with self.assertRaises(ValueError):
            _resolve_imports(ast.Module(body=[node], type_ignores=[]), ("capture_import",))

    def test_wildcard_imports_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            _resolve_imports(ast.parse("from capture_import.workflow_ocr_models import *\n"), ("capture_import",))
        with self.assertRaises(ValueError):
            _resolve_imports(ast.parse("from . import *\n"), ("capture_import",))

    def test_policy_scope_matches_enforced_module_scope(self) -> None:
        policy_scope = _extract_policy_scope_by_layer()
        self.assertEqual(policy_scope["Layer A"], set(_LAYER_A_MODULES))
        self.assertEqual(policy_scope["Layer B"], set(_LAYER_B_MODULES))
        self.assertEqual(policy_scope["Layer C"], set(_LAYER_C_MODULES))
        self.assertEqual(set(_IMPORT_ALLOWLISTS), set(_ENFORCED_MODULES))


if __name__ == "__main__":
    unittest.main()
