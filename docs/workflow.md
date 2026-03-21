# CK Sans — 개발 워크플로우

> 아이폰 + Claude만으로 폰트를 개발하는 구체적인 작업 흐름.

## 제약 조건

| 항목 | 상태 |
|---|---|
| 데스크탑 앱 (Glyphs, FontForge, RoboFont) | ✗ 사용 불가 |
| GUI 에디터 | ✗ 사용 불가 |
| 작업 도구 | Claude + Python 스크립트 |
| 미리보기 | preview/index.html (브라우저) |
| 입력 장치 | 아이폰 화면 |

## 핵심 결정: 컴파일된 .ttf 직접 수정

Noto Sans 소스는 `.glyphspackage` 형식이고, 빌드에 noto-build 파이프라인이 필요하다.
이걸 분해해서 UFO/Designspace로 변환하는 건 불필요한 복잡도를 만든다.

**→ 릴리즈된 Variable TTF (`NotoSans[wdth,wght].ttf`)를 fonttools로 직접 수정한다.**

이유:
- 단일 파일로 관리 (UFO는 수백 개 파일)
- fonttools TTFont API로 모든 테이블 접근 가능
- Noto 빌드 인프라 의존성 제거
- Claude와의 대화로 즉시 수정 → 빌드 → 미리보기 가능

## 작업 사이클

```
[1] 혁이 수정 방향 지시 (예: "A의 꼭짓점을 더 날카롭게")
     ↓
[2] Claude가 config/ck-font.yaml에 수정 사항 기록
     ↓
[3] Claude가 스크립트 실행 (modify_params → modify_glyphs → build)
     ↓
[4] preview/index.html에 빌드된 폰트 반영
     ↓
[5] 혁이 브라우저에서 확인 → 피드백
     ↓
[6] 만족하면 git commit, 아니면 [1]로 돌아감
```

### 이 사이클이 가능한 이유
- 모든 수정이 YAML 설정 + Python 스크립트로 **재현 가능**
- 빌드가 몇 초 안에 끝남 (컴파일이 아니라 테이블 수정)
- 미리보기가 HTML이므로 아이폰 브라우저에서 즉시 확인

## Variable Font 수정 시 반드시 알아야 할 것

### gvar 테이블 = 핵심

Variable Font에서 글리프 형태는 두 곳에 저장된다:

1. **`glyf` 테이블**: 기본 축 값(default)에서의 좌표
2. **`gvar` 테이블**: 각 축 값 변화에 따른 **좌표 델타(Δ)**

```
예: "A" 글리프의 꼭짓점
  glyf 기본 좌표: (300, 700)
  gvar 델타 (wght=900): (+20, +10)  → Black에서는 (320, 710)
  gvar 델타 (wdth=62.5): (-30, 0)   → UltraCondensed에서는 (270, 700)
```

**⚠ 절대 규칙**: `glyf`를 수정하면 `gvar`도 반드시 확인/수정해야 한다.
안 그러면 기본값(wght=700, wdth=75)에서는 멀쩡하지만 다른 축 값에서 글리프가 깨진다.

### 컴포넌트 글리프

많은 글리프가 "조립식"이다:
- `é` = `e` + `acutecomb` (합성 글리프)
- `e`를 수정하면 `é`도 자동으로 바뀜
- 하지만 합성 글리프를 직접 수정하려면 먼저 분해(decompose)해야 함

### 힌팅 데이터

글리프 좌표를 수정하면 힌팅(hinting) 데이터가 무효화된다.
**→ 수정 후 힌팅을 제거**한다 (`fpgm`, `prep`, `cvt` 테이블 삭제).
웹/모바일에서는 힌팅 없이도 충분히 렌더링된다.

## 글리프 수정 패턴 (구체적 방법)

### 1. 포인트 직접 이동
가장 기본적인 수정. 특정 좌표를 이동한다.
```python
glyph = glyf["A"]
coords = list(glyph.coordinates)
coords[2] = (coords[2][0], coords[2][1] + 10)  # 포인트 2를 위로 10 이동
glyph.coordinates = coords
```
**용도**: 꼭짓점 각도 조정, 특정 부분 미세 수정

### 2. 글리프 스케일링
전체 형태를 비율로 조정한다.
```python
for i, (x, y) in enumerate(coords):
    coords[i] = (int(x * 0.95), y)  # x축 5% 축소 (더 좁게)
```
**용도**: 개별 글리프의 너비/높이 조정

### 3. 코너 처리
On-curve 점 사이에 off-curve 제어점을 삽입하여 코너를 둥글게/날카롭게.
**용도**: CK의 기하학적 특성 강화

### 4. 메트릭 수정
글리프 형태가 아닌 간격 조정.
```python
hmtx = font["hmtx"]
width, lsb = hmtx["A"]
hmtx["A"] = (width - 20, lsb)  # A의 advance width 축소
```
**용도**: 자간 조정, 글리프별 간격 최적화

## 검증 도구

| 도구 | 용도 | 명령어 |
|---|---|---|
| **fontbakery** | 종합 QA (200+ 체크) | `fontbakery check-universal build/CKSans-Variable.ttf` |
| **fonttools ttx** | XML 덤프로 변경사항 비교 | `ttx -o before.ttx source.ttf && diff before.ttx after.ttx` |
| **diffenator2** | 수정 전후 시각적 비교 | `diffenator2 before.ttf after.ttf -o diff-report` |
| **preview/index.html** | 실시간 브라우저 미리보기 | 빌드 후 바로 확인 |

## 작업 Phase 별 구체적 할 일

### Phase 1: 파라미터 세팅 (현재)
1. ~~Noto Sans Variable TTF 다운로드~~ → `make download`
2. ~~이름 변경 (Noto Sans → CK Sans)~~ → `modify_params.py`
3. ~~축 기본값 변경 (wdth=75, wght=700)~~ → `modify_params.py`
4. ~~Named Instance 정의~~ → `modify_params.py`
5. OS/2 테이블 수정 (usWidthClass, usWeightClass) → 추가 필요
6. 힌팅 제거 → 추가 필요
7. `fontbakery` 검증 → 설치 필요
8. preview에서 확인 → 빌드 후

### Phase 2: 핵심 글리프 수정
1. 현재 글리프 좌표 덤프 (A-Z 각각의 포인트 구조 파악)
2. 혁과 논의: 어떤 문자를, 어떻게 수정할지 결정
3. 수정 사항을 YAML에 기록
4. 수정 적용 + gvar 델타 정합성 확인
5. 수정 전후 비교 (diffenator2 또는 preview 비교 뷰)

### Phase 3 이후: 확장
- 소문자, 숫자, 한글(Noto Sans CJK 연계)

## 주의사항 (피해야 할 함정)

1. **gvar 무시하고 glyf만 수정** → 다른 축 값에서 깨짐
2. **포인트 추가/삭제** → gvar 델타 개수 불일치로 크래시
3. **힌팅 유지** → 수정된 좌표와 안 맞아서 렌더링 이상
4. **컴포넌트 글리프 직접 수정** → 분해 없이 수정하면 무시됨
5. **이름 안 바꾸고 배포** → OFL Reserved Font Name 위반
