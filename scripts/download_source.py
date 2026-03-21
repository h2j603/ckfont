#!/usr/bin/env python3
"""
Noto Sans Variable Font 소스 다운로드 스크립트.
Google Fonts GitHub 릴리즈에서 최신 Noto Sans Variable TTF를 가져온다.
"""

import os
import sys
import urllib.request
import json
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources" / "NotoSans"

# Noto Sans Latin/Greek/Cyrillic 릴리즈 API
REPO_API = "https://api.github.com/repos/notofonts/latin-greek-cyrillic/releases/latest"

# 다운로드할 파일 패턴
TARGET_PATTERNS = [
    "NotoSans",           # Latin 기본
]


def get_latest_release():
    """GitHub API에서 최신 릴리즈 정보 조회."""
    print("Fetching latest Noto Sans release info...")
    req = urllib.request.Request(REPO_API)
    req.add_header("User-Agent", "ckfont-downloader")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data
    except Exception as e:
        print(f"Error fetching release info: {e}")
        sys.exit(1)


def find_variable_ttf_assets(release):
    """릴리즈 에셋 중 Variable TTF 파일 찾기."""
    assets = []
    for asset in release.get("assets", []):
        name = asset["name"]
        # Variable TTF 파일만 선택
        if name.endswith(".ttf") and "Variable" in name:
            for pattern in TARGET_PATTERNS:
                if pattern in name:
                    assets.append({
                        "name": name,
                        "url": asset["browser_download_url"],
                        "size": asset["size"],
                    })
                    break
    return assets


def download_file(url, dest_path):
    """파일 다운로드."""
    print(f"  Downloading: {dest_path.name} ...", end=" ", flush=True)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "ckfont-downloader")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        dest_path.write_bytes(data)
        size_mb = len(data) / (1024 * 1024)
        print(f"OK ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def main():
    # 출력 디렉토리 생성
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    # 최신 릴리즈 조회
    release = get_latest_release()
    tag = release.get("tag_name", "unknown")
    print(f"Latest release: {tag}")

    # Variable TTF 에셋 찾기
    assets = find_variable_ttf_assets(release)
    if not assets:
        print("No Variable TTF assets found in the latest release.")
        print("Falling back to direct font file download...")
        # 직접 URL로 폴백
        fallback_url = (
            "https://github.com/notofonts/latin-greek-cyrillic/releases/latest"
        )
        print(f"Please manually download from: {fallback_url}")
        sys.exit(1)

    print(f"\nFound {len(assets)} Variable TTF file(s):")
    for a in assets:
        print(f"  - {a['name']} ({a['size'] / 1024:.0f} KB)")

    # 다운로드
    print("\nDownloading to sources/NotoSans/ ...")
    success = 0
    for asset in assets:
        dest = SOURCES_DIR / asset["name"]
        if dest.exists():
            print(f"  Skipping (already exists): {asset['name']}")
            success += 1
            continue
        if download_file(asset["url"], dest):
            success += 1

    # 버전 정보 기록
    version_file = SOURCES_DIR / "VERSION"
    version_file.write_text(f"{tag}\n")

    print(f"\nDone: {success}/{len(assets)} files downloaded.")
    print(f"Version: {tag}")


if __name__ == "__main__":
    main()
