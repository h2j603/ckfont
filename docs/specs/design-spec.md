# CK Sans — Design Specification

## 1. 개요

**CK Sans**는 Condensed Kiwi 디자인 팀의 시각적 아이덴티티를 구현하는 커스텀 타이포그래피다.
Noto Sans Variable Font를 기반으로, 파라미터 수정과 글리프 수정을 통해 CK만의 톤을 확립한다.

### 왜 Noto Sans인가
- **150+ 문자 체계**: 다국어 피드 전략(30개 언어) 구현을 위한 유일한 현실적 선택
- **Variable Font**: wght/wdth 축으로 다양한 스타일을 하나의 파일로 커버
- **OFL 라이선스**: 자유로운 포크와 배포 가능
- **중립적 기본형**: 수정의 기반으로 적합한 깔끔한 기본 형태

### CK Sans ≠ Noto Sans
Noto Sans를 그대로 쓰는 것이 아니라, 아래의 수정을 통해 별도의 서체로 분화시킨다:
1. **축 기본값 재설정** — Condensed + Bold를 기본 성격으로
2. **메트릭 조정** — CK 레이아웃에 최적화된 행간/자간
3. **글리프 형태 수정** — 핵심 문자의 기하학적 특성 강화
4. **Named Instance** — CK 용도에 맞는 프리셋

## 2. 디자인 원칙

### 2.1 Condensed
- CK의 핵심 톤: **긴박함, 밀도, 효율**
- Width 축 기본값: 75 (Condensed)
- 좁은 글자폭이 만드는 수직적 리듬감

### 2.2 Bold
- 시각적 무게감: **확신, 강건함, 결정적**
- Weight 축 기본값: 700 (Bold)
- 헤드라인/콜아웃 용도에 최적화

### 2.3 Geometric
- CK 브랜딩의 기하학적 추상화/옵아트 방향과 일관
- 글리프 수정 시 기하학적 특성 강화 (직선화, 각도 정리)
- 유기적/손글씨 느낌 배제

### 2.4 Modular
- 타이포그래피 시스템으로서의 모듈성
- Named Instance로 용도별 프리셋 제공
- Variable Font 축으로 미세 조정 가능

## 3. Variable Font 축 전략

### 3.1 Weight (wght)
| 값 | 이름 | CK 용도 |
|---|---|---|
| 100 | Thin | — |
| 200 | ExtraLight | — |
| 300 | Light | 본문 보조 |
| 400 | Regular | 본문 |
| 500 | Medium | — |
| 600 | SemiBold | — |
| 700 | **Bold** | **CK 기본** — 헤드라인, UI |
| 800 | ExtraBold | 강조 |
| 900 | Black | 극적 강조, 포스터 |

### 3.2 Width (wdth)
| 값 | 이름 | CK 용도 |
|---|---|---|
| 62.5 | Ultra Condensed | 극적 효과, 포스터 |
| 75 | **Condensed** | **CK 기본** |
| 87.5 | Semi Condensed | 본문 가독성 필요 시 |
| 100 | Normal | 일반 용도 |

## 4. Named Instance 프리셋

| 이름 | wght | wdth | 용도 |
|---|---|---|---|
| CK Sans Condensed Bold | 700 | 75 | **주력** — 모든 CK 콘텐츠의 기본 |
| CK Sans Condensed ExtraBold | 800 | 75 | 강조 헤드라인 |
| CK Sans Condensed Black | 900 | 75 | 포스터, 히어로 텍스트 |
| CK Sans Compressed Bold | 700 | 62.5 | 극적 효과 |
| CK Sans Regular | 400 | 87.5 | 본문, 캡션 |

## 5. 글리프 수정 방향 (Phase 계획)

### Phase 1: 파라미터만 (현재)
- 이름 변경, 축 기본값 재설정, 메트릭 조정
- Noto Sans의 형태는 유지하되 CK의 톤으로 세팅
- **목표**: 즉시 사용 가능한 CK Sans v0.1

### Phase 2: 핵심 글리프 수정
- 라틴 대문자 A–Z의 기하학적 특성 강화
  - 코너 각도 정리
  - 곡선→직선 전환 (기하학적 느낌)
  - 특정 글자의 시그니처 형태 부여
- 숫자 0–9 수정
- **목표**: CK의 시각적 차별화 확보

### Phase 3: 확장 글리프 수정
- 소문자 a–z 수정
- 특수문자/기호 수정
- 한글 글리프 검토 (Noto Sans CJK 연계 시)

### Phase 4: 다국어 일관성
- 수정된 디자인 원칙을 다른 문자 체계에도 적용 검토
- 키릴, 그리스, 데바나가리 등

## 6. 메트릭 가이드라인

(Phase 1에서는 Noto Sans 기본값 유지, 테스트 후 조정)

- **UPM**: 1000 (Noto Sans 기본)
- **Ascender**: 추후 조정
- **Descender**: 추후 조정
- **Line Gap**: 추후 조정
- **Tracking**: CK 레이아웃 테스트 후 결정

## 7. 출력 형식

| 형식 | 용도 |
|---|---|
| .ttf (Variable) | 범용 — 앱, 시스템 |
| .woff2 (Variable) | 웹 — CK 웹사이트/인스타 링크드 페이지 |

## 8. 라이선스

- **원본**: Noto Sans — SIL Open Font License 1.1
- **파생물**: CK Sans — OFL 유지 (의무)
- **이름**: "Noto" 제거 필수 (Reserved Font Name)
- **배포**: 자유 배포 가능, 폰트 단독 판매 불가

## 9. 레퍼런스 서체 비교

| 서체 | 특성 | CK와의 관계 |
|---|---|---|
| **Druk** (Commercial Type) | Ultra condensed, editorial | 톤 레퍼런스 (극적 압축감) |
| **Dharma Gothic** | Condensed gothic | 구조적 레퍼런스 |
| **GT America Compressed** | Swiss neo-grotesque compressed | 깔끔한 압축 레퍼런스 |
| **ABC Diatype Condensed** | 현대적 condensed | 동시대 레퍼런스 |
| **Monument Extended** | Brutalist, extended | 대조 레퍼런스 (반대 방향) |
| **산돌 고딕 네오 Condensed** | 한글 condensed | 한글 확장 시 참고 |
