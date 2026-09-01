"""Allow running as ``python -m cyberglossary``."""

from __future__ import annotations

import sys

from cyberglossary.main import main

if __name__ == "__main__":
    sys.exit(main())
