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

# 처리할 인스턴스: (입력 파일명, 출력 파일명, 폰트 이름 접미사)
INSTANCES = [
    ("CKSans-Regular.ttf",       "CKSans-Cut.ttf",           "Cut"),
    ("CKSans-KR-Regular.ttf",    "CKSans-Cut-KR.ttf",        "Cut KR"),
    ("CKSans-JP-Regular.ttf",    "CKSans-Cut-JP.ttf",         "Cut JP"),
    ("CKSans-SC-Regular.ttf",    "CKSans-Cut-SC.ttf",         "Cut SC"),
]

# ── 커팅 대상: 폰트 내 모든 비-공백 글리프 ──
# cmap에서 동적으로 수집 (main에서 설정)
CUT_ALL = True  # True면 cmap 전체 대상

# 커팅 제외: 너무 작거나 모듈화가 의미 없는 글리프
SKIP_CODEPOINTS = {
    0x0020,  # space
    0x00A0,  # nbsp
    0x00AD,  # soft hyphen
    0x200B,  # zero-width space
    0x200C, 0x200D, 0x200E, 0x200F,  # zero-width joiners
    0xFEFF,  # BOM
}

# 최소 모듈 크기 (이보다 작으면 무시)
MIN_MODULE_W = 10
MIN_MODULE_H = 20  # 짧은 건 정원(원)으로 표현하므로 낮게


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


def extract_modules(glyph_path, glyph_obj, module_w, gap, hmtx_entry):
    """글리프에서 모듈 bbox 목록 추출.

    pathops INTERSECTION: 컬럼 직사각형과 글리프의 boolean 교차.
    카운터(D, O, B 내부 구멍)를 정확히 처리.

    Monospaced 그리드: advance width를 pitch 배수로 스냅하여
    같은 AW 그룹의 글리프들이 동일한 컬럼 그리드를 공유.
    """
    pitch = module_w + gap

    # advance width 기준 그리드 (pitch 배수로 스냅)
    adv_w = hmtx_entry[0]
    n_cols = max(1, round(adv_w / pitch))
    snapped_w = n_cols * pitch  # 스냅된 advance width
    grid_cx = adv_w / 2  # 원래 AW 중심 기준

    total_grid_w = n_cols * module_w + (n_cols - 1) * gap
    grid_start = grid_cx - total_grid_w / 2

    y_lo = glyph_obj.yMin - 50
    y_hi = glyph_obj.yMax + 50

    modules = []

    for ci in range(n_cols):
        col_x = grid_start + ci * pitch

        # 컬럼 직사각형
        col = pathops.Path()
        pen = col.getPen()
        pen.moveTo((col_x, y_lo))
        pen.lineTo((col_x + module_w, y_lo))
        pen.lineTo((col_x + module_w, y_hi))
        pen.lineTo((col_x, y_hi))
        pen.closePath()

        # Boolean intersection — 카운터 자동 처리
        try:
            result = pathops.op(
                glyph_path, col,
                pathops.PathOp.INTERSECTION,
                fix_winding=True, clockwise=True,
            )
        except Exception:
            continue

        # 결과 컨투어 → 모듈 bbox
        rec = RecordingPen()
        result.draw(rec)

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
                    # 바 너비 고정, y만 교차 결과에서
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


def process_font(input_path, output_path, name_suffix, module_w, gap, radius):
    """하나의 폰트 인스턴스에 모듈러 컷 적용."""
    if not input_path.exists():
        print(f"  Skip: {input_path.name} not found")
        return

    font = TTFont(str(input_path))
    glyf = font["glyf"]
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    hmtx = font["hmtx"]

    pitch = module_w + gap

    # Monospaced: 글리프별 advance width → 가장 가까운 pitch 배수로 스냅
    # 같은 폭의 글리프끼리 동일한 그리드를 공유 → 동일 스템 = 동일 바 수
    # 최대 AW는 쓰지 않음 (합자 등 극단값 제외)

    print(f"\n── {input_path.name} → {output_path.name} ──")
    print(f"  module_w={module_w}, gap={gap}, radius={radius}, pitch={pitch}")

    modified = 0
    errors = 0

    for cp, glyph_name in sorted(cmap.items()):
        if cp in SKIP_CODEPOINTS:
            continue
        if glyph_name not in glyf:
            continue

        g = glyf[glyph_name]
        if g.isComposite() or g.numberOfContours <= 0:
            continue

        if not hasattr(g, 'xMax') or g.xMax is None:
            continue
        glyph_w = g.xMax - g.xMin
        if glyph_w < module_w:
            continue
        glyph_h = g.yMax - g.yMin
        if glyph_h < MIN_MODULE_H:
            continue

        try:
            glyph_path = pathops.Path()
            gs[glyph_name].draw(glyph_path.getPen())

            adv_w = hmtx[glyph_name][0]
            modules = extract_modules(
                glyph_path, g, module_w, gap, hmtx[glyph_name],
            )

            if not modules:
                continue

            new_glyph = modules_to_ttglyph(modules, radius, glyf)
            if new_glyph is None:
                errors += 1
                continue

            glyf[glyph_name] = new_glyph
            # advance width를 pitch 스냅 값으로 통일
            n = max(1, round(adv_w / pitch))
            snapped_aw = n * pitch
            _, lsb = hmtx[glyph_name]
            hmtx[glyph_name] = (snapped_aw, lsb)
            modified += 1

        except Exception as e:
            errors += 1
            errors += 1

    print(f"  Modified {modified} glyph(s), {errors} error(s).")

    # 이름 변경 — "CK Sans XX" → "CK Sans Cut XX" (이중 접미사 방지)
    name_table = font["name"]
    for record in name_table.names:
        text = record.toUnicode()
        if "CK Sans" in text:
            # "CK Sans KR" → "CK Sans Cut KR" 등 "CK Sans" 바로 뒤에 "Cut" 삽입
            new_text = text.replace("CK Sans", "CK Sans Cut", 1)
            name_table.setName(
                new_text, record.nameID, record.platformID,
                record.platEncID, record.langID,
            )

    # 저장
    font.save(str(output_path))
    font.close()
    print(f"  Saved: {output_path}")

    # WOFF2
    woff2_path = output_path.with_suffix(".woff2")
    woff2_font = TTFont(str(output_path))
    woff2_font.flavor = "woff2"
    woff2_font.save(str(woff2_path))
    woff2_font.close()
    print(f"  WOFF2: {woff2_path.name}")

    # preview 복사
    preview_dir = ROOT / "preview"
    if preview_dir.exists():
        shutil.copy2(output_path, preview_dir / output_path.name)
        shutil.copy2(woff2_path, preview_dir / woff2_path.name)
        print(f"  Copied to preview/")


def main():
    dry_run = "--dry-run" in sys.argv
    module_w = 65
    gap = 25
    radius = 32

    # 인자 파싱
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--module-w" and i + 1 < len(args):
            module_w = int(args[i + 1])
        elif arg == "--gap" and i + 1 < len(args):
            gap = int(args[i + 1])
        elif arg == "--radius" and i + 1 < len(args):
            radius = int(args[i + 1])

    if dry_run:
        print("[Dry run mode]")
        return

    for in_name, out_name, name_suffix in INSTANCES:
        input_path = BUILD_DIR / in_name
        output_path = BUILD_DIR / out_name
        process_font(input_path, output_path, name_suffix, module_w, gap, radius)


if __name__ == "__main__":
    main()
