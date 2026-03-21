#!/usr/bin/env python3
"""
수직 인라인 컷 테스트 — H 글자 1개에만 적용.
ExtraBold Condensed (wght:800, wdth:75) static instance 기준.
결과물을 preview에서 확인 후 전체 적용 여부 결정.
"""

import pathops
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.recordingPen import RecordingPen

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"

# 컷 파라미터 (나중에 조정 가능)
CUT_WIDTH = 18      # 컷(빈 공간) 두께
CUT_SPACING = 55    # 컷 간격 (center to center)


def apply_vertical_cuts(font, glyph_name, cut_width, cut_spacing):
    """글리프에 수직 인라인 컷 적용 (pathops boolean difference)."""
    glyf_table = font["glyf"]

    if glyph_name not in glyf_table:
        print(f"  Warning: '{glyph_name}' not found")
        return False

    glyph = glyf_table[glyph_name]

    if glyph.numberOfContours <= 0 and not glyph.isComposite():
        return False

    # 컴포지트면 분해
    if glyph.isComposite():
        glyphset = font.getGlyphSet()
        rec = RecordingPen()
        glyphset[glyph_name].draw(rec)
        pen = TTGlyphPen(None)
        rec.replay(pen)
        glyf_table[glyph_name] = pen.glyph()
        glyph = glyf_table[glyph_name]

    # 원본 글리프 → pathops Path
    glyphset = font.getGlyphSet()
    glyph_path = pathops.Path()
    glyphset[glyph_name].draw(glyph_path.getPen())

    # 바운딩 박스
    bounds = glyph_path.bounds
    if bounds is None:
        return False
    x_min, y_min, x_max, y_max = bounds

    # 커터 생성: 수직 직사각형 배열
    cutter = pathops.Path()
    pen = cutter.getPen()

    x = x_min + cut_spacing
    cut_count = 0
    while x < x_max:
        half = cut_width / 2
        # 수직 직사각형 (글리프 전체 높이 + 여유)
        pen.moveTo((x - half, y_min - 100))
        pen.lineTo((x + half, y_min - 100))
        pen.lineTo((x + half, y_max + 100))
        pen.lineTo((x - half, y_max + 100))
        pen.closePath()
        x += cut_spacing
        cut_count += 1

    if cut_count == 0:
        return False

    # Boolean difference: 원본 - 커터
    result = pathops.Path()
    pathops.op(glyph_path, cutter, pathops.PathOp.DIFFERENCE, result)

    # 결과를 TrueType 글리프로 변환
    tt_pen = TTGlyphPen(None)
    result.draw(tt_pen)
    glyf_table[glyph_name] = tt_pen.glyph()

    print(f"  '{glyph_name}': {cut_count} vertical cuts applied")
    return True


def main():
    source = BUILD_DIR / "CKSans-Variable.ttf"
    if not source.exists():
        print("Error: build/CKSans-Variable.ttf not found. Run 'make modify-params' first.")
        return

    print("Extracting ExtraBold Condensed static instance...")
    font = TTFont(str(source))
    instantiateVariableFont(font, {"wght": 800, "wdth": 75})

    print(f"\nApplying vertical inline cuts (width={CUT_WIDTH}, spacing={CUT_SPACING})...")

    # 테스트 글리프들
    test_chars = "H"
    cmap = font.getBestCmap()

    for char in test_chars:
        code = ord(char)
        glyph_name = cmap.get(code)
        if glyph_name:
            apply_vertical_cuts(font, glyph_name, CUT_WIDTH, CUT_SPACING)

    # 저장
    out_path = BUILD_DIR / "CKSans-InlineTest.ttf"
    font.save(str(out_path))
    font.close()

    # WOFF2도 생성
    font2 = TTFont(str(out_path))
    font2.flavor = "woff2"
    woff2_path = BUILD_DIR / "CKSans-InlineTest.woff2"
    font2.save(str(woff2_path))
    font2.close()

    print(f"\nSaved: {out_path}")
    print(f"Saved: {woff2_path}")
    print(f"\nH 글자만 인라인 컷 적용됨. preview에서 확인하세요.")


if __name__ == "__main__":
    main()
