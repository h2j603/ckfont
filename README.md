# CK Font

**Condensed Kiwi** 디자인 팀의 커스텀 타이포그래피 프로젝트.

Noto Sans Variable Font를 기반으로 파라미터 수정(축 값, 메트릭)과 글리프 수정(형태 변형)을 통해 CK의 시각적 아이덴티티를 폰트로 구현한다.

## 특징

- **Condensed + Bold 중심** — CK의 긴박하고 현대적인 톤
- **Variable Font** — Weight(100–900), Width(62.5–100) 축 지원
- **다국어 지원** — Noto Sans 기반 150+ 문자 체계 커버리지 유지
- **OFL 라이선스** — 자유 배포 가능

## Quick Start

```bash
# 의존성 설치
pip install -r requirements.txt

# Noto Sans 소스 다운로드
python scripts/download_source.py

# CK Font 빌드
make build
```

## 프로젝트 구조

```
sources/          원본 Noto Sans 소스
scripts/          빌드 및 수정 스크립트
config/           폰트 파라미터 설정 (YAML)
build/            빌드 출력물
docs/specs/       디자인 스펙 문서
```

## 연계

- [CK Branding Research](https://github.com/h2j603/researchlab) — 브랜딩 리서치 및 방향성

## License

SIL Open Font License 1.1
