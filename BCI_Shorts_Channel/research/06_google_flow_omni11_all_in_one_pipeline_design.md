# 🎬 [파이프라인 설계서] Google Flow (Gemini Omni 1.1) All-in-One 완전 자동화 비디오 파이프라인 아키텍처

> [!WARNING]
> **Superseded by [`.agents/rules/visual_prompt_spec.md`](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md)** (Production Contract v4, 2026-10-17).
> - **Still valid:** dynamic drill-down / orbit / macro camera grammar; real exterior → X-ray → interior progression.
> - **Invalid:** hex / ARRI tokens, calm baritone 2.6 wps, 75–84 words, Möbius loop, cyberspace subjects, paid TTS.
> - Numbers: [`.agents/rules/production_constants.md`](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md).

- **문서 ID:** `pipeline-spec-google-flow-omni11`
- **적용 채널:** MindConnect AI (UCL 뇌과학 기반 BCI Shorts 다큐멘터리)
- **표준 벤치마크:** '신비한 건축사전' 3D 절개 단면(Cutaway) + 5단 카메라 안무 + 4단계 텐션 커브
- **기본 고정 모델:** **Gemini Omni 1.1 (Omni 1.1 Flash / Quality)** 영구 고정
- **실행 환경:** Full Google Stack (Google Flow + Gemini 2.0 Flash + Google Colab + Naver Whale DevTools Bridge + YouTube Studio)

---

## 1. 아키텍처 개요 및 사용자 요구사항 반영

### 1.1 핵심 변경 및 결정 사항
1. **모델 고정 (Omni 1.1 Permanent Lock):**
   - 구글 플로우(Google Flow, `labs.google/fx/tools/flow` / `flow.google`)에서 구동되는 모든 영상 생성, 씬 확장, 프레임 보간, 텍스트 기반 비디오 편집의 기본 엔진을 **Gemini Omni 1.1 (Omni 1.1 Flash / Quality)**로 영구 고정합니다.
   - `pipeline/config.py`의 `DEFAULT_FLOW_MODEL = "Omni 1.1 Flash"` 및 `FLOW_MODEL_QUALITY = "Omni 1.1 Quality"` 적용 완료.
   - `AGENTS.md`의 규칙 R5에 영구 락 명시 완료.

2. **Google Flow All-in-One 파이프라인의 필요성과 범위:**
   - 기존의 파편화된 외부 툴(런웨이, 캡컷, 프리미어 등)을 일체 배제하고, **기획부터 생성, 컷 편집, 합성, 자막, 렌더링, 발행까지 구글 생태계(Google Flow + Gemini + Colab + YouTube Studio)** 내부에서 완결되는 올인원 시스템을 구축합니다.

---

## 2. Google Flow (Omni 1.1) 네이티브 기능 매핑 분석

Google Flow는 단순한 프롬프트 비디오 생성기를 넘어, 타임라인 기반의 **AI 네이티브 영상 편집 스튜디오(Scene Builder)**로 진화했습니다.

| 제작 단계 | 전통적 툴체인 | Google Flow (Omni 1.1) 네이티브 대체 방식 | 장점 및 특징 |
|---|---|---|---|
| **1. 비주얼 생성** | Midjourney + RunWay / Kling | **Google Flow (Omni 1.1 Flash/Quality)** | 텍스트-투-비디오, 이미지-투-비디오, 3D 절개 단면 물리 엔진 |
| **2. 장면 일관성** | 시드 고정, LoRA 학습 | **First & Last Frame Guidance (Frame-to-Video)** | 시작 프레임과 끝 프레임을 지정하여 카메라 궤적 및 형태 완벽 보간 |
| **3. 씬 확장/길이 조절** | 슬로우모션, 리타이밍 | **Omni 1.1 Scene Extension (10s~40s)** | 영상 끝단에서 자연스러운 3D 궤도 회전 카메라 무빙 연장 |
| **4. 클립 타임라인 편집** | Premiere Pro / CapCut | **Google Flow Scene Builder Timeline** | 5개 클립 멀티트랙 배치, 트리밍, 0.1초 무음 하드컷 스냅 |
| **5. 씬 수정 및 인페인팅** | After Effects 마스킹 | **Flow Natural Language Prompt Editing** | "이 전극 실을 금색 네온으로 발광시켜줘" 자연어 지시로 재합성 |
| **6. 오디오 배치** | DAW 믹서 (Audition) | **Flow Native Audio Track + Google Cloud TTS** | 432Hz 앰비언트 BGM 및 2.6 wps 바리톤 보이스 멀티트랙 동기화 |
| **7. 공학 HUD & 자막** | 모션 그래픽 템플릿 | **Google Vids / Transparent Canvas Layer** | Flow 타임라인 오버레이 트랙 또는 Google Vids 캡션 엔진 |

---

## 3. 6단계 All-in-One 파이프라인 세부 아키텍처

```
[Google Flow (Omni 1.1) All-in-One Production Flow]

 Stage 1: 대본 & 텐션 커브 설계 (Gemini 2.0 Flash)
   ├── 7대 필러 기반 75~84단어 (2.6 wps) 스크립트 자동 생성
   ├── 4단계 텐션 커브 (역설적 훅 → 현실 위기 → 절개 메커니즘 → 뫼비우스 루프)
   └── 10개 마스터 QA 게이트 (G1-G10) 사전 검증
         │
         ▼
 Stage 2: Google Flow (Omni 1.1) 씬 생성 및 프레임 보간
   ├── Visible Naver Whale 브라우저 (포트 9222 DevTools 브릿지) 연동
   ├── Omni 1.1 Flash / Quality 엔진 선택 및 9:16 Vertical 포맷 고정
   ├── 5개 클립 6계층 프롬프트 일괄 주입 (Hook → Setup → Core 1 → Core 2 → Payoff)
   └── First/Last Frame 보간으로 Clip 2 → Clip 3 간의 X-Ray 침투 트래킹 구현
         │
         ▼
 Stage 3: Google Flow Scene Builder 타임라인 컷 편집 & 인페인팅
   ├── Flow Scene Builder 트랙에 5개 클립 순차 배치
   ├── 문장 간 0.35~0.45초 마이크로 포즈 무음 구간에 0.1초 정밀 하드컷 스냅
   ├── R23-C 규격: Clip 2와 Clip 3 접합부에 0.25s 절개 디졸브 적용
   └── 미세 오차 발생 시 Flow 자연어 편집창("Make the electrodes pulse with gold voltage")으로 즉시 교정
         │
         ▼
 Stage 4: 오디오 디자인 & 음향 레이어링
   ├── Voice: Typecast 필재 물리학 이식 Deep Baritone (en-US-ChristopherNeural / Google Cloud Journey Voice)
   ├── BGM: Hans Zimmer 스타일 432Hz Sub-bass Ambient Drone (-22dB)
   └── SFX: 활동전위 시냅스 발화 디지털 펄스 (-14dB)
         │
         ▼
 Stage 5: 공학 HUD 텔레메트리 & Inter 자막 합성
   ├── [옵션 A - 순수 Google Cloud/Flow]: Google Vids 자막 엔진 또는 Canvas 투명 PNG 오버레이 트랙 배치
   └── [옵션 B - 무인화 CLI 고속 렌더링]: pipeline/assembly.py (FFmpeg CFR 30.0fps, Inter 44px ASS 자막, 1080x1920)
         │
         ▼
 Stage 6: 무손실 아카이빙 & 1-Click 유튜브 쇼츠 발행
   ├── Google Drive 동기화 및 41개 아티팩트 SHA-256 무결성 검증
   ├── 9:16 모바일 최적화 고대비 썸네일 자동 생성
   └── YouTube Data API / Studio 원클릭 예약 발행 ("AI-assisted content" 자동 선언)
```

---

## 4. Google Flow Omni 1.1 프롬프트 엔지니어링 표준 템플릿

Omni 1.1은 멀티모달 이해도가 높아 카메라 파라미터와 3D 공간 좌표 지시를 정밀하게 수용합니다.

### 4.1 Omni 1.1 필수 프롬프트 뼈대 (Mandatory Skeleton)
```text
[Camera Movement]: {Cinematic Camera & Focal Length}
[Subject]: {Photorealistic 3D Cutaway Subject with millimeter precision}
[Action & Physics]: {Accurate biophysical and mechanical dynamics}
[Style & Octane]: cinematic sci-fi documentary style, cool blue (#1A73E8) and teal (#0E9AA7) color palette, volumetric lighting, photorealistic Octane render, shot on ARRI Alexa 65, 3D architectural cross-section cutaway with millimeter-level precision.
[Format]: 9:16 vertical format.
[Audio & Ambience]: ambient low electronic hum, subtle sci-fi atmospheric drone, 432Hz deep resonance. SFX: soft digital pulse synced to visual neural action. No music.
[Voice Instruction]: Narration voice: deep, calm male narrator with a warm baritone voice (2.6 words/sec). Serious, intellectual documentary gravitas.
```

### 4.2 5단 카메라 시퀀스 안무 가이드
1. **Clip 1 (Hook / 0-6s):** `Macro Push-in shot on ARRI Alexa 65. Extreme close-up of a coin-sized BCI neural implant on brain tissue...`
2. **Clip 2 (Setup / 6-12s):** `High-angle Dolly down shot. Looking down at translucent human skull, brain neural network...`
3. **Clip 3 (Core 1 / 12-18s):** `Cross-section Cutaway tracking shot. Vertical architectural section cut through cerebral cortex layers...`
4. **Clip 4 (Core 2 / 18-24s):** `360-degree Orbital Rotation shot around microscopic electrode-neuron junction...`
5. **Clip 5 (Payoff / 24-30s):** `Pull-back Reveal shot. Expanding neural network web pulsing outward into digital cyberspace...`

---

## 5. 실전 운영 매뉴얼 (Operator Manual)

### 5.1 네이버 웨일 브라우저 연동 Google Flow 원클릭 작업
```bash
# 1. 네이버 웨일 가시 브라우저를 열고 Google Flow 전용 1클릭 클립보드 어시스턴트 대시보드 구동
python main.py flow-assist --project 20261008_flow_omni_demo --pillar bci_tech --topic "Neuralink N1 Telemetry"

# 2. 구글 플로우(flow.google / labs.google)에서 Omni 1.1 모델 선택 및 9:16 세로 비율 지정
# 3. 어시스턴트 화면에서 [📋 Copy Clip 1 Prompt] ~ [Clip 5] 버튼 클릭 후 Flow 프롬프트창에 붙여넣기 및 생성
# 4. 렌더링된 5개 클립을 다운로드 폴더에서 프로젝트로 자동 인제스트
python main.py import-clips --project 20261008_flow_omni_demo --dir "C:/Users/yunky/Downloads"

# 5. 최종 완성 쇼츠 렌더링 (CFR 30.0fps, ASS 자막, 432Hz BGM, 마스터 QA 10게이트 검증)
python main.py render --project 20261008_flow_omni_demo
```

### 5.2 검증 결과 확인
```bash
# 무손실 41개 아티팩트 해시 및 10개 마스터 QA 게이트 통과 여부 검증
python main.py verify --project 20261008_flow_omni_demo
```
