.PHONY: all download download-cjk base cjk cut validate build clean info dump rebuild

# Default: 베이스 + CJK + 모듈러 컷 + 검증
all: base cjk cut validate

# Noto Sans 소스 다운로드 (Latin + CJK)
download:
	python3 scripts/download_source.py

# CJK 소스만 다운로드
download-cjk:
	python3 scripts/download_source.py --cjk

# 베이스 폰트 빌드 (인스턴싱 → WOFF2)
base:
	python3 scripts/build_base.py

# CJK 폰트 빌드 (CFF→TrueType 변환 + 서브셋 + Condensed)
cjk:
	python3 scripts/build_cjk.py

# 모듈러 컷 변형 (베이스 + CJK 기반)
cut: base cjk
	python3 scripts/modular_cut.py

# 폰트 검증 (테이블 구조, maxp, 이름, cmap 등)
validate:
	python3 scripts/validate_fonts.py

# 레거시: 파라미터 수정 + 글리프 수정 + Variable Font 빌드
build-variable:
	python3 scripts/modify_params.py
	python3 scripts/modify_glyphs.py
	python3 scripts/build.py

# 폰트 정보 출력
info:
	python3 -c "from scripts.build_base import print_info; from pathlib import Path; print_info(Path('build/CKSans-Base.ttf'))"

# 글리프 좌표 덤프 (make dump GLYPHS="A B C")
dump:
	python3 scripts/modify_glyphs.py --dump-all $(GLYPHS)

# 클린
clean:
	rm -rf build/*
	rm -f preview/CKSans-Base.ttf preview/CKSans-Base.woff2
	rm -f preview/CKSans-Variable.ttf preview/CKSans-Variable.woff2
	rm -f preview/CKSans-KR-*.ttf preview/CKSans-KR-*.woff2
	rm -f preview/CKSans-JP-*.ttf preview/CKSans-JP-*.woff2
	rm -f preview/CKSans-SC-*.ttf preview/CKSans-SC-*.woff2
	rm -f preview/CKSans-Cut-KR.* preview/CKSans-Cut-JP.* preview/CKSans-Cut-SC.*
	@echo "Cleaned."

# 풀 리빌드
rebuild: clean all
