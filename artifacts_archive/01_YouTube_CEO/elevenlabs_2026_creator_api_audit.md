# ElevenLabs 2026 실시간 브라우저/공식 문서 전수 감사 보고서 (`elevenlabs.io` Live Audit)

> [!IMPORTANT]
> **검증 일시 및 방법**: 2026-11-09 (Naver Whale CDP `127.0.0.1:9222` 격리 탭으로 실시간 브라우징 후 탭 즉시 정리 완료)
> **검증 범위**: `https://elevenlabs.io/pricing` (12개 비교 탭 전수), `https://elevenlabs.io/pricing/api`, `https://elevenlabs.io/docs/overview/models`, `https://elevenlabs.io/docs/llms.txt` 및 공식 API 레퍼런스/가이드 `.md` 원문 34종 전수 대조

---

## 1. Creator Plan (`$22/mo`) 전수 해부 & 왜 `121k credits/month`인가?

### 1-1. `100k`가 아닌 `121k credits/month`가 뜬 정확한 이유
- **결론**: 무료(Free) 플랜 잔여 크레딧 이월이 **아닙니다** (Free 플랜은 이월 불가). ElevenLabs가 **2026년 요금제 개편에서 Creator 플랜의 기본 월간 제공량을 기존 `100,000`에서 `121,000 credits/month`로 공식 `+21%` 영구 상향**했습니다 (Pro 플랜 역시 `500k` → `600k credits/month`로 상향).
- **2026년 실시간 전 플랜 기본 쿼터 & 가격표 (`ElevenCreative` `/pricing` 기준)**:
  - **Free**: `$0/mo` — `10,000` credits/mo (비상업적 용도, 귀속 표기 필수)
  - **Starter**: `$6/mo` (첫 달 `$1` 프로모션 / 연간 `$5/mo`) — `30,000` credits/mo, 상업적 라이선스, IVC 해금
  - **Creator**: **`$22/mo`** (**첫 달 50% 할인 `$11` 프로모션** / 연간 결제 시 2개월 무료 = **`$18.33/mo`**) — **`121,000` credits/mo**
  - **Pro**: `$99/mo` (연간 `$82.50/mo`) — `600,000` credits/mo, `44.1 kHz PCM/WAV` TTS API 해금
  - **Scale**: `$299/mo` — `1,800,000` credits/mo (3 시트)
  - **Business**: `$990/mo` — `6,000,000` credits/mo (10 시트)

### 1-2. 2026 최대 핵심 발견: 웹 UI(`ElevenCreative`) vs API(`ElevenAPI`) 차감 단가 이원화
`docs/overview/administration/billing.md` 및 `https://elevenlabs.io/pricing/api` 실시간 대조 결과, ElevenLabs는 2026년에 요금 표시를 **웹 크리에이티브(`ElevenCreative`)** 와 **개발자 API(`ElevenAPI`)** 로 통합 풀 운영하되 **웹 UI 생성보다 API 호출 시 글자당 차감 단가를 대폭 낮췄습니다**:
- **웹 UI (`ElevenCreative`)에서 TTS 생성 시**: `1 credit = 1 character` (`eleven_v4` / `eleven_v3` / `eleven_multilingual_v2`) → 월 **`121,000`자** (`~121분`)
- **API (`ElevenAPI`)에서 TTS 생성 시 (`/pricing/api` 공식 수치)**:
  - 플래그십 모델 (`eleven_v4`, `eleven_v3`, `eleven_multilingual_v2`): **`$0.08 / 1,000 chars`** → `$22` 플랜 기준 월 최대 **`275,000`자 (`~275분`, 웹 UI 대비 `2.27배`)**
  - 고속 모델 (`eleven_v4_turbo`, `eleven_v3_conversational`, `eleven_flash_v2_5`): **`$0.04 / 1,000 chars`** → 월 최대 **`550,000`자 (`~550분`)**
- **검증 포인트**: 결제 체크아웃 경로가 `/app/subscription/creative?tier=creator` 와 `/app/subscription/api?tier=creator` 두 가지로 나뉘므로, 가입 직후 `GET /v1/user/subscription` 및 첫 테스트 호출의 응답 헤더 `character-cost`로 차감 배율을 즉시 자동 확인할 수 있습니다. 보수적으로 `1 char = 1 credit` (`121,000`자) 기준으로 잡아도 월 70편 이상, API 요율(`275,000`자) 적용 시 월 **160편 이상** 제작됩니다.

### 1-3. 미사용 크레딧 이월(`Credit Rollover`) & 초과 과금(`PAYG Top Up`) 개편
- **최대 2개월치 크레딧 자동 이월 (`Credit Rollover`)**:
  - 유료 플랜 유지 중 미사용 구독 크레딧은 **최대 2개월치(`2 × 121,000 = 242,000` credits)** 까지 자동 이월됩니다.
  - 당월 신규 지급분(`121,000`) + 최대 이월분(`242,000`) = 계정에 쌓을 수 있는 **최대 누적 크레딧 풀은 `363,000` credits (`3×`)** 입니다.
  - **소멸 조건**: 구독 해지(Cancel) 또는 하위 플랜 다운그레이드 시 결제 주기 종료일에 이월분이 소멸하며, 상위 플랜 업그레이드 시에는 그대로 유지됩니다.
  - **웹 UI 무료 재생성**: 웹 대시보드에서 완전히 동일한 텍스트+설정으로 다시 뽑을 때 **최대 2회 무료 재생성**이 제공됩니다 (API 호출은 미적용).
- **초과 요금 폭탄 원천 차단 (`Usage-Based Billing` 폐지 → 선불 `Pay As You Go Top Up`)**:
  - 과거의 월말 후불 초과 과금(`$0.30/1K`)은 신규 셀프서브 계정에서 **공식 폐지(Deprecated)** 되었습니다.
  - 대신 `Developers → Top Up`에서 필요할 때만 충전하는 선불식 **Pay As You Go (`$5` 최소 충전, 유효기간 12개월, `Auto Top Up` 기본값 OFF)** 로 전환되어 **자동 초과 청구 위험이 `0%`** 입니다. (참고: 계정에 2FA가 꺼져 있으면 월 충전 한도가 `$100/월`로 제한됨)

### 1-4. Creator 플랜 세부 스펙 매트릭스 (음질 / 동시성 / 보이스 슬롯 / 부가 도구)

| 항목 | Creator (`$22/mo`, 첫 달 `$11`) 실시간 검증 스펙 | 치명적 주의사항 (`Gotchas`) |
|---|---|---|
| **TTS API 최대 음질** | **`mp3_44100_192` (`44.1kHz 192kbps MP3`)**, **`opus_48000_192` (`48kHz 192kbps`)**, `pcm_8000`~`pcm_32000`, `wav_8000`~`wav_32000` | **`pcm_44100` / `wav_44100`은 Pro (`$99/mo`) 전용!** Creator에서 요청 시 거절됨 |
| **Studio (웹 에디터) 음질** | 프로젝트 `1,000`개, 무워터마크 내보내기 — **단, 웹 Studio 내보내기 음질은 `128 kbps MP3` 고정!** | 웹 UI에서 다운로드하면 `128kbps`로 손실됨! **무조건 API로 `mp3_44100_192` / `opus_48000_192` 수확 필수!** |
| **동시성 (`Concurrency`)** | 우선순위 `Level 5` / 일반 HTTP TTS & Dialogue: **`5`개** / 고속 TTS (`v4_turbo`, `flash_v2_5`): **`10`개** / SFX (`v3`): **`6`개** / STT (`scribe_v2`): **`20`개** | 에피소드 원패스/소수 병렬 호출에 병목 제로 |
| **보이스 슬롯 (`Voice Slots`)** | 커스텀 슬롯 **`30`개** (IVC + PVC + Voice Design 공유) + **Voice Library(`17,000+` 커뮤니티 보이스)는 커스텀 슬롯 `0`개 소모!** | Starter(`10`개) 대비 3배 여유 |
| **Professional Voice Cloning** | **`1`개 포함 (`1 PVC slot`)** — Creator 이상 전용, `eleven_v4` 전용 `clone_strength` (`0.0~1.0`) 지원 | 단일 채널 시그니처 성우 구축에 `1`개면 충분 |
| **Voice Design v3** | **`eleven_ttv_v3`** 포함 — 텍스트 프롬프트 + 레퍼런스 오디오 블렌딩으로 독점 보이스 3종 프리뷰 생성 | 프리뷰 샘플 글자수(`~300`자)만 차감, 슬롯 저장 비용 `0` |
| **Sound Effects (`SFX v3`)** | 월 약 `605`회 (시간 지정 시 **`40 credits/초`**, 미지정 시 약 `200 cr/회`, API `$0.12/분`), 최대 `30초`, `loop=true`, **`48 kHz WAV` 지원!** | TTS와 달리 **효과음은 Creator에서도 무손실 `48 kHz WAV` 지원!** |
| **Music (`music_v2_5`)** | 월 약 `134분` UI (`900 cr/분`) / API `147분` (`$0.15/분`), 2 & 4 스템 분리, 유튜브 상업 이용 가능 | 자체 다크 서스펜스 BGM 생성/스템 분리 실험 가능 |
| **Scribe v2 (초정밀 STT)** | 웹 UI `6시간 7분` / **API 호출 시 월 `100시간` (`$0.22/시간`)** | `posthoc-qa` 발음/단어 누락 역검증기가 사실상 공짜 |

---

## 2. 2026 공식 모델 라인업 & 호환성 매트릭스 (`docs/overview/models`)

> [!TIP]
> **2026 핵심 변화 — `Eleven v4` (`eleven_v4`) 및 `Eleven v4 Turbo` (`eleven_v4_turbo`) 정식 출시!**
> 공식 문서에서 `eleven_v3`는 *"previous generation"* 으로 분류되었으며, **동일 가격에 글자 한도 2배(`10,000`자), 감정 표현력, `[audio tags]`, 슬래시 `"/IPA/"` 발음, PVC `clone_strength`, 그리고 `v3`에 없던 `previous_request_ids` 오디오 스티칭까지 모두 지원하는 `eleven_v4`가 2026 최우선 플래그십 모델**입니다.

### 2-1. 현역 & 레거시 오디오 모델 전수 비교표

| 모델명 | 정확한 `model_id` | 단가 (UI / API) | 1회 한도 | 핵심 특징 및 주의점 |
|---|---|---|---|---|
| **Eleven v4** *(2026 플래그십)* | `eleven_v4` | `1 cr` / **`$0.08/1K`** | **`10,000`자** | **최상위 권장 모델**. `[audio tags]`, `"/IPA/"` 발음, PVC `clone_strength`, `previous_request_ids` 스티칭 완벽 지원 |
| **Eleven v4 Turbo** *(신규 고속)* | `eleven_v4_turbo` | `0.5 cr` / **`$0.04/1K`** | `10,000`자 | `~100ms` 저지연 + 반값으로 `[audio tags]` 지원 |
| **Eleven v3** *(이전 세대)* | `eleven_v3` | `1 cr` / `$0.08/1K` | `5,000`자 | `[audio tags]` 지원하나 **`previous_request_ids` 스티칭 미지원** (단, Voice Design 보이스 A/B 비교용 가치 있음) |
| **Eleven Multilingual v2** | `eleven_multilingual_v2` | `1 cr` / `$0.08/1K` | `10,000`자 | 정통 다큐 톤. `speed`(`0.7~1.2`), `style`, `<break>` 지원 (`[audio tags]`는 글자 그대로 읽으므로 사용 금지) |
| **Eleven Flash v2.5** | `eleven_flash_v2_5` | `0.5 cr` / `$0.04/1K` | `40,000`자 | `~75ms` 초고속 반값 (`eleven_turbo_v2_5`는 공식 Deprecated) |
| **SFX v3** *(효과음 주력)* | `eleven_text_to_sound_v3` | `40 cr/s` / `$0.12/분` | `0.5~30.0s` | `48kHz WAV` + `loop=true` 지원. API 기본값이 아직 구형 `v2`(2027-03-01 삭제)이므로 **`model_id` 명시 필수!** |
| **Voice Design v3** | `eleven_ttv_v3` | 샘플 글자수만 차감 | 프롬프트 `1k`자 | 레퍼런스 오디오 하이브리드 보이스 설계. API 기본값이 `v2`이므로 **`eleven_ttv_v3` 명시 필수!** |

> [!WARNING]
> **2026년 12월 31일 구형 기본(Default) 보이스 일괄 만료 경고 (`voices.md`)**
> 구 Rachel(`21m00Tcm4TlvDq8ikWAM`) 등 레거시 기본 프리셋 보이스들이 **2026-12-31부로 일괄 Sunset(만료)** 됩니다. 파이프라인에는 반드시 **신규 영구(Perpetual) 보이스, Voice Library 검증 보이스, 또는 자체 생성한 Voice Design / PVC 보이스 ID**만 등록해야 합니다.

### 2-2. 모델별 파라미터/기능 호환성 대조표

| 기능 / 파라미터 | `eleven_v4` *(권장)* | `eleven_v3` | `eleven_multilingual_v2` | `eleven_flash_v2_5` |
|---|---|---|---|---|
| `/v1/text-to-speech/{id}/with-timestamps` | ✅ 지원 | ✅ 지원 | ✅ 지원 | ✅ 지원 |
| `/v1/text-to-dialogue/with-timestamps` | ✅ **완벽 지원** (`model_id` 명시!) | ✅ 지원 (기본값) | ❌ 미지원 | ❌ 미지원 |
| 인라인 `[audio tags]` (`[whispers]` 등) | ✅ **최상위 지원** | ✅ 지원 | ❌ 글자 그대로 읽음 | ❌ 글자 그대로 읽음 |
| 슬래시 IPA 발음 (`"/pəˈraɪɪtəl/"`) | ✅ **네이티브 지원** | ❌ 미지원 | ❌ 사전 Alias 필요 | ❌ 미지원 |
| SSML `<break time="1.0s"/>` | ❌ **미지원** (`[short pause]`, `—` 사용) | ❌ 미지원 | ✅ 지원 | ✅ 지원 |
| `voice_settings.speed` (`0.7~1.2`) | ❌ **미지원** (`[Quick pace]` 태그 사용) | ❌ 미지원 | ✅ 지원 | ✅ 지원 |
| `previous_request_ids` 스티칭 | ✅ **지원** (최대 3개, 2시간 유효) | ❌ **공식 미지원** | ✅ 지원 | ✅ 지원 |

---

## 3. 쇼츠 파이프라인 직결 API 스펙 & 실전 함정 (`Gotchas`)

### 3-1. 쇼츠 게임체인저: `POST /v1/text-to-dialogue/with-timestamps`
단일 내레이터의 `13~20`문장 멀티비트 스토리텔링(또는 중간 1줄 `foil_v8` 카메오 포함)을 **단 1번의 호출로 통째로 연기하면서 문장별 시작/종료 초(`voice_segments`)와 글자별 타임스탬프(`normalized_alignment`)를 동시에 반환**합니다.
- **절대 놓치면 안 되는 스키마 차이점 4가지**:
  1. **1회 권장 총 글자수 상한 = `2,000 characters`**: 우리 `58~88s` 쇼츠 대본(`185~230`단어 + `[audio tags]`)은 총 **`1,350 ~ 1,700 characters`** 로 `2,000`자 한도 안에 정확히 들어와 **쇼츠 1편 = API 단 1회 호출**로 완결됩니다 (2,000자 초과 시에만 전반/후반 2분할 + `previous_request_ids` 스티칭).
  2. 필드명이 `voice_settings` / `similarity_boost`가 아니라 **`"settings": {"stability": 0.45, "similarity": 0.75}`** 입니다 (`voice_settings` 전송 시 `422` 오류).
  3. 후행 문맥 필드명이 `next_text`가 아니라 **`future_text` (최대 `100`자)** 입니다.
  4. 기본 `model_id`가 `"eleven_v3"`이므로 반드시 **`"model_id": "eleven_v4"`** 와 쿼리 **`?output_format=mp3_44100_192`** 를 명시해야 합니다.
- **SFX 오인 발화 함정 (`best-practices.md` 경고)**:
  - `eleven_v4`는 효과음 생성도 함께 학습되어 있어 `[alarm]`, `[heartbeat]`처럼 명사만 단독으로 쓰면 성우 연기 대신 실제 효과음을 낼 수 있습니다. 반드시 **`[urgent, breathless voice]`**, **`[low, tense narration]`**, **`[quiet, stunned realization]`** 처럼 발성/어조 지시어를 명시해야 합니다.

### 3-2. 사전 쿼터 가드레일: `GET /v1/user/subscription`
- `tier` (`"creator"`), `character_count` (사용량), `character_limit` (`121000` + 이월분 합산 시 최대 `363000`), `next_character_count_reset_unix`를 반환하므로 우리 파이프라인의 `flow_credit_state.json`처럼 **실행 전 잔여 크레딧을 100% 자동 체크하고 부족 시 `emma_v7`으로 무중단 폴백**할 수 있습니다.

---

## 4. 하루 1개 쇼츠(월 30편) 기준: Google Flow Omni vs ElevenLabs Creator 정밀 밸런스 비교

실시간 브라우저 검증 수치(`121k` 기본 + `242k` 이월 + `ElevenAPI` `$0.08/1K` 단가)를 반영한 **월 30편(일 1편) 생산 시 양쪽 크레딧 수지표**입니다.

| 비교 항목 | Google Flow (영상/키프레임 엔진) | ElevenLabs Creator (보이스/폴리 엔진, 첫 달 `$11` / 이후 `$22`) | 밸런스 판정 |
|---|---|---|---|
| **쇼츠 1편당 소모량** | • 키프레임(`35`장): **`0` cr** (`0-credit` 이미지 `x4` 배치)<br>• 비디오(`20~24`컷): `Omni 1.1 Flash` 시 **`400 ~ 480` cr** (`20 cr/컷`) / `Veo 3.1 - Lite` 시 **`0` cr** | • 마스터 내레이션(`~190~220w` + 태그 = `~1,500 chars`):<br>  - 웹/1:1 차감 기준: **`~1,500` cr**<br>  - `ElevenAPI` (`$0.08/1K`) 기준: **`~660` cr 상당 (`$0.12`)**<br>• 문장 재녹음 여유(20%) 포함 시: **`~800 ~ 1,800` cr/편** | 1편당 원가 균형 우수 |
| **하루 1편 × 30일 총 필요량** | • 전량 `Omni 1.1 Flash` 사용 시: **월 `12,000 ~ 14,400` cr**<br>• `0-credit` `Veo 3.1 - Lite` 병행 시: **월 `0 ~ 14,400` cr** | • 보수적(`1 char=1 cr`) 기준: **월 `45,000 ~ 54,000` cr**<br>• `ElevenAPI`(`$0.08/1K`) 기준: **월 `20,000 ~ 24,000` cr 상당** | 둘 다 월 쿼터 이내 |
| **월 제공 쿼터 & 이월 한도** | • Google AI Ultra 월 크레딧 (리셋: 매월 17일 `00:03`)<br>• **월간 미사용분 이월 불가** + 소진 시 **`0-credit` `Veo 3.1 - Lite` 무제한 폴백** | • 월 기본 **`121,000` cr** (`ElevenAPI` 환산 시 **`275,000`자**)<br>• 미사용분 **최대 `242,000` cr까지 다음 달 자동 이월** (최대 풀 `363,000` cr) | **양쪽 모두 부족 현상 `0%`!** |
| **남는 여유분 (Surplus)** | • Omni 잔여 시 핵심 클라이맥스 컷 재생성(Auto-Heal)에 투입<br>• Omni `0`일 때도 `0-credit` `Veo 3.1 - Lite`로 **일 1편 100% 무중단 생산** (현재 Pilot #3도 `0` 크레딧으로 생성 중) | • 월 30편 제작 후에도 매달 **`67,000 ~ 97,000` cr** 남음!<br>• 1) 다음 달로 **자동 이월 적립** (`242k` 한도)<br>• 2) 채널 전용 **`SFX v3` (`48kHz WAV`) 시그니처 효과음 30~50종 영구 구축** (`4,000~6,000` cr 1회 투자) | 남는 ElevenLabs 크레딧이 버려지지 않고 이월 + 효과음 자산화됨 |
| **Starter (`$6`, `30k`) 대비 결론** | — | • Starter(`30k`)는 192kbps 미지원(`128kbps` 제한) + PVC 미지원 + 재녹음/SFX 포함 시 월 30편에서 빠듯함<br>• **Creator(`121k`, 첫 달 `$11`)는 `192kbps` 해금 + `1 PVC` + 월 73~166편 캐파 + 2개월 이월**로 병목 완전 해소 | **Creator 선택이 최적해** |
