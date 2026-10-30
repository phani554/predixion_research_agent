"""Executable module entrypoint: python -m research_agent."""
from __future__ import annotations

import sys
from research_agent.cli import main

if __name__ == "__main__":
    sys.exit(main())

