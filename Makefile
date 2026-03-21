.PHONY: all download modify-params modify-glyphs build clean info dump validate rebuild

# Default target
all: download modify-params modify-glyphs build

# Download Noto Sans source
download:
	python3 scripts/download_source.py

# Apply parameter modifications (metrics, axes, naming, hints)
modify-params:
	python3 scripts/modify_params.py

# Apply glyph modifications (shape changes + gvar sync)
modify-glyphs:
	python3 scripts/modify_glyphs.py

# Build final CK Font files (ttf, woff2, preview copy)
build:
	python3 scripts/build.py

# Print current font info
info:
	python3 scripts/build.py --info

# Dump glyph coordinates (A-Z by default, or specify: make dump GLYPHS="A B C")
dump:
	python3 scripts/modify_glyphs.py --dump-all $(GLYPHS)

# Validate font with fontbakery
validate:
	fontbakery check-universal build/CKSans-Variable.ttf

# Clean build artifacts
clean:
	rm -rf build/*
	rm -f preview/CKSans-Variable.ttf preview/CKSans-Variable.woff2
	@echo "Build artifacts cleaned."

# Full rebuild from scratch
rebuild: clean all
