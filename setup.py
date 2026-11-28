"""Install Offline, encrypted Cloud API key, and/or Ollama integration for the current Windows user."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from core_engine.config_manager import PROVIDERS, save_encrypted_credential
from go_cai_dat import (
    _remove_tree,
    copy_runtime_files,
    install_root,
    install_lock,
    list_extensions,
    load_runtime,
    remove_obsolete_runtimes,
    run_ide_cli,
    save_runtime,
    stop_daemon_processes,
)
from setup_lab.local_ai import (
    DEFAULT_MODEL,
    check_managed_local_ai,
    install_local_ai,
    migrate_legacy_local_ai,
    normalize_model,
    recommend_model_for_machine,
)
from shells.vscode_ext.pack_vsix import build_vsix


SOURCE = Path(__file__).resolve().parent
WHEELS = SOURCE / "setup_lab" / "wheels"
IDE_NAMES = {"vscode": "code", "antigravity": "antigravity"}
IDE_DIRS = {"vscode": "Microsoft VS Code", "antigravity": "antigravity"}
DEPENDENCIES = {"simpleai": ("simpleai",), "full": ("simpleai", "miniKanren", "sympy")}


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


def check_install(ide: str, ide_cli: Path | None, profile: str = "simpleai") -> tuple[Path | None, Path]:
    if sys.platform != "win32" or sys.version_info < (3, 8):
        raise RuntimeError("Can Windows va Python 3.8 tro len.")
    bootstrap = Path(sys._base_executable).resolve()
    if not bootstrap.is_file():
        raise RuntimeError(f"Khong tim thay Python goc: {bootstrap}")
    missing = [name for name in DEPENDENCIES.get(profile, ()) if not any(WHEELS.glob(f"{name.lower()}-*.whl"))]
    if missing:
        packages = ", ".join(missing)
        raise RuntimeError(f"Goi offline thieu {packages}. Dung ban ZIP full neu can thu vien bo sung.")

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
        if ide in ("auto", "antigravity") and any(
            (Path.home() / folder / "extensions").is_dir() for folder in (".antigravity-ide", ".antigravity")
        ):
            return None, bootstrap
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


def prepare_engine(runtime: Path, bootstrap: Path, profile: str = "simpleai") -> Path:
    if profile == "local":
        return bootstrap
    python = runtime / ".venv" / "Scripts" / "python.exe"
    run_python(bootstrap, "-m", "venv", str(runtime / ".venv"), cwd=runtime, timeout=120)
    print("Dang cai thu vien Python tu goi offline...", flush=True)
    extra_pip_flags = ("--ignore-requires-python",) if sys.version_info < (3, 9) else ()
    run_python(
        python, "-m", "pip", "--isolated", "install",
        "--no-index", "--no-cache-dir", "--disable-pip-version-check",
        *extra_pip_flags,
        "--find-links", str(WHEELS),
        *DEPENDENCIES[profile],
        cwd=runtime, timeout=180,
    )
    return python


def smoke_test(python: Path, runtime: Path, profile: str = "simpleai") -> None:
    cli = str(runtime / "core_engine" / "cli_entry.py")
    if profile == "local":
        run_python(python, cli, "--help", cwd=runtime, timeout=30)
        return
    imports = "from simpleai.search import SearchProblem, astar, CspProblem, backtrack"
    if profile == "full":
        imports += "\nimport kanren, sympy"
    run_python(python, "-c", imports, cwd=runtime, timeout=30)
    request = json.dumps({
        "text": '# @solve {"type":"simpleai_graph","start":"A","goals":["B"],"edges":[["A","B"]],"algorithm":"bfs"}',
        "mode": "instant",
        "verify": False,
    })
    reply = json.loads(run_python(
        python,
        cli,
        "--mode", "instant",
        cwd=runtime, timeout=30, input_text=request,
    ))
    if (
        reply.get("tier_used") != "offline_simpleai_graph"
        or reply.get("validation_status") != "verified"
        or not reply.get("code")
    ):
        raise RuntimeError("Kiem tra offline khong tao duoc loi giai da xac minh.")


def _sync_vsix_into_extension_dir(vsix: Path, pkg: dict, ext_root: Path) -> None:
    """Install/update VSIX directly into an IDE extensions directory (e.g., .antigravity-ide/extensions)."""
    if not ext_root.is_dir():
        return
    ext_id = f"{pkg['publisher']}.{pkg['name']}"
    folder_name = f"{ext_id}-{pkg['version']}"
    for old_dir in ext_root.glob(f"{ext_id}-[0-9]*"):
        if old_dir.is_dir():
            shutil.rmtree(old_dir, ignore_errors=True)

    target_dir = ext_root / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(vsix, "r") as zf:
        for member in zf.namelist():
            if member.startswith("extension/") and not member.endswith("/"):
                rel = member[len("extension/"):]
                dest = target_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(member))

    manifest_file = ext_root / "extensions.json"
    entries: list = []
    if manifest_file.is_file():
        try:
            loaded = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, list):
                entries = [
                    e for e in loaded
                    if not (
                        isinstance(e, dict)
                        and isinstance(e.get("identifier"), dict)
                        and str(e["identifier"].get("id", "")).casefold() == ext_id.casefold()
                    )
                ]
        except (OSError, ValueError):
            return

    posix_path = "/" + target_dir.resolve().as_posix().lstrip("/")
    if len(posix_path) >= 3 and posix_path[2] == ":":
        posix_path = "/" + posix_path[1].lower() + posix_path[2:]
    entries.append({
        "identifier": {"id": ext_id},
        "version": pkg["version"],
        "location": {"$mid": 1, "fsPath": str(target_dir.resolve()), "path": posix_path, "scheme": "file"},
        "relativeLocation": folder_name,
        "metadata": {
            "installedTimestamp": int(time.time() * 1000),
            "pinned": False,
            "source": "vsix",
            "publisherDisplayName": pkg["publisher"],
            "targetPlatform": "universal",
            "updated": True,
            "isPreReleaseVersion": False,
            "hasPreReleaseVersion": False,
        },
    })
    manifest_file.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Da dong bo extension vao {ext_root}", flush=True)


def install_all(
    ide_cli: Path | None,
    bootstrap: Path,
    profile: str = "simpleai",
    local_model: str | None = None,
    *,
    wants_local: bool = False,
    auto_model: bool = False,
    api_provider: str | None = None,
    api_key: str | None = None,
    sync_secondary_ides: bool = False,
) -> None:
    root = install_root()
    with install_lock(root):
        root.mkdir(exist_ok=True)
        previous = load_runtime(root) or {}
        migrate_legacy_local_ai(previous)
        existing_python = None
        if profile == "local" and previous and previous.get("baseEnabled", True):
            previous_profile = previous.get("dependencyProfile", "simpleai")
            if previous_profile in DEPENDENCIES:
                profile = previous_profile
                candidate = Path(previous.get("python", ""))
                if candidate.is_absolute() and candidate.is_file():
                    existing_python = candidate
        if (root / "shells" / "stealth_daemon" / "daemon.pyw").exists():
            stop_daemon_processes()
        runtime = Path(tempfile.mkdtemp(prefix="runtime-", dir=root))
        installed = False
        try:
            print(f"Dang tao moi truong Python rieng tai {runtime}", flush=True)
            python = existing_python or prepare_engine(runtime, bootstrap, profile)
            copy_runtime_files(SOURCE, runtime)
            smoke_test(python, runtime, profile)

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
            if sync_secondary_ides:
                for ide_folder in (".vscode", ".vscode-insiders", ".antigravity-ide", ".antigravity", ".cursor", ".windsurf", ".vscodium"):
                    ext_dir = Path.home() / ide_folder / "extensions"
                    if ext_dir.is_dir():
                        _sync_vsix_into_extension_dir(vsix, pkg, ext_dir)

            config = {
                "engineRoot": str(runtime),
                "python": str(python),
                "dependencyProfile": profile,
                "baseEnabled": profile != "local",
                "uninstallPython": str(bootstrap),
                "ides": ides,
                "manualExtension": ide_cli is None or previous.get("manualExtension", False),
            }
            save_runtime(root, config)
            if api_provider and api_key:
                save_encrypted_credential(api_provider, api_key, install_dir=root)
                print(f"[OK] Da ma hoa va luu san API key ({api_provider}) cho che do chay ngam.", flush=True)
            installed = True
            (root / ".uninstalling").unlink(missing_ok=True)
        finally:
            if not installed:
                _remove_tree(runtime, root)

        remove_obsolete_runtimes(root, config)

        print(f"[OK] Python va tich hop IDE ({profile}) da duoc kiem tra.")
        print(f"Python de chay bai trong IDE: {python}")
        if ide_cli is None:
            print(f"Cai extension trong IDE qua Extensions > Install from VSIX: {vsix}")
        print("Neu IDE dang mo, dung Reload Window de nap ban moi.")
        if wants_local or local_model is not None:
            try:
                if auto_model and local_model is None:
                    optional = install_local_ai(None, auto_model=True)
                else:
                    optional = install_local_ai(local_model)
            except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                raise RuntimeError(f"Da cai tich hop IDE. Local AI chua san sang. {exc}") from exc
            print(f"[OK] Local AI san sang voi {optional['localModel']}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ide", choices=("auto", *IDE_NAMES, "manual"), default="auto")
    parser.add_argument("--ide-cli", type=Path, help="Duong dan day du den CLI cua IDE.")
    parser.add_argument("--profile", choices=DEPENDENCIES, default="simpleai", help="simpleai gon nhe; full them miniKanren va SymPy.")
    parser.add_argument("--check", action="store_true", help="Kiem tra Python, goi offline va CLI.")
    component = parser.add_mutually_exclusive_group()
    component.add_argument("--local", action="store_true", help="Cai Offline, API va Ollama.")
    component.add_argument("--local-shell", action="store_true", help="Cai Ollama va tich hop Alt+5.")
    parser.add_argument("--local-model", help=f"Model Ollama dung voi --local-shell. Mac dinh {DEFAULT_MODEL}.")
    parser.add_argument("--auto-model", action="store_true", help="Tu chon model Ollama theo dung luong RAM.")
    parser.add_argument("--provider", choices=PROVIDERS, help="Nha cung cap Cloud luu san API key ma hoa.")
    parser.add_argument("--key", help="API key luu ma hoa san cho Alt+2 / Alt+3.")
    args = parser.parse_args()
    wants_local = getattr(args, "local", False) or getattr(args, "local_shell", False)
    auto_model = getattr(args, "auto_model", False)
    api_provider = getattr(args, "provider", None)
    api_key = getattr(args, "key", None)
    if args.local_model is not None and not wants_local:
        parser.error("--local-model can dung cung --local-shell hoac --local.")
    if bool(api_provider) != bool(api_key):
        parser.error("--provider va --key can truyen cung nhau.")
    try:
        local_model = normalize_model(args.local_model) if args.local_model is not None else None
        profile = "local" if args.local_shell else args.profile
        cli, python = check_install(args.ide, args.ide_cli, profile)
        if args.check:
            print(f"[OK] Python {sys.version.split()[0]}: {python}")
            if not args.local_shell:
                print(f"[OK] Goi offline ({profile}): {WHEELS}")
            print(f"[OK] IDE: {cli or 'Cai VSIX tu menu Extensions'}")
            if wants_local:
                target_model = local_model or (recommend_model_for_machine() if auto_model else None)
                print(f"[OK] Local AI: {check_managed_local_ai(target_model)}")
        else:
            install_all(
                cli, python, profile, local_model,
                wants_local=wants_local,
                auto_model=auto_model,
                api_provider=api_provider,
                api_key=api_key,
                sync_secondary_ides=(args.ide in ("auto", "antigravity")),
            )
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"[LOI] Cai dat chua hoan tat. {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
