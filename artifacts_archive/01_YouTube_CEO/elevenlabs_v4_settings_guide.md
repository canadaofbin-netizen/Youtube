# ElevenLabs `Eleven v4` 실전 세팅 & 하이브리드 API 연동 가이드

> [!IMPORTANT]
> 본 가이드는 `canadaofbin` Creator 계정(`130,757 / 131,000` 크레딧 잔여)에 직접 로그인하여 **웹 UI 실측 캡처 + REST API 실시간 응답(`v1/voices`, `v1/audio-effects/catalog`, `v1/text-to-speech/{voice_id}/with-timestamps`)**을 교차 검증한 결과입니다.

## 0. 브라우저 UI에서 직접 생성한 `Eleven v4` 샘플 나레이션 바로 듣기 (`13.01초`)

![ElevenLabs 브라우저 v4 실측 샘플 오디오 (Bella · Eleven v4)](./elevenlabs_browser_v4_narration.mp3)

- **생성 텍스트**: `[brisk, urgent voice] Your brain makes the decision before you even reach for the marshmallow! Yet one hidden promise rewires the entire prefrontal brake. [measured, deliberate voice] Trust is what changes the circuit.`
- **적용 세팅**: `Bella - Professional, Bright, Warm` · `Eleven v4` · `Stability 45%` · `Similarity 78%` · `Language: English` · `Audio effects: None`
- **파일 위치**:
  - 워크스페이스 아카이브: [elevenlabs_browser_v4_narration.mp3](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/artifacts_archive/01_YouTube_CEO/elevenlabs_browser_v4_narration.mp3)
  - Pilot #3 오디오 폴더: [elevenlabs_browser_v4_narration.mp3](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_pilot_03_marshmallow_trust_previs/04_audio/elevenlabs_browser_v4_narration.mp3)
  - ElevenLabs 웹 확인: 브라우저에서 `https://elevenlabs.io/app/speech-synthesis/text-to-speech` 접속 → 우측 패널 상단 **`History` 탭**에서 바로 재생 가능

---

## 1. 스크린샷 UI 항목별 최적 세팅 요약표 (ALL ABOUT BRAIN 쇼츠 기준)

````carousel
![업로드하신 Eleven v4 기본 세팅 화면](./elevenlabs_v4_ui_reference.jpg)
<!-- slide -->
![실계정 웹 UI 세팅 적용 및 샘플 생성 화면](./el_live_02_generated_ui.jpg)
<!-- slide -->
![Eleven v4 Audio Effects 프리셋 카탈로그](./el_live_03_audio_effects_menu.jpg)
<!-- slide -->
![웹 UI vs Creator API 출력 포맷 비교](./el_live_output_formats.jpg)
````

| UI 항목 | 스크린샷 기본값 | **ALL ABOUT BRAIN 권장값** | 이유 및 실측 포인트 |
|---|---|---|---|
| **Try Voice Design for v4** | 상단 배너 | 필요 시 커스텀 보이스 생성용 (`✕` 닫아도 무방) | 텍스트 설명만으로 v4 전용 영구 보이스 제작 가능 |
| **Voice** | `Roger - Laid-Back...` | **여성 기본**: `Bella - Professional, Bright, Warm` (`hpp4J3VqNfWAUOO0d1Us`) 또는 `Hope - upbeat and clear` (`tnSpp4vdxKPjI9w0GnoV`)<br>**남성 보조/Foil**: `Adam` / `George` | ⚠️ `Roger`, `Sarah`, `Charlie` 등 구형 기본 보이스 19종은 **2026년 12월 31일 공식 종료(Sunset)** 예정이므로 신규 쇼츠 고정 내레이터로 비권장 |
| **Model** | `Eleven v4` | **`Eleven v4` (`model_id="eleven_v4"`)** | v3 대비 발음 오류 대폭 감소 + `[brisk, urgent voice]` 등 인라인 디렉팅 태그 완벽 지원 (`1 문자 = 1 크레딧`, 추가 할증 없음) |
| **Stability** (`Creative` ↔ `Robust`) | `50%` (중앙) | **`42% ~ 48%` (API `0.45`)** | 너무 낮으면(`<0.30`) 쇼츠 훅에서 과장·숨소리 노이즈가 생기고, 너무 높으면(`>0.65`) 다큐멘터리 억양이 평탄해짐. `0.45`가 생동감과 발음 안정성의 최적 균형점 |
| **Similarity** (`Low` ↔ `High`) | `75%` | **`75% ~ 80%` (API `0.78`)** | 보이스 고유의 명료한 공명감 유지 (`0.90` 이상은 원음 아티팩트까지 복제될 수 있어 `0.78` 권장) |
| **Language** | `Auto` | **`English` 고정 (API `language_code="en"`)** | 약어(`fMRI`, `PFC`, 숫자 단위)에서 자동 언어 감지 오작동을 원천 차단하고 합성 지연을 줄임 |
| **Audio effects** | `None` (미적용) | **`None` (꺼둠 — 기본 파이프라인과 중복 방지)** | 웹/API의 `Audio effects`(`Room Reverb`, `Radio`, `Telephone` 등 공간·전화 변조 필터 9종)는 특수 연출용임. 우리 파이프라인은 이미 `_master_storyteller_vocal` 방송용 마스터링 체인을 거치므로 **중복 적용 금지** |
| **Output Format** | `MP3 44.1 kHz (128kbps)` | **웹 UI**: `MP3 44.1 kHz (128kbps)` 또는 `WAV 48 kHz`<br>**API 연동**: **`mp3_44100_192` (`192kbps`, 추가 과금 0)** | 웹 드롭다운은 `128kbps MP3`와 `WAV 48kHz`만 노출되지만, Creator 플랜 REST API에서는 **고음질 `mp3_44100_192`(`192kbps`)**와 글자 단위 타임스탬프를 동시에 받을 수 있음 |

> [!WARNING]
> **`Eleven v4`에는 `Speed(속도)` 슬라이더·`Style Exaggeration`·`SSML <prosody>`가 없습니다.**
> 대신 대본 문장 앞에 **`[brisk, urgent voice]`** (빠른 훅/전개) 또는 **`[measured, deliberate voice]`** (결론 각인) 같은 **음성 전용 오디오 태그(Audio Tags)**를 붙이면 `v4` 모델이 자연스러운 호흡과 속도로 연기합니다. (`[applause]`, `[explosion]` 같은 효과음 명사 단독 태그는 절대 넣지 마세요.)

---

## 2. 브라우저 UI vs 하이브리드 API 1:1 매핑 (`pipeline/elevenlabs_tts.py`)

파이프라인에 방금 구현 완료된 [elevenlabs_tts.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/elevenlabs_tts.py) 및 [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)는 위 권장 세팅을 아래와 같이 자동 적용합니다.

```json
{
  "endpoint": "POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_192",
  "body": {
    "text": "[brisk, urgent voice] Your brain makes the decision before you even reach.",
    "model_id": "eleven_v4",
    "language_code": "en",
    "voice_settings": {
      "stability": 0.45,
      "similarity_boost": 0.78
    },
    "previous_request_ids": ["<직전 문장 request-id (최대 3개, 2시간 이내)>"],
    "next_request_ids": ["<다음 문장 request-id (부분 수정 시 앞뒤 톤 완벽 연결)>"]
  }
}
```

### 하이브리드 연동의 4가지 핵심 이점
1. **동일한 Creator `131,000` 크레딧 풀 공유 (추가 비용 \$0)**: 브라우저 결제 계정에서 발급한 API 키(`/home/canadaofbin/.config/aab/elevenlabs.env`, 권한 `0600`)로 동일 크레딧을 사용합니다.
2. **`192kbps` 고음질 + 글자 단위 타임스탬프 동시 추출**: Whisper 재정렬 오차 없이 `normalized_alignment`에서 `[audio tag]` 구간을 자동 제거한 순수 단어 타임스탬프를 추출해 R68 `1~2단어` 팝업 자막 및 컷 전환에 직결합니다.
3. **영구 문장 캐시 + 1문장 외과수술 재생성 (`previous_request_ids` / `next_request_ids`)**: `BCI_Shorts_Channel/.cache/elevenlabs_tts_v4/`에 문장별 SHA-256 캐시를 저장하여, 재조립 시 **크레딧 소모 `0`**, 대본 1줄 수정 시 **수정한 1문장(~80자)만 과금**하면서도 앞뒤 문장 억양을 매끄럽게 잇습니다.
4. **무중단 무료 폴백**: 잔여 크레딧이 안전 예비선(`5,000`자) 미만이거나 `--precheck-only` 드라이런일 때는 자동으로 무료 `emma_v7`(`Edge-TTS`)로 전환되어 파이프라인이 절대 멈추지 않습니다.

---

## 3. 바로 사용하는 CLI 명령어

- **브라우저 UI에서 직접 뽑은 실측 샘플 오디오**: [elevenlabs_browser_v4_narration.mp3](./elevenlabs_browser_v4_narration.mp3)
- **에피소드 조립 시 ElevenLabs `v4` (`192kbps`) 적용**:
  ```bash
  /home/canadaofbin/hermes-venv/bin/python -X utf8 main.py diorama-assemble \
    --project <project_id> \
    --voice-preset elevenlabs_v4 \
    --force
  ```
- **남성 내레이터(`elevenlabs_v4_male`) 적용 시**: `--voice-preset elevenlabs_v4_male`
