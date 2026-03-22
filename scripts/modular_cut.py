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
from fontTools.pens.transformPen import TransformPen

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


def compute_mono_aw(cmap, glyf, hmtx, pitch):
    """폰트 내 모든 처리 대상 글리프의 모노스페이스 advance width 계산.

    최대 snapped AW를 사용하여 가장 넓은 글리프도 수용.
    극단적 아웃라이어(상위 2%)는 제외.
    """
    snapped_aws = []
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
        if glyph_w < MIN_MODULE_W:
            continue

        adv_w = hmtx[glyph_name][0]
        n = max(1, round(adv_w / pitch))
        snapped_aws.append(n * pitch)

    if not snapped_aws:
        return None

    # 상위 98% 지점 사용 (극단적 합자 등 제외)
    snapped_aws.sort()
    idx = min(len(snapped_aws) - 1, int(len(snapped_aws) * 0.98))
    return snapped_aws[idx]


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


def extract_modules(glyph_path, glyph_obj, module_w, gap, hmtx_entry, mono_aw=None):
    """글리프에서 모듈 bbox 목록 추출 — 커버리지 정보 포함.

    pathops INTERSECTION: 컬럼 직사각형과 글리프의 boolean 교차.
    카운터(D, O, B 내부 구멍)를 정확히 처리.

    반환: [(x0, y0, x1, y1, coverage), ...]
    coverage: 컬럼 내 x방향 채움 비율 (0.0~1.0)
    """
    pitch = module_w + gap

    # 모노스페이스: 고정 AW 기준 그리드 / 일반: 글리프 AW 기준
    effective_aw = mono_aw if mono_aw else hmtx_entry[0]
    n_cols = max(1, round(effective_aw / pitch))

    # 고정 그리드: effective_aw 중심 기준 (모노스페이스면 모든 글리프 동일)
    grid_cx = effective_aw / 2
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

        # 결과 컨투어 → 모듈 bbox + 커버리지
        rec = RecordingPen()
        result.draw(rec)

        cur_pts = []
        for op_name, args in rec.value:
            if op_name == "moveTo":
                cur_pts = [args[0]]
            elif op_name in ("lineTo", "curveTo", "qCurveTo"):
                cur_pts.extend(args)
            elif op_name == "closePath" and cur_pts:
                valid_pts = [p for p in cur_pts if p is not None]
                if valid_pts:
                    xs = [p[0] for p in valid_pts]
                    ys = [p[1] for p in valid_pts]
                    seg_w = max(xs) - min(xs)
                    seg_h = max(ys) - min(ys)
                    if seg_h >= MIN_MODULE_H:
                        coverage = min(1.0, seg_w / module_w)
                        modules.append((col_x, min(ys), col_x + module_w, max(ys), coverage))
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


def quantize_stems(modules, module_w, gap):
    """2차 보정: 커버리지 기반 스템 정규화.

    스템이 컬럼 경계에 걸려서 양쪽에 얇은 슬리버로 분할되는 문제를 해결.
    같은 너비의 세로 획이 항상 같은 수의 컬럼을 차지하도록 보장.

    알고리즘:
      1. 각 모듈의 커버리지(x방향 채움 비율) 확인
      2. 저커버리지(< SLIVER_THRESHOLD) 모듈 = 슬리버(파편)로 판정
      3. 인접 컬럼에 같은 y범위의 고커버리지 모듈이 있으면:
         → 슬리버 제거, 인접 모듈의 y범위 확장
      4. 양쪽 모두 저커버리지면 (스템이 정확히 경계 위):
         → 둘 중 커버리지가 높은 쪽 유지, 나머지 제거

    coverage 기반이므로 스템 너비에 관계없이 일관된 결과 보장.
    """
    if len(modules) < 2:
        return [(m[0], m[1], m[2], m[3]) for m in modules]

    pitch = module_w + gap
    SLIVER_THRESHOLD = 0.55  # 이 미만이면 슬리버(파편)으로 판단

    n = len(modules)
    remove = [False] * n
    y_extend = {}  # idx -> (y0, y1) 확장된 범위

    # 컬럼 인덱스 계산
    col_idx = [round(m[0] / pitch) for m in modules]

    # 패스 1: 저커버리지 슬리버 감지 + 인접 고커버리지 모듈로 병합
    for i in range(n):
        if remove[i]:
            continue
        x0_i, y0_i, x1_i, y1_i, cov_i = modules[i]

        if cov_i >= SLIVER_THRESHOLD:
            continue  # 충분한 커버리지 → 유지

        ci = col_idx[i]

        # 인접 컬럼에서 같은 스템의 고커버리지 모듈 찾기
        best_j = -1
        best_cov = -1
        for j in range(n):
            if i == j or remove[j]:
                continue
            cj = col_idx[j]
            if abs(ci - cj) != 1:
                continue

            x0_j, y0_j, x1_j, y1_j, cov_j = modules[j]

            # y범위 겹침 확인
            overlap = min(y1_i, y1_j) - max(y0_i, y0_j)
            min_h = min(y1_i - y0_i, y1_j - y0_j)
            if min_h <= 0:
                continue
            if overlap / min_h < 0.5:
                continue

            # 인접 컬럼 중 가장 높은 커버리지를 가진 것 선택
            if cov_j > best_cov:
                best_cov = cov_j
                best_j = j

        if best_j >= 0:
            # 슬리버 제거, 인접 모듈의 y범위 확장
            remove[i] = True
            x0_j, y0_j, x1_j, y1_j, cov_j = modules[best_j]
            cur_y0, cur_y1 = y_extend.get(best_j, (y0_j, y1_j))
            y_extend[best_j] = (min(cur_y0, y0_i), max(cur_y1, y1_i))

    # 패스 2: 양쪽 모두 저커버리지인 분할 스템 처리
    # (스템이 정확히 경계 위에 위치한 경우)
    for i in range(n):
        if remove[i]:
            continue
        x0_i, y0_i, x1_i, y1_i, cov_i = modules[i]
        if cov_i >= SLIVER_THRESHOLD:
            continue

        ci = col_idx[i]

        for j in range(i + 1, n):
            if remove[j]:
                continue
            cj = col_idx[j]
            if abs(ci - cj) != 1:
                continue

            x0_j, y0_j, x1_j, y1_j, cov_j = modules[j]
            if cov_j >= SLIVER_THRESHOLD:
                continue

            # y범위 겹침 확인
            overlap = min(y1_i, y1_j) - max(y0_i, y0_j)
            min_h = min(y1_i - y0_i, y1_j - y0_j)
            if min_h <= 0 or overlap / min_h < 0.5:
                continue

            # 둘 다 슬리버 → 커버리지 낮은 쪽 제거
            if cov_i >= cov_j:
                remove[j] = True
                cur_y0, cur_y1 = y_extend.get(i, (y0_i, y1_i))
                y_extend[i] = (min(cur_y0, y0_j), max(cur_y1, y1_j))
            else:
                remove[i] = True
                cur_y0, cur_y1 = y_extend.get(j, (y0_j, y1_j))
                y_extend[j] = (min(cur_y0, y0_i), max(cur_y1, y1_i))
                break

    # 결과 생성 (4-tuple로 변환, 커버리지 제거)
    result = []
    for i in range(n):
        if remove[i]:
            continue
        x0, y0, x1, y1, cov = modules[i]
        if i in y_extend:
            y0, y1 = y_extend[i]
        result.append((x0, y0, x1, y1))

    return result


def process_font(input_path, output_path, name_suffix, module_w, gap, radius):
    """하나의 폰트 인스턴스에 모듈러 컷 적용.

    모노스페이스 모드:
      1. 모든 글리프의 AW를 고정값(mono_aw)으로 통일
      2. 각 글리프를 mono_aw 중앙에 센터링 (TransformPen)
      3. 고정 그리드로 모든 글리프가 동일한 컬럼 위치 공유
      4. 2차 보정으로 스템 경계 파편 모듈 병합
    """
    if not input_path.exists():
        print(f"  Skip: {input_path.name} not found")
        return

    font = TTFont(str(input_path))
    glyf = font["glyf"]
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    hmtx = font["hmtx"]

    pitch = module_w + gap

    # ── 모노스페이스 AW 계산 ──
    mono_aw = compute_mono_aw(cmap, glyf, hmtx, pitch)

    print(f"\n── {input_path.name} → {output_path.name} ──")
    print(f"  module_w={module_w}, gap={gap}, radius={radius}, pitch={pitch}")
    print(f"  mono_aw={mono_aw} ({mono_aw // pitch} cols)")

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
        if glyph_w < MIN_MODULE_W:
            continue
        glyph_h = g.yMax - g.yMin
        if glyph_h < MIN_MODULE_H:
            continue

        try:
            # ── 글리프 센터링: 시각적 중심을 mono_aw/2에 맞춤 ──
            glyph_visual_cx = (g.xMin + g.xMax) / 2
            target_cx = mono_aw / 2
            shift_x = target_cx - glyph_visual_cx

            glyph_path = pathops.Path()
            transform_pen = TransformPen(
                glyph_path.getPen(),
                (1, 0, 0, 1, shift_x, 0),  # x방향 이동
            )
            gs[glyph_name].draw(transform_pen)

            modules = extract_modules(
                glyph_path, g, module_w, gap, hmtx[glyph_name],
                mono_aw=mono_aw,
            )

            if not modules:
                continue

            # ── 2차 보정: 커버리지 기반 스템 정규화 ──
            modules = quantize_stems(modules, module_w, gap)

            new_glyph = modules_to_ttglyph(modules, radius, glyf)
            if new_glyph is None:
                errors += 1
                continue

            glyf[glyph_name] = new_glyph
            # bounds 재계산 (TTGlyphPen.glyph()은 xMin 없이 반환)
            new_glyph.recalcBounds(glyf)
            # 모노스페이스: 모든 글리프 동일 AW
            # LSB = 글리프의 실제 xMin (그리드 기반 센터링 이미 적용됨)
            new_lsb = new_glyph.xMin if new_glyph.xMin is not None else 0
            hmtx[glyph_name] = (mono_aw, new_lsb)
            modified += 1

        except Exception as e:
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

    # CFF 전용 테이블 제거 (CFF→TrueType 변환 폰트에 남아있으면 Safari 거부)
    for cff_table in ("VORG",):
        if cff_table in font:
            del font[cff_table]
            print(f"  Removed {cff_table} table")

    # sfntVersion 교정: CFF→TrueType 변환 폰트가 OTTO로 남아있으면 Safari 거부
    if "glyf" in font and font.sfntVersion != "\x00\x01\x00\x00":
        old_ver = repr(font.sfntVersion)
        font.sfntVersion = "\x00\x01\x00\x00"
        print(f"  Fixed sfntVersion: {old_ver} → TrueType")

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
    module_w = 120
    gap = 40
    radius = 55

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
