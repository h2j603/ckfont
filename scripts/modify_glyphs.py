#!/usr/bin/env python3
"""
CK Font 글리프 수정 스크립트.
config/ck-font.yaml의 glyph_modifications 설정에 따라 글리프 형태를 수정한다.

지원하는 수정 타입:
- move_point: 특정 포인트 좌표 이동
- scale: 글리프 전체 또는 부분 스케일링
- round_corners: 코너 라운딩 (추후 구현)
- custom: 사용자 정의 변환

이 스크립트는 build/CKSans-Variable.ttf를 수정한다.
먼저 modify_params.py가 실행되어 있어야 한다.
"""

import sys
from pathlib import Path

import yaml
from fontTools.ttLib import TTFont
from fontTools.pens.t2Pen import T2Pen
from fontTools.pens.recordingPen import RecordingPen

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


def apply_move_point(glyf_table, glyph_name, operation):
    """특정 포인트를 이동."""
    if glyph_name not in glyf_table:
        print(f"    Warning: glyph '{glyph_name}' not found")
        return False

    glyph = glyf_table[glyph_name]
    if not glyph.isComposite() and glyph.numberOfContours > 0:
        contour_idx = operation.get("contour", 0)
        point_idx = operation.get("point", 0)
        dx = operation.get("dx", 0)
        dy = operation.get("dy", 0)

        coords = list(glyph.coordinates)
        # 컨투어 내 포인트 인덱스 계산
        if contour_idx < len(glyph.endPtsOfContours):
            start = 0 if contour_idx == 0 else glyph.endPtsOfContours[contour_idx - 1] + 1
            abs_idx = start + point_idx
            if abs_idx < len(coords):
                old_x, old_y = coords[abs_idx]
                coords[abs_idx] = (old_x + dx, old_y + dy)
                glyph.coordinates = coords
                print(f"    Point moved: contour={contour_idx}, point={point_idx}, "
                      f"({old_x},{old_y}) → ({old_x+dx},{old_y+dy})")
                return True
            else:
                print(f"    Warning: point index {abs_idx} out of range")
        else:
            print(f"    Warning: contour index {contour_idx} out of range")
    return False


def apply_scale(glyf_table, glyph_name, operation):
    """글리프 전체 스케일링."""
    if glyph_name not in glyf_table:
        print(f"    Warning: glyph '{glyph_name}' not found")
        return False

    glyph = glyf_table[glyph_name]
    sx = operation.get("sx", 1.0)
    sy = operation.get("sy", 1.0)

    if not glyph.isComposite() and glyph.numberOfContours > 0:
        coords = list(glyph.coordinates)
        new_coords = []
        for x, y in coords:
            new_coords.append((int(x * sx), int(y * sy)))
        glyph.coordinates = new_coords
        print(f"    Scaled: sx={sx}, sy={sy}")
        return True
    return False


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

        print(f"  Modifying '{char}' ({glyph_name}): {desc}")

        for op in mod.get("operations", []):
            action = op.get("action")
            if action == "move_point":
                apply_move_point(glyf, glyph_name, op)
            elif action == "scale":
                apply_scale(glyf, glyph_name, op)
            else:
                print(f"    Unknown action: {action}")


def main():
    config = load_config()

    # 빌드된 폰트 찾기
    font_path = BUILD_DIR / "CKSans-Variable.ttf"
    if not font_path.exists():
        print("Error: build/CKSans-Variable.ttf not found.")
        print("Run 'make modify-params' first.")
        sys.exit(1)

    print(f"Loading: {font_path.name}")
    font = TTFont(str(font_path))

    modifications = config.get("glyph_modifications", [])
    print(f"\nGlyph modifications: {len(modifications)} defined")

    apply_modifications(font, modifications)

    # 저장 (덮어쓰기)
    font.save(str(font_path))
    font.close()

    print(f"\nSaved: {font_path}")


if __name__ == "__main__":
    main()
