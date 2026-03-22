#!/usr/bin/env python3
"""
CK Sans CJK 폰트 빌드.

Noto Sans CJK OTF (CFF 아웃라인) → TrueType 변환 + 서브셋 + Condensed 스케일.
CFF→TrueType 5단계 변환을 모두 수행하여 Safari/Core Text 호환성 보장.

변환 체크리스트:
  1. CFF 3차 → TrueType 2차 곡선 변환
  2. CFF 테이블 제거, glyf+loca 생성
  3. VORG 테이블 제거
  4. maxp v1.0 (TrueType) 업데이트
  5. sfntVersion → '\x00\x01\x00\x00' (TrueType)

출력:
  build/CKSans-KR-Regular.ttf / .woff2
  build/CKSans-JP-Regular.ttf / .woff2
  build/CKSans-SC-Regular.ttf / .woff2
"""

import shutil
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools import ttLib

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources" / "NotoSans"
BUILD_DIR = ROOT / "build"
PREVIEW_DIR = ROOT / "preview"

FAMILY_NAME = "CK Sans"
VERSION = "0.3.0"

# CJK 인스턴스: (소스 파일명, 출력 접미사, 스타일명, 스크립트 라벨)
CJK_INSTANCES = [
    ("NotoSansKR-Regular.otf",  "KR-Regular", "KR Regular",  "KR"),
    ("NotoSansJP-Regular.otf",  "JP-Regular", "JP Regular",  "JP"),
    ("NotoSansSC-Regular.otf",  "SC-Regular", "SC Regular",  "SC"),
]

# Condensed 스케일 (wdth=62.5 상당)
X_SCALE = 0.732

# 서브셋: 유지할 유니코드 범위
# 한글: AC00-D7AF (11,172자), 라틴: 0020-007F, 기호 등
SUBSET_RANGES_KR = [
    (0x0020, 0x007F),   # Basic Latin
    (0x00A0, 0x00FF),   # Latin-1 Supplement
    (0x2000, 0x206F),   # General Punctuation
    (0x3000, 0x303F),   # CJK Symbols
    (0x3130, 0x318F),   # Hangul Compatibility Jamo
    (0xAC00, 0xD7AF),   # Hangul Syllables
    (0xFE10, 0xFE1F),   # Vertical Forms
    (0xFF00, 0xFFEF),   # Halfwidth/Fullwidth
]

SUBSET_RANGES_JP = [
    (0x0020, 0x007F),
    (0x00A0, 0x00FF),
    (0x2000, 0x206F),
    (0x3000, 0x303F),   # CJK Symbols
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xFF00, 0xFFEF),
]

SUBSET_RANGES_SC = [
    (0x0020, 0x007F),
    (0x00A0, 0x00FF),
    (0x2000, 0x206F),
    (0x3000, 0x303F),
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xFF00, 0xFFEF),
]

SUBSET_MAP = {
    "KR": SUBSET_RANGES_KR,
    "JP": SUBSET_RANGES_JP,
    "SC": SUBSET_RANGES_SC,
}


def codepoint_in_ranges(cp, ranges):
    """유니코드 코드포인트가 범위 목록에 포함되는지."""
    return any(lo <= cp <= hi for lo, hi in ranges)


def convert_cff_to_truetype(font):
    """CFF 아웃라인 → TrueType (glyf+loca) 변환.

    5단계 변환 체크리스트 모두 수행.
    """
    print("  [1/5] CFF cubic → TrueType quadratic 곡선 변환...")

    glyph_order = font.getGlyphOrder()
    glyf_table = ttLib.getTableClass("glyf")()
    glyf_table.glyphs = {}
    glyf_table.glyphOrder = glyph_order

    cff = font["CFF "]
    top_dict = cff.cff.topDictIndex[0]
    charset = top_dict.charset
    char_strings = top_dict.CharStrings

    gs = font.getGlyphSet()
    converted = 0
    errors = 0

    for gname in glyph_order:
        try:
            tt_pen = TTGlyphPen(None)
            cu2qu_pen = Cu2QuPen(tt_pen, max_err=1.0, reverse_direction=False)

            gs[gname].draw(cu2qu_pen)

            glyf_table.glyphs[gname] = tt_pen.glyph()
            converted += 1
        except Exception:
            # 빈 글리프 (space 등)
            from fontTools.ttLib.tables._g_l_y_f import Glyph
            glyf_table.glyphs[gname] = Glyph()
            errors += 1

    print(f"    Converted {converted} glyphs ({errors} empty/errors)")

    # [2/5] CFF 테이블 제거, glyf+loca 추가
    print("  [2/5] CFF 테이블 제거, glyf+loca 생성...")
    for table_tag in ("CFF ", "CFF2"):
        if table_tag in font:
            del font[table_tag]

    font["glyf"] = glyf_table

    # loca 테이블은 save 시 자동 생성되지만, 빈 테이블을 먼저 세팅
    from fontTools.ttLib.tables._l_o_c_a import table__l_o_c_a
    font["loca"] = table__l_o_c_a()

    # head.glyphDataFormat = 0 (TrueType)
    font["head"].glyphDataFormat = 0
    # head.indexToLocFormat은 save 시 자동 설정

    # [3/5] VORG 테이블 제거
    print("  [3/5] VORG 테이블 제거...")
    for cff_only in ("VORG",):
        if cff_only in font:
            del font[cff_only]
            print(f"    Removed {cff_only}")

    # [4/5] maxp v1.0 업데이트
    print("  [4/5] maxp → v1.0 (TrueType)...")
    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000

    # TrueType 필수 필드 계산
    max_points = 0
    max_contours = 0
    max_comp_points = 0
    max_comp_contours = 0

    for gname in glyph_order:
        g = glyf_table.glyphs[gname]
        if g.numberOfContours > 0:
            n_pts = sum(len(c) for c in g.coordinates) if hasattr(g, 'coordinates') else 0
            # coordinates is a flat list, count from endPtsOfContours
            if hasattr(g, 'endPtsOfContours') and g.endPtsOfContours:
                n_pts = g.endPtsOfContours[-1] + 1
                max_points = max(max_points, n_pts)
                max_contours = max(max_contours, g.numberOfContours)
        elif g.isComposite():
            # Composite glyphs — point/contour count from components
            max_comp_points = max(max_comp_points, 128)  # 안전한 추정값
            max_comp_contours = max(max_comp_contours, 16)

    maxp.maxPoints = max_points
    maxp.maxContours = max_contours
    maxp.maxCompositePoints = max_comp_points
    maxp.maxCompositeContours = max_comp_contours
    maxp.maxZones = 2
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.maxComponentElements = max(1, len([
        g for g in glyph_order
        if gname in glyf_table.glyphs and glyf_table.glyphs.get(gname, None)
        and hasattr(glyf_table.glyphs.get(gname), 'isComposite')
        and glyf_table.glyphs[gname].isComposite()
    ]))
    maxp.maxComponentDepth = 1

    # [5/5] sfntVersion 변경 — 핵심!
    print("  [5/5] sfntVersion → TrueType (\\x00\\x01\\x00\\x00)...")
    font.sfntVersion = "\x00\x01\x00\x00"

    print("  CFF→TrueType 변환 완료!")


def subset_font(font, script_label):
    """유니코드 범위 기반 서브셋."""
    ranges = SUBSET_MAP.get(script_label)
    if not ranges:
        print(f"  Skip subsetting: no range for {script_label}")
        return

    cmap = font.getBestCmap()
    if not cmap:
        print("  Warning: no cmap found")
        return

    keep_cps = {cp for cp in cmap if codepoint_in_ranges(cp, ranges)}
    remove_cps = set(cmap.keys()) - keep_cps

    # cmap에서 제거
    for table in font["cmap"].tables:
        if hasattr(table, "cmap"):
            for cp in remove_cps:
                table.cmap.pop(cp, None)

    before = len(cmap)
    after = len(keep_cps)
    print(f"  Subset: {before} → {after} codepoints ({before - after} removed)")


def apply_condensed_scale(font, x_scale):
    """Condensed 스케일 적용 (x축만 축소)."""
    if "glyf" not in font:
        print("  Warning: no glyf table for scaling")
        return

    glyf = font["glyf"]
    hmtx = font["hmtx"]
    scaled = 0

    for gname in font.getGlyphOrder():
        g = glyf[gname]

        # advance width 스케일
        aw, lsb = hmtx[gname]
        new_aw = int(round(aw * x_scale))
        new_lsb = int(round(lsb * x_scale))
        hmtx[gname] = (new_aw, new_lsb)

        if g.numberOfContours > 0 and hasattr(g, 'coordinates'):
            coords = g.coordinates
            new_coords = [(int(round(x * x_scale)), y) for x, y in coords]
            # GlyphCoordinates 타입 유지
            from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
            g.coordinates = GlyphCoordinates(new_coords)

            # bbox 재계산
            if new_coords:
                xs = [p[0] for p in new_coords]
                g.xMin = min(xs)
                g.xMax = max(xs)

            scaled += 1

    print(f"  Condensed scale x={x_scale}: {scaled} glyphs")


def rename_font(font, style_name):
    """폰트 이름을 CK Sans로 변경."""
    name_table = font["name"]
    full_name = f"{FAMILY_NAME} {style_name}"
    ps_name = full_name.replace(" ", "-")

    entries = {
        0: "Copyright 2024 Condensed Kiwi. Based on Noto Sans (OFL).",
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

    # 나머지 모든 name 레코드에서 'Noto' 잔존 제거 (OFL Reserved Name)
    for record in name_table.names:
        text = record.toUnicode()
        if "Noto" in text and record.nameID not in entries:
            cleaned = text.replace("Noto Sans CJK", "CK Sans")
            cleaned = cleaned.replace("NotoSansCJK", "CKSans")
            cleaned = cleaned.replace("Noto Sans", "CK Sans")
            cleaned = cleaned.replace("NotoSans", "CKSans")
            cleaned = cleaned.replace("Noto", "CK")
            name_table.setName(
                cleaned, record.nameID, record.platformID,
                record.platEncID, record.langID,
            )

    print(f"  Renamed: {full_name}")


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


def build_cjk_instance(source_name, suffix, style_name, script_label):
    """하나의 CJK 인스턴스 빌드."""
    source_path = SOURCES_DIR / source_name
    if not source_path.exists():
        print(f"\n── Skip {source_name}: 파일 없음 ──")
        print(f"  (make download-cjk 실행 필요)")
        return None

    print(f"\n── {FAMILY_NAME} {style_name} ──")
    print(f"  Source: {source_name}")

    font = TTFont(str(source_path))

    # sfntVersion 확인
    print(f"  Original sfntVersion: {repr(font.sfntVersion)}")

    # CFF→TrueType 변환
    if "CFF " in font or "CFF2" in font:
        convert_cff_to_truetype(font)
    else:
        print("  Already TrueType, skipping conversion")

    # 서브셋
    subset_font(font, script_label)

    # Condensed 스케일
    apply_condensed_scale(font, X_SCALE)

    # 이름 변경
    rename_font(font, style_name)

    # 힌팅 제거
    for table_tag in ("fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX", "gasp"):
        if table_tag in font:
            del font[table_tag]

    # 최종 sfntVersion 확인
    assert font.sfntVersion == "\x00\x01\x00\x00", \
        f"sfntVersion이 TrueType이 아님: {repr(font.sfntVersion)}"

    # 저장
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    ttf_path = BUILD_DIR / f"CKSans-{suffix}.ttf"
    font.save(str(ttf_path))
    font.close()
    size_kb = ttf_path.stat().st_size / 1024
    print(f"  TTF: {ttf_path.name} ({size_kb:.0f} KB)")

    # WOFF2
    woff2_path = build_woff2(ttf_path)

    # preview 복사
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ttf_path, PREVIEW_DIR / ttf_path.name)
    shutil.copy2(woff2_path, PREVIEW_DIR / woff2_path.name)
    print(f"  Copied to preview/")

    return ttf_path


def main():
    print("CK Sans CJK 폰트 빌드")
    print("=" * 50)

    built = []
    for source_name, suffix, style_name, script_label in CJK_INSTANCES:
        result = build_cjk_instance(source_name, suffix, style_name, script_label)
        if result:
            built.append(result)

    print(f"\n{'=' * 50}")
    if built:
        print(f"빌드 완료: {len(built)}개 CJK 폰트")
        for p in built:
            print(f"  {p.name}")
    else:
        print("빌드된 폰트 없음. sources/NotoSans/에 CJK OTF가 필요합니다.")
        print("  make download-cjk 실행 또는 수동 다운로드:")
        print("  - NotoSansKR-Regular.otf")
        print("  - NotoSansJP-Regular.otf")
        print("  - NotoSansSC-Regular.otf")


if __name__ == "__main__":
    main()
