#!/usr/bin/env python3
"""
CK Font 글리프 수정 스크립트.
config/ck-font.yaml의 glyph_modifications 설정에 따라 글리프 형태를 수정한다.

지원하는 수정 타입:
- move_point: 특정 포인트 좌표 이동 (glyf + gvar 동시 처리)
- scale: 글리프 전체 또는 부분 스케일링 (glyf + gvar 동시 처리)
- adjust_metrics: advance width / LSB 수정

⚠ Variable Font 핵심 규칙:
  glyf 좌표를 수정할 때 gvar 델타도 반드시 확인/수정해야 한다.
  포인트 개수를 추가/삭제하면 안 된다 (gvar 불일치로 크래시).
  컴포넌트 글리프는 자동 분해 후 수정한다.

이 스크립트는 build/CKSans-Variable.ttf를 수정한다.
먼저 modify_params.py가 실행되어 있어야 한다.
"""

import sys
from pathlib import Path

import yaml
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "ck-font.yaml"
BUILD_DIR = ROOT / "build"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_glyph_name(font, char):
    """문자로부터 글리프 이름 찾기."""
    cmap = font.getBestCmap()
    if cmap is None:
        return None
    code = ord(char) if isinstance(char, str) else char
    return cmap.get(code)


def decompose_composite(font, glyph_name):
    """컴포넌트(합성) 글리프를 단순 글리프로 분해."""
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

    # gvar: 컴포지트 분해 후 델타 제거 (기본값 형태만 유지)
    if "gvar" in font and glyph_name in font["gvar"].variations:
        del font["gvar"].variations[glyph_name]
        print(f"    Decomposed composite + cleared gvar deltas")
    else:
        print(f"    Decomposed composite glyph")

    return True


def apply_move_point(font, glyph_name, operation):
    """특정 포인트를 이동. gvar 델타도 같은 포인트에 대해 조정."""
    glyf = font["glyf"]
    if glyph_name not in glyf:
        print(f"    Warning: glyph '{glyph_name}' not found")
        return False

    glyph = glyf[glyph_name]

    # 컴포지트면 분해
    if glyph.isComposite():
        decompose_composite(font, glyph_name)
        glyph = glyf[glyph_name]

    if glyph.numberOfContours <= 0:
        print(f"    Warning: glyph has no contours")
        return False

    contour_idx = operation.get("contour", 0)
    point_idx = operation.get("point", 0)
    dx = operation.get("dx", 0)
    dy = operation.get("dy", 0)

    coords = list(glyph.coordinates)

    if contour_idx >= len(glyph.endPtsOfContours):
        print(f"    Warning: contour index {contour_idx} out of range")
        return False

    start = 0 if contour_idx == 0 else glyph.endPtsOfContours[contour_idx - 1] + 1
    abs_idx = start + point_idx

    if abs_idx >= len(coords):
        print(f"    Warning: point index {abs_idx} out of range "
              f"(total points: {len(coords)})")
        return False

    old_x, old_y = coords[abs_idx]
    coords[abs_idx] = (old_x + dx, old_y + dy)
    glyph.coordinates = coords
    print(f"    glyf: point[{abs_idx}] ({old_x},{old_y}) → ({old_x+dx},{old_y+dy})")

    # gvar 델타 확인 (이동량이 축 변화에도 일관되게 적용되어야 하는지)
    if "gvar" in font and glyph_name in font["gvar"].variations:
        var_count = len(font["gvar"].variations[glyph_name])
        print(f"    gvar: {var_count} variation tuple(s) — deltas preserved "
              f"(point move is axis-independent)")

    return True


def apply_scale(font, glyph_name, operation):
    """글리프 전체 스케일링. gvar 델타도 비례 조정."""
    glyf = font["glyf"]
    if glyph_name not in glyf:
        print(f"    Warning: glyph '{glyph_name}' not found")
        return False

    glyph = glyf[glyph_name]

    if glyph.isComposite():
        decompose_composite(font, glyph_name)
        glyph = glyf[glyph_name]

    sx = operation.get("sx", 1.0)
    sy = operation.get("sy", 1.0)

    if glyph.numberOfContours <= 0:
        return False

    # glyf 좌표 스케일링
    coords = list(glyph.coordinates)
    new_coords = [(int(x * sx), int(y * sy)) for x, y in coords]
    glyph.coordinates = new_coords
    print(f"    glyf: scaled sx={sx}, sy={sy} ({len(coords)} points)")

    # gvar 델타도 같은 비율로 스케일링
    if "gvar" in font and glyph_name in font["gvar"].variations:
        for var in font["gvar"].variations[glyph_name]:
            if var.coordinates is None:
                continue
            new_deltas = []
            for delta in var.coordinates:
                if delta is not None:
                    ddx, ddy = delta
                    new_deltas.append((int(ddx * sx), int(ddy * sy)))
                else:
                    new_deltas.append(None)
            var.coordinates = new_deltas
        print(f"    gvar: deltas scaled proportionally")

    # hmtx advance width도 스케일링
    if sx != 1.0 and "hmtx" in font:
        hmtx = font["hmtx"]
        width, lsb = hmtx[glyph_name]
        hmtx[glyph_name] = (int(width * sx), int(lsb * sx))
        print(f"    hmtx: width {width} → {int(width * sx)}")

    return True


def apply_adjust_metrics(font, glyph_name, operation):
    """글리프의 advance width / LSB 수정."""
    if "hmtx" not in font:
        return False

    hmtx = font["hmtx"]
    if glyph_name not in hmtx.metrics:
        print(f"    Warning: glyph '{glyph_name}' not in hmtx")
        return False

    width, lsb = hmtx[glyph_name]
    dw = operation.get("dwidth", 0)
    dlsb = operation.get("dlsb", 0)

    new_width = width + dw
    new_lsb = lsb + dlsb
    hmtx[glyph_name] = (new_width, new_lsb)

    changes = []
    if dw:
        changes.append(f"width {width}→{new_width}")
    if dlsb:
        changes.append(f"lsb {lsb}→{new_lsb}")
    print(f"    hmtx: {', '.join(changes)}")
    return True


def dump_glyph_info(font, glyph_name):
    """글리프의 좌표 정보를 출력 (디버그/설계용)."""
    glyf = font["glyf"]
    glyph = glyf[glyph_name]

    if glyph.isComposite():
        print(f"    [Composite] components:")
        for comp in glyph.components:
            print(f"      → {comp.glyphName} (offset: {comp.x}, {comp.y})")
        return

    if glyph.numberOfContours <= 0:
        print(f"    [Empty glyph]")
        return

    coords = list(glyph.coordinates)
    flags = list(glyph.flags)
    endPts = list(glyph.endPtsOfContours)

    print(f"    Contours: {glyph.numberOfContours}, Points: {len(coords)}")
    print(f"    Bounding box: ({glyph.xMin},{glyph.yMin}) – ({glyph.xMax},{glyph.yMax})")

    start = 0
    for ci, end in enumerate(endPts):
        print(f"    Contour {ci} (points {start}–{end}):")
        for pi in range(start, end + 1):
            x, y = coords[pi]
            on_curve = "on" if flags[pi] & 1 else "off"
            print(f"      [{pi:3d}] ({x:6d}, {y:6d}) {on_curve}")
        start = end + 1

    # hmtx
    if "hmtx" in font:
        width, lsb = font["hmtx"][glyph_name]
        print(f"    Metrics: width={width}, LSB={lsb}")

    # gvar 요약
    if "gvar" in font and glyph_name in font["gvar"].variations:
        vars_ = font["gvar"].variations[glyph_name]
        print(f"    gvar: {len(vars_)} variation tuple(s)")
        for vi, var in enumerate(vars_):
            axes_str = ", ".join(f"{k}:{v}" for k, v in var.axes.items())
            print(f"      [{vi}] axes=({axes_str})")


def apply_modifications(font, modifications):
    """글리프 수정 사항 적용."""
    if not modifications:
        print("  No glyph modifications configured.")
        return

    glyf = font.get("glyf")
    if glyf is None:
        print("  Warning: No glyf table found (CFF outlines not yet supported)")
        return

    for mod in modifications:
        char = mod.get("glyph", "")
        unicode_val = mod.get("unicode")
        desc = mod.get("description", "")

        # 글리프 이름 결정
        if unicode_val:
            glyph_name = get_glyph_name(font, unicode_val)
        else:
            glyph_name = get_glyph_name(font, char)

        if not glyph_name:
            print(f"  Skipping '{char}': glyph not found")
            continue

        print(f"\n  Modifying '{char}' ({glyph_name}): {desc}")

        # --dump 모드면 좌표만 출력하고 수정하지 않음
        if "--dump" in sys.argv:
            dump_glyph_info(font, glyph_name)
            continue

        for op in mod.get("operations", []):
            action = op.get("action")
            if action == "move_point":
                apply_move_point(font, glyph_name, op)
            elif action == "scale":
                apply_scale(font, glyph_name, op)
            elif action == "adjust_metrics":
                apply_adjust_metrics(font, glyph_name, op)
            else:
                print(f"    Unknown action: {action}")


def main():
    config = load_config()

    font_path = BUILD_DIR / "CKSans-Variable.ttf"
    if not font_path.exists():
        print("Error: build/CKSans-Variable.ttf not found.")
        print("Run 'make modify-params' first.")
        sys.exit(1)

    print(f"Loading: {font_path.name}")
    font = TTFont(str(font_path))

    modifications = config.get("glyph_modifications", [])

    # --dump-all: 특정 글리프들의 좌표 덤프
    if "--dump-all" in sys.argv:
        glyphs_to_dump = sys.argv[sys.argv.index("--dump-all") + 1:]
        if not glyphs_to_dump:
            glyphs_to_dump = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        glyf = font["glyf"]
        for char in glyphs_to_dump:
            glyph_name = get_glyph_name(font, char)
            if glyph_name:
                print(f"\n=== '{char}' ({glyph_name}) ===")
                dump_glyph_info(font, glyph_name)
        font.close()
        return

    print(f"\nGlyph modifications: {len(modifications)} defined")
    apply_modifications(font, modifications)

    if "--dump" not in sys.argv:
        font.save(str(font_path))
        print(f"\nSaved: {font_path}")
    else:
        print(f"\n[Dump mode — no changes saved]")

    font.close()


if __name__ == "__main__":
    main()
