"""Bundle the Windows installer, engine, and offline wheels."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
INCLUDE = (
    "README.md",
    "setup.py",
    "setup_nhanh.bat",
    "go_cai_dat.py",
    "go_cai_dat.bat",
    "nhap_api_key.py",
    "nhap_api_key.bat",
    "setup_lab/deploy_usb.bat",
    "setup_lab/deploy_oneliner.ps1",
    "shells/vscode_ext/pack_vsix.py",
    "shells/vscode_ext/package.json",
    "shells/vscode_ext/src/*.js",
    "core_engine/**/*.py",
    "setup_lab/wheels/*.whl",
)


def build() -> Path:
    output = ROOT / "dist" / "python-ai-helper-windows.zip"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for pattern in INCLUDE:
            paths = sorted(ROOT.glob(pattern))
            if not paths:
                raise FileNotFoundError(f"Missing release input: {pattern}")
            for path in paths:
                archive.write(path, path.relative_to(ROOT))
    return output


if __name__ == "__main__":
    print(build())
