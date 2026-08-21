#!/usr/bin/env python3
"""兼容入口：主口径已是 Extended-27，请直接跑 train_models.py。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent


def main() -> None:
    print("asin-gmv-nn 主口径 = Extended 27 维（已无 19 维 Baseline 训练）。")
    print("运行: python3 train_models.py")
    raise SystemExit(subprocess.call([sys.executable, str(CODE / "train_models.py")]))


if __name__ == "__main__":
    main()
