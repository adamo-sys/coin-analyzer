"""Collection-neutral structural validation for workflow image bytes."""

from __future__ import annotations


def require_complete_jpeg(payload: bytes) -> None:
    """Parse markers and entropy data, requiring the first JPEG to end at EOF."""

    if len(payload) < 4 or payload[:2] != b"\xff\xd8":
        raise ValueError("invalid JPEG structure")
    offset = 2
    in_entropy = False
    saw_scan = False
    while offset < len(payload):
        if in_entropy:
            if payload[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(payload) and payload[offset] == 0xFF:
                offset += 1
            if offset >= len(payload):
                raise ValueError("invalid JPEG structure")
            marker = payload[offset]
            offset += 1
            if marker == 0x00 or 0xD0 <= marker <= 0xD7:
                continue
            in_entropy = False
        else:
            if payload[offset] != 0xFF:
                raise ValueError("invalid JPEG structure")
            while offset < len(payload) and payload[offset] == 0xFF:
                offset += 1
            if offset >= len(payload):
                raise ValueError("invalid JPEG structure")
            marker = payload[offset]
            offset += 1

        if marker == 0xD9:
            if not saw_scan or offset != len(payload):
                raise ValueError("invalid JPEG structure")
            return
        if marker == 0xD8 or marker == 0x00 or 0xD0 <= marker <= 0xD7:
            raise ValueError("invalid JPEG structure")
        if marker == 0x01:
            continue
        if not 0xC0 <= marker <= 0xFE or offset + 2 > len(payload):
            raise ValueError("invalid JPEG structure")
        segment_length = int.from_bytes(payload[offset : offset + 2], "big")
        if segment_length < 2:
            raise ValueError("invalid JPEG structure")
        segment_end = offset + segment_length
        if segment_end > len(payload):
            raise ValueError("invalid JPEG structure")
        offset = segment_end
        if marker == 0xDA:
            saw_scan = True
            in_entropy = True
    raise ValueError("invalid JPEG structure")
