#!/usr/bin/env python3
"""
CK Sans 모듈러 컷 변형 생성.

글리프를 세로 컬럼 그리드로 분해하여 둥근 사각형 모듈로 재구성한다.
각 글자는 일정한 폭의 세로 모듈들의 조합으로 표현됨.

원리:
  1. 글리프를 세로 컬럼 직사각형과 교차(INTERSECTION)
  2. 교차 결과의 각 컨투어 → bbox 추출
  3. bbox에 둥근 사각형 모듈 배치
  4. 모든 모듈을 합쳐서 새 글리프로

파라미터:
  --module-w  모듈 폭 (기본 80)
  --gap       모듈 간 갭 (기본 35)
  --radius    코너 라운드 반지름 (기본 40, =w/2면 캡슐형)
  --dry-run   저장하지 않고 결과만 출력

사용법:
  python3 scripts/modular_cut.py [--module-w 55] [--gap 22] [--radius 14]
"""

import sys
import shutil
import math
from pathlib import Path

import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
BASE_PATH = BUILD_DIR / "CKSans-Base.ttf"
OUT_NAME = "CKSans-Cut"

# ── 커팅 대상 ──
CUT_TARGETS = set()
CUT_TARGETS.update(chr(c) for c in range(0x41, 0x5B))  # A-Z
CUT_TARGETS.update(chr(c) for c in range(0x61, 0x7B))  # a-z
CUT_TARGETS.update(chr(c) for c in range(0x30, 0x3A))  # 0-9

SKIP_GLYPHS = {"i", "l", ".", ",", "'", '"', "-", "_", " "}

# 최소 모듈 크기 (이보다 작으면 무시)
MIN_MODULE_W = 10
MIN_MODULE_H = 25  # 짧은 건 정원(원)으로 표현하므로 낮게


def circle_path(cx, cy, r):
    """정원 (완전한 원) pathops.Path 생성."""
    # cubic Bézier로 원 근사 (4개 세그먼트)
    k = r * 0.5522847498  # 4/3 * (sqrt(2) - 1)
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((cx + r, cy))
    pen.curveTo((cx + r, cy + k), (cx + k, cy + r), (cx, cy + r))
    pen.curveTo((cx - k, cy + r), (cx - r, cy + k), (cx - r, cy))
    pen.curveTo((cx - r, cy - k), (cx - k, cy - r), (cx, cy - r))
    pen.curveTo((cx + k, cy - r), (cx + r, cy - k), (cx + r, cy))
    pen.closePath()
    return path


def rounded_rect_path(x0, y0, x1, y1, r):
    """둥근 사각형 또는 정원을 pathops.Path로 생성.

    높이 <= 너비 → 정원 (완전한 원)
    높이 > 너비 → 캡슐형 둥근 사각형
    """
    w = x1 - x0
    h = y1 - y0

    # 높이가 너비 이하 → 정원으로
    if h <= w:
        cr = h / 2
        return circle_path((x0 + x1) / 2, (y0 + y1) / 2, cr)

    # 캡슐형
    r = min(r, w / 2, h / 2)

    path = pathops.Path()
    pen = path.getPen()

    pen.moveTo((x0, y0 + r))
    pen.lineTo((x0, y1 - r))
    pen.qCurveTo((x0, y1), (x0 + r, y1))
    pen.lineTo((x1 - r, y1))
    pen.qCurveTo((x1, y1), (x1, y1 - r))
    pen.lineTo((x1, y0 + r))
    pen.qCurveTo((x1, y0), (x1 - r, y0))
    pen.lineTo((x0 + r, y0))
    pen.qCurveTo((x0, y0), (x0, y0 + r))

    pen.closePath()
    return path


def scanline_spans(glyph_path, x):
    """수직 스캔라인: x 위치에서 글리프의 채워진 y 구간 반환.

    even-odd 규칙으로 안/밖 판별 → D, O 등 카운터 정확히 처리.
    """
    # pathops Path에서 세그먼트 추출
    rec = RecordingPen()
    glyph_path.draw(rec)

    # 모든 직선 세그먼트로 변환 (곡선은 세분화)
    edges = []
    cur = None
    for op_name, args in rec.value:
        if op_name == "moveTo":
            cur = args[0]
        elif op_name == "lineTo":
            if cur is not None:
                edges.append((cur, args[0]))
            cur = args[0]
        elif op_name == "curveTo":
            # cubic → 직선 세분화
            if cur is not None:
                p0 = cur
                steps = 8
                for s in range(1, steps + 1):
                    t = s / steps
                    mt = 1 - t
                    px = mt**3*p0[0] + 3*mt**2*t*args[0][0] + 3*mt*t**2*args[1][0] + t**3*args[2][0]
                    py = mt**3*p0[1] + 3*mt**2*t*args[0][1] + 3*mt*t**2*args[1][1] + t**3*args[2][1]
                    edges.append((cur, (px, py)))
                    cur = (px, py)
            cur = args[-1]
        elif op_name == "qCurveTo":
            if cur is not None:
                p0 = cur
                steps = 8
                for s in range(1, steps + 1):
                    t = s / steps
                    mt = 1 - t
                    px = mt**2*p0[0] + 2*mt*t*args[0][0] + t**2*args[1][0]
                    py = mt**2*p0[1] + 2*mt*t*args[0][1] + t**2*args[1][1]
                    edges.append((cur, (px, py)))
                    cur = (px, py)
            cur = args[-1]
        elif op_name == "closePath":
            cur = None

    # x 위치에서 교차하는 y 값 수집
    hits = []
    for (ax, ay), (bx, by) in edges:
        if (ax <= x < bx) or (bx <= x < ax):
            t = (x - ax) / (bx - ax)
            hits.append(ay + t * (by - ay))

    hits.sort()

    # even-odd 페어링
    spans = []
    for i in range(0, len(hits) - 1, 2):
        spans.append((hits[i], hits[i + 1]))
    return spans


def extract_modules(glyph_path, glyph_obj, module_w, gap, hmtx_entry):
    """글리프에서 모듈 bbox 목록 추출.

    스캔라인 방식: 컬럼 내 여러 x에서 수직 스캔 → 채워진 y 구간 → 모듈.
    카운터(D, O 등 내부 구멍)를 정확히 처리.
    """
    pitch = module_w + gap

    # 글리프 중심 기준으로 그리드 정렬
    glyph_cx = (glyph_obj.xMin + glyph_obj.xMax) / 2
    glyph_w = glyph_obj.xMax - glyph_obj.xMin

    n_cols = max(1, int(round(glyph_w / pitch)))
    total_grid_w = n_cols * module_w + (n_cols - 1) * gap
    grid_start = glyph_cx - total_grid_w / 2

    modules = []

    for ci in range(n_cols):
        col_x = grid_start + ci * pitch

        # 컬럼 내 3개 x에서 스캔 (좌/중/우)
        probes = [col_x + module_w * 0.2,
                  col_x + module_w * 0.5,
                  col_x + module_w * 0.8]

        all_spans = []
        for px in probes:
            all_spans.extend(scanline_spans(glyph_path, px))

        # y 구간 병합
        all_spans.sort()
        merged = []
        for a, b in all_spans:
            if b - a < 2:
                continue
            if merged and a <= merged[-1][1] + MIN_MODULE_H * 0.3:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))

        # 모듈 생성
        for y0, y1 in merged:
            if y1 - y0 >= MIN_MODULE_H:
                modules.append((col_x, y0, col_x + module_w, y1))

    return modules


def modules_to_ttglyph(modules, radius, glyf_table):
    """모듈 bbox 목록 → 둥근 사각형으로 구성된 TTGlyph."""
    if not modules:
        return None

    # 모든 모듈의 둥근 사각형을 합치기 (union)
    combined = pathops.Path()
    for x0, y0, x1, y1 in modules:
        rrect = rounded_rect_path(x0, y0, x1, y1, radius)
        combined = pathops.op(
            combined, rrect,
            pathops.PathOp.UNION,
            fix_winding=True, clockwise=True,
        )

    # pathops (cubic) → recording → cu2qu → TTGlyph
    rec = RecordingPen()
    combined.draw(rec)

    if not rec.value:
        return None

    tt_pen = TTGlyphPen(glyf_table)
    cu2qu = Cu2QuPen(tt_pen, max_err=1.0, reverse_direction=False)

    for op_name, args in rec.value:
        getattr(cu2qu, op_name)(*args)

    try:
        return tt_pen.glyph()
    except Exception:
        return None


def main():
    dry_run = "--dry-run" in sys.argv
    module_w = 80
    gap = 35
    radius = 40

    # 인자 파싱
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--module-w" and i + 1 < len(args):
            module_w = int(args[i + 1])
        elif arg == "--gap" and i + 1 < len(args):
            gap = int(args[i + 1])
        elif arg == "--radius" and i + 1 < len(args):
            radius = int(args[i + 1])

    pitch = module_w + gap

    if not BASE_PATH.exists():
        print(f"Error: {BASE_PATH} not found. Run 'make base' first.")
        sys.exit(1)

    font = TTFont(str(BASE_PATH))
    glyf = font["glyf"]
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    hmtx = font["hmtx"]

    print(f"Modular cut: module_w={module_w}, gap={gap}, radius={radius}, pitch={pitch}")

    modified = 0
    errors = 0

    for char in sorted(CUT_TARGETS):
        cp = ord(char)
        glyph_name = cmap.get(cp)
        if not glyph_name or glyph_name not in glyf:
            continue

        g = glyf[glyph_name]
        if g.isComposite() or g.numberOfContours <= 0:
            continue
        if char in SKIP_GLYPHS:
            continue

        # 너무 좁은 글리프는 스킵
        glyph_w = g.xMax - g.xMin
        if glyph_w < module_w:
            continue

        try:
            # 글리프 → pathops Path
            glyph_path = pathops.Path()
            gs[glyph_name].draw(glyph_path.getPen())

            # 모듈 추출
            modules = extract_modules(
                glyph_path, g, module_w, gap, hmtx[glyph_name]
            )

            if not modules:
                continue

            # 모듈 → 둥근 사각형 TTGlyph
            new_glyph = modules_to_ttglyph(modules, radius, glyf)
            if new_glyph is None:
                print(f"  '{char}': build failed")
                errors += 1
                continue

            glyf[glyph_name] = new_glyph
            modified += 1
            print(f"  '{char}': {len(modules)} modules")

        except Exception as e:
            print(f"  '{char}': error — {e}")
            errors += 1

    print(f"\nModified {modified} glyph(s), {errors} error(s).")

    if dry_run:
        print("[Dry run — not saved]")
        font.close()
        return

    # 이름 변경
    name_table = font["name"]
    for record in name_table.names:
        text = record.toUnicode()
        if "CK Sans" in text:
            new_text = text.replace("CK Sans", "CK Sans Cut")
            name_table.setName(
                new_text, record.nameID, record.platformID,
                record.platEncID, record.langID,
            )

    # 저장
    ttf_path = BUILD_DIR / f"{OUT_NAME}.ttf"
    font.save(str(ttf_path))
    font.close()
    print(f"Saved: {ttf_path}")

    # WOFF2
    woff2_path = BUILD_DIR / f"{OUT_NAME}.woff2"
    woff2_font = TTFont(str(ttf_path))
    woff2_font.flavor = "woff2"
    woff2_font.save(str(woff2_path))
    woff2_font.close()
    print(f"WOFF2: {woff2_path.name}")

    # preview 복사
    preview_dir = ROOT / "preview"
    if preview_dir.exists():
        shutil.copy2(ttf_path, preview_dir / ttf_path.name)
        shutil.copy2(woff2_path, preview_dir / woff2_path.name)
        print("Copied to preview/")

    sz = ttf_path.stat().st_size // 1024
    print(f"TTF: {sz}KB")


if __name__ == "__main__":
    main()
