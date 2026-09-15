#!/usr/bin/env python3
"""Run the same stage-1 audit used by Notebook 17B, without Jupyter."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aia17_metadata_audit import main
if __name__ == "__main__":
    raise SystemExit(main())
