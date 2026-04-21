"""Formatting utilities for e-paper display values.

Pure functions for converting raw numbers into human-readable,
space-efficient strings suitable for small displays.
"""

from __future__ import annotations

import math


def fmt_cost(cost: float | None) -> str:
    """Format cost with ceiling rounding, max 2 decimals.

    Examples:
        0.0041 -> "$0.01"
        0.0040 -> "$0.01"
        0.0001 -> "$0.01"
        0.0    -> "$0.00"
        None   -> ""
    """
    if cost is None:
        return ""
    c = float(cost)
    if c <= 0:
        return "$0.00"
    rounded = math.ceil(c * 100) / 100
    return f"${rounded:.2f}"


def fmt_duration(ms: int | float | None) -> str:
    """Convert milliseconds to human-readable duration string.

    Examples:
        245000  -> "4m 5s"
        3600000 -> "1h"
        59000   -> "59s"
        0       -> "0s"
        None    -> ""
    """
    if ms is None:
        return ""
    total_seconds = int(ms) // 1000
    if total_seconds <= 0:
        return "0s"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and hours == 0:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def fmt_tokens(n: int | float | None) -> str:
    """Compact token count with K/M suffix.

    Examples:
        1029   -> "1.0K"
        102900 -> "102.9K"
        1500000 -> "1.5M"
        0      -> "0"
        None   -> ""
    """
    if n is None:
        return ""
    val = float(n)
    if val <= 0:
        return "0"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val / 1_000:.1f}K"
    return str(int(val))


def auto_format(label: str, value: Any) -> str:
    """Automatically format a value based on its label hint.

    Matches label substrings to pick the right formatter:
      - "cost" -> fmt_cost
      - "duration", "time", "elapsed" -> fmt_duration
      - "token", "tok" -> fmt_tokens

    Falls back to str(value) if no match or formatting fails.
    """
    if value is None or value == "":
        return ""
    label_lower = str(label).lower()
    try:
        if "cost" in label_lower:
            return fmt_cost(float(value))
        if "duration" in label_lower or "time" in label_lower or "elapsed" in label_lower:
            return fmt_duration(value)
        if "token" in label_lower or "tok" in label_lower:
            return fmt_tokens(value)
    except (ValueError, TypeError):
        pass
    return str(value)
