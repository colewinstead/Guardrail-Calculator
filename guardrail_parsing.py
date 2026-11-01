"""Strict numeric parsing at input boundaries; no engineering calculations."""

import re
from guardrail_validation import require_finite as _require_finite

def parse_number(s: str) -> float:
    """Parse one complete finite number, with optional grouped thousands/exponent."""
    text = s.strip()
    if not re.fullmatch(
        r"[+-]?(?:(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]*)?|\.[0-9]+)"
        r"(?:[eE][+-]?[0-9]+)?", text,
    ):
        raise ValueError("Enter a complete number; use commas only for thousands (for example, 6,000).")
    value = float(text.replace(",", ""))
    _require_finite(value=value)
    return value
