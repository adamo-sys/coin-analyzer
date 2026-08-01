from __future__ import annotations

from dataclasses import dataclass
import unittest

from tests.frozen_dataclass_compat import (
    _CPYTHON_312_SLOTS_ERROR,
    assert_frozen_slotted_assignment_rejected,
)


@dataclass(frozen=True, slots=True)
class _FrozenSlottedValue:
    value: str


class FrozenDataclassCompatibilityTests(unittest.TestCase):
    def test_accepts_native_frozen_slotted_rejection(self) -> None:
        value = _FrozenSlottedValue("original")

        with assert_frozen_slotted_assignment_rejected(self, value):
            value.extra = "changed"  # type: ignore[attr-defined]

    def test_accepts_only_the_known_cpython_312_type_error(self) -> None:
        value = _FrozenSlottedValue("original")
        original = _FrozenSlottedValue.__setattr__

        def known_failure(_self: object, _name: str, _value: object) -> None:
            raise TypeError(_CPYTHON_312_SLOTS_ERROR)

        try:
            _FrozenSlottedValue.__setattr__ = known_failure  # type: ignore[method-assign]
            with assert_frozen_slotted_assignment_rejected(self, value):
                value.extra = "changed"  # type: ignore[attr-defined]
        finally:
            _FrozenSlottedValue.__setattr__ = original  # type: ignore[method-assign]

    def test_rejects_an_unrelated_type_error(self) -> None:
        value = _FrozenSlottedValue("original")
        original = _FrozenSlottedValue.__setattr__

        def unrelated_failure(_self: object, _name: str, _value: object) -> None:
            raise TypeError("unrelated")

        try:
            _FrozenSlottedValue.__setattr__ = unrelated_failure  # type: ignore[method-assign]
            with self.assertRaises(AssertionError):
                with assert_frozen_slotted_assignment_rejected(self, value):
                    value.extra = "changed"  # type: ignore[attr-defined]
        finally:
            _FrozenSlottedValue.__setattr__ = original  # type: ignore[method-assign]


if __name__ == "__main__":
    unittest.main()
