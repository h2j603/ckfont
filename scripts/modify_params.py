#!/usr/bin/env python3
"""
CK Font 파라미터 수정 스크립트.
config/ck-font.yaml의 설정에 따라 Noto Sans의 메타데이터와 메트릭을 수정한다.

수정 항목:
- 폰트 이름 (Family Name, Unique ID 등)
- Variable Font 축 기본값
- 타이포그래피 메트릭 (ascender, descender, line gap)
- Named Instance 정의
"""

import sys
from pathlib import Path

import yaml
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "ck-font.yaml"
SOURCES_DIR = ROOT / "sources" / "NotoSans"
BUILD_DIR = ROOT / "build"


def load_config():
    """YAML 설정 파일 로드."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_source_font():
    """소스 디렉토리에서 Variable TTF 파일 찾기."""
    ttf_files = list(SOURCES_DIR.glob("*.ttf"))
    if not ttf_files:
        print("Error: No .ttf files found in sources/NotoSans/")
        print("Run 'make download' first.")
        sys.exit(1)

    # 가장 기본적인 파일 선택
    # wdth,wght 축이 있는 파일 우선, 그 다음 Variable 패턴
    for f in ttf_files:
        if "wdth" in f.name and "wght" in f.name and "Italic" not in f.name:
            return f
    for f in ttf_files:
        if ("Variable" in f.name or "variable" in f.name) and "Italic" not in f.name:
            return f
    return ttf_files[0]


def rename_font(font, config):
    """폰트 이름을 CK Sans로 변경."""
    meta = config["meta"]
    family = meta["family_name"]
    version = meta["version"]

    name_table = font["name"]

    # Name ID 매핑
    name_updates = {
        0: meta.get("license", "SIL Open Font License 1.1"),   # Copyright
        1: family,                                                # Family Name
        2: "Regular",                                             # Subfamily
        3: f"{family.replace(' ', '')}-{version}",               # Unique ID
        4: f"{family} Regular",                                   # Full Name
        5: f"Version {version}",                                  # Version
        6: f"{family.replace(' ', '')}-Regular",                  # PostScript Name
        8: meta.get("designer", "Condensed Kiwi"),               # Manufacturer
        9: meta.get("designer", "Condensed Kiwi"),               # Designer
        11: meta.get("license_url", ""),                          # Vendor URL
        13: meta.get("license", "SIL Open Font License 1.1"),    # License
        14: meta.get("license_url", ""),                          # License URL
        16: family,                                                # Typographic Family
    }

    for name_id, value in name_updates.items():
        if not value:
            continue
        # Platform 3 (Windows), Encoding 1 (Unicode BMP), Language 0x0409 (English)
        name_table.setName(value, name_id, 3, 1, 0x0409)
        # Platform 1 (Mac), Encoding 0 (Roman), Language 0 (English)
        name_table.setName(value, name_id, 1, 0, 0)

    print(f"  Font renamed to: {family}")


def update_axes_defaults(font, config):
    """Variable Font 축 기본값 수정."""
    if "fvar" not in font:
        print("  Warning: No fvar table (not a Variable Font)")
        return

    fvar = font["fvar"]
    axes_config = config.get("axes", {})

    for axis in fvar.axes:
        tag = axis.axisTag
        if tag in axes_config:
            new_default = axes_config[tag].get("default")
            if new_default is not None:
                old_default = axis.defaultValue
                axis.defaultValue = new_default
                print(f"  Axis '{tag}' default: {old_default} → {new_default}")


def update_named_instances(font, config):
    """Named Instance 업데이트."""
    if "fvar" not in font:
        return

    fvar = font["fvar"]
    instances_config = config.get("instances", [])

    if not instances_config:
        return

    # 기존 인스턴스 제거 후 새로 추가
    from fontTools.ttLib.tables._f_v_a_r import NamedInstance

    name_table = font["name"]
    new_instances = []

    for inst_cfg in instances_config:
        inst = NamedInstance()
        inst.coordinates = inst_cfg["coordinates"]

        # 인스턴스 이름 등록
        name_id = name_table.addName(inst_cfg["name"])
        inst.subfamilyNameID = name_id

        new_instances.append(inst)

    fvar.instances = new_instances
    print(f"  Named instances updated: {len(new_instances)} instances")


def update_metrics(font, config):
    """타이포그래피 메트릭 수정."""
    metrics = config.get("metrics", {})

    if not any(v != 0 for v in metrics.values() if isinstance(v, (int, float))):
        print("  Metrics: no adjustments configured (all zero)")
        return

    # OS/2 테이블 수정
    if "OS/2" in font:
        os2 = font["OS/2"]

        asc_adj = metrics.get("ascender_adjust", 0)
        desc_adj = metrics.get("descender_adjust", 0)
        gap_adj = metrics.get("line_gap_adjust", 0)

        if asc_adj:
            os2.sTypoAscender += asc_adj
            print(f"  Ascender adjusted by {asc_adj}")
        if desc_adj:
            os2.sTypoDescender += desc_adj
            print(f"  Descender adjusted by {desc_adj}")
        if gap_adj:
            os2.sTypoLineGap += gap_adj
            print(f"  Line gap adjusted by {gap_adj}")

    # 자간 조정 (tracking)
    tracking = metrics.get("tracking_adjust", 0)
    if tracking and "hmtx" in font:
        hmtx = font["hmtx"]
        for glyph_name in hmtx.metrics:
            width, lsb = hmtx.metrics[glyph_name]
            hmtx.metrics[glyph_name] = (width + tracking, lsb)
        print(f"  Global tracking adjusted by {tracking}")


def update_os2_classes(font, config):
    """OS/2 테이블의 usWidthClass, usWeightClass를 CK 기본값에 맞게 수정."""
    if "OS/2" not in font:
        return

    os2 = font["OS/2"]
    axes = config.get("axes", {})

    # usWeightClass: 기본 Weight에 맞게
    default_wght = axes.get("wght", {}).get("default")
    if default_wght:
        old = os2.usWeightClass
        os2.usWeightClass = int(default_wght)
        print(f"  usWeightClass: {old} → {os2.usWeightClass}")

    # usWidthClass: wdth 값 → OS/2 usWidthClass 매핑
    wdth_to_class = {
        50: 1,     # Ultra-condensed
        62.5: 2,   # Extra-condensed
        75: 3,     # Condensed
        87.5: 4,   # Semi-condensed
        100: 5,    # Medium (normal)
        112.5: 6,  # Semi-expanded
        125: 7,    # Expanded
        150: 8,    # Extra-expanded
        200: 9,    # Ultra-expanded
    }
    default_wdth = axes.get("wdth", {}).get("default")
    if default_wdth and default_wdth in wdth_to_class:
        old = os2.usWidthClass
        os2.usWidthClass = wdth_to_class[default_wdth]
        print(f"  usWidthClass: {old} → {os2.usWidthClass} (wdth={default_wdth})")


def strip_hints(font):
    """힌팅 데이터 제거. 글리프 수정 후 무효화된 힌트를 정리한다."""
    hint_tables = ["fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX", "gasp"]
    removed = []
    for table_tag in hint_tables:
        if table_tag in font:
            del font[table_tag]
            removed.append(table_tag)

    # glyf 테이블의 개별 글리프 힌트도 제거
    if "glyf" in font:
        glyf = font["glyf"]
        for glyph_name in font.getGlyphOrder():
            glyph = glyf[glyph_name]
            if hasattr(glyph, "program") and glyph.program:
                glyph.program = None

    if removed:
        print(f"  Hints stripped: {', '.join(removed)}")
    else:
        print(f"  Hints: already clean")


def main(info_only=False):
    config = load_config()

    # 소스 폰트 찾기
    source_path = find_source_font()
    print(f"Source font: {source_path.name}")

    # 폰트 로드
    font = TTFont(source_path)

    if info_only:
        print("\n--- Font Info ---")
        if "fvar" in font:
            for axis in font["fvar"].axes:
                print(f"  Axis: {axis.axisTag} "
                      f"(min={axis.minValue}, default={axis.defaultValue}, max={axis.maxValue})")
            print(f"  Named instances: {len(font['fvar'].instances)}")
        if "name" in font:
            for record in font["name"].names:
                if record.nameID in (1, 2, 4, 6) and record.platformID == 3:
                    print(f"  Name[{record.nameID}]: {record.toUnicode()}")
        font.close()
        return

    print("\nApplying modifications...")

    # 1. 이름 변경
    rename_font(font, config)

    # 2. 축 기본값 수정
    update_axes_defaults(font, config)

    # 3. Named Instance 업데이트
    update_named_instances(font, config)

    # 4. 메트릭 수정
    update_metrics(font, config)

    # 5. OS/2 클래스 수정
    update_os2_classes(font, config)

    # 6. 힌팅 제거
    strip_hints(font)

    # 저장
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BUILD_DIR / "CKSans-Variable.ttf"
    font.save(str(output_path))
    font.close()

    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    info_only = "--info" in sys.argv
    main(info_only=info_only)
