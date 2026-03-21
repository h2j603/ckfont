# CK Sans CJK 폰트 Safari 로드 실패 — 디버깅 리포트

> 작성일: 2026-03-21
> 상태: **근본 원인 특정 완료, 수정 미적용**

---

## 1. 문제 요약

CK Sans Cut 폰트가 **Safari iOS에서 로드 실패** (`status=error`)하며 시스템 폰트로 폴백된다.
Chrome에서는 정상 작동한다.

| 폰트 | Chrome | Safari iOS |
|------|--------|------------|
| CKSans-Cut (Latin) | OK | OK |
| CKSans-Cut-KR (한글) | OK | **error** |
| CKSans-Cut-JP (일본어) | OK | **error** (추정) |
| CKSans-Cut-SC (중국어) | OK | **error** (추정) |
| CKSans-KR-Regular (pre-cut) | OK | **error** |

**핵심**: 모듈러 컷 적용 여부와 무관하게, 모든 CJK 폰트가 Safari에서 실패한다.

---

## 2. 근본 원인

### 원인 1: `sfntVersion` 불일치 (핵심 — 미수정)

소스 폰트인 `NotoSansKR-Regular.otf`는 CFF 아웃라인 폰트로, 파일 헤더의 `sfntVersion`이 `OTTO` (0x4F54544F)이다.

빌드 과정에서 CFF 아웃라인을 TrueType(`glyf`+`loca`)으로 변환했지만, **파일 헤더의 sfntVersion은 `OTTO`로 그대로 남아있다.**

```
CKSans-Regular.ttf     → sfntVersion='\x00\x01\x00\x00' (TrueType) ✅ Safari OK
CKSans-KR-Regular.ttf  → sfntVersion='OTTO' (CFF 선언)              ❌ Safari error
CKSans-Cut-KR.ttf      → sfntVersion='OTTO' (CFF 선언)              ❌ Safari error
```

- `OTTO`는 "이 폰트는 CFF 아웃라인을 포함한다"는 선언
- 실제로는 CFF 테이블이 없고 `glyf` 테이블만 있음
- **Chrome**: 실제 테이블을 보고 관대하게 처리
- **Safari/WebKit**: 헤더를 엄격하게 검증하고 불일치 시 폰트 거부

### 원인 2: `VORG` 테이블 잔류 (부분 수정)

CFF 전용 테이블인 `VORG`(Vertical Origin)가 TrueType 폰트에 남아있었다.
일부 파일에서 제거했지만 **모든 파일에 일관되게 적용되지 않았다.**

현재 VORG 상태:

| 파일 | VORG |
|------|------|
| CKSans-Cut-KR-v4.woff2 (index.html 사용) | **있음** ❌ |
| CKSans-Cut-KR-v5.woff2 | 제거됨 |
| CKSans-Cut-KR.woff2 | **있음** ❌ |
| CKSans-Cut-JP-v4.woff2 | 제거됨 |
| CKSans-Cut-SC-v4.woff2 | 제거됨 |
| CKSans-KR-Regular.woff2 | 제거됨 |

### 두 원인의 관계

VORG만 제거해도 `sfntVersion=OTTO`가 남아있으면 Safari는 여전히 거부한다.
두 문제를 **모두** 수정해야 Safari에서 로드된다.

---

## 3. 기술적 배경

### 폰트 파일 구조
```
[sfntVersion (4 bytes)] [numTables] [searchRange] [entrySelector] [rangeShift]
[Table Directory...]
[Table Data...]
```

- `sfntVersion = '\x00\x01\x00\x00'` → TrueType 아웃라인 (`glyf` 테이블 기대)
- `sfntVersion = 'OTTO'` → CFF 아웃라인 (`CFF ` 또는 `CFF2` 테이블 기대)

### CFF→TrueType 변환 시 필수 작업
1. CFF 곡선(3차 베지어) → TrueType 곡선(2차 베지어) 변환
2. `CFF`/`CFF2` 테이블 제거, `glyf`+`loca` 테이블 생성
3. `VORG` 테이블 제거 (CFF 전용)
4. `maxp` 테이블을 v1.0 (TrueType)으로 업데이트
5. **`sfntVersion`을 `'\x00\x01\x00\x00'`으로 변경** ← 이것이 누락됨

### 왜 Chrome은 되고 Safari는 안 되는가

**Chrome/Firefox — OTS (OpenType Sanitizer) 사용:**
- Google이 개발한 OTS 라이브러리로 폰트를 파싱
- 잘못된 값을 자동으로 수정(silent fix)하고 로드 계속
- sfntVersion이 OTTO여도 실제 glyf 테이블이 있으면 그냥 사용

**Safari — Apple Core Text 사용:**
- Apple의 Core Text 프레임워크로 폰트를 검증
- OTS보다 엄격하며 auto-fix 범위가 좁음
- `CGFontCreateWithDataProvider` API가 파싱 실패 시 폰트를 통째로 거부
- sfntVersion과 실제 테이블의 불일치를 허용하지 않음
- macOS Font Book의 검증과 동일한 엔진 사용

**iOS 추가 제약:**
- iOS의 모든 브라우저(Chrome, Firefox 포함)가 WebKit/Core Text 사용
- 따라서 iOS에서는 어떤 브라우저에서도 이 폰트가 로드되지 않음

---

## 4. 디버깅 타임라인

### Phase 1: 초기 CJK 모듈러 컷 구현
- `e3d1b35` — 한글/CJK 모듈러 컷 최초 추가
- `f1623f1` — CJK 서브셋 적용 + 리빌드
- `d44f005` — CJK Condensed 적용 (x-scale 0.732)

### Phase 2: 첫 번째 수정 시도 — maxp 테이블
- `fa6a8d9` — maxp 테이블 version을 0x5000(CFF)에서 0x10000(TrueType)으로 수정
- maxp에 TrueType 필수 필드(maxPoints, maxContours 등) 추가
- 결과: Chrome은 이미 작동 중이었고, Safari는 여전히 실패

### Phase 3: 프리뷰 페이지 + 캐시 무효화
- `28cb79c` — 프리뷰 페이지 새로 작성
- `7823757` — 파일명에 v4 추가 (CDN 캐시 무효화)
- 결과: 폰트 파일이 정상 전달되지만 Safari에서 여전히 error

### Phase 4: 디버그 페이지 도입
- `bcf973c` — 폰트 렌더링 디버그 페이지 추가
- `document.fonts` API로 로드 상태 확인
- 발견: `document.fonts.check()` = true이지만 실제 status = error
- 발견: canvas 측정에서 CKCutKR 너비 = system font 너비 → 폴백 확인

### Phase 5: VORG 제거 시도
- `cc5afa0` — TTF/woff2/pre-cut 비교 디버그 페이지
- 발견: Pre-cut Regular KR도 error → 모듈러 컷이 원인이 아님
- `07d3bc9` — 모든 CJK 폰트에서 VORG 테이블 제거
- `modular_cut.py`에 VORG 자동 제거 로직 추가
- 결과: VORG 제거했지만 **Safari 여전히 error**

### Phase 6: 근본 원인 특정
- 전체 테이블 구조 정밀 비교 (Latin vs KR)
- **sfntVersion 불일치 발견**: KR 폰트의 sfntVersion이 `OTTO`로 남아있음
- 모든 CJK 폰트(KR, JP, SC)가 동일 문제

---

## 5. 영향 범위

### 영향받는 파일 (sfntVersion=OTTO + glyf)

**build/ 디렉토리:**
- `CKSans-KR-Regular.ttf`
- `CKSans-JP-Regular.ttf`
- `CKSans-SC-Regular.ttf`
- `CKSans-Cut-KR.ttf`
- `CKSans-Cut-JP.ttf`
- `CKSans-Cut-SC.ttf`

**preview/ 디렉토리 (웹 서빙):**
- 위 파일들의 .woff2 변환본 전부

### 정상 파일 (sfntVersion=\x00\x01\x00\x00)
- `CKSans-Base.ttf`
- `CKSans-Regular.ttf`
- `CKSans-Cut.ttf` (Latin)
- `CKSans-Variable.ttf`
- `CKSans-InlineTest.ttf`

### 차이점
정상 파일은 Noto Sans Variable **TTF** (이미 TrueType)에서 인스턴싱.
문제 파일은 Noto Sans KR/JP/SC **OTF** (CFF 아웃라인)에서 변환.

---

## 6. 수정 방안

### 즉시 수정 (1줄)
```python
font.sfntVersion = '\x00\x01\x00\x00'
```
CFF→TrueType 변환 직후, 저장 전에 이 한 줄을 추가한다.

### 적용 위치
1. **CJK 베이스 폰트 빌드** — CFF OTF를 TTF로 변환하는 스크립트 (현재 코드베이스에 독립 스크립트 없음, 수동으로 빌드된 것으로 추정)
2. **`scripts/modular_cut.py`** — 이미 VORG 제거 로직이 있는 곳에 sfntVersion 수정 추가
3. **전체 리빌드** — build/ 폴더의 모든 CJK TTF 재생성

### 함께 수정할 사항
- VORG 제거가 일관되지 않은 파일 정리 (CKSans-Cut-KR-v4.woff2 등)
- preview/ 폴더의 v4 파일명 동기화
- `scripts/validate_fonts.py`에 sfntVersion 검증 추가

---

## 7. 검증 계획

수정 후 `debug.html`에서 확인:
1. `CKCutKR: status=loaded` (현재 `error`)
2. Canvas 너비 측정에서 `DIFFERENT → custom font loaded!`
3. 한글 글리프에 모듈러 컷 바가 보이는지 시각 확인

---

## 8. CJK 폰트 빌드 파이프라인 현황

현재 CJK 폰트는 명시적 빌드 스크립트 없이 수동으로 생성되었다.

### 소스 → 빌드 경로
```
sources/NotoSans/NotoSansKR-Regular.otf  (CFF, 24,964 glyphs, sfntVersion=OTTO)
    ↓ [1. CFF→TrueType 변환 — 수동 인라인 실행, 스크립트 미존재]
    ↓ [2. 서브셋: 24,964 → 14,309 글리프 (한글 11,172 + 라틴 95 + 기호)]
    ↓ [3. Condensed 스케일: x축 73.2% (wdth=62.5 상당)]
build/CKSans-KR-Regular.ttf              (glyf, 그러나 sfntVersion=OTTO ❌)
    ↓ [modular_cut.py]
build/CKSans-Cut-KR.ttf                  (glyf+cut, sfntVersion=OTTO ❌)
    ↓ [woff2 변환]
preview/CKSans-Cut-KR-v4.woff2           (서빙, sfntVersion=OTTO ❌)
```

### 라틴 폰트 (정상 작동)와의 비교
```
sources/NotoSans/NotoSans[wdth,wght].ttf  (TrueType Variable, sfntVersion=\x00\x01\x00\x00)
    ↓ [build_base.py — instancing (wdth=62.5, wght=400)]
build/CKSans-Regular.ttf                   (glyf, sfntVersion=\x00\x01\x00\x00 ✅)
    ↓ [modular_cut.py]
build/CKSans-Cut.ttf                       (glyf+cut, sfntVersion=\x00\x01\x00\x00 ✅)
```

**핵심 차이**: 라틴 소스는 이미 TrueType(TTF)이므로 sfntVersion이 처음부터 올바르다.
CJK 소스는 CFF(OTF)에서 변환되었으나, 이 변환이 스크립트 없이 이전 Claude 세션에서
인라인으로 실행되었기 때문에 재현 불가능하며, sfntVersion 변경이 누락되었다.

### CFF→TrueType 변환 시 수행된 작업 vs 누락된 작업
| 작업 | 상태 | 비고 |
|------|------|------|
| CFF 3차 → TrueType 2차 곡선 변환 | ✅ 완료 | cu2quPen 사용 |
| CFF 테이블 제거, glyf+loca 생성 | ✅ 완료 | |
| 서브셋 (CJK Unified 제거) | ✅ 완료 | 24,964→14,309 글리프 |
| Condensed 스케일링 | ✅ 완료 | x축 73.2% |
| maxp 버전 0x5000→0x10000 | ✅ 수정됨 | commit `fa6a8d9` |
| VORG 테이블 제거 | ⚠️ 부분 수정 | commit `07d3bc9`, 일부 파일 미적용 |
| **sfntVersion OTTO→\x00\x01\x00\x00** | **❌ 누락** | **근본 원인** |

---

## 9. 교훈

1. **CFF→TrueType 변환은 5단계** — 아웃라인 변환, CFF 테이블 제거, VORG 제거, maxp 업데이트, **sfntVersion 변경**. 어느 하나라도 빠지면 특정 브라우저에서 실패.
2. **Chrome의 관대함이 버그를 숨긴다** — Chrome(OTS)은 잘못된 sfntVersion을 자동 수정하므로 개발 중 문제를 발견하기 어렵다. Safari(Core Text)는 이를 허용하지 않는다.
3. **`document.fonts.check()`는 신뢰할 수 없다** — Safari에서 check()=true이면서 status=error인 경우가 있다. 실제 로드 상태는 `FontFace.status`로 확인해야 한다.
4. **폰트 검증 자동화 필요** — sfntVersion과 테이블 일관성을 빌드 시 자동 검증해야 이런 문제를 사전 방지할 수 있다.
5. **iOS에서는 모든 브라우저가 WebKit** — iOS Chrome도 Core Text를 사용하므로, Safari에서 안 되면 iOS 전체에서 안 된다.
