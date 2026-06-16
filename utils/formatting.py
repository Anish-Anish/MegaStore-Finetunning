"""Shared formatting helpers — keep currency + time formatting consistent."""


def rupees(value) -> str:
    """Format an integer amount as ₹ with thousands separators."""
    try:
        return f"₹{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def lakhs(value) -> str:
    """Format a large amount in lakhs, e.g. ₹12.4L."""
    try:
        return f"₹{float(value) / 100000:.1f}L"
    except (TypeError, ValueError):
        return str(value)


def fmt_ts(ts: str) -> str:
    """Turn an ISO timestamp into a readable 'YYYY-MM-DD HH:MM' UTC string."""
    if not ts:
        return ""
    return ts[:16].replace("T", " ")


def minutes_ago_label(minutes: int) -> str:
    if minutes is None:
        return ""
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hrs = minutes // 60
    return f"{hrs} hr ago" if hrs == 1 else f"{hrs} hrs ago"
