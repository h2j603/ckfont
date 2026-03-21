#!/usr/bin/env python3
"""
CK Sans 글리프 아웃라인을 JSON으로 추출.
p5.js 웹 에디터에서 사용할 폴리곤 데이터를 생성한다.
곡선은 직선 세그먼트로 플래트닝하여 폴리곤화.
"""

import json
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import RecordingPen

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
PREVIEW_DIR = ROOT / "preview"

CHARS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "0123456789.,;:!?-'\"()/@#&*+=_~ "
)

INSTANCES = [
    {"key": "extrabold", "name": "CK Sans ExtraBold", "wght": 800, "wdth": 75},
]

FLATTEN_STEPS = 16  # 곡선당 직선 세그먼트 수 (높을수록 부드러움)


def flatten_qcurve(points, steps=FLATTEN_STEPS):
    """Quadratic B-spline → 직선 근사. implied on-curve 포인트 처리."""
    if len(points) <= 2:
        return points

    result = []
    on_start = points[0]
    off_curves = points[1:-1]
    on_end = points[-1]

    # off-curve 사이에 implied on-curve 삽입
    expanded = [on_start]
    for i, off in enumerate(off_curves):
        expanded.append(off)
        if i < len(off_curves) - 1:
            nxt = off_curves[i + 1]
            expanded.append(((off[0] + nxt[0]) / 2, (off[1] + nxt[1]) / 2))
    expanded.append(on_end)

    # 2포인트씩 quadratic bezier 플래트닝
    result.append(expanded[0])
    i = 0
    while i < len(expanded) - 2:
        p0 = expanded[i]
        p1 = expanded[i + 1]
        p2 = expanded[i + 2]
        for t_idx in range(1, steps + 1):
            t = t_idx / steps
            mt = 1 - t
            x = mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0]
            y = mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]
            result.append((x, y))
        i += 2

    return result


def flatten_cubic(points, steps=FLATTEN_STEPS):
    """Cubic bezier → 직선 근사."""
    if len(points) < 4:
        return points
    result = [points[0]]
    for i in range(0, len(points) - 3, 3):
        p0, p1, p2, p3 = points[i], points[i + 1], points[i + 2], points[i + 3]
        for t_idx in range(1, steps + 1):
            t = t_idx / steps
            mt = 1 - t
            x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
            y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
            result.append((x, y))
    return result


def glyph_to_paths(font, glyph_name):
    """글리프를 플래트닝된 폴리곤 패스 리스트로 변환."""
    glyphset = font.getGlyphSet()
    if glyph_name not in glyphset:
        return []

    rec = RecordingPen()
    glyphset[glyph_name].draw(rec)

    paths = []
    current = []

    for op, args in rec.value:
        if op == "moveTo":
            if len(current) >= 3:
                paths.append(current)
            current = [list(args[0])]
        elif op == "lineTo":
            current.append(list(args[0]))
        elif op == "qCurveTo":
            pts = [tuple(current[-1])] + [tuple(a) for a in args]
            flat = flatten_qcurve(pts)
            for p in flat[1:]:
                current.append(list(p))
        elif op == "curveTo":
            pts = [tuple(current[-1])] + [tuple(a) for a in args]
            flat = flatten_cubic(pts)
            for p in flat[1:]:
                current.append(list(p))
        elif op in ("closePath", "endPath"):
            if len(current) >= 3:
                paths.append(current)
            current = []

    if len(current) >= 3:
        paths.append(current)

    # 정수 좌표 + 중복 제거
    clean = []
    for path in paths:
        pts = [[round(p[0]), round(p[1])] for p in path]
        deduped = [pts[0]]
        for p in pts[1:]:
            if p != deduped[-1]:
                deduped.append(p)
        if len(deduped) >= 3:
            clean.append(deduped)

    return clean


def main():
    source = BUILD_DIR / "CKSans-Variable.ttf"
    if not source.exists():
        print("Error: build/CKSans-Variable.ttf not found")
        sys.exit(1)

    # 메타 정보
    font = TTFont(str(source))
    meta = {
        "unitsPerEm": font["head"].unitsPerEm,
        "ascender": font["OS/2"].sTypoAscender,
        "descender": font["OS/2"].sTypoDescender,
    }
    font.close()

    output = {"meta": meta, "instances": {}}

    for inst in INSTANCES:
        print(f"Extracting {inst['name']}...")
        font = TTFont(str(source))
        instantiateVariableFont(font, {"wght": inst["wght"], "wdth": inst["wdth"]})

        cmap = font.getBestCmap()
        hmtx = font["hmtx"]
        glyphs = {}

        for char in CHARS:
            code = ord(char)
            glyph_name = cmap.get(code)
            if not glyph_name:
                continue

            paths = glyph_to_paths(font, glyph_name)
            advance = hmtx[glyph_name][0] if glyph_name in hmtx.metrics else 0

            glyphs[char] = {
                "n": glyph_name,
                "u": code,
                "a": advance,
                "p": paths,
            }

        output["instances"][inst["key"]] = {
            "name": inst["name"],
            "wght": inst["wght"],
            "wdth": inst["wdth"],
            "glyphs": glyphs,
        }

        font.close()
        print(f"  {len(glyphs)} glyphs")

    out_path = PREVIEW_DIR / "glyphs.json"
    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"\nSaved: {out_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
