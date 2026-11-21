"""Install an offline runtime and a VSIX for the current Windows user."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from go_cai_dat import (
    _remove_tree,
    install_root,
    install_lock,
    list_extensions,
    load_runtime,
    run_ide_cli,
    stop_daemon_processes,
)
from shells.vscode_ext.pack_vsix import build_vsix


SOURCE = Path(__file__).resolve().parent
WHEELS = SOURCE / "setup_lab" / "wheels"
IDE_NAMES = {"vscode": "code", "antigravity": "antigravity"}
IDE_DIRS = {"vscode": "Microsoft VS Code", "antigravity": "antigravity"}


def find_ide_cli(ide: str) -> Path | None:
    name = IDE_NAMES[ide]
    in_path = shutil.which(name)
    if in_path:
        return Path(in_path).resolve()
    for variable in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(variable):
            base = Path(os.environ[variable])
            if variable == "LOCALAPPDATA":
                base = base / "Programs"
            cli = base / IDE_DIRS[ide] / "bin" / (name + ".cmd")
            if cli.is_file():
                return cli.resolve()
    return None


def check_install(ide: str, ide_cli: Path | None) -> tuple[Path | None, Path]:
    if sys.platform != "win32" or sys.version_info < (3, 10):
        raise RuntimeError("Can Windows va Python 3.10 tro len.")
    bootstrap = Path(sys._base_executable).resolve()
    if not bootstrap.is_file():
        raise RuntimeError(f"Khong tim thay Python goc: {bootstrap}")
    if not any(WHEELS.glob("*.whl")):
        raise RuntimeError("Khong tim thay goi offline trong setup_lab/wheels.")

    if ide == "manual":
        if ide_cli is not None:
            raise ValueError("--ide manual khong dung chung voi --ide-cli.")
        return None, bootstrap

    if ide_cli is None:
        candidates = IDE_NAMES if ide == "auto" else (ide,)
        for candidate in candidates:
            ide_cli = find_ide_cli(candidate)
            if ide_cli:
                break
    if ide_cli is None or not ide_cli.is_file():
        raise RuntimeError(
            "Khong tim thay CLI cua IDE. Dung --ide-cli DUONG_DAN, "
            "hoac --ide manual de tu cai VSIX tu menu Extensions."
        )
    cli = ide_cli.resolve()
    list_extensions(cli)
    return cli, bootstrap


def run_python(python: Path, *args: str, cwd: Path, timeout: int, input_text=None) -> str:
    command = [str(python), "-I", *args]
    result = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode:
        detail = (result.stderr.strip() or result.stdout.strip())[-2000:]
        raise RuntimeError(f"Python thoat voi ma {result.returncode}. {detail}")
    return result.stdout


def prepare_engine(runtime: Path, bootstrap: Path) -> Path:
    python = runtime / ".venv" / "Scripts" / "python.exe"
    run_python(bootstrap, "-m", "venv", str(runtime / ".venv"), cwd=runtime, timeout=120)
    print("Dang cai thu vien Python tu goi offline...", flush=True)
    run_python(
        python, "-m", "pip", "--isolated", "install",
        "--no-index", "--no-cache-dir", "--disable-pip-version-check",
        "--find-links", str(WHEELS),
        "simpleai", "miniKanren", "sympy",
        cwd=runtime, timeout=180,
    )
    shutil.copytree(
        SOURCE / "core_engine",
        runtime / "core_engine",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pylance_cache.json"),
    )
    shutil.copy2(SOURCE / "go_cai_dat.py", runtime / "go_cai_dat.py")
    return python


def smoke_test(python: Path, runtime: Path) -> None:
    run_python(python, "-c", "import simpleai, kanren, sympy", cwd=runtime, timeout=30)
    request = json.dumps({
        "text": '# @solve {"type":"coin_change","amount":17,"denominations":[4,7,9],"algorithm":"bfs"}',
        "mode": "instant",
        "verify": False,
    })
    reply = json.loads(run_python(
        python,
        str(runtime / "core_engine" / "cli_entry.py"),
        "--mode", "instant",
        cwd=runtime, timeout=30, input_text=request,
    ))
    if (
        reply.get("tier_used") != "offline_coin_change"
        or reply.get("validation_status") != "verified"
        or not reply.get("code")
    ):
        raise RuntimeError("Kiem tra offline khong tao duoc loi giai da xac minh.")


def install_all(ide_cli: Path | None, bootstrap: Path) -> None:
    root = install_root()
    with install_lock(root):
        root.mkdir(exist_ok=True)
        previous = load_runtime(root) or {}
        if (root / "shells" / "stealth_daemon" / "daemon.pyw").exists():
            stop_daemon_processes()
        runtime = Path(tempfile.mkdtemp(prefix="runtime-", dir=root))
        installed = False
        try:
            print(f"Dang tao moi truong Python rieng tai {runtime}", flush=True)
            python = prepare_engine(runtime, bootstrap)
            smoke_test(python, runtime)

            pkg = json.loads((SOURCE / "shells" / "vscode_ext" / "package.json").read_text(encoding="utf-8"))
            extension_id = f"{pkg['publisher']}.{pkg['name']}"
            vsix = build_vsix(runtime / f"{pkg['name']}-{pkg['version']}.vsix")
            ides = previous.get("ides", [])
            if ide_cli is not None:
                print(f"Dang cai extension qua {ide_cli}...", flush=True)
                run_ide_cli(ide_cli, "--install-extension", str(vsix), "--force")
                installed_version = f"{extension_id}@{pkg['version']}".casefold()
                if installed_version not in list_extensions(ide_cli, show_versions=True):
                    raise RuntimeError(f"IDE chua nhan extension {installed_version} sau khi cai.")
                current = {"cli": str(ide_cli), "extension": extension_id}
                ides = [entry for entry in ides if entry["cli"].casefold() != str(ide_cli).casefold()]
                ides.append(current)

            config = {
                "engineRoot": str(runtime),
                "python": str(python),
                "uninstallPython": str(bootstrap),
                "ides": ides,
                "manualExtension": ide_cli is None or previous.get("manualExtension", False),
            }
            config_staging = runtime / "runtime.json"
            config_staging.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            config_staging.replace(root / "runtime.json")
            installed = True
            (root / ".uninstalling").unlink(missing_ok=True)
        finally:
            if not installed:
                _remove_tree(runtime, root)

        for obsolete in root.glob("runtime-*"):
            if obsolete != runtime and obsolete.is_dir() and (obsolete / ".venv" / "pyvenv.cfg").is_file():
                try:
                    _remove_tree(obsolete, root)
                except OSError as exc:
                    print(f"[CANH BAO] Khong xoa duoc ban cu {obsolete.name}. {exc}")

        print("[OK] Python va che do offline da duoc kiem tra.")
        if ide_cli is None:
            print(f"Cai extension trong IDE qua Extensions > Install from VSIX: {vsix}")
        print("Neu IDE dang mo, dung Reload Window de nap ban moi.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ide", choices=("auto", *IDE_NAMES, "manual"), default="auto")
    parser.add_argument("--ide-cli", type=Path, help="Duong dan day du den CLI cua IDE.")
    parser.add_argument("--check", action="store_true", help="Kiem tra Python, goi offline va CLI.")
    args = parser.parse_args()
    try:
        cli, python = check_install(args.ide, args.ide_cli)
        if args.check:
            print(f"[OK] Python {sys.version.split()[0]}: {python}")
            print(f"[OK] Goi offline: {WHEELS}")
            print(f"[OK] IDE: {cli or 'Cai VSIX tu menu Extensions'}")
        else:
            install_all(cli, python)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"[LOI] Cai dat chua hoan tat. {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
