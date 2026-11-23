# 실제 실험 동영상 클립(`Split-Sync` & 뷰파인더) 리스크 검증 및 `R89` 무리스크 규칙 청사진

> **검증 완료 (CEO Gate 3 PASS)**: `@Deep_Research` 1차 공식 법률·저널·YouTube 문서 검증([원문 리포트](../04_Deep_Research/deep_research_archival_video_split_sync_report.md)) + `pipeline/config.py` 좌표 교차검증 완료 (`코드 수정 0건 · 승인 대기`).

---

## 1. 최종 판정 요약: **도입 강력 찬성 — 단, '0% Fair Use 도박 · 0-Face · 1차 CC-BY/PD 소스 전용' 잠금 필수**

1. **전략적 가치 (`PASS`)**: `2.0–4.0s` 무음 실제 실험 영상 + 하단 `Ep #31` 3D 뇌 실시간 동기화(`Split-Sync`)는 AI 캐릭터 피로감을 단번에 깨고, **0.5초 음소거 테스트(`R87`)**·**Semantic ID 고유성**·**YouTube 2025-07-15 `Inauthentic / Reused Content`(`answer/1311392`)** 방어력을 동시에 극대화합니다.
2. **원문 제안에서 반드시 수정해야 할 4대 위험 신화 (`FAIL -> R89 하드 차단`)**:
   - **❌ "분할 화면이면 Content ID를 피한다"** → 자동 매칭은 방해해도 **Manual Claiming Tool(타임스탬프 수동 청구)** 및 **DMCA 스트라이크(3회 영구 정지)**는 못 막음. **`PD / CC0 / CC-BY 4.0`만 YouTube Content ID 독점 참조 등록 자체가 금지되어 구조적 면역** 제공.
   - **❌ "밀그램·분리뇌·마시멜로·에인스워스 대학/Internet Archive 원본"** → 대부분 **현역 저작권 보유 + 아동/환자 얼굴 프라이버시 지뢰** (`Alexander Street/Penn State`, `Chedd-Angier/PBS`, `Harvard/Skinner Foundation`, `Stanford/MIT`). 방송국 로고가 없어도 `17 U.S.C. § 302–303`으로 보호되며, Internet Archive의 유저 태그 `"Public Domain"`은 법적 효력 `0`.
   - **❌ "`PNAS` 포함 오픈액세스 + 설명란 DOI만 표기"** → **`PNAS` 기본 OA는 `CC BY-NC-ND`(상업+개작 이중 금지)**, **`Science Advances`는 `CC BY-NC` 다수**, **`Nature Communications`는 임상/제3자 영상 개별 제외(`excluded from CC-BY`) 조항** 존재! 또한 `CC BY 4.0 § 3(a)`는 DOI 단독이 아닌 **저자 + 라이선스 URI + 수정(`cropped, muted`) 표기**가 법적 필수.
   - **❌ "단순 50/50 상하 분할"** → 쇼츠/릴스/틱톡 하단 UI(`Y=1248..1920`, `672px`) + 우리 노란 자막(`MarginV=510`, `Y≈1235..1410`)과 정면 충돌 → **상단 영상과 하단 뇌를 모두 `X=80..908, Y=288..1218` 안에 수납**해야 충돌 `0%`.

---

## 2. `1080×1920` 크로스플랫폼 무충돌 듀얼 모드 설계도 (`R89`)

![R89 Archival Video Dual-Mode Blueprint — Mode 1 Split-Sync & Mode 2 Dark-Navy Viewfinder + Porcelain Locator](./r89_video_split_sync_modes_blueprint.jpg)

| 구분 | **Mode 1: `Split-Sync` 상하 동기화 분할** | **Mode 2: 다크 네이비 라운드 뷰파인더 + 무광 백자 두상** |
|---|---|---|
| **적합 영상** | **행동 ↔ 뇌 회로 인과 직결** (BCI 커서 타이핑·로봇팔·거울 그리기 손 ↔ `Ep #31` 3D 뇌 실시간 발화) | **현미경·텔레메트리** (2광자 뇌척수액 세척·안구 추적 히트맵·스파이크 래스터) |
| **안전영역 (`1080×1920`)** | `X=80..908`, `Y=288..1218` (상단·우측·하단 UI & 자막 침범 `0px`) | `X=80..908`, `Y=288..1218` |
| **실제 영상 창** | 상단 라운드 창 **`X=80..908, Y=288..728`** (`828×440`, `16:9` 무왜곡 수납, `-an`) | 대형 라운드 뷰파인더 **`X=80..908, Y=288..1058`** (`828×770`, `-an`) |
| **3D 뇌 / 위치 표시** | 하단 스테이지 **`X=80..908, Y=774..1218`** (`828×444`, `Ep #31` 3D 뇌 동기화) | 좌하단 무광 백자 두상 배지 **`X=94..294, Y=948..1148`** (`200×200`, 표적 부위 점등) |
| **출처 필(`CC BY 4.0`)** | 중앙 브리지 `Y=735..767` (`Source: <Author> (<Year>) · CC BY 4.0 (cropped, muted)`) | 배지 우측 `X=312..896, Y=1084..1138` (자막 `Y=1235` 위로 `87px` 여유) |

---

## 3. `R89` 무리스크 소스 신호등 & 저널 감사 매트릭스

| 등급 | 허용 / 금지 소스 | 필수 자동 검증 게이트 (`Gear 4` & `DQ`) |
|---|---|---|
| **🟢 Tier 1 (즉시 허용 · `PD / CC0`)** | • **`17 U.S.C. § 105` 미 연방정부 직무 제작 영상** (`NIH` 내부 연구소·`NIMH`·`DARPA`·`NASA`·`NARA` — **주의: NIH 연구비 받은 일반 대학 영상은 PD 아님!**)<br>• 검증된 **`CC0 1.0`** 연구 데이터셋<br>• `1930-12-31` 이전 공표 무성 역사 필름 | • `ffmpeg -an` (**오디오 스트림 `0`**)<br>• 다중 프레임 `YuNet` (`5fps`, `< 0.42`) **얼굴 `0`건**<br>• `Google Flow` 업로드 **`0`회** (100% 로컬 Gear 4 합성) |
| **🟡 Tier 2 (조건부 허용 · `CC BY 4.0`)** | • **`PLOS Biology / PLOS ONE` · `eLife`** 보충 동영상 (가장 안전)<br>• **`Nature Communications`** (캡션/권리란 `"excluded from CC-BY"` 미포함 확인 시)<br>• **`PMC OA Subset` / `Science Advances` / `PNAS`** — **오직 개별 논문 XML/메타데이터가 `CC BY 4.0`일 때만** (`CC BY-NC` / `CC BY-NC-ND` 자동 거부!) | Tier 1 게이트 전부 +<br>• 캡션 제외 조항 정규식 검사 (`excluded`, `third party`, `permission` 차단)<br>• 화면 출처 필 + 설명란 **`Video credit:` (`TASL` + URI + `cropped & muted`)** 자동 출력 |
| **🔴 Tier 3 (영구 차단 → `R67` 백자 재연 라우팅)** | • **고전 심리학 유명 영상 전부**: 밀그램(*Obedience*), 가자니가 분리뇌(*Joe* PBS), 마시멜로 테스트, 에인스워스(*Strange Situation*), 스키너(Harvard/Skinner Foundation), H.M.(MIT), 할로우 원숭이<br>• 모든 `CC BY-NC` · `CC BY-ND` · `CC BY-SA` · 방송사/유튜브 2차 클립 · 유저 태그 `archive.org` 가짜 PD · `"Fair Use"` 주장<br>• **생존 환자/일반인 얼굴 & 18세 미만 아동 전부** (`CC BY`여도 불가 → `0-Face` 모니터/손 크롭만 허용) | `validate_archival_videos_manifest()` + `DQ8` 하드 블록 → 역사적 인간 실험은 기존 **`R67` 무표정 백자 재연**으로 자동 전환 |

---

## 4. `R89` 수치 제작 가드레일 (수익화 & 품질 잠금)
- **오디오**: `100%` 음소거 (`-an`, `audio_streams == 0`)
- **클립 길이 & 비중**: 컷당 **`2.0–4.0초`**, 편당 **`R88-A(사진) + R89(영상)` 합산 최대 `2`컷 · 전체 러닝타임 `<= 10%`** (`>= 90%` 오리지널 `Ep #31` 3D/2.5D 유지)
- **배치 금지 구역**: **Cut 1 (`0.00–2.20s`, `118pt HookTitle`) 금지** → **`Cut >= 2` (`>= 2.20s`)부터 배치** *(단, 첫 2초 훅은 `R87` + `R88` 시그니처 3D/실사급 백자 오프닝으로 잡고, 바로 이어지는 Cut 2 `2.2s` 지점에서 `Split-Sync` 실물 증거로 터뜨리는 구조가 UI·타이틀 충돌 `0%`로 가장 안전!)*
- **실동작 검증 (`DQ7`)**: 실제 프레임 움직임 확인(`min_frame_diff >= 0.30`, 정지 화면 위장 차단)
