"""Validate local Task Packet and Outcome Packet JSON artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATHS = {
    'task': ROOT / '.ops/task-packet.schema.json',
    'outcome': ROOT / '.ops/outcome-packet.schema.json',
}


class PacketError(Exception):
    """Raised when a packet does not satisfy its local schema."""


def resolve_reference(schema: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith('#/$defs/'):
        raise PacketError('unsupported schema reference')
    name = reference.removeprefix('#/$defs/')
    definition = schema.get('$defs', {}).get(name)
    if not isinstance(definition, dict):
        raise PacketError('invalid local schema reference')
    return definition


def matches_type(value: Any, expected: str) -> bool:
    return {
        'array': isinstance(value, list),
        'integer': isinstance(value, int) and not isinstance(value, bool),
        'null': value is None,
        'object': isinstance(value, dict),
        'string': isinstance(value, str),
    }.get(expected, False)


def validate(value: Any, rules: dict[str, Any], schema: dict[str, Any], path: str = 'packet') -> None:
    if '$ref' in rules:
        validate(value, resolve_reference(schema, rules['$ref']), schema, path)
        return
    if 'anyOf' in rules:
        for option in rules['anyOf']:
            try:
                validate(value, option, schema, path)
                return
            except PacketError:
                continue
        raise PacketError(f'{path}: invalid value')
    if 'enum' in rules and value not in rules['enum']:
        if path == 'packet.execution_class':
            raise PacketError('invalid execution_class')
        raise PacketError(f'{path}: invalid value')
    if 'const' in rules and value != rules['const']:
        raise PacketError(f'{path}: invalid value')
    if 'type' in rules and not matches_type(value, rules['type']):
        raise PacketError(f'{path}: expected {rules["type"]}')
    if 'minLength' in rules and len(value) < rules['minLength']:
        raise PacketError(f'{path}: must not be empty')
    if 'minimum' in rules and value < rules['minimum']:
        raise PacketError(f'{path}: below minimum')
    if rules.get('type') == 'object':
        properties = rules.get('properties', {})
        for name in rules.get('required', []):
            if name not in value:
                raise PacketError(f'missing required field: {name}')
        if rules.get('additionalProperties') is False:
            unknown = set(value) - set(properties)
            if unknown:
                raise PacketError(f'{path}: unknown field: {sorted(unknown)[0]}')
        for name, child_rules in properties.items():
            if name in value:
                validate(value[name], child_rules, schema, f'{path}.{name}')
    if rules.get('type') == 'array':
        item_rules = rules.get('items')
        if item_rules:
            for index, item in enumerate(value):
                validate(item, item_rules, schema, f'{path}[{index}]')


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError) as exc:
        raise PacketError('packet is unavailable') from exc
    except json.JSONDecodeError as exc:
        raise PacketError('malformed JSON') from exc


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    validate_parser = subparsers.add_parser('validate')
    validate_parser.add_argument('--kind', choices=sorted(SCHEMA_PATHS), required=True)
    validate_parser.add_argument('--path', type=Path, required=True)
    args = parser.parse_args(arguments)
    try:
        schema = load_json(SCHEMA_PATHS[args.kind])
        if not isinstance(schema, dict):
            raise PacketError('local schema is invalid')
        validate(load_json(args.path), schema, schema)
    except PacketError as exc:
        print(f'invalid {args.kind} packet: {exc}', file=sys.stderr)
        return 2
    print(f'valid {args.kind} packet')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
