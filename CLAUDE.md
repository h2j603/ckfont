# CK Font — Claude 협업 가이드

## 프로젝트 개요
Condensed Kiwi(CK) 디자인 팀의 커스텀 폰트 개발 리포지토리.
Noto Sans Variable Font를 기반으로 파라미터 수정과 글리프 수정을 통해 CK의 타이포그래피 아이덴티티를 확립한다.

## 연계 프로젝트
- **researchlab**: `condensed-kiwi/projects/2026-04-01_ck-branding/` — CK 브랜딩 리서치 및 방향성
- 폰트 디자인 결정은 researchlab의 브랜딩 리서치와 일관성을 유지한다

## 사용자 프로필
- **직업**: 그래픽 디자이너
- **현재 상황**: 군복무 중 — 아이폰으로만 작업 가능
- **작업 방식**: Claude와만 개발 (FontForge, Glyphs 등 GUI 도구 미사용)
- **빌드 환경**: 이 리포지토리의 Python 스크립트 + fonttools/fontmake

## 기술 스택
- **언어**: Python 3
- **핵심 라이브러리**: fonttools, fontmake, ufo2ft, ufoLib2, glyphsLib
- **소스 폰트**: Noto Sans Variable Font (OFL 라이선스)
- **출력 형식**: .ttf, .otf, .woff2

## 디자인 방향 (researchlab 브랜딩 리서치 기반)
- **Condensed + Bold** 중심 — 긴박함, 혁신, 현대성
- **Sans-serif** — 장식 배제
- **모듈러 타이포그래피** — 기하학적 구조
- **레퍼런스**: Druk, Dharma Gothic, GT America Compressed, ABC Diatype Condensed

## Variable Font 축 (Noto Sans 기반)
- **wght** (Weight): 100–900
- **wdth** (Width): 62.5–100
- CK 기본값: wdth=75 (Condensed), wght=700 (Bold) 영역을 핵심 구간으로 설정

## 디렉토리 구조
```
ckfont/
├── CLAUDE.md            # 이 파일 — Claude 협업 규칙
├── README.md            # 프로젝트 소개
├── requirements.txt     # Python 의존성
├── Makefile             # 빌드 자동화
├── sources/             # 원본 소스 폰트 파일
│   └── NotoSans/        # Noto Sans 소스 (git에서 제외)
├── scripts/             # 폰트 빌드/수정 스크립트
│   ├── download_source.py   # Noto Sans 소스 다운로드
│   ├── modify_params.py     # 파라미터(축 값, 메트릭) 수정
│   ├── modify_glyphs.py     # 글리프 형태 수정
│   └── build.py             # 최종 빌드
├── build/               # 빌드 출력물 (git에서 제외)
├── preview/             # 웹 미리보기 (빌드 시 폰트 자동 복사)
│   └── index.html       # 브라우저에서 폰트 확인
├── docs/                # 문서
│   └── specs/           # 디자인 스펙 문서
│       └── design-spec.md
└── config/              # 폰트 설정
    └── ck-font.yaml     # CK Font 파라미터 설정
```

## 작업 원칙

### 폰트 수정 워크플로우
1. `config/ck-font.yaml`에서 파라미터 정의 (축 값, 메트릭, 글리프 수정 목록)
2. `scripts/modify_params.py`로 파라미터 적용
3. `scripts/modify_glyphs.py`로 글리프 형태 수정
4. `scripts/build.py`로 최종 폰트 빌드
5. 빌드 결과 검증

### Claude 협업 규칙
- Claude는 폰트 엔지니어링 파트너로서, 스크립트 작성과 파라미터 조정을 담당한다
- 디자인 결정(어떤 글리프를, 어떻게 수정할지)은 사용자가 한다
- 수정 사항은 항상 config에 기록하여 재현 가능하게 유지한다
- 글리프 수정 시 좌표 변경 내역을 명확히 문서화한다

### 커밋 메시지 규칙
- `font: 내용` — 폰트 파라미터/글리프 수정
- `build: 내용` — 빌드 스크립트/파이프라인 관련
- `config: 내용` — 설정 변경
- `docs: 내용` — 문서 관련
- `chore: 내용` — 프로젝트 구조/설정

## 라이선스 참고
- Noto Sans: SIL Open Font License (OFL)
- CK Font (파생물): OFL 유지 필수 — 폰트 단독 판매 불가, 소프트웨어 번들 가능
- 폰트 이름은 반드시 변경해야 함 (OFL Reserved Font Name 조항)
