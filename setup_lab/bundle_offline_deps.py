# -*- coding: utf-8 -*-
"""
Script trich xuat toan bo thu vien Python cua mon hoc (simpleai, miniKanren, sympy, toolz...)
tu `.venv` hien tai sang:
1. `setup_lab/offline_pkgs/` (de PYTHONPATH dung truc tiep khong can pip install!)
2. `setup_lab/wheels/` (de cai offline qua `pip install --no-index --find-links` tren may truong)
"""

import shutil
import subprocess
import sys
from pathlib import Path

PACKAGES_TO_COPY = [
    "simpleai",
    "kanren",
    "etuples",
    "unification",
    "cons",
    "multipledispatch",
    "toolz",
    "tlz",
    "sympy",
    "mpmath",
]

SINGLE_FILE_MODULES = [
    "typing_extensions.py",
]


def bundle_site_packages() -> None:
    setup_dir = Path(__file__).resolve().parent
    root_dir = setup_dir.parent
    ueh_venv_site = root_dir.parent / ".venv" / "Lib" / "site-packages"

    if not ueh_venv_site.exists():
        print(f"[!] Khong tim thay {ueh_venv_site}")
        return

    offline_pkgs = setup_dir / "offline_pkgs"
    offline_pkgs.mkdir(parents=True, exist_ok=True)

    copied = []
    for pkg in PACKAGES_TO_COPY:
        src = ueh_venv_site / pkg
        dst = offline_pkgs / pkg
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            copied.append(pkg)

    for mod_file in SINGLE_FILE_MODULES:
        src_f = ueh_venv_site / mod_file
        if src_f.exists():
            shutil.copy2(src_f, offline_pkgs / mod_file)
            copied.append(mod_file)

    print(f"[OK] Da dong goi truc tiep {len(copied)} thu vien vao {offline_pkgs}: {', '.join(copied)}")

    # Build .whl files from installed packages or pip cache if available
    wheels_dir = setup_dir / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)
    req_file = root_dir.parent / "requirements.txt"
    py_exe = root_dir.parent / ".venv" / "Scripts" / "python.exe"
    if req_file.exists() and py_exe.exists():
        try:
            subprocess.run(
                [
                    str(py_exe),
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "-r",
                    str(req_file),
                    "-w",
                    str(wheels_dir),
                ],
                timeout=30,
                check=False,
            )
        except Exception as exc:
            print(f"[Info] Bo qua pip wheel online ({exc}), da co offline_pkgs day du.")


if __name__ == "__main__":
    bundle_site_packages()
