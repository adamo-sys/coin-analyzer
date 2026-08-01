"""Strict cross-version assertions for frozen, slotted dataclasses."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import is_dataclass
from typing import Iterator
import unittest


_CPYTHON_312_SLOTS_ERROR = (
    "super(type, obj): obj must be an instance or subtype of type"
)


@contextmanager
def assert_frozen_slotted_assignment_rejected(
    test_case: unittest.TestCase,
    value: object,
) -> Iterator[None]:
    """Require an assignment to fail through a known immutable-slots path.

    CPython 3.12's generated ``__setattr__`` for
    ``@dataclass(frozen=True, slots=True)`` raises a ``TypeError`` with one
    exact message for undeclared attributes. Newer CPython releases raise an
    ``AttributeError`` subtype instead. Both paths reject the mutation; no
    other ``TypeError`` is accepted.
    """

    test_case.assertTrue(is_dataclass(value))
    parameters = getattr(type(value), "__dataclass_params__", None)
    test_case.assertIsNotNone(parameters)
    test_case.assertTrue(parameters.frozen)
    test_case.assertFalse(hasattr(value, "__dict__"))

    try:
        yield
    except AttributeError:
        return
    except TypeError as error:
        test_case.assertEqual(str(error), _CPYTHON_312_SLOTS_ERROR)
        return
    test_case.fail("assignment unexpectedly succeeded")
