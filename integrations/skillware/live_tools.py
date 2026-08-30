#!/usr/bin/env python3
"""Run the Skillware reference ToolHost with live registry skills."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ["SKILLWARE_LIVE"] = "1"

from integrations.skillware.reference_tool_host import main  # noqa: E402

if __name__ == "__main__":
    main()
