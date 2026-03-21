#!/usr/bin/env python3
"""
CK Font 지오메트릭 산스화 스크립트.
라틴 알파벳·숫자·부호의 곡선을 기하학적으로 보정한다.

실행 순서: modify_params.py → geometrize.py → modify_glyphs.py → build.py

Phase 1: 라운드 글리프 — 곡선을 정타원에 가깝게 보정
Phase 2: 도트류 — 완전한 원형화
Phase 3: 각진 글리프 — 대칭성 강화

⚠ Variable Font 안전 규칙:
  - 포인트 개수 변경 없음 (gvar 보존)
  - glyf 좌표만 블렌딩 방식으로 수정
  - gvar 델타는 유지 (축 독립적 보정)
"""

import math
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"


# ═══════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════

CURVE_STRENGTH = 0.30     # 라운드 글리프 → 타원 보정 강도
DOT_STRENGTH = 0.85       # 도트 → 정원 보정 강도
SYMMETRY_STRENGTH = 0.40  # 각진 글리프 → 대칭 보정 강도

# Phase 1: 라운드 글리프
ROUND_CHARS = list("OCGQDPBRUocedgpqbu0368S")

# Phase 2: 도트 글리프 (contour 중 작은 원형 컨투어를 자동 감지)
DOT_CHARS = list("ij!?;:")
DOT_EXTRA_NAMES = ["period", "colon", "semicolon", "exclam", "question",
                   "exclamdown", "questiondown"]

# Phase 3: 각진 글리프
ANGULAR_CHARS = list("AVWMNXYZKvwxykz147")


# ═══════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════

def get_glyph_name(font, char):
    cmap = font.getBestCmap()
    if not cmap:
        return None
    return cmap.get(ord(char))


def contour_range(glyph, ci):
    start = 0 if ci == 0 else glyph.endPtsOfContours[ci - 1] + 1
    end = glyph.endPtsOfContours[ci]
    return start, end


def contour_bbox(coords, start, end):
    xs = [coords[i][0] for i in range(start, end + 1)]
    ys = [coords[i][1] for i in range(start, end + 1)]
    return min(xs), min(ys), max(xs), max(ys)


def contour_center(coords, start, end):
    n = end - start + 1
    cx = sum(coords[i][0] for i in range(start, end + 1)) / n
    cy = sum(coords[i][1] for i in range(start, end + 1)) / n
    return cx, cy


def contour_size(coords, start, end):
    x0, y0, x1, y1 = contour_bbox(coords, start, end)
    return max(x1 - x0, y1 - y0)


def off_curve_ratio(flags, start, end):
    n = end - start + 1
    off = sum(1 for i in range(start, end + 1) if not (flags[i] & 1))
    return off / n if n > 0 else 0


def is_round_contour(coords, flags, start, end):
    """라운드 컨투어 판별: 오프커브 비율 높고 적절한 크기."""
    n = end - start + 1
    if n < 8:
        return False
    if off_curve_ratio(flags, start, end) < 0.35:
        return False
    x0, y0, x1, y1 = contour_bbox(coords, start, end)
    w, h = x1 - x0, y1 - y0
    if w < 30 or h < 30:
        return False
    aspect = min(w, h) / max(w, h)
    return aspect > 0.25


def is_dot_contour(coords, flags, start, end):
    """도트 컨투어 판별: 작고 원형에 가까운 컨투어."""
    n = end - start + 1
    if n < 6:
        return False
    x0, y0, x1, y1 = contour_bbox(coords, start, end)
    w, h = x1 - x0, y1 - y0
    size = max(w, h)
    if size > 200 or size < 15:
        return False
    aspect = min(w, h) / max(w, h) if max(w, h) > 0 else 0
    return aspect > 0.6


def decompose_if_composite(font, glyph_name):
    """컴포지트 글리프면 단순 글리프로 분해."""
    glyf = font["glyf"]
    glyph = glyf[glyph_name]
    if not glyph.isComposite():
        return False

    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    glyphset = font.getGlyphSet()
    rec_pen = RecordingPen()
    glyphset[glyph_name].draw(rec_pen)
    tt_pen = TTGlyphPen(None)
    rec_pen.replay(tt_pen)
    glyf[glyph_name] = tt_pen.glyph()

    if "gvar" in font and glyph_name in font["gvar"].variations:
        del font["gvar"].variations[glyph_name]

    return True


# ═══════════════════════════════════════════
#  Phase 1: 라운드 글리프 → 정타원 보정
# ═══════════════════════════════════════════

def push_toward_ellipse(coords, flags, start, end, strength):
    """컨투어의 각 포인트를 이상적인 타원 위치로 블렌딩."""
    cx, cy = contour_center(coords, start, end)
    x0, y0, x1, y1 = contour_bbox(coords, start, end)
    rx = (x1 - x0) / 2
    ry = (y1 - y0) / 2

    if rx < 5 or ry < 5:
        return 0

    changes = 0
    new_coords = list(coords)

    for i in range(start, end + 1):
        px, py = coords[i]
        dx, dy = px - cx, py - cy

        if abs(dx) < 0.5 and abs(dy) < 0.5:
            continue

        # 타원 위의 이상적인 위치 계산
        angle = math.atan2(dy / ry, dx / rx)
        ideal_x = cx + rx * math.cos(angle)
        ideal_y = cy + ry * math.sin(angle)

        new_x = int(round(px + (ideal_x - px) * strength))
        new_y = int(round(py + (ideal_y - py) * strength))

        if new_x != px or new_y != py:
            new_coords[i] = (new_x, new_y)
            changes += 1

    # Apply changes
    for i in range(start, end + 1):
        coords[i] = new_coords[i]

    return changes


def process_round_glyphs(font):
    """Phase 1: 라운드 글리프의 곡선 보정."""
    glyf = font["glyf"]
    total = 0

    for char in ROUND_CHARS:
        glyph_name = get_glyph_name(font, char)
        if not glyph_name or glyph_name not in glyf:
            continue

        decompose_if_composite(font, glyph_name)
        glyph = glyf[glyph_name]

        if glyph.numberOfContours <= 0:
            continue

        coords = list(glyph.coordinates)
        flags = list(glyph.flags)
        glyph_changes = 0

        for ci in range(glyph.numberOfContours):
            start, end = contour_range(glyph, ci)
            if is_round_contour(coords, flags, start, end):
                n = push_toward_ellipse(coords, flags, start, end, CURVE_STRENGTH)
                glyph_changes += n

        if glyph_changes > 0:
            glyph.coordinates = GlyphCoordinates(coords)
            total += 1
            print(f"    '{char}' ({glyph_name}): {glyph_changes} points adjusted")

    return total


# ═══════════════════════════════════════════
#  Phase 2: 도트 → 정원화
# ═══════════════════════════════════════════

def push_toward_circle(coords, flags, start, end, strength):
    """컨투어의 각 포인트를 완전한 원 위치로 블렌딩."""
    cx, cy = contour_center(coords, start, end)

    # 평균 반지름
    distances = []
    for i in range(start, end + 1):
        dx, dy = coords[i][0] - cx, coords[i][1] - cy
        distances.append(math.sqrt(dx * dx + dy * dy))
    avg_r = sum(distances) / len(distances)

    if avg_r < 3:
        return 0

    changes = 0
    new_coords = list(coords)

    for i in range(start, end + 1):
        px, py = coords[i]
        dx, dy = px - cx, py - cy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.5:
            continue

        scale = avg_r / dist
        ideal_x = cx + dx * scale
        ideal_y = cy + dy * scale

        new_x = int(round(px + (ideal_x - px) * strength))
        new_y = int(round(py + (ideal_y - py) * strength))

        if new_x != px or new_y != py:
            new_coords[i] = (new_x, new_y)
            changes += 1

    for i in range(start, end + 1):
        coords[i] = new_coords[i]

    return changes


def process_dot_glyphs(font):
    """Phase 2: 도트 컨투어를 정원으로."""
    glyf = font["glyf"]
    total = 0

    # 문자 기반 + 글리프 이름 기반 타겟 수집
    targets = set()
    for char in DOT_CHARS:
        name = get_glyph_name(font, char)
        if name:
            targets.add(name)

    cmap = font.getBestCmap()
    if cmap:
        for name in DOT_EXTRA_NAMES:
            # 글리프 이름으로 직접 확인
            if name in glyf:
                targets.add(name)

    for glyph_name in targets:
        if glyph_name not in glyf:
            continue

        decompose_if_composite(font, glyph_name)
        glyph = glyf[glyph_name]

        if glyph.numberOfContours <= 0:
            continue

        coords = list(glyph.coordinates)
        flags = list(glyph.flags)
        glyph_changes = 0

        for ci in range(glyph.numberOfContours):
            start, end = contour_range(glyph, ci)
            if is_dot_contour(coords, flags, start, end):
                n = push_toward_circle(coords, flags, start, end, DOT_STRENGTH)
                glyph_changes += n

        if glyph_changes > 0:
            glyph.coordinates = GlyphCoordinates(coords)
            total += 1
            print(f"    '{glyph_name}': {glyph_changes} points adjusted (dot)")

    return total


# ═══════════════════════════════════════════
#  Phase 3: 각진 글리프 → 대칭 보정
# ═══════════════════════════════════════════

def enforce_bilateral_symmetry(coords, flags, start, end, axis_x, strength):
    """수직 축 기준 좌우 대칭 강화."""
    n = end - start + 1
    changes = 0

    # y좌표 기준으로 미러 파트너 매칭
    paired = set()
    pairs = []

    for i in range(start, end + 1):
        if i in paired:
            continue
        px, py = coords[i]
        mirror_x = 2 * axis_x - px

        best_j = None
        best_dist = 40  # 매칭 허용 범위

        for j in range(start, end + 1):
            if j == i or j in paired:
                continue
            jx, jy = coords[j]
            dist = math.sqrt((jx - mirror_x) ** 2 + (jy - py) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_j = j

        if best_j is not None:
            paired.add(i)
            paired.add(best_j)
            pairs.append((i, best_j))

    new_coords = list(coords)

    for i, j in pairs:
        ix, iy = coords[i]
        jx, jy = coords[j]

        # 대칭 y: 평균값
        avg_y = (iy + jy) / 2
        # 대칭 x: 축으로부터 같은 거리
        dist_i = abs(ix - axis_x)
        dist_j = abs(jx - axis_x)
        avg_dist = (dist_i + dist_j) / 2

        if ix >= axis_x:
            ideal_ix = axis_x + avg_dist
            ideal_jx = axis_x - avg_dist
        else:
            ideal_ix = axis_x - avg_dist
            ideal_jx = axis_x + avg_dist

        new_ix = int(round(ix + (ideal_ix - ix) * strength))
        new_iy = int(round(iy + (avg_y - iy) * strength))
        new_jx = int(round(jx + (ideal_jx - jx) * strength))
        new_jy = int(round(jy + (avg_y - jy) * strength))

        if new_ix != ix or new_iy != iy:
            new_coords[i] = (new_ix, new_iy)
            changes += 1
        if new_jx != jx or new_jy != jy:
            new_coords[j] = (new_jx, new_jy)
            changes += 1

    for i in range(start, end + 1):
        coords[i] = new_coords[i]

    return changes


def process_angular_glyphs(font):
    """Phase 3: 각진 글리프의 대칭성 강화."""
    glyf = font["glyf"]
    hmtx = font["hmtx"] if "hmtx" in font else None
    total = 0

    for char in ANGULAR_CHARS:
        glyph_name = get_glyph_name(font, char)
        if not glyph_name or glyph_name not in glyf:
            continue

        decompose_if_composite(font, glyph_name)
        glyph = glyf[glyph_name]

        if glyph.numberOfContours <= 0:
            continue

        # 대칭축: 글리프 advance width의 중심
        if hmtx and glyph_name in hmtx.metrics:
            width, lsb = hmtx[glyph_name]
            axis_x = width / 2
        else:
            x0, _, x1, _ = contour_bbox(
                list(glyph.coordinates), 0,
                glyph.endPtsOfContours[-1])
            axis_x = (x0 + x1) / 2

        coords = list(glyph.coordinates)
        flags = list(glyph.flags)
        glyph_changes = 0

        for ci in range(glyph.numberOfContours):
            start, end = contour_range(glyph, ci)
            n = enforce_bilateral_symmetry(
                coords, flags, start, end, axis_x, SYMMETRY_STRENGTH)
            glyph_changes += n

        if glyph_changes > 0:
            glyph.coordinates = GlyphCoordinates(coords)
            total += 1
            print(f"    '{char}' ({glyph_name}): {glyph_changes} points adjusted (symmetry)")

    return total


# ═══════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════

def main():
    font_path = BUILD_DIR / "CKSans-Variable.ttf"
    if not font_path.exists():
        print("Error: build/CKSans-Variable.ttf not found.")
        print("Run 'make modify-params' first.")
        sys.exit(1)

    print(f"Loading: {font_path.name}")
    font = TTFont(str(font_path))

    print(f"\n[Phase 1] Round glyphs → ellipse correction "
          f"(strength={CURVE_STRENGTH})")
    n1 = process_round_glyphs(font)
    print(f"  → {n1} glyphs modified")

    print(f"\n[Phase 2] Dots → circle perfection "
          f"(strength={DOT_STRENGTH})")
    n2 = process_dot_glyphs(font)
    print(f"  → {n2} glyphs modified")

    print(f"\n[Phase 3] Angular glyphs → symmetry enforcement "
          f"(strength={SYMMETRY_STRENGTH})")
    n3 = process_angular_glyphs(font)
    print(f"  → {n3} glyphs modified")

    total = n1 + n2 + n3
    if total > 0:
        font.save(str(font_path))
        print(f"\nSaved: {font_path}")
        print(f"Total: {total} glyphs geometrized")
    else:
        print("\nNo changes made.")

    font.close()


if __name__ == "__main__":
    main()
