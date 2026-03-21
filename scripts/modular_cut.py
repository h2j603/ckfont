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
MIN_MODULE_H = 40  # 너무 짧은 바 제거 (캡슐 r*2 이상은 되어야)


def rounded_rect_path(x0, y0, x1, y1, r):
    """둥근 사각형을 pathops.Path로 생성.

    TrueType quadratic Bézier로 코너를 근사.
    코너 하나당 off-curve 1개 + on-curve 2개.
    """
    w = x1 - x0
    h = y1 - y0
    # 코너 반지름이 사이즈의 절반을 넘지 않게
    r = min(r, w / 2, h / 2)

    path = pathops.Path()
    pen = path.getPen()

    # CW (clockwise) 방향으로 그리기 — TrueType 외곽 기준
    # 시작: 하단 왼쪽 코너의 직선 시작점
    pen.moveTo((x0, y0 + r))

    # 좌측 상행
    pen.lineTo((x0, y1 - r))
    # 좌상 코너 (quadratic: 코너점이 control point)
    pen.qCurveTo((x0, y1), (x0 + r, y1))

    # 상단 우행
    pen.lineTo((x1 - r, y1))
    # 우상 코너
    pen.qCurveTo((x1, y1), (x1, y1 - r))

    # 우측 하행
    pen.lineTo((x1, y0 + r))
    # 우하 코너
    pen.qCurveTo((x1, y0), (x1 - r, y0))

    # 하단 좌행
    pen.lineTo((x0 + r, y0))
    # 좌하 코너
    pen.qCurveTo((x0, y0), (x0, y0 + r))

    pen.closePath()
    return path


def extract_modules(glyph_path, glyph_obj, module_w, gap, hmtx_entry):
    """글리프에서 모듈 bbox 목록 추출.

    세로 컬럼 그리드와 교차시켜 존재하는 영역의 bbox를 반환.
    """
    pitch = module_w + gap
    advance_w, lsb = hmtx_entry

    # 글리프 경계
    y_lo = glyph_obj.yMin - 10
    y_hi = glyph_obj.yMax + 10

    modules = []

    # 글리프 중심 기준으로 그리드 정렬
    glyph_cx = (glyph_obj.xMin + glyph_obj.xMax) / 2
    glyph_w = glyph_obj.xMax - glyph_obj.xMin

    # 필요한 컬럼 수 계산, 중앙 정렬
    n_cols = max(1, int(round(glyph_w / pitch)))
    total_grid_w = n_cols * module_w + (n_cols - 1) * gap
    grid_start = glyph_cx - total_grid_w / 2

    for ci in range(n_cols):
        col_x = grid_start + ci * pitch

        # 이 컬럼의 직사각형 (높이는 넉넉하게)
        col = pathops.Path()
        pen = col.getPen()
        pen.moveTo((col_x, y_lo))
        pen.lineTo((col_x + module_w, y_lo))
        pen.lineTo((col_x + module_w, y_hi))
        pen.lineTo((col_x, y_hi))
        pen.closePath()

        # 교차
        try:
            inter = pathops.op(
                glyph_path, col,
                pathops.PathOp.INTERSECTION,
                fix_winding=True, clockwise=True,
            )
        except Exception:
            continue

        # 결과의 각 컨투어 → 모듈
        # x는 고정(col_x ~ col_x+module_w), y만 교차에서 추출
        rec = RecordingPen()
        inter.draw(rec)

        cur_pts = []
        for op_name, args in rec.value:
            if op_name == "moveTo":
                cur_pts = [args[0]]
            elif op_name in ("lineTo", "curveTo", "qCurveTo"):
                cur_pts.extend(args)
            elif op_name == "closePath" and cur_pts:
                ys = [p[1] for p in cur_pts]
                bh = max(ys) - min(ys)
                if bh >= MIN_MODULE_H:
                    # 바 너비는 항상 module_w로 고정, 높이만 유동
                    modules.append((col_x, min(ys), col_x + module_w, max(ys)))
                cur_pts = []

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
