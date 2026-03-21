#!/usr/bin/env python3
"""
수직 인라인 컷 테스트 — H 글자 1개에만 적용.
ExtraBold Condensed (wght:800, wdth:75) static instance 기준.
pyclipper로 boolean difference 수행.
"""

import pyclipper
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"

# 컷 파라미터
CUT_WIDTH = 18      # 컷(빈 공간) 두께
CUT_SPACING = 55    # 컷 간격 (center to center)
SCALE = 1           # pyclipper는 정수 좌표 — fontTools도 정수이므로 스케일 불필요


def glyph_to_polygons(font, glyph_name):
    """TrueType 글리프를 폴리곤 리스트로 변환.
    quadratic 곡선은 직선 세그먼트로 플래트닝한다."""
    glyphset = font.getGlyphSet()
    rec = RecordingPen()
    glyphset[glyph_name].draw(rec)

    polygons = []
    current = []

    for op, args in rec.value:
        if op == "moveTo":
            if current:
                polygons.append(current)
            current = [args[0]]
        elif op == "lineTo":
            current.append(args[0])
        elif op == "qCurveTo":
            # Quadratic B-spline → 직선 근사 (8 세그먼트/곡선)
            pts = [current[-1]] + list(args)
            flattened = flatten_qcurve(pts, steps=8)
            current.extend(flattened[1:])  # 첫 점은 이미 current에 있음
        elif op == "curveTo":
            # Cubic bezier → 직선 근사
            pts = [current[-1]] + list(args)
            flattened = flatten_cubic(pts, steps=8)
            current.extend(flattened[1:])
        elif op in ("closePath", "endPath"):
            if current:
                polygons.append(current)
            current = []

    if current:
        polygons.append(current)

    # 정수 좌표로 변환 (pyclipper 요구사항)
    int_polygons = []
    for poly in polygons:
        int_poly = [(int(round(x)), int(round(y))) for x, y in poly]
        # 중복 포인트 제거
        deduped = [int_poly[0]]
        for p in int_poly[1:]:
            if p != deduped[-1]:
                deduped.append(p)
        if len(deduped) >= 3:
            int_polygons.append(deduped)

    return int_polygons


def flatten_qcurve(points, steps=8):
    """Quadratic B-spline (TrueType) → 직선 근사.
    points: [on, off1, off2, ..., on] (implied on-curves between off-curves)."""
    if len(points) <= 1:
        return points
    if len(points) == 2:
        return points  # 직선

    result = [points[0]]

    # TrueType implied on-curve 처리
    on_curves = [points[0]]
    off_curves = points[1:-1]
    last_on = points[-1]

    # off-curve 사이에 implied on-curve 삽입
    expanded = [on_curves[0]]
    for i, off in enumerate(off_curves):
        expanded.append(off)
        if i < len(off_curves) - 1:
            # Implied on-curve = midpoint
            next_off = off_curves[i + 1]
            mid = ((off[0] + next_off[0]) / 2, (off[1] + next_off[1]) / 2)
            expanded.append(mid)
    expanded.append(last_on)

    # 이제 expanded는 [on, off, on, off, on, ...] 순서
    i = 0
    while i < len(expanded) - 2:
        p0 = expanded[i]
        p1 = expanded[i + 1]
        p2 = expanded[i + 2]
        # Quadratic bezier flatten
        for t_idx in range(1, steps + 1):
            t = t_idx / steps
            mt = 1 - t
            x = mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0]
            y = mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]
            result.append((x, y))
        i += 2

    return result


def flatten_cubic(points, steps=8):
    """Cubic bezier → 직선 근사."""
    if len(points) < 4:
        return points
    result = [points[0]]
    for i in range(0, len(points) - 3, 3):
        p0, p1, p2, p3 = points[i], points[i+1], points[i+2], points[i+3]
        for t_idx in range(1, steps + 1):
            t = t_idx / steps
            mt = 1 - t
            x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
            y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
            result.append((x, y))
    return result


def make_vertical_cuts(x_min, x_max, y_min, y_max, cut_width, cut_spacing):
    """수직 컷 직사각형들을 폴리곤 리스트로 생성."""
    cuts = []
    margin = 50
    x = x_min + cut_spacing
    while x < x_max:
        half = cut_width / 2
        rect = [
            (int(x - half), int(y_min - margin)),
            (int(x + half), int(y_min - margin)),
            (int(x + half), int(y_max + margin)),
            (int(x - half), int(y_max + margin)),
        ]
        cuts.append(rect)
        x += cut_spacing
    return cuts


def polygons_to_ttglyph(polygons):
    """폴리곤 리스트를 TrueType 글리프로 변환."""
    pen = TTGlyphPen(None)
    for poly in polygons:
        if len(poly) < 3:
            continue
        pen.moveTo(poly[0])
        for pt in poly[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.glyph()


def apply_vertical_cuts(font, glyph_name, cut_width, cut_spacing):
    """글리프에 수직 인라인 컷 적용."""
    glyf_table = font["glyf"]

    if glyph_name not in glyf_table:
        print(f"  Warning: '{glyph_name}' not found")
        return False

    # 글리프를 폴리곤으로 변환
    polygons = glyph_to_polygons(font, glyph_name)
    if not polygons:
        print(f"  Warning: '{glyph_name}' empty polygons")
        return False

    # 바운딩 박스
    all_pts = [p for poly in polygons for p in poly]
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # 수직 컷 생성
    cuts = make_vertical_cuts(x_min, x_max, y_min, y_max, cut_width, cut_spacing)
    if not cuts:
        return False

    # pyclipper boolean difference
    pc = pyclipper.Pyclipper()
    pc.AddPaths(polygons, pyclipper.PT_SUBJECT, True)
    pc.AddPaths(cuts, pyclipper.PT_CLIP, True)

    result = pc.Execute(
        pyclipper.CT_DIFFERENCE,
        pyclipper.PFT_NONZERO,
        pyclipper.PFT_NONZERO
    )

    if not result:
        print(f"  Warning: '{glyph_name}' boolean difference returned empty")
        return False

    # 결과를 TrueType 글리프로 변환
    result_tuples = [[(p[0], p[1]) for p in contour] for contour in result]
    new_glyph = polygons_to_ttglyph(result_tuples)
    glyf_table[glyph_name] = new_glyph

    print(f"  '{glyph_name}': {len(cuts)} vertical cuts → {len(result)} contours")
    return True


def main():
    source = BUILD_DIR / "CKSans-Variable.ttf"
    if not source.exists():
        print("Error: build/CKSans-Variable.ttf not found.")
        return

    print("Extracting ExtraBold Condensed static instance...")
    font = TTFont(str(source))
    instantiateVariableFont(font, {"wght": 800, "wdth": 75})

    print(f"\nApplying vertical inline cuts (width={CUT_WIDTH}, spacing={CUT_SPACING})...")

    cmap = font.getBestCmap()
    for char in "H":
        glyph_name = cmap.get(ord(char))
        if glyph_name:
            apply_vertical_cuts(font, glyph_name, CUT_WIDTH, CUT_SPACING)

    # 저장
    out_path = BUILD_DIR / "CKSans-InlineTest.ttf"
    font.save(str(out_path))

    # WOFF2
    font2 = TTFont(str(out_path))
    font2.flavor = "woff2"
    woff2_path = BUILD_DIR / "CKSans-InlineTest.woff2"
    font2.save(str(woff2_path))
    font2.close()
    font.close()

    print(f"\nSaved: {out_path}")
    print(f"Saved: {woff2_path}")


if __name__ == "__main__":
    main()
