# -*- coding: utf-8 -*-
"""
Script dong goi daemon.pyw thanh file .exe chay ngam (--noconsole) bang PyInstaller (tuy chon).
Tren may phong lab, uu tien chay truc tiep qua `pythonw.exe daemon.pyw` de khong can build .exe.
"""

import subprocess
import sys
from pathlib import Path


def build_executable() -> None:
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    target_pyw = here / "daemon.pyw"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--noconsole",
        "--name",
        "pylance-indent-helper",
        "--paths",
        str(root),
        str(target_pyw),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    build_executable()
