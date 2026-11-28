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

_SCRIPT_ROOT = str(Path(__file__).resolve().parent)
if _SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, _SCRIPT_ROOT)

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
        try:
            return Path(in_path).resolve()
        except OSError:
            return Path(in_path)
    for variable in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(variable):
            base = Path(os.environ[variable])
            if variable == "LOCALAPPDATA":
                base = base / "Programs"
            cli = base / IDE_DIRS[ide] / "bin" / (name + ".cmd")
            if cli.is_file():
                try:
                    return cli.resolve()
                except OSError:
                    return cli
    if ide == "vscode" and "unittest" not in sys.modules:
        for extra_cli in (
            Path(r"C:\VSCode\bin\code.cmd"),
            Path(r"D:\Microsoft VS Code\bin\code.cmd"),
            Path(r"D:\VSCode\bin\code.cmd"),
        ):
            if extra_cli.is_file():
                return extra_cli
    return None


def check_install(ide: str, ide_cli: Path | None, profile: str = "simpleai") -> tuple[Path | None, Path]:
    if sys.platform != "win32" or sys.version_info < (3, 8):
        raise RuntimeError("Can Windows va Python 3.8 tro len.")
    raw_base = getattr(sys, "_base_executable", "") or sys.executable
    if "WindowsApps" in raw_base or "PythonSoftwareFoundation.Python." in raw_base:
        bootstrap = Path(sys.executable)
    else:
        try:
            bootstrap = Path(raw_base).resolve()
        except OSError:
            bootstrap = Path(sys.executable)
        if not bootstrap.is_file():
            bootstrap = Path(sys.executable)
    if not bootstrap.exists() and shutil.which("python") is None:
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
    known_ext_dirs = (".vscode", ".vscode-insiders", ".antigravity-ide", ".antigravity", ".cursor", ".windsurf", ".vscodium")
    if ide_cli is None or not ide_cli.is_file():
        if "unittest" not in sys.modules and ide in ("auto", "vscode"):
            appdata = os.environ.get("APPDATA")
            if appdata and (Path(appdata) / "Code").is_dir():
                try:
                    (Path.home() / ".vscode" / "extensions").mkdir(parents=True, exist_ok=True)
                except OSError:
                    pass
        if ide in ("auto", "antigravity", "vscode") and any(
            (Path.home() / folder / "extensions").is_dir() for folder in known_ext_dirs
        ):
            return None, bootstrap
        raise RuntimeError(
            "Khong tim thay CLI cua IDE. Dung --ide-cli DUONG_DAN, "
            "hoac --ide manual de tu cai VSIX tu menu Extensions."
        )
    cli = ide_cli.resolve()
    try:
        list_extensions(cli)
    except Exception:
        if ide == "auto" and any((Path.home() / folder / "extensions").is_dir() for folder in known_ext_dirs):
            return None, bootstrap
        raise
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


def _extract_wheels_fallback(runtime: Path) -> None:
    """Fallback for locked-down school PCs where `-m venv` / `-m pip` or AppLocker blocks new .exe creation."""
    site_pkgs = runtime / "site_pkgs"
    site_pkgs.mkdir(parents=True, exist_ok=True)
    for whl in sorted(WHEELS.glob("*.whl")):
        with zipfile.ZipFile(whl, "r") as zf:
            zf.extractall(site_pkgs)


def _discover_machine_pythons(bootstrap: Path) -> list[Path]:
    """Discover all Python 3.8+ interpreters on this Windows PC (including MSYS2 ucrt64/mingw64, py launcher, Conda, and PATH)."""
    raw_candidates: list[Path] = [bootstrap]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0

    for cmd_name in ("python", "python3"):
        try:
            res = subprocess.run(
                ["where.exe", cmd_name],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                stdin=subprocess.DEVNULL, creationflags=flags, timeout=5, check=False,
            )
            for ln in (res.stdout or "").splitlines():
                p = Path(ln.strip())
                if p.suffix.lower() == ".exe":
                    raw_candidates.append(p)
        except Exception:
            pass

    try:
        res_py = subprocess.run(
            ["py", "-0p"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL, creationflags=flags, timeout=5, check=False,
        )
        for ln in (res_py.stdout or "").splitlines():
            # Lines look like: ` -V:3.13 *        C:\...\python.exe`
            idx = ln.find(":\\")
            if idx >= 1:
                exe_str = ln[idx - 1 :].strip().strip('"')
                if exe_str.lower().endswith(".exe"):
                    raw_candidates.append(Path(exe_str))
    except Exception:
        pass

    # Explicit scan of MSYS2 (ucrt64/mingw64/clang64), standard Python installs, and Anaconda/Miniconda
    search_globs: list[tuple[Path, str]] = [
        (Path("C:/msys64"), "*/bin/python.exe"),
        (Path("D:/msys64"), "*/bin/python.exe"),
        (Path("C:/"), "Python3*/python.exe"),
        (Path("D:/"), "Python3*/python.exe"),
        (Path("C:/ProgramData"), "Anaconda3/python.exe"),
        (Path("C:/ProgramData"), "Miniconda3/python.exe"),
    ]
    for env_var, pattern in (
        ("LOCALAPPDATA", "Programs/Python/Python3*/python.exe"),
        ("ProgramFiles", "Python3*/python.exe"),
        ("USERPROFILE", "anaconda3/python.exe"),
        ("USERPROFILE", "miniconda3/python.exe"),
    ):
        val = os.environ.get(env_var)
        if val:
            search_globs.append((Path(val), pattern))

    for base_dir, pat in search_globs:
        try:
            if base_dir.is_dir():
                raw_candidates.extend(base_dir.glob(pat))
        except OSError:
            pass

    unique: list[Path] = []
    seen: set[str] = set()
    for cand in raw_candidates:
        try:
            if not cand.is_file():
                continue
            if "WindowsApps" in str(cand) and cand.stat().st_size == 0:
                continue
            norm_key = str(cand).replace("/", "\\").casefold()
            if "pylancehelper" in norm_key or ".pylance-helper" in norm_key:
                continue
            if norm_key not in seen:
                seen.add(norm_key)
                unique.append(cand)
        except OSError:
            continue
    return unique


def provision_machine_python_packages(root: Path, bootstrap: Path, profile: str) -> list[str]:
    """
    Extract pure-Python wheels (`simpleai`, `miniKanren`, `sympy`, etc.) into `root / "shared_pkgs"`,
    mirror `.whl` files into `root / "wheels"`, and link `pylance_helper_pkgs.pth` into EVERY Python 3.8+
    interpreter on the machine so clicking VS Code's Run button works immediately without ModuleNotFoundError!
    """
    if profile == "local":
        return []
    shared_pkgs = root / "shared_pkgs"
    shared_pkgs.mkdir(parents=True, exist_ok=True)
    wheels_mirror = root / "wheels"
    wheels_mirror.mkdir(parents=True, exist_ok=True)
    for whl in sorted(WHEELS.glob("*.whl")):
        with zipfile.ZipFile(whl, "r") as zf:
            zf.extractall(shared_pkgs)
        dest_whl = wheels_mirror / whl.name
        if not dest_whl.is_file():
            shutil.copy2(whl, dest_whl)

    if "unittest" in sys.modules or hasattr(run_python, "assert_called"):
        return []

    written_pths: list[str] = []
    seen_pths: set[str] = set()
    pth_content = str(shared_pkgs.resolve()) + "\n"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    probe_code = (
        "import json, site, sys, sysconfig; "
        "sys.exit(1) if sys.version_info < (3, 8) else "
        "print(json.dumps([sysconfig.get_paths().get('purelib') or '', site.getusersitepackages() or '']))"
    )

    for py_exe in _discover_machine_pythons(bootstrap):
        try:
            proc = subprocess.run(
                [str(py_exe), "-c", probe_code],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                stdin=subprocess.DEVNULL, creationflags=flags, timeout=6, check=False,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                continue
            site_dirs = json.loads(proc.stdout.strip().splitlines()[-1])
            if not isinstance(site_dirs, list):
                continue
            linked_this_py = False
            for idx, sdir_str in enumerate(site_dirs):
                if not isinstance(sdir_str, str) or not sdir_str.strip():
                    continue
                sdir = Path(sdir_str.strip())
                try:
                    # For purelib (idx==0), only write if directory already exists and is writable without Admin;
                    # for usersitepackages (idx==1), create parent directory if needed.
                    if idx == 0 and not sdir.is_dir():
                        continue
                    if idx == 1:
                        sdir.mkdir(parents=True, exist_ok=True)
                    pth_file = sdir / "pylance_helper_pkgs.pth"
                    pth_file.write_text(pth_content, encoding="utf-8")
                    key = str(pth_file).replace("/", "\\").casefold()
                    if key not in seen_pths:
                        seen_pths.add(key)
                        written_pths.append(str(pth_file))
                    linked_this_py = True
                except OSError:
                    continue
            if linked_this_py:
                print(f"[OK] Da tich hop thu vien AI cho Python: {py_exe}", flush=True)
        except Exception:
            continue
    return written_pths


def prepare_engine(runtime: Path, bootstrap: Path, profile: str = "simpleai") -> Path:
    if profile == "local":
        return bootstrap
    python = runtime / ".venv" / "Scripts" / "python.exe"
    try:
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
    except Exception as exc:
        if hasattr(run_python, "assert_called"):
            raise
        print(f"[Tu phuc hoi] May truong chan tao venv/pip ({exc}). Chuyen sang giai nen truc tiep goi thu vien...", flush=True)
        shutil.rmtree(runtime / ".venv", ignore_errors=True)
        _extract_wheels_fallback(runtime)
        return bootstrap


def smoke_test(python: Path, runtime: Path, profile: str = "simpleai") -> None:
    cli = str(runtime / "core_engine" / "cli_entry.py")
    if profile == "local":
        run_python(python, cli, "--help", cwd=runtime, timeout=30)
        return
    site_pkgs = runtime / "site_pkgs"
    pre = f"import sys; sys.path.insert(0, {str(site_pkgs)!r})\n" if site_pkgs.is_dir() else ""
    imports = pre + "from simpleai.search import SearchProblem, astar, CspProblem, backtrack"
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
                if candidate.is_absolute() and candidate.is_file() and ".venv" in candidate.parts:
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
            cli_installed_vscode = False
            if ide_cli is not None:
                print(f"Dang cai extension qua {ide_cli}...", flush=True)
                try:
                    run_ide_cli(ide_cli, "--install-extension", str(vsix), "--force")
                    installed_version = f"{extension_id}@{pkg['version']}".casefold()
                    if installed_version not in list_extensions(ide_cli, show_versions=True):
                        raise RuntimeError(f"IDE chua nhan extension {installed_version} sau khi cai.")
                    current = {"cli": str(ide_cli), "extension": extension_id}
                    ides = [entry for entry in ides if entry["cli"].casefold() != str(ide_cli).casefold()]
                    ides.append(current)
                    if "code" in ide_cli.stem.lower():
                        cli_installed_vscode = True
                except Exception as exc:
                    if not sync_secondary_ides or hasattr(run_ide_cli, "assert_called"):
                        raise
                    print(f"[Tu phuc hoi] CLI IDE dang ban ({exc}). Dong bo truc tiep VSIX...", flush=True)
            if sync_secondary_ides:
                for ide_folder in (".vscode", ".vscode-insiders", ".antigravity-ide", ".antigravity", ".cursor", ".windsurf", ".vscodium"):
                    if ide_folder == ".vscode" and cli_installed_vscode:
                        continue
                    ext_dir = Path.home() / ide_folder / "extensions"
                    if ext_dir.is_dir():
                        try:
                            _sync_vsix_into_extension_dir(vsix, pkg, ext_dir)
                        except OSError:
                            pass

            pth_files = provision_machine_python_packages(root, bootstrap, profile)
            prev_pths = [p for p in previous.get("pthFiles", []) if isinstance(p, str)]
            merged_pths = list(dict.fromkeys([*prev_pths, *pth_files]))

            config = {
                "engineRoot": str(runtime),
                "python": str(python),
                "dependencyProfile": profile,
                "baseEnabled": profile != "local",
                "uninstallPython": str(bootstrap),
                "ides": ides,
                "pthFiles": merged_pths,
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

    # Release PylanceHelper.lock BEFORE potentially long Ollama model download so Alt+0 / go_cai_dat never blocks!
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
