"""Bundle the Windows installer, engine, and offline wheels."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
INCLUDE = (
    "README.md",
    "thu_nghiem.py",
    "docs/course-coverage.md",
    "setup.py",
    "setup_nhanh.bat",
    "setup_ollama.bat",
    "go_cai_dat.py",
    "go_cai_dat.bat",
    "go_cai_dat.vbs",
    "go_ollama.bat",
    "go_ollama.vbs",
    "nhap_api_key.py",
    "nhap_api_key.bat",
    "setup_lab/deploy_usb.bat",
    "setup_lab/deploy_oneliner.ps1",
    "setup_lab/local_ai.py",
    "setup_lab/run_python.bat",
    "shells/vscode_ext/pack_vsix.py",
    "shells/vscode_ext/package.json",
    "shells/vscode_ext/src/*.js",
    "core_engine/**/*.py",
)


def build(full: bool = False) -> Path:
    filename = "python-ai-helper-windows-full.zip" if full else "python-ai-helper-windows.zip"
    output = ROOT / "dist" / filename
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        wheel_pattern = "setup_lab/wheels/*.whl" if full else "setup_lab/wheels/simpleai-*.whl"
        for pattern in (*INCLUDE, wheel_pattern):
            paths = sorted(ROOT.glob(pattern))
            if not paths:
                raise FileNotFoundError(f"Missing release input: {pattern}")
            for path in paths:
                archive.write(path, path.relative_to(ROOT))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Include optional miniKanren and SymPy wheels.")
    print(build(parser.parse_args().full))
