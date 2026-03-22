from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable


OPTION_SYMBOL_RE = re.compile(
    r"^(?P<underlying>.+?) (?P<expiry>\d{1,2}[A-Z]{3}\d{2}) (?P<strike>[0-9.]+) (?P<right>[CP])$"
)


def stable_hash(*parts: object) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part if part is not None else "").encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def canonical_decimal_text(value: str | None) -> str | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    cleaned = cleaned.replace(",", "")
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return cleaned
    if number == 0:
        return "0"
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def parse_decimal(value: str | None) -> Decimal | None:
    cleaned = canonical_decimal_text(value)
    if cleaned is None:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_broker_datetime(value: str | None) -> datetime | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d, %H:%M:%S")
    except ValueError:
        return None


def parse_iso_date(value: str | None) -> date | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d%b%y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def json_dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def utc_now() -> datetime:
    return datetime.now(UTC)


def split_codes(code_text: str | None) -> list[str]:
    cleaned = clean_text(code_text)
    if cleaned is None:
        return []
    return [part.strip() for part in cleaned.split(";") if part.strip()]


def unique_headers(headers: Iterable[str]) -> list[str]:
    counts: dict[str, int] = {}
    result: list[str] = []
    for index, header in enumerate(headers, start=1):
        base = header.strip() or f"column_{index}"
        seen = counts.get(base, 0)
        counts[base] = seen + 1
        result.append(base if seen == 0 else f"{base}_{seen + 1}")
    return result


def row_mapping(headers: list[str], values: list[str]) -> dict[str, str]:
    names = unique_headers(headers)
    return {name: values[index] if index < len(values) else "" for index, name in enumerate(names)}


def parse_option_symbol(symbol: str | None) -> dict[str, str | None]:
    cleaned = clean_text(symbol)
    if cleaned is None:
        return {"underlying": None, "expiry": None, "strike": None, "right": None}
    match = OPTION_SYMBOL_RE.match(cleaned)
    if match is None:
        return {"underlying": None, "expiry": None, "strike": None, "right": None}
    data = match.groupdict()
    return {
        "underlying": data["underlying"],
        "expiry": data["expiry"],
        "strike": data["strike"],
        "right": data["right"],
    }
