#!/usr/bin/env python3
"""
CK Font 최종 빌드 스크립트.
수정된 Variable TTF에서 최종 출력물을 생성한다.

출력:
- CKSans-Variable.ttf (Variable Font)
- CKSans-Variable.woff2 (Web Font)
- Static instances (설정에 따라)
"""

import shutil
import sys
from pathlib import Path

import yaml
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "ck-font.yaml"
BUILD_DIR = ROOT / "build"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def print_font_info(font_path):
    """폰트 정보 출력."""
    font = TTFont(str(font_path))

    print(f"\n{'='*50}")
    print(f"  CK Font Info: {font_path.name}")
    print(f"{'='*50}")

    # 이름
    name = font["name"]
    for record in name.names:
        if record.platformID == 3 and record.nameID in (1, 2, 4, 5, 6, 16):
            labels = {1: "Family", 2: "Subfamily", 4: "Full Name",
                      5: "Version", 6: "PostScript", 16: "Typo Family"}
            label = labels.get(record.nameID, f"ID {record.nameID}")
            print(f"  {label}: {record.toUnicode()}")

    # 축
    if "fvar" in font:
        print(f"\n  Variable Font Axes:")
        for axis in font["fvar"].axes:
            print(f"    {axis.axisTag}: {axis.minValue} – {axis.defaultValue} – {axis.maxValue}")

        print(f"\n  Named Instances ({len(font['fvar'].instances)}):")
        for inst in font["fvar"].instances:
            inst_name = name.getName(inst.subfamilyNameID, 3, 1, 0x0409)
            inst_name = inst_name.toUnicode() if inst_name else "unnamed"
            print(f"    {inst_name}: {inst.coordinates}")

    # 메트릭
    if "OS/2" in font:
        os2 = font["OS/2"]
        print(f"\n  Metrics:")
        print(f"    Ascender: {os2.sTypoAscender}")
        print(f"    Descender: {os2.sTypoDescender}")
        print(f"    Line Gap: {os2.sTypoLineGap}")
        print(f"    Units/Em: {font['head'].unitsPerEm}")

    # 글리프 수
    print(f"\n  Glyphs: {len(font.getGlyphOrder())}")

    file_size = font_path.stat().st_size
    print(f"  File size: {file_size / 1024:.0f} KB ({file_size / (1024*1024):.1f} MB)")

    font.close()
    print(f"{'='*50}\n")


def build_woff2(source_path, output_path):
    """WOFF2 형식으로 변환."""
    print(f"  Building WOFF2: {output_path.name} ...", end=" ", flush=True)
    try:
        font = TTFont(str(source_path))
        font.flavor = "woff2"
        font.save(str(output_path))
        font.close()
        size_kb = output_path.stat().st_size / 1024
        print(f"OK ({size_kb:.0f} KB)")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def build_static_instance(source_path, instance_config, output_dir):
    """Static instance 빌드."""
    from fontTools.instancer import instantiateVariableFont

    name = instance_config["name"].replace(" ", "")
    coords = instance_config["coordinates"]

    output_path = output_dir / f"{name}.ttf"
    print(f"  Building static: {output_path.name} ...", end=" ", flush=True)

    try:
        font = TTFont(str(source_path))
        instantiateVariableFont(font, coords)
        font.save(str(output_path))
        font.close()
        print("OK")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def main():
    config = load_config()
    output_config = config.get("output", {})

    # --info 모드
    if "--info" in sys.argv:
        font_path = BUILD_DIR / "CKSans-Variable.ttf"
        if font_path.exists():
            print_font_info(font_path)
        else:
            print("No built font found. Run 'make modify-params' first.")
        return

    # 소스 확인
    source_path = BUILD_DIR / "CKSans-Variable.ttf"
    if not source_path.exists():
        print("Error: build/CKSans-Variable.ttf not found.")
        print("Run 'make modify-params' and 'make modify-glyphs' first.")
        sys.exit(1)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    formats = output_config.get("formats", ["ttf"])

    print("Building CK Font outputs...")
    print(f"  Source: {source_path.name}")
    print(f"  Formats: {formats}")

    # WOFF2 빌드
    if "woff2" in formats:
        woff2_path = BUILD_DIR / "CKSans-Variable.woff2"
        build_woff2(source_path, woff2_path)

    # Static instance 빌드
    if output_config.get("static", False):
        instances = config.get("instances", [])
        static_dir = BUILD_DIR / "static"
        static_dir.mkdir(exist_ok=True)
        print(f"\n  Building {len(instances)} static instances...")
        for inst in instances:
            build_static_instance(source_path, inst, static_dir)

    # Preview 폴더에 폰트 복사 (웹 미리보기용)
    preview_dir = ROOT / "preview"
    if preview_dir.exists():
        for ext in ("ttf", "woff2"):
            src = BUILD_DIR / f"CKSans-Variable.{ext}"
            if src.exists():
                shutil.copy2(src, preview_dir / src.name)
                print(f"  Copied to preview/: {src.name}")

    # 최종 정보 출력
    print_font_info(source_path)

    print("Build complete!")
    print("Open preview/index.html to see the font in browser.")


if __name__ == "__main__":
    main()
