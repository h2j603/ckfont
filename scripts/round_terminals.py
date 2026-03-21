#!/usr/bin/env python3
"""
CK Sans 터미널 라운딩.

지정된 글리프의 직선 터미널(스트로크 끝)을 둥글게 수정한다.
정적 인스턴스(gvar 없음)이므로 포인트 추가/삭제가 자유롭다.

원리:
  직선 세그먼트(ON→ON)의 중점에 off-curve 제어점을 삽입하여
  quadratic Bézier 곡선으로 변환. 제어점은 외곽 방향으로 오프셋.

사용법:
  python3 scripts/round_terminals.py [--dry-run] [--amount 0.35]
"""

import math
import sys
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
FONT_PATH = BUILD_DIR / "CKSans-Base.ttf"

# ── 터미널 정의 ──
# (glyph_char, contour_index, point_a_local, point_b_local)
# point_a, point_b: 컨투어 내 로컬 인덱스 (직선 세그먼트의 시작/끝)
# 이 세그먼트가 곡선으로 변환됨

TERMINALS = [
    # 대문자
    ("C", 0, 12, 13),   # 하단 터미널 (488,166→488,27)
    ("C", 0, 28, 29),   # 상단 터미널 (513,677→468,548)
    ("G", 0, 16, 17),   # 상단 터미널 (557,679→510,552)
    ("S", 0, 8, 9),     # 좌하단 터미널 (34,33→34,189)
    ("S", 0, 32, 33),   # 우상단 터미널 (444,674→398,542)
    ("J", 0, 3, 4),     # 하단 좌측 터미널 (-62,-207→-62,-73)
    # 숫자
    ("2", 0, 13, 14),   # 좌상단 커브 끝 (106,518→27,619)
    ("3", 0, 15, 16),   # 좌하단 터미널 (33,26→33,166)
    ("3", 0, 40, 41),   # 좌상단 터미널 (96,546→33,657)
    ("5", 0, 11, 12),   # 좌하단 터미널 (48,27→48,166)
    # 소문자
    ("c", 0, 11, 12),   # 하단 터미널
    ("c", 0, 26, 27),   # 상단 터미널
    ("r", 0, 3, 4),     # 우상단 터미널 (380,553→366,397)
    ("s", 0, 7, 8),     # 좌하단 터미널
    ("s", 0, 28, 29),   # 우상단 터미널
    ("j", 0, 3, 4),     # 하단 터미널 (-38,-228→-38,-102)
    ("y", 0, 20, 21),   # 하단 좌측 터미널 (43,-232→43,-103)
]


def get_contour_points(glyph, contour_idx):
    """컨투어의 포인트 목록 추출. [(x, y, on_curve), ...]"""
    coords = list(glyph.coordinates)
    flags = list(glyph.flags)
    ends = list(glyph.endPtsOfContours)

    start = 0 if contour_idx == 0 else ends[contour_idx - 1] + 1
    end = ends[contour_idx]

    points = []
    for i in range(start, end + 1):
        x, y = coords[i]
        on = bool(flags[i] & 1)
        points.append((x, y, on))
    return points


def set_contour_points(glyph, contour_idx, points):
    """컨투어의 포인트를 새 목록으로 교체."""
    coords = list(glyph.coordinates)
    flags = list(glyph.flags)
    ends = list(glyph.endPtsOfContours)

    start = 0 if contour_idx == 0 else ends[contour_idx - 1] + 1
    end = ends[contour_idx]
    old_count = end - start + 1
    new_count = len(points)
    diff = new_count - old_count

    # 새 좌표/플래그 구성
    new_coords = list(coords[:start])
    new_flags = list(flags[:start])
    for x, y, on in points:
        new_coords.append((int(round(x)), int(round(y))))
        new_flags.append(1 if on else 0)
    new_coords.extend(coords[end + 1:])
    new_flags.extend(flags[end + 1:])

    # endPtsOfContours 업데이트
    new_ends = list(ends)
    new_ends[contour_idx] = start + new_count - 1
    for i in range(contour_idx + 1, len(new_ends)):
        new_ends[i] += diff

    glyph.coordinates = GlyphCoordinates(new_coords)
    glyph.flags = bytes(new_flags)
    glyph.endPtsOfContours = new_ends
    glyph.numberOfContours = len(new_ends)


def round_terminal(points, local_a, local_b, amount=0.35):
    """
    직선 세그먼트 local_a → local_b 사이에 off-curve 제어점 삽입.

    CW 컨투어(TrueType 외곽)에서 외곽 방향 = 진행방향의 왼쪽 수직.
    amount: 세그먼트 길이 대비 벌지 크기 (0.35 = 적당히 둥근 느낌)
    """
    n = len(points)
    ax, ay, _ = points[local_a % n]
    bx, by, _ = points[local_b % n]

    dx = bx - ax
    dy = by - ay
    length = math.hypot(dx, dy)
    if length < 1:
        return points  # 너무 짧으면 스킵

    # 중점
    mx = (ax + bx) / 2
    my = (ay + by) / 2

    # 외곽 방향 (CW 컨투어에서 진행방향의 왼쪽 수직 = 외부)
    # 방향 (dx, dy)의 왼쪽 수직: (-dy, dx)
    nx = -dy / length
    ny = dx / length

    # 제어점: 중점에서 외곽으로 오프셋
    offset = length * amount
    cx = mx + nx * offset
    cy = my + ny * offset

    # 새 포인트 리스트: local_a와 local_b 사이에 off-curve 삽입
    new_points = []
    insert_idx = (local_a + 1) % n

    if insert_idx == 0:
        # local_b가 컨투어의 처음인 경우
        for i in range(n):
            new_points.append(points[i])
        new_points.append((cx, cy, False))
    else:
        for i in range(n):
            new_points.append(points[i])
            if i == local_a:
                new_points.append((cx, cy, False))  # off-curve 삽입

    return new_points


def main():
    dry_run = "--dry-run" in sys.argv
    amount = 0.35

    for i, arg in enumerate(sys.argv):
        if arg == "--amount" and i + 1 < len(sys.argv):
            amount = float(sys.argv[i + 1])

    if not FONT_PATH.exists():
        print(f"Error: {FONT_PATH} not found. Run 'make base' first.")
        sys.exit(1)

    font = TTFont(str(FONT_PATH))
    glyf = font["glyf"]
    cmap = font.getBestCmap()

    print(f"Rounding terminals (amount={amount})...")

    # 같은 글리프의 여러 터미널을 처리할 때, 포인트가 추가되면
    # 인덱스가 밀림. 역순으로 처리하여 앞의 인덱스가 영향받지 않게 함.
    # 같은 글리프+컨투어의 터미널은 local_a 기준 역순 정렬.
    sorted_terminals = sorted(TERMINALS, key=lambda t: (t[0], t[1], -t[2]))

    # 글리프별로 그룹핑
    glyph_groups = {}
    for char, ci, la, lb in sorted_terminals:
        key = (char, ci)
        if key not in glyph_groups:
            glyph_groups[key] = []
        glyph_groups[key].append((la, lb))

    modified = 0

    for (char, ci), edges in glyph_groups.items():
        gname = cmap.get(ord(char))
        if not gname or gname not in glyf:
            print(f"  Skip '{char}': not found")
            continue

        glyph = glyf[gname]
        if glyph.isComposite():
            print(f"  Skip '{char}': composite")
            continue

        if ci >= glyph.numberOfContours:
            print(f"  Skip '{char}' contour {ci}: out of range")
            continue

        # 역순으로 처리 (뒤쪽 인덱스부터)
        edges_sorted = sorted(edges, key=lambda e: -e[0])
        points = get_contour_points(glyph, ci)

        for la, lb in edges_sorted:
            if la >= len(points) or lb >= len(points):
                print(f"  Skip '{char}' [{la}→{lb}]: index out of range")
                continue

            ax, ay, a_on = points[la]
            bx, by, b_on = points[lb]

            if not a_on or not b_on:
                print(f"  Skip '{char}' [{la}→{lb}]: not both ON-curve")
                continue

            old_len = len(points)
            points = round_terminal(points, la, lb, amount)

            if len(points) > old_len:
                cx, cy, _ = points[la + 1]  # 삽입된 제어점
                print(f"  '{char}' [{la}]({ax},{ay}) → [{lb}]({bx},{by}): "
                      f"ctrl ({cx:.0f},{cy:.0f})")
                modified += 1

        set_contour_points(glyph, ci, points)

    print(f"\nRounded {modified} terminal(s).")

    if dry_run:
        print("[Dry run — not saved]")
        font.close()
        return

    font.save(str(FONT_PATH))
    font.close()
    print(f"Saved: {FONT_PATH}")

    # WOFF2 + preview 복사
    import shutil
    woff2_path = FONT_PATH.with_suffix(".woff2")
    woff2_font = TTFont(str(FONT_PATH))
    woff2_font.flavor = "woff2"
    woff2_font.save(str(woff2_path))
    woff2_font.close()
    print(f"WOFF2: {woff2_path.name}")

    preview_dir = ROOT / "preview"
    if preview_dir.exists():
        shutil.copy2(FONT_PATH, preview_dir / FONT_PATH.name)
        shutil.copy2(woff2_path, preview_dir / woff2_path.name)
        print("Copied to preview/")


if __name__ == "__main__":
    main()
