.PHONY: all download modify-params modify-glyphs build clean info

# Default target
all: download modify-params modify-glyphs build

# Download Noto Sans source
download:
	python3 scripts/download_source.py

# Apply parameter modifications (metrics, axes)
modify-params:
	python3 scripts/modify_params.py

# Apply glyph modifications (shape changes)
modify-glyphs:
	python3 scripts/modify_glyphs.py

# Build final CK Font files
build:
	python3 scripts/build.py

# Print current font info
info:
	python3 scripts/build.py --info

# Clean build artifacts
clean:
	rm -rf build/*
	@echo "Build artifacts cleaned."

# Full rebuild from scratch
rebuild: clean all
