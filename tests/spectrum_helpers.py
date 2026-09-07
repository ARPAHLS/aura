"""Shared spectrum blocks for tests (#73)."""


def spectrum_block(level: str, **extra: object) -> dict:
    """Build spectrum dict; high/full opt out of verified-ID default unless explicitly set."""
    block: dict = {"level": level}
    if level in ("high", "full") and "identity_required" not in extra:
        block["identity_required"] = False
    block.update(extra)
    return block
