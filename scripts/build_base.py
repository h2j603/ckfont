#!/usr/bin/env python3
"""
CK Sans 베이스 폰트 빌드.

Noto Sans Variable Font → Condensed ExtraBold 정적 인스턴스 추출.
이 베이스 위에 장식 변형(inline, cut, outline 등)을 적용한다.

출력:
  build/CKSans-Base.ttf
  build/CKSans-Base.woff2
  preview/CKSans-Base.woff2
"""

import shutil
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources" / "NotoSans"
BUILD_DIR = ROOT / "build"
PREVIEW_DIR = ROOT / "preview"

# CK Sans 인스턴스 정의
# (파일명 접미사, wdth, wght, 스타일명)
INSTANCES = [
    ("Base",        62.5, 800, "ExtraBold"),
    ("Regular",     62.5, 400, "Regular"),
]

FAMILY_NAME = "CK Sans"
VERSION = "0.3.0"


def find_source():
    """Noto Sans Variable TTF 찾기."""
    for f in SOURCES_DIR.glob("*.ttf"):
        if "wdth" in f.name and "wght" in f.name and "Italic" not in f.name:
            return f
    ttfs = list(SOURCES_DIR.glob("*.ttf"))
    if ttfs:
        return ttfs[0]
    print("Error: sources/NotoSans/ 에 TTF 없음. make download 먼저 실행.")
    sys.exit(1)


def instance_font(source_path, wdth, wght):
    """Variable Font에서 정적 인스턴스 추출."""
    print(f"  Instancing: wdth={wdth}, wght={wght}")
    font = TTFont(str(source_path))
    instantiateVariableFont(font, {"wdth": wdth, "wght": wght}, inplace=True)
    return font


def rename_font(font, style_name):
    """폰트 이름을 CK Sans로 변경."""
    name_table = font["name"]
    full_name = f"{FAMILY_NAME} {style_name}"
    ps_name = full_name.replace(" ", "-")

    entries = {
        0: f"Copyright 2024 Condensed Kiwi. Based on Noto Sans (OFL).",
        1: FAMILY_NAME,
        2: style_name,
        3: f"{ps_name}-{VERSION}",
        4: full_name,
        5: f"Version {VERSION}",
        6: ps_name,
        8: "Condensed Kiwi",
        9: "Condensed Kiwi",
        13: "SIL Open Font License 1.1",
        16: FAMILY_NAME,
        17: style_name,
    }

    for name_id, value in entries.items():
        name_table.setName(value, name_id, 3, 1, 0x0409)
        name_table.setName(value, name_id, 1, 0, 0)

    print(f"  Renamed: {full_name}")


def strip_hints(font):
    """힌팅 제거."""
    tables = ["fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX", "gasp"]
    removed = [t for t in tables if t in font]
    for t in removed:
        del font[t]

    if "glyf" in font:
        for name in font.getGlyphOrder():
            g = font["glyf"][name]
            if hasattr(g, "program") and g.program:
                g.program = None

    print(f"  Hints stripped: {', '.join(removed) if removed else 'already clean'}")


def build_woff2(ttf_path):
    """WOFF2 변환."""
    woff2_path = ttf_path.with_suffix(".woff2")
    font = TTFont(str(ttf_path))
    font.flavor = "woff2"
    font.save(str(woff2_path))
    font.close()
    size_kb = woff2_path.stat().st_size / 1024
    print(f"  WOFF2: {woff2_path.name} ({size_kb:.0f} KB)")
    return woff2_path


def print_info(font_path):
    """빌드된 폰트 정보 출력."""
    font = TTFont(str(font_path))
    name = font["name"]

    print(f"\n{'='*40}")
    print(f"  {font_path.name}")
    print(f"{'='*40}")

    for r in name.names:
        if r.platformID == 3 and r.nameID in (1, 2, 4, 5):
            labels = {1: "Family", 2: "Style", 4: "Full", 5: "Version"}
            print(f"  {labels[r.nameID]}: {r.toUnicode()}")

    if "OS/2" in font:
        os2 = font["OS/2"]
        print(f"  UPM: {font['head'].unitsPerEm}")
        print(f"  Ascender: {os2.sTypoAscender}")
        print(f"  Descender: {os2.sTypoDescender}")

    is_variable = "fvar" in font
    print(f"  Variable: {'Yes' if is_variable else 'No (static)'}")

    glyphs = font.getGlyphOrder()
    print(f"  Glyphs: {len(glyphs)}")

    size_kb = font_path.stat().st_size / 1024
    print(f"  Size: {size_kb:.0f} KB")
    print(f"{'='*40}")

    font.close()


def build_instance(source_path, suffix, wdth, wght, style_name):
    """하나의 인스턴스 빌드."""
    print(f"\n── {FAMILY_NAME} {style_name} (wdth={wdth}, wght={wght}) ──")

    font = instance_font(source_path, wdth, wght)
    rename_font(font, style_name)
    strip_hints(font)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    ttf_path = BUILD_DIR / f"CKSans-{suffix}.ttf"
    font.save(str(ttf_path))
    font.close()
    print(f"  TTF: {ttf_path.name} ({ttf_path.stat().st_size / 1024:.0f} KB)")

    woff2_path = build_woff2(ttf_path)

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(woff2_path, PREVIEW_DIR / woff2_path.name)
    shutil.copy2(ttf_path, PREVIEW_DIR / ttf_path.name)
    print(f"  Copied to preview/")

    print_info(ttf_path)
    return ttf_path


def main():
    source_path = find_source()
    print(f"Source: {source_path.name}")

    for suffix, wdth, wght, style_name in INSTANCES:
        build_instance(source_path, suffix, wdth, wght, style_name)


if __name__ == "__main__":
    main()
