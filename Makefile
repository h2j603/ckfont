.PHONY: all download base build clean info dump rebuild

# Default: 베이스 폰트 빌드
all: base

# Noto Sans 소스 다운로드
download:
	python3 scripts/download_source.py

# 베이스 폰트 빌드 (Condensed ExtraBold 정적 인스턴스)
base:
	python3 scripts/build_base.py

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
	@echo "Cleaned."

# 풀 리빌드
rebuild: clean base
