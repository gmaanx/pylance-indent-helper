# -*- coding: utf-8 -*-
"""
Script dong goi truc tiep VS Code Extension thanh file `.vsix` chuan OpenVSIX
chi bang thu vien chuan `zipfile` cua Python (khong can cai npm hay vsce!).
"""

import json
import zipfile
from pathlib import Path

EXTENSION_VSIXMANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="{name}" Version="{version}" Publisher="{publisher}" />
    <DisplayName>{displayName}</DisplayName>
    <Description xml:space="preserve">{description}</Description>
    <Tags>python,formatters,linters</Tags>
    <Categories>Formatters,Linters</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.75.0" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
  </Assets>
</PackageManifest>
"""

CONTENT_TYPES_XML = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json"/>
  <Default Extension=".js" ContentType="application/javascript"/>
  <Default Extension=".vsixmanifest" ContentType="text/xml"/>
</Types>
"""


def build_vsix() -> Path:
    ext_dir = Path(__file__).resolve().parent
    pkg_json_path = ext_dir / "package.json"
    pkg = json.loads(pkg_json_path.read_text(encoding="utf-8"))

    vsix_name = f"{pkg['name']}-{pkg['version']}.vsix"
    out_vsix = ext_dir.parents[1] / "setup_lab" / vsix_name

    manifest_xml = EXTENSION_VSIXMANIFEST.format(
        name=pkg["name"],
        version=pkg["version"],
        publisher=pkg["publisher"],
        displayName=pkg["displayName"],
        description=pkg["description"],
    )

    with zipfile.ZipFile(out_vsix, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML.strip())
        zf.writestr("extension.vsixmanifest", manifest_xml.strip())
        zf.write(pkg_json_path, "extension/package.json")
        zf.write(ext_dir / "src" / "extension.js", "extension/src/extension.js")

    print(f"Built VSIX package: {out_vsix}")
    return out_vsix


if __name__ == "__main__":
    build_vsix()
