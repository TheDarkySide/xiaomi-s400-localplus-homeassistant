"""Authenticated S400 measurement stream helpers.

CMTP framing and CSV field behavior were independently adapted from the
Apache-2.0 ``xiaomi-s400-live`` project; see ``THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .crypto import SessionKeys, decrypt_cmtp


@dataclass(frozen=True, slots=True)
class ActiveMeasurement:
    """Values observed in one authenticated CMTP measurement message."""

    weight: float | None
    stabilized: bool
    profile_id: int | None = None
    timestamp: int | None = None
    impedance_low: float | None = None
    impedance_high: float | None = None
    heart_rate: int | None = None


class CmtpFrames:
    """Reassemble Xiaomi's header plus numbered CMTP data frames."""

    def __init__(self) -> None:
        self.expected = 0
        self.next_frame = 1
        self.payload = bytearray()

    def start(self, header: bytes) -> None:
        if len(header) < 6 or header[:3] != b"\x00\x00\x00":
            raise ValueError("invalid CMTP parcel header")
        expected = int.from_bytes(header[4:6], "little")
        if not 1 <= expected <= 64:
            raise ValueError("invalid CMTP frame count")
        self.expected = expected
        self.next_frame = 1
        self.payload.clear()

    def add(self, frame: bytes) -> bytes | None:
        if not self.expected:
            raise ValueError("CMTP data frame received without a header")
        if len(frame) < 2:
            raise ValueError("CMTP data frame is too short")
        frame_number = int.from_bytes(frame[:2], "little")
        if frame_number != self.next_frame:
            raise ValueError(
                f"expected CMTP frame {self.next_frame}, received {frame_number}"
            )
        self.payload.extend(frame[2:])
        self.next_frame += 1
        if frame_number != self.expected:
            return None
        result = bytes(self.payload)
        self.expected = 0
        self.next_frame = 1
        self.payload.clear()
        return result


def parse_cmtp_plaintext(plaintext: bytes) -> ActiveMeasurement | None:
    """Parse the S400 CSV found after the MIoT binary envelope marker."""
    marker = plaintext.find(b"\xa0")
    if marker < 0:
        return None
    try:
        text = plaintext[marker + 1 :].rstrip(b"\x00").strip().decode("ascii")
    except UnicodeDecodeError:
        return None
    fields = text.split(",")

    def integer(value: str) -> int | None:
        try:
            return int(value)
        except ValueError:
            return None

    if len(fields) == 2:
        weight = integer(fields[0])
        if weight is None:
            return None
        return ActiveMeasurement(weight=weight / 10, stabilized=fields[1] == "1")
    if len(fields) < 8:
        return None

    weight = integer(fields[3])
    # The last CSV field matches the larger value seen in the weight-bearing
    # MiBeacon frame (50 kHz); the preceding field matches the secondary frame.
    impedance_high = integer(fields[-2])
    impedance_low = integer(fields[-1])
    # Parse heart rate if reported
    heart_val = integer(fields[5]) if len(fields) > 5 else None
    heart_rate = heart_val if (heart_val is not None and 35 <= heart_val <= 220) else None

    return ActiveMeasurement(
        weight=weight / 10 if weight is not None else None,
        stabilized=fields[4] == "1",
        profile_id=integer(fields[2]),
        timestamp=integer(fields[6]),
        impedance_low=(impedance_low / 10 if impedance_low is not None else None),
        impedance_high=(impedance_high / 10 if impedance_high is not None else None),
        heart_rate=heart_rate,
    )


def decode_cmtp(keys: SessionKeys, message: bytes) -> ActiveMeasurement | None:
    """Authenticate, decrypt and parse one complete S400 CMTP message."""
    return parse_cmtp_plaintext(decrypt_cmtp(keys, message))
