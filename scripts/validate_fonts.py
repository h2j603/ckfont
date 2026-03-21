#!/usr/bin/env python3
"""
빌드된 폰트 파일 자동 검증.

빌드 파이프라인 마지막에 실행하여 구조적 오류를 조기 발견한다.
검증 실패 시 exit(1)로 빌드를 중단시킨다.

검증 항목:
  1. 테이블 구조 — glyf/CFF 일치, maxp 버전, head.glyphDataFormat
  2. 글리프 무결성 — 빈 글리프 비율, contour 수 범위
  3. 메트릭 — advance width 범위, UPM 일관성
  4. 이름 — "Noto" 잔존 여부, CK Sans 이름 확인
  5. cmap — 최소 커버리지 확인
  6. woff2 — 대응 woff2 존재 및 로드 가능 여부

사용법:
  python3 scripts/validate_fonts.py [directory]
  기본: build/ + preview/ 내 모든 .ttf, .woff2
"""

import sys
from pathlib import Path
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
PREVIEW_DIR = ROOT / "preview"


class FontValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = 0

    def error(self, font_name, msg):
        self.errors.append(f"FAIL  {font_name}: {msg}")

    def warn(self, font_name, msg):
        self.warnings.append(f"WARN  {font_name}: {msg}")

    def ok(self):
        self.passed += 1

    def validate_file(self, path):
        name = path.name
        try:
            font = TTFont(str(path))
        except Exception as e:
            self.error(name, f"파일 로드 실패: {e}")
            return

        self._check_tables(font, name)
        self._check_maxp(font, name)
        self._check_glyphs(font, name)
        self._check_metrics(font, name)
        self._check_names(font, name)
        self._check_cmap(font, name)

        font.close()

    def _check_tables(self, font, name):
        """glyf/CFF 테이블 일관성."""
        has_glyf = "glyf" in font
        has_cff = "CFF " in font or "CFF2" in font

        if has_glyf and has_cff:
            self.error(name, "glyf와 CFF 테이블이 동시에 존재")
        elif not has_glyf and not has_cff:
            self.error(name, "glyf도 CFF도 없음")
        else:
            self.ok()

        # head.glyphDataFormat
        if has_glyf:
            fmt = font["head"].glyphDataFormat
            if fmt != 0:
                self.error(name, f"head.glyphDataFormat={fmt} (TrueType은 0이어야 함)")
            else:
                self.ok()

        # loca 테이블 (glyf 필수 동반)
        if has_glyf and "loca" not in font:
            self.error(name, "glyf 존재하나 loca 테이블 없음")

    def _check_maxp(self, font, name):
        """maxp 테이블 버전 및 필드."""
        maxp = font["maxp"]

        has_glyf = "glyf" in font
        expected_ver = 0x00010000 if has_glyf else 0x00005000

        if maxp.tableVersion != expected_ver:
            self.error(
                name,
                f"maxp version=0x{maxp.tableVersion:08X} "
                f"(expected 0x{expected_ver:08X} for {'glyf' if has_glyf else 'CFF'})",
            )
        else:
            self.ok()

        # TrueType maxp 필수 필드
        if has_glyf:
            required = [
                "maxPoints", "maxContours", "maxZones",
                "maxCompositePoints", "maxCompositeContours",
            ]
            for field in required:
                if not hasattr(maxp, field):
                    self.error(name, f"maxp.{field} 필드 누락")
                else:
                    self.ok()

            # maxPoints가 0이면 의심
            if hasattr(maxp, "maxPoints") and maxp.maxPoints == 0:
                n_glyphs = maxp.numGlyphs
                if n_glyphs > 10:
                    self.warn(name, f"maxPoints=0 (글리프 {n_glyphs}개인데 의심스러움)")

    def _check_glyphs(self, font, name):
        """글리프 무결성."""
        if "glyf" not in font:
            return

        glyf = font["glyf"]
        glyph_order = font.getGlyphOrder()
        total = len(glyph_order)
        empty = 0

        for gname in glyph_order:
            g = glyf[gname]
            if g.numberOfContours == 0 and not g.isComposite():
                empty += 1

        empty_pct = empty / total * 100 if total else 0

        if empty_pct > 50:
            self.error(name, f"빈 글리프 {empty}/{total} ({empty_pct:.0f}%) — 변환 실패 의심")
        elif empty_pct > 20:
            self.warn(name, f"빈 글리프 {empty}/{total} ({empty_pct:.0f}%)")
        else:
            self.ok()

    def _check_metrics(self, font, name):
        """메트릭 범위."""
        upm = font["head"].unitsPerEm
        if upm not in (1000, 2048):
            self.warn(name, f"UPM={upm} (일반적이지 않음)")
        else:
            self.ok()

        hmtx = font["hmtx"]
        max_aw = 0
        zero_aw = 0
        for gname, (aw, lsb) in hmtx.metrics.items():
            max_aw = max(max_aw, aw)
            if aw == 0:
                zero_aw += 1

        if max_aw > upm * 3:
            self.warn(name, f"최대 advance width={max_aw} (UPM의 {max_aw/upm:.1f}배)")

    def _check_names(self, font, name):
        """이름 테이블에 Noto 잔존 여부."""
        name_table = font["name"]
        noto_found = False
        ck_found = False

        for record in name_table.names:
            text = record.toUnicode()
            if record.nameID in (1, 4, 6):
                if "Noto" in text:
                    noto_found = True
                if "CK" in text:
                    ck_found = True

        if noto_found:
            self.error(name, "이름 테이블에 'Noto' 잔존 (OFL Reserved Name 위반)")
        else:
            self.ok()

        if not ck_found:
            self.warn(name, "이름 테이블에 'CK' 없음")

    def _check_cmap(self, font, name):
        """cmap 최소 커버리지."""
        cmap = font.getBestCmap()
        if cmap is None:
            self.error(name, "cmap 테이블 없음")
            return

        count = len(cmap)
        if count < 50:
            self.error(name, f"cmap에 {count}개 문자만 매핑 — 서브셋 오류 의심")
        else:
            self.ok()

        # 기본 Latin 확인
        for cp in [0x41, 0x61, 0x30]:  # A, a, 0
            if cp not in cmap:
                self.warn(name, f"기본 Latin U+{cp:04X} 누락")

    def validate_woff2_pair(self, ttf_path):
        """TTF에 대응하는 woff2가 존재하고 로드 가능한지."""
        woff2_path = ttf_path.with_suffix(".woff2")
        name = ttf_path.name

        if not woff2_path.exists():
            self.warn(name, f"대응 woff2 없음: {woff2_path.name}")
            return

        try:
            f = TTFont(str(woff2_path))
            f.close()
            self.ok()
        except Exception as e:
            self.error(name, f"woff2 로드 실패: {e}")

    def report(self):
        print(f"\n{'='*50}")
        print(f"  Font Validation Report")
        print(f"{'='*50}")

        if self.errors:
            print(f"\n  ERRORS ({len(self.errors)}):")
            for e in self.errors:
                print(f"    {e}")

        if self.warnings:
            print(f"\n  WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"    {w}")

        print(f"\n  Passed: {self.passed}")
        print(f"  Errors: {len(self.errors)}")
        print(f"  Warnings: {len(self.warnings)}")
        print(f"{'='*50}")

        if self.errors:
            print("\n  BUILD FAILED — 위 에러를 수정하세요.\n")
            return False
        else:
            print("\n  BUILD OK\n")
            return True


def main():
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else BUILD_DIR

    validator = FontValidator()

    # TTF 검증
    ttf_files = sorted(target_dir.glob("*.ttf"))
    if not ttf_files:
        print(f"No TTF files in {target_dir}")
        sys.exit(1)

    for ttf in ttf_files:
        print(f"  Validating {ttf.name}...")
        validator.validate_file(ttf)
        validator.validate_woff2_pair(ttf)

    # preview/ woff2도 검증
    if target_dir == BUILD_DIR:
        for woff2 in sorted(PREVIEW_DIR.glob("*.woff2")):
            if woff2.stem.startswith("CKSans-Cut"):
                print(f"  Validating {woff2.name} (preview)...")
                validator.validate_file(woff2)

    ok = validator.report()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
