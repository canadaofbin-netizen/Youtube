# `@Deep_Research` 심층 분석 리포트: `mr miro` (`WTqUoZt4k8g` + `inkbeat-shorts.zip`), Google `Semantic IDs`·`YouTube 2025.07 정책` & `ALL ABOUT BRAIN` 파이프라인·마스터 바이블 교차 감사

- **작성 주체**: [`@Deep_Research`](conversation://8c666be9-5bad-43d9-b91a-e7ba2b936c62) (Deep Research & Strategy VP)
- **수신 보고 대상**: [`@YouTube_CEO`](conversation://b57c97a8-6324-4c31-a2bb-16b25e28dd55)
- **작업 일시**: `2026-11-21 UTC` (`코드 수정 0건 · Google Flow 호출 0건 · 브라우저 호출 0건 · 압축 해제 스크립트 실행 0건`)

---

## Executive Summary (핵심 요약)

1. **`Semantic IDs`·`PLUM(Gemini-1.5 MoE)` + `Inauthentic Content` 정책의 실체 (사실 vs 추론 분리)**:
   - Google Research/DeepMind/YouTube의 `arXiv:2305.05065`(TIGER), `arXiv:2306.08121`(YouTube Ranking + SentencePiece), `arXiv:2510.07784`(PLUM: Gemini-1.5 MoE 기반 생성형 추천, Shorts Panel CTR `+4.96%`·Effective Vocab `13.24x`)은 실제로 **텍스트 메타데이터 + 비주얼 + 오디오**를 결합한 멀티모달 임베딩을 `RQ-VAE` 계층형 이산 코드(`Semantic IDs`)로 양자화해 추천·랭킹한다.
   - `mr miro` 영상의 "완전 복제본이 11~12뷰·~800뷰로 추락한다"는 주장은 크리에이터 경험적 관찰 + 추론이지만, 수학적 원리상 동일 시각 구도·동일 음향·동일 스크립트는 동일 `Semantic ID` 프리픽스/리프 버킷에 충돌하여 기존 히트작과 구별되는 고유 탐색 가치를 잃기 쉽다. 반면 **같은 질문이라도 세계관·캐릭터·시청자 각도가 다르면(`Yellow Dude` 5.5M vs `Ryoga` 7.5M)** 서로 다른 `Semantic ID` 버킷과 오디언스로 분리되어 동반 성공한다.
   - **YouTube 2025년 7월 15일 정책 업데이트**([answer/1311392](https://support.google.com/youtube/answer/1311392?hl=en))는 기존 `repetitious content`를 **`inauthentic content`**로 개명하고 *"창작자 고유의 통찰·관점 없이 일반적 템플릿으로 대량 생산한 인상을 주는 AI 생성 콘텐츠"*를 채널 단위 수익화 박탈 대상으로 못 박았다. 반대로 **고정 캐릭터 시리즈나 동일 인트로/아웃트로라도 매 영상의 스토리·콘셉트·교육적 가치가 실질적으로 다르면 허용**된다.
2. **`inkbeat-shorts.zip`의 정체 (핵심 아키텍처 대조)**:
   - SHA-256(`b1af56111e24cb9043f010dbbe360b6f3f0607554e1f3940ac4602b9b9bc949b`) 완벽 검증 후 64개 파일을 읽기 전용 해부한 결과, `inkbeat-shorts`는 **Google Flow AI 영상 생성기가 아니라 100% 결정론적 코드 기반 3D 엔진(`Remotion 4 + three.js / React Three Fiber`) 스킬**이다.
   - 따라서 렌더링 엔진 자체(`three.js` 절차적 메시·셰이더·4x `tmix` 모션블러)는 Google Flow(`Nano Banana 2.1` + `Omni 1.2 Flash`) 기반인 우리에게 직접 이식 대상이 아니지만, **워크플로 공학 6가지**(`단어 타임스탬프 기반 기획`, `Demo/DemoHero/DemoCast 기준 스틸`, `서사 기반 조명 아크 & 사운드오프 인월드 태그`, `~40% 로우앵글 히어로 구도`, `약점 우선 적대적 검수`, `1프레임 루미넌스 스파이크/플리커 검출`)는 **추가 Flow 크레딧 `0`으로 즉시 흡수 가능**하다.
3. **우리 채널(`ALL ABOUT BRAIN`) 교차 감사 결론**:
   - 우리는 이미 **`99`개 SHA-256 잠금 정본 레퍼런스(`v1` 42 + `v1_1` 43 + `v1_2` 14 + 보류 `J04`) + `R85 Ep #31` 6-Scale 뇌 + `120ft` 드론 + `Siren -14.0 LUFS` 오디오 선행 마스터 클럭 + `10+`개 자동 QA 게이트 + 3중 VLM 검수**에서 `inkbeat-shorts` 수동 템플릿보다 훨씬 고도화되어 있다.
   - **가장 시급한 리스크**: `99`슬롯 정본 라이브러리를 **"원본 프레임 그대로 재삽입"**하거나 매 편 같은 배경·소품·훅 패턴(`J01`)·조명으로만 조립하면 YouTube `Inauthentic Content` 및 자기 채널 내 `Semantic ID` 붕괴 위험이 생긴다. **"스타일·캐스트·뇌 뼈대(`Ingredients`)는 잠그고, 매 편 DOI 사건·오픈라이선스 실제 랜드마크(`R72-R`)·실험 소품·조명·데이터 스탬프를 반드시 갈아끼우는"** 5대 방어 가드레일이 필수다.

---

## 1. YouTube `WTqUoZt4k8g` (`mr miro`) + Google `Semantic IDs` + YouTube `2025.07` 정책 원문 검증

### 1.1 Google Research `Semantic IDs` & `Gemini` 추천 메커니즘 (1차 논문 원문 검증)

> [!NOTE]
> **사실(1차 논문 검증) vs 해석(크리에이터 관찰·추론) 엄격 분리**: 아래 논문 수치·구조는 arXiv 1차 원문에서 직접 검증된 사실이며, 복제 채널 조회수 추락 메커니즘은 논문 구조에 근거한 `mr miro`의 경험적 관찰 + 전략적 해석이다.

| 구분 | 1차 출처 (제목 · 저자 · 학회/일자 · URL) | 핵심 메커니즘 & 검증 수치 | 채널 전략적 함의 |
|---|---|---|---|
| **TIGER (기초)** | *Recommender Systems with Generative Retrieval*, Shashank Rajput et al. (Google, NeurIPS 2023) · [arXiv:2305.05065](https://arxiv.org/abs/2305.05065) | 아이템 콘텐츠 임베딩을 **RQ-VAE**로 양자화해 계층형 이산 코드워드 튜플(**Semantic ID**)로 변환하고, Transformer가 다음 아이템의 Semantic ID를 자기회귀 디코딩. | 상호작용 이력이 `0`인 신규 영상(**Cold-Start**)도 콘텐츠 기반 Semantic ID의 상위 코드 공유로 즉시 유사 클러스터에 매핑·추천됨. |
| **YouTube 랭킹 실전** | *Better Generalization with Semantic IDs: A Case Study in Ranking for Recommendations*, Anima Singh et al. (Google/DeepMind, RecSys 2024) · [arXiv:2306.08121](https://arxiv.org/abs/2306.08121) | 무작위 해시 Video ID 대신 동결된 콘텐츠 임베딩 기반 **RQ-VAE Semantic ID** + LLM 토크나이징 기법(**SentencePiece**, N-gram 대비 우위)을 **실제 YouTube 랭킹 모델**에 적용. | 기억(Memorization)과 일반화(Generalization)를 동시 달성. 롱테일·신규 영상 슬라이스 일반화 성능이 뚜렷하게 개선됨. |
| **PLUM × Gemini × Shorts** | *PLUM: Adapting Pre-trained Language Models for Industrial-scale Generative Recommendations*, Ruining He et al. (Google DeepMind & YouTube, 2025-10-09) · [arXiv:2510.07784](https://arxiv.org/abs/2510.07784) | **Gemini-1.5 MoE** 계열(활성 파라미터 `900M`)을 YouTube **LFV + Shorts**에 적용. 영상의 **텍스트 메타데이터 + 비주얼 + 오디오** 멀티모달 벡터 `z = [z_1, ..., z_M]`를 융합해 Co-occurrence 대조 정규화 RQ-VAE로 Semantic ID 토큰화 후 연속 사전학습(CPT). | 실제 YouTube Shorts 라이브 A/B 테스트(Table 2 & Live Experiments vs `LEM`/`LEM+`): **Effective Vocab Size `13.24x`**, **CTR 비율 `1.33x`**, 라이브 **Panel CTR `+4.96%`**, **Views `+0.39%`**, **Satisfaction `+0.39%`**, **Engaged Users `+0.28%`**. |

- **왜 '완전 복제'가 죽는가 (`mr miro` 사례와 `PLUM/SID`의 연결)**:
  - `PLUM` 섹션 2.1.1 원문은 *"a video's full semantic meaning is conveyed through a combination of its textual metadata, visual content, and audio"*라고 명시한다.
  - 따라서 제목·스크립트·구도·색감·인물을 그대로 복제한 채널은(예: `RicksClips`의 뉴욕/도쿄 분할 화면 + 보라색 셔츠 인물 텔레포트 복사본 `12`뷰·`11`뷰; `Ryoga` 6주 뒤 팔·밴드 복사본 `~800`뷰) **멀티모달 `Semantic ID` 상위+하위 코드워드까지 기존 1위 히트작과 동일 버킷에 몰릴 확률이 높고**(추론), 사용자 만족/시청 데이터에서 이미 압도적인 원작 대비 차별화된 시청자 틈새나 신규 탐색 신호를 주지 못한다.
  - 반대로 **동일 질문("근육이 어떻게 크는가?" / "텔레포트가 발명된다면?")이라도 세계관·화풍·화자 포지셔닝이 다르면**(`Yellow Dude` 밝은 해부 카툰 호기심 접근 `5.5M` vs `Ryoga` 어두운 만화풍·마른 남성 고통 타깃 `7.5M`; 다른 세계관·캐릭터로 재해석한 텔레포트 영상 `11M`), 서로 다른 `Semantic ID` 리프 및 수용자 클러스터로 분류되어 동반 히트가 가능하다.

### 1.2 YouTube `2025년 7월 15일` `Inauthentic Content` 수익화 정책 원문 해부

1차 공식 출처: [YouTube channel monetization policies (Google Help Center answer/1311392)](https://support.google.com/youtube/answer/1311392?hl=en)

- **공식 개정 요지 (`July 15, 2025`)**:
  - 기존 **"repetitious content"** 정책을 **"inauthentic content"**로 공식 개명 및 명확화(*"clarify this includes content that is repetitive or mass-produced"*). 기존 `reused content` 정책은 변경 없음.
  - **채널 단위 제재**: 개별 영상 1개가 아니라 **채널 전체**를 검토하여, *"시청자가 같은 채널 영상을 연달아 볼 때 서로 교체 가능(interchangeable)하고 반복적으로 느껴지면"* **전체 채널의 YPP 수익화를 박탈**할 수 있음.
- **위반선 vs 안전선 원문 대조표**:

| 구분 | YouTube 공식 조항 원문 (`support.google.com/youtube/answer/1311392`) | `ALL ABOUT BRAIN` 현재 판정 및 경계 |
|---|---|---|
| **❌ 수익화 불가 (위험선)** | • *"AI-generated content made with generic or unoriginal templates giving the impression of mass production without adding the creator's original, authentic insights or perspective"*<br/>• *"Videos where characters are put in the same situation over and over again with the same outcome (i.e., using a highly similar storyline template across multiple videos)"*<br/>• *"Image slideshows, templated storylines, or scrolling text with minimal or no narrative, commentary, or educational value"* | 매 편 동일한 2.5D 방·동일 소품·동일 플롯("X 실험 → 뇌가 놀람 → 끝")이 피상적 단어만 바뀐 채 반복되거나, Canonical 정본 정지 이미지를 그대로 슬라이드쇼처럼 재사용하면 **고위험**. |
| **✅ 수익화 허용 (안전선)** | • *"Same intro and outro for your videos, but the bulk of your content is different"*<br/>• *"Similar content, like a series following a set of characters across episodes or a channel that does product reviews, but in which each video has a distinct storyline, focus, or concept"* | **동일한 화풍·캐릭터 패밀리(`2.5D 비닐` + `Ep #31 뇌` + `Siren 내레이션`)**를 유지하더라도, 매 편 **고유 단일 학술논문(DOI) 사건·고유 대학교 실물 랜드마크·고유 실험 장치·고유 `1x1` 데이터 스탬프·고유 뇌 부위 해부 시점**으로 본문이 실질적으로 다르면 **정식 시리즈물로 허용**. (`R4` Studio AI 체크박스 유지 필수) |

### 1.3 영상 내 채널 사례 정량 비교표 & `RicksClips` 4대 공통 분모 + `"Mute & Hide Name Test"`

참고 원문: [`/tmp/yt_WTqUoZt4k8g_clean.txt`](/tmp/yt_WTqUoZt4k8g_clean.txt)

| 채널 / 사례 | 규모 / 수치 (`WTqUoZt4k8g` 인용) | 시각·서사 전략 | 결과 & 시사점 |
|---|---|---|---|
| **RicksClips** | 동 스타일 `29`편 중 **`26`편이 `1M+` 뷰**; 운전 시점 차량 충돌 편 `4M` 뷰 (`< 1주`); 기존 `100+` Shorts 선행 학습 | 첫 편(텔레포트: 평면 색·단순 거리) → 1달 만에 3D 차내 1인칭·파손 물리·실사 질감으로 고도화. 짧은 질문형 제목, 숨은 현실 이유, 0.5초 인식 캐릭터, 일관된 차분한 내레이터. | **"당신은 1편이 아니라 그의 29번째 진화본과 경쟁한다."** 고정 스타일 안에서 물리·디테일을 지속 상승시킴. |
| **텔레포트 복제 채널 2곳** | 제목·뉴욕/도쿄 분할·보라색 셔츠 인물 동일 복사 | `0%` 독자적 각색, 프레임·스크립트 직복사 | 조회수 **`12`뷰 / `11`뷰** (완전 사장) |
| **텔레포트 독자 변주 채널** | 같은 질문 → **다른 세계관·다른 캐릭터·다른 감정** | 아이디어만 차용, 시청각 세계 자체 재구축 | 조회수 **`11M`뷰** (원작 추월) |
| **Knox Clips** | 구독자 `9,000`명 → `5M` 뷰 (`6일`) | 둥근 머리 단순 캐릭터 + 정밀 월드 + 반전 스토리 | 소규모 채널도 **고유 월드+비틀기**로 즉시 폭발 |
| **ZooBow Animations** | 구독자 `293`명 → `~700K` 뷰 (`2일`) | 동 계열 단순 캐릭터이나 독자적 세계·개그·발상 | 초반 구독자 무관, 콘텐츠 고유성이 분배 결정 |
| **Yellow Dude vs Ryoga vs 6주 뒤 복제** | Yellow Dude `5.5M` / Ryoga `7.5M` / 6주 뒤 복제 `~800` | 동일 주제("팔/근육 키우기")+동일 팔 전후 구도 → Yellow Dude(밝은 해부 카툰·일반 호기심) vs Ryoga(어두운 만화·마른 사람 타깃). 6주 뒤 복제는 팔+찢어지는 밴드 그대로 모방. | **주제/핵심 아이디어 공유는 무방, 시각·타깃 페르소나까지 복제하면 `~800`뷰로 몰락**. |

- **`mr miro`의 4대 성공 공통분모 + 자기진단 테스트**:
  1. **제목**: 짧고 즉각적인 호기심 질문(`"Why Perfect Railroads Don't Work"` — 단, 우리 채널은 `R87-H` 실측상 `"Why do..."` 식 약한 질문보다 **강한 역설 단정문 + 훅 타이틀**이 3초 방어에 유리함 확인 완료).
  2. **소재**: 누구나 본 적 있지만 진짜 이유를 몰랐던 현실 현상 (`ALL ABOUT BRAIN`의 "일상 행동/사건 뒤의 숨은 뇌 메커니즘"과 정확히 일치).
  3. **캐릭터**: 단순하고 일관되며 **`0.5초` 안에 즉시 식별 가능한 고정 패밀리**.
  4. **목소리**: 매 편 동일한 차분한 내레이터 음색(`R76` Solo `Siren` 일치).
  - **핵심 검수 테스트 — `"Mute & Hide Name Test"`**: *"음소거하고 채널명을 가린 채 화면만 보아도 당신의 영상인지 알 수 있는가? '아니오'라면 유튜브가 이미 가진 남의 영상을 또 만들고 있을 뿐이다."*

---

## 2. Google Doc (`AI Cartoon Step by Step`) & `inkbeat-shorts.zip` 전수 역설계

### 2.1 다운로드 · SHA-256 · 압축 해제 증적 (읽기 전용, 실행 `0`건)

- **원문 Google Doc**: [`/tmp/ref_gdoc_17vHdvnLiOMtTQ4Qd5femJvdyG2ycKDOWWN_pI8gb2EI.txt`](/tmp/ref_gdoc_17vHdvnLiOMtTQ4Qd5femJvdyG2ycKDOWWN_pI8gb2EI.txt) (`138`줄)
- **공개 ZIP URL**: `https://drive.google.com/file/d/1MwNc-8kSBqnW0GD3r1js1ScsJRyO0tfa/view?usp=sharing`
- **저장 경로**: `/tmp/inkbeat_teardown/inkbeat-shorts.zip` (`349,569 bytes`, HTTP `200`)
- **SHA-256 실측**: `b1af56111e24cb9043f010dbbe360b6f3f0607554e1f3940ac4602b9b9bc949b` (**문서 명시 예상치와 100% 일치: `True`**)
- **해제 경로 & 규모**: `/tmp/inkbeat_teardown/extracted/inkbeat-shorts/` (`64`개 파일; 경로 역참조 검증 완료, 스크립트/바이너리 실행 `0`건)

### 2.2 `inkbeat-shorts` 내부 아키텍처 해부표

| 디렉터리 / 핵심 파일 | 바이트 (SHA-256 앞 12자리) | 실제 기술 구현 내용 | 우리 `ALL ABOUT BRAIN` 대비 핵심 차이 |
|---|---|---|---|
| [`SKILL.md`](file:///tmp/inkbeat_teardown/extracted/inkbeat-shorts/SKILL.md) | `14,427 B` (`847bd3bd9614`) | Remotion 4 + R3F 3D 카툰 제작 마스터 지침 (`56±4 beats/min`, `<=35%` 고속 프레임, 하드컷 `~0`, 4단계 게이트, 물리 관통 차단) | AI 영상 모델(`Flow/Veo`)이 아닌 **WebGL/Three.js 코드 기반 절차적 3D 렌더링** |
| [`templates/plan/plan_src.py`](file:///tmp/inkbeat_teardown/extracted/inkbeat-shorts/templates/plan/plan_src.py) | `5,875 B` (`c63b83b8abc3`) | 초(s) 수기 입력 금지! `vo/timings.json`의 `(turn, word, nth)`에 `SHOTS`/`ACCENT`/`TAGS`를 앵커링해 `plan.json` + `src/plan.gen.ts` 결정론적 컴파일 | 우리는 이미 `R58` Audio-First + `prosody.py` word timestamps 기반 EDL 매핑으로 동등 이상 구현 중 |
| `templates/src/demo/` (`Demo.tsx`, `DemoCast.tsx`, `DemoMove.tsx`, `Street.tsx`) | `2,451–5,810 B` | 씬 제작 전 **기준 스틸(`Demo`, `DemoHero`, `DemoCast`)** 먼저 뽑아 조명·스케일·인물 패밀리(성인·아이·노인) 일관성 확인 | 우리 `Canonical 99슬롯 + Ep #31 4장`에 대응하나, 단일 한눈 비교용 **"카나리 기준 시트(`Golden Style Sheet`)"** 미구축 상태였음 |
| `templates/src/inkbeat/core/` (`shots.ts`, `moods.ts`, `captions.tsx`, `liquid.tsx`, `ik.ts`, `rig.ts`) | `1,605–14,585 B` | `heroLow`(`~40%` 높이 채움, `fov 56`, 전경 DOF 프롭), `6`종 서사 조명 프리셋(`day/dusk/night/cold/lamp/golden` + 보색 그림자), `captions.tsx`(`y=70%`, `92px`, `-2f` 선행, 1–2단어 소문자), 2-bone IK | `shots.ts`의 **`~40%` 로우 앵글 히어로 구도 + 전경 프롭 프레임감**과 `moods.ts`의 **막(Act)별 조명·보색 그림자 공식**이 매우 정교함 |
| `templates/src/inkbeat/char/` (`family.ts`, `Character3D.tsx`, `face.ts`, `clothes.ts`, `cast.ts`) | `1,127–30,459 B` | 키 `h=1` 기준 비율 상수(`HEAD_HW=0.135`, `3/4` 요 `20–35°`, 이목구비 표정/깜빡임 주기 `3.9s`, `7.5Hz` 립플랩은 직접 인용 대사에서만 허용) | 우리 캐스트는 눈·눈썹 2D 잉크만 있는 무표정/무입 비닐 2.5D이므로 **내레이션 중 입 벙긋거림 `0%` 강제가 필수** |
| [`scripts/flicker.py`](file:///tmp/inkbeat_teardown/extracted/inkbeat-shorts/scripts/flicker.py) | `3,344 B` (`b577730c6b06`) | `64x36` 4×3 그리드에서 `min(\|b-a\|, \|b-c\|) > 4.0` & 이웃 일치(`\|a-c\| < 0.35*spike`) **1프레임 루미넌스 스파이크** + `mod k (2..16)` 스트라이드 패턴 탐지 (`exit 3`) | 우리 `dynamic_episode_qa.py`는 연속 프레임 동결(`DQ_Smooth`, MAD `<0.12`), 컷 경계 모핑/플래시를 잡지만 **컷 내부 임의 단일 프레임 암전/깜빡임 스파이크** 전용 검출기는 부재 |
| [`scripts/analyze_pacing.py`](file:///tmp/inkbeat_teardown/extracted/inkbeat-shorts/scripts/analyze_pacing.py) | `4,256 B` (`2052713c175c`) | `180x320` 10프레임 간 휘도 변화량으로 `beats/min` (`56±4`), `frac_still` (`~5–20%`), `frac_fast` (`<=35%`), `hard_cuts` (`ffmpeg scene>0.3`), `CIE L* mean` (`>=50`) 계측 | 우리 채널은 `R82` (`18–28`컷, 인간 `1.90–4.25s`, 뇌 `4.20–6.80s`) 구조로, `analyze_pacing.py`의 `CIE L*` 밝기 분포와 정지율 지표가 보완 참고 가능 |
| [`scripts/gpu_lock.py`](file:///tmp/inkbeat_teardown/extracted/inkbeat-shorts/scripts/gpu_lock.py) | `7,328 B` (`00e392c8cd17`) | 파일 락(`flock`/`msvcrt`)으로 GPU 동시 렌더 `1`개 직렬화 | 우리는 Google Flow 클라우드 + `cdp_tab_manager.py` 및 단일 워커 탭 락으로 이미 대응 중 |
| `references/*.md` (`9`종) | `3.4–10.9 KB` | `render-and-qa.md`(`2fps` 컨택트 시트 + 무음 스토리 체크 + `tmix` 4-subframe 모션블러), `audio-and-voice.md`(`-14 LUFS`, `-1 dBTP`, BGM `-14dB` + `-3dB` 덕킹), `production.md`(약점 우선 자기비판, `<=3` 이미지/스텝 컨택트 시트, 파일 프라이버시) | **`production.md` / `shorts.md`의 검수·오브젝트 태그·약점 우선 루프**는 AI 영상 파이프라인에도 100% 직결됨 |

### 2.3 `inkbeat-shorts` + Google Doc에서 뽑은 6대 실전 공학 패턴

1. **카나리 기준 스틸 3종 먼저 검증 (`Demo / DemoHero / DemoCast`)**: 본격 씬 제작 전에 1프레임의 기준 조명·인물 비율·대비를 확정하고, 이후 검수는 항상 기준 스틸과 나란히 대조(*"Compare this frame with the skill's demo stills and tell me the 3 biggest differences"*).
2. **단어 타임스탬프 고정(`plan_src.py`) + 막(Act)별 서사 조명 아크**: 초 단위 하드코딩 대신 단어 타임스탬프에 샷·태그를 묶고, 사건 전환에 따라 조명을 설계한다(예: Google Doc 보스턴 1919 사례 — *"1월 정오의 차가운 흐린 빛 → 파도 충격 시 짙은 호박/갈색 → 수습 시 차가운 겨울빛 → 엔딩 황금빛"*).
3. **사운드-오프 인월드 태그 vs 플로팅 카드 금지**: `"BOSTON 1919"` 같은 연도/핵심 수치를 허공 카드에 띄우지 않고 **화면 속 실제 구조물(창고 간판·전차 측면)에 무광(`unlit`)으로 배치**하거나(AI 깨짐 방지 위해 우리는 **후처리 프로그래매틱 `1x1` 데이터 스탬프·콜아웃**으로 정교화), 15초당 1개 수준으로 핵심만 전달해 무음(`2fps` 컨택트 시트) 상태로도 이야기가 읽히게 한다.
4. **히어로 샷 `~40%` 로우 앵글 원칙(`shots.ts:43-49`)**: 모든 컷을 작은 원경(`wide ~18%`)으로만 찍지 않고, 결정적 감정/행동 컷 2~3곳에서 로우 앵글로 인물이 **세로 화면의 약 `40%`**를 채우게 배치하고, 전경 소품(`fgSpots`)으로 깊이감을 확보한다.
5. **1장당 값싼 룩데브(Look-Dev) 검증 + 부분 재렌더 + `2fps` 델타 컨택트 시트**: 본 렌더 전 씬당 1장 스틸로 빛·스케일을 잠그고, 수정 시에는 **"문제가 있는 컷과 접촉 영역만 부분 재렌더 후 `2fps` 컨택트 시트로 물리 관통/플리커 검증"**.
6. **수치화된 스타일 가이드 + 적대적 약점 우선 검수(Adversarial Critique)**:
   - Google Doc: *"Claude has no taste of its own. Give it a target it can measure, and it can hit it."* / *"Don't tell me what's good. List what is still weak, biggest problem first."*
   - 모든 피드백을 **`① 무엇이 잘못되었는지(Wrong) · ② 어디에 있는지(Exact Scene/Second/Word) · ③ 대신 무엇으로 바꿀지(What Instead)`** 3요소로 강제한다.

---

## 3. `ALL ABOUT BRAIN` 현재 파이프라인 정밀 교차 대조 (`Canonical 99슬롯` · `R85/R87` · `Omni 1.2` · `x1/x2` · `'신비한 건축사전'` 4대 공식)

### 3.1 이미 우리가 명백히 앞서 있는 핵심 강점 (유지·잠금 대상)

| 영역 | 우리 현재 실측 자산·구현 (직접 확인 근거) | 경쟁 대비 우위 |
|---|---|---|
| **이중 이미지+텍스트 스타일 잠금** | `Canonical Library v1(42) + v1_1(43) + v1_2(14 승인 + J04 보류)` = **`99`개 SHA-256 잠금 슬롯** + `Ep #31` 원조 스틸 4장 (`_reference_31_O2CmlKOk/`) + `Omni 1.2 Flash` `Start+End` 보간 (`config.py:111-114`, `canonical_assets/v1..v1_2/manifest.json`) | 100% 텍스트 프롬프트 반복('신비한 건축사전' 복제법)보다 1단계 위인 **물리 레퍼런스 잠금** 달성. |
| **오디오 선행 마스터 클럭 (`R58`, `R76`)** | `ElevenLabs v4` Solo `Siren` (`eXpIbVcVbLo8ZJQDlDnl`) + `-14.0 LUFS` / `-1.5 dBTP` + `curious_marimba_strings` 120s/65s BGM(`-21.5/-16.5 dB` 덕킹) (`config.py:1315-1346, 1642`) | `inkbeat-shorts`의 오디오 후속 단어 앵커링과 대등하며, 단일 `Siren` 화자 고정으로 `Semantic ID` 음성 시그니처 완성. |
| **`Mute & Hide Name Test` 통과 DNA** | ① 2.5D 크림화이트 민머리 비닐+2D 잉크 표정, ② `Ep #31` 6-Scale 뇌(`#9CA5AC~#C3C9CE` + `#27D8FF` over `#040711`), ③ `120ft` 실물 기관 드론, ④ `R87-A` 조건부 `#FF2525` 화살표 vs `Category K` 소품 대비 | 음소거하고 채널명을 가려도 `0.5초` 만에 `ALL ABOUT BRAIN`임을 식별 가능. |
| **다층 자동+VLM 게이트 (`R85/R87`)** | `prompt-gate`, `reference_image_qa.py`(Gate 1), `dynamic_episode_qa.py`(`DQ1–DQ13`, `DQ_Smooth`, `DQ_Border`, `DQ_R85_*`, `DQ_R87_*`), `dq8_suspect_classifier.py`, `posthoc_semantic_qa.py`(Gate 2 `UNMANNED_QA_SIGNOFF_DEFAULT=False`), Lock 4 48시간 리텐션 경보 | `inkbeat-shorts`보다 훨씬 엄격한 **기계+VLM 3중 사인오프** 및 해부학/실물 오픈라이선스(`R72-R`) 검증 보유. |
| **크레딧 방어 (`x1/x2`)** | `FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT = 1` (1차 패스 `x1`), `RETRY = 2`, `THUMBNAIL = 2`, `FLOW_OMNI_EPISODE_CREDIT_CAP = 200` (`config.py:134-166`) | 일일 Flow 이미지 소모 `75~86%` 절감 상태 유지. |

### 3.2 `Semantic ID` 자기잠식 & `Inauthentic Content` 리스크 점검 (`99`슬롯 정본 라이브러리 운영 경계)

Google의 `PLUM/Semantic IDs` + YouTube `2025.07 Inauthentic Content` 기준을 우리 **`99`개 정본 슬롯**에 대입하면, 아래 **2가지 오남용 시나리오**를 반드시 차단해야 한다:
1. **위험 ① — 정본 이미지를 '비디오 프레임(또는 정적 컷)'으로 직접 재사용하는 행위**: `J01`, `E01..E10`, `B05` 등의 정본 PNG를 여러 편에서 똑같은 시작 구도·똑같은 소품·똑같은 카메라 경로로 연속 송출하면, `Semantic ID` 비주얼 임베딩과 YouTube `Inauthentic Content` 심사관 모두에게 **"동일 템플릿 대량 복제"**로 인식될 위험이 커진다(`DQ6_zero_clip_reuse`는 에피소드 *내부* 재사용만 막으며 *에피소드 간* 시각 중복은 보지 않음).
2. **위험 ② — 연속 에피소드의 훅 시각 모드(`J01` 편중)·조명·서사 아크 고착**: 매 편 첫 3초가 `J01` 주방/커피잔 + `Mode 1`으로 열리고, 중반 2.5D 공간이 늘 같은 화이트 룸 + 같은 플랫 조명이면, 시청자와 추천기 모두 "내용만 바뀐 같은 영상"으로 묶는다.

**✅ 5대 Semantic ID & Inauthentic Content 방어 가드레일 (규칙 잠금 권고)**:
1. **정본 `99`슬롯 = `재료(Ingredients) / 스타일·캐스트 잠금 앵커` 전용 (직접 재방영 금지)**: 정본 이미지는 **`Nano Banana 2.1` 에피소드 전용 키프레임 생성 시 화풍·캐스트·뇌 톤을 고정하는 조건화 입력**으로만 쓰고, 매 에피소드 컷은 해당 논문의 **고유 행동·고유 소품·고유 배경 구도**로 새로 생성한다.
2. **매 편 3종 고유 비주얼 델타 의무화**: ① **`R72-R` 오픈라이선스 실물 기관/실험실(`120ft` 드론 포함) 에피소드별 교체**, ② **실험별 핵심 전경 소품 1종+ 풀컬러 강조**, ③ **`R70-M` DOI 실측 데이터 스탬프(편당 다른 수치·다른 차트 유형)**.
3. **연속 에피소드 `J01–J06` 훅 시각 아키타입 & `R87_OPENING_MODES` 강제 순환**: 직전 2편과 동일한 `J` 슬롯 및 동일 `opening_mode` 연속 사용 금지.
4. **에피소드 내부 서사 조명 아크(`Story Lighting Arc`) 적용**: 전 구간 동일 평면 조명 대신, 도입(일상 주광/냉백색) → 갈등(짙은 실내 그림자/긴장 색온도) → `Ep #31` 뇌(`#040711` 네이비) → 반전/결론(명쾌한 고키/골든 아워)으로 **컷 간 시각 엔트로피 확보**.
5. **YouTube `R4` + `R68-D` 투명성 및 교육 밀도 유지**: 1논문 1사건(DOI 팩트 기반), `Research: <Author> et al., <Institution> (<Year>).` 인용, Studio AI 체크박스(`ai_content_declaration=True`) 상시 유지.

---

### 3.3 즉시 이식할 고효율 파이프라인 업그레이드 TOP 6 (`Flow 크레딧 추가 0건`)

아래 6개 항목은 `inkbeat-shorts` 해부 + Google Doc + '신비한 건축사전' 4대 프롬프트 공식에서 추출한 고효율 개선안이며, **실제 코드/테스트 라인 대조를 거쳐 부작용 없이 바로 구현 가능하도록 명세**했다.

#### [P0-1] Google Flow 오디오·립싱크 부정 가드 강화 *(기존 테스트 호환성 검증 포함)*
- **출처 근거**: '신비한 건축사전' 4대 공식 ③ (`no voiceover, no narration, no background music`) + `inkbeat-shorts/references/characters.md:77` (내레이션 중 립플랩 금지).
- **현재 갭 & 호환성 함정 실측**:
  - 현재 [`pipeline/depiction_rules.py:2049`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py#L2049) 및 [`pipeline/flow_prompt_builder.py:2504,2540-2565`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L2504-L2565)는 `"Silent voice track."`만 삽입한다.
  - **중요 호환성 발견**: [`tests/test_credit_safe_pipeline.py:385-389`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_credit_safe_pipeline.py#L385-L389)가 `prompt_core.endswith("Silent voice track.")` 및 `EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE = (18, 64)`를 직접 assert하고 있으며, [`pipeline/flow_diorama_sharded_worker.py:311`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py#L311)과 [`pipeline/flow_prompt_builder.py:2919`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L2919)도 `"Silent voice track."` / `"silent voice track"`을 기준 마커로 사용한다.
- **권장 적용 방식**:
  - **방법 A(무회귀 권장)**: [`pipeline/depiction_rules.py:1486`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py#L1486)의 `FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD`(이미 `test_credit_safe_pipeline.py`와 `validate_expressive_v8_prompts`가 단어 수 계산 전 스트립함) 뒤에 **`"No voiceover, no narration, no background music, no lip movement."`**를 통합(또는 별도 `FLOW_AUDIO_LIPSYNC_NEGATIVE_GUARD` 상수로 붙여 동일하게 스트립)한다. 이렇게 하면 기존 테스트 깨짐 `0`건 · 단어 수 예산 `(18, 64)` 유지 · Flow 프롬프트 끝단 립싱크/잡음 억제 `100%` 달성.
  - **방법 B(직접 치환)**: `"Silent voice track."` 자체를 `"Silent video, no voiceover, no narration, no background music, no lip movement."`로 교체할 경우, 반드시 위 4곳(`test_credit_safe_pipeline.py:386`, `flow_diorama_sharded_worker.py:311`, `flow_prompt_builder.py:2540..2565`, `EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE` 여유치)을 함께 갱신해야 함.
- **기대효과**: `Omni 1.2 Flash`의 불필요한 입 벙긋거림 환각 및 오디오 생성 연산 낭비 차단.

#### [P0-2] 일반 2.5D 컷 **선택적 색채 대비(Selective Color Isolation)** + **서사 조명 아크(Story Lighting Arc)**
- **출처 근거**: '신비한 건축사전' 공식 ① (*"설명 대상은 선명한 풀컬러, 주변 배경 지형은 저채도 무채색"*) + `inkbeat-shorts/references/moods.ts` & `SKILL.md:82` (*"Light follows the acts"*).
- **현재 갭 실측**: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py) 및 [`pipeline/depiction_rules.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py) grep 결과 **`selective_saturation` / 배경 저채도 대비 로직 `0`건**. 뇌 컷(`#040711` + `#27D8FF`)만 대비가 있고, 일반 2.5D 실내/실험 컷은 전·배경 채도가 비슷해 시선이 분산된다.
- **주의할 기존 QA 충돌 체크**: [`pipeline/flow_diorama_sharded_worker.py:953-955`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py#L953-L955)에 `desaturated_grayscale_v7` 차단기가 있으므로, **화면 전체 흑백이 아니라 "배경 건축물만 저채도 쿨그레이/미색으로 누르고 핵심 실험 소품·행동만 선명한 풀컬러로 분리"**하는 프롬프트 문구로 작성해야 한다.
- **적용 대상**: `pipeline/depiction_rules.py`(`EXPRESSIVE_V8_WORLD_LEAD` 또는 비뇌 씬 컴포저 `context_split` 보조 절) 및 `pipeline/porcelain_anchor_pack.py`(키프레임 스펙 생성 시 Act별 조명 토큰: `Act 1` crisp daylight → `Act 2` shadowed moody interior → `Act 3` deep dark void brain → `Act 5–6` crisp golden rim).
- **기대효과**: 무음 스크롤 1초 시선 고정력 상승 + 에피소드 간 `Semantic ID` 비주얼 다양성 확보.

#### [P0-3] `@Research` Gate 1/2 **적대적 약점 우선 검수 프로토콜 + `"Mute & Hide Name Test"` 게이트 추가**
- **출처 근거**: Google Doc Quick Fix (*"Don't tell me what's good. List what is still weak, biggest problem first."* + `Wrong / Exact Where / What Instead` 3요소) + `WTqUoZt4k8g` (`"Mute & Hide Name Test"`).
- **현재 갭 실측**: [`pipeline/reference_image_qa.py:1882-1916`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py#L1882-L1916)과 [`pipeline/posthoc_semantic_qa.py:1414-1417`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py#L1414-L1417)은 `observed_visual_summary`와 `R87` 3대 불리언(`silent_3s_scroll_stop`, `narration_visual_logic_match`, `thumbnail_to_0s_promise_kept`)을 검사하지만, **"칭찬 금지 · 치명 결함 최상단 배치 · Wrong/Where/Instead 3요소 기재"**와 **"채널 고유 시그니처(무음·채널명 숨김 테스트) + 전편 대비 비주얼 차별성"** 항목은 명시되어 있지 않다.
- **적용 대상**: [`.agents/rules/qa_gates_rules.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) (`@Research` Gate 1/2 리포트 양식 의무화) + `pipeline/reference_image_qa.py` / `pipeline/posthoc_semantic_qa.py` 선택적 권고 체크리스트(`semantic_distinctiveness_check`).
- **기대효과**: LLM 비전 검수의 자기합리화('전반적으로 깔끔함'류 관대한 통과) 억제 및 `Semantic ID` 자기복제 사전 차단.

#### [P1-4] 히어로 인물 `~35–45%` 로우 앵글 프레이밍 & `Dolly-in ↔ Dynamic dolly-out` 호흡 교차
- **출처 근거**: Google Doc Step 3 #4 (*"hero shots with a low lens and the character filling ~40% of the frame... Right now everyone is small"*) + `inkbeat-shorts/templates/src/inkbeat/core/shots.ts:43-49` (`heroLow`, `fill=0.4`, `fgSpots`) + '신비한 건축사전' 공식 ② (`Dolly-in` ↔ `Dynamic dolly-out` 교차).
- **현재 갭 실측**: [`pipeline/depiction_rules.py:1562-1593`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py#L1562-L1593)에 30종 카메라 디스크립터가 있으나, **`heroLow`(`~40%` 인물 점유 + 로우 앵글 + 전경 소품 프레임)에 해당하는 전용 구도 앵커**와 **푸시인/풀백 연속 교차 제약**이 규칙으로 잠겨 있지 않다.
- **적용 대상**: [`.agents/rules/camera_choreography_rules.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md) + `pipeline/depiction_rules.py` (`hero_low_40pct` 샷 프리셋/카메라 디스크립터 보강) + `youtube-script/SKILL.md` (에피소드당 `2–3`회 히어로 40% 로우 앵글 컷 배치 + `push-in` / `pullback` 교차 리듬).
- **기대효과**: 세로 9:16 모바일 화면에서 캐릭터 표정·손동작 전달력(`R79-M`) 극대화 및 상하단 안전영역(상단 `HookTitle` `Y=238..422px`, 하단 자막 `70%`)과의 물리적 충돌 회피.

#### [P1-5] 대본 4단 감정 곡선 명문화 & '사운드-오프 사실 태그' 규율 정립
- **출처 근거**: '신비한 건축사전' 공식 ④ (*도입 → 난관 → 역발상 해결 → 요약 클로징*) + `inkbeat-shorts/references/shorts.md:33-44` (*15초당 1개 핵심 팩트 태그, 무음 `2fps` 시트 가독성 테스트*).
- **현재 갭 실측**: [`.agents/skills/youtube-script/SKILL.md:14-25`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md#L14-L25)는 6막(`Act 1–6`) 구조와 4가지 오프닝 모드를 정의하지만, 시청자 몰입을 유지하는 **4단 감정 리듬(① 충격 직관 파괴 → ② 난관/기존 통념 막힘 → ③ 역발상 뇌 메커니즘 해부 → ④ 1줄 일상 미러 클로징)**과 **"AI 이미지 안의 깨지는 간판 텍스트는 계속 `0%` 금지하되, 후처리 `1x1` 데이터 스탬프·`PatrickHand` 콜아웃으로 `15초당 1핵심 팩트` 무음 스토리 완결성 확보"** 역할 분담이 명시되어 있지 않다.
- **적용 대상**: [`.agents/skills/youtube-script/SKILL.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md) (4단 감정 아크 템플릿 + `Mute & Hide Name Test` + 무음 `posthoc_viewer_strips` 스토리 판독 체크).

#### [P1-6] 단일 프레임 휘도 급변/플리커(`1f Spike`) 경량 검출 보강 *(기존 `DQ_Smooth` 보완)*
- **출처 근거**: [`flicker.py`](file:///tmp/inkbeat_teardown/extracted/inkbeat-shorts/scripts/flicker.py) (4×3 그리드 1프레임 스파이크 탐지: `min(|b-a|, |b-c|) > 4.0` & `|a-c| < 0.35 * spike`).
- **현재 갭 실측**: [`pipeline/posthoc_semantic_qa.py:691-740`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py#L691-L740)의 `DQ_Smooth_temporal_smoothness`는 **연속 프레임 동결(`MAD < 0.12`)**만 잡고, [`pipeline/dynamic_episode_qa.py:2637-2723`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py#L2637-L2723)은 **뇌 컷 네온 스파크 플래시**만 잡는다. 일반 2.5D `Omni 1.2` 클립 중간에 끼어든 **1~2프레임 단일 암전/번쩍임 아티팩트**를 컷 내부에서 직접 잡는 4×3 스파이크 체크는 현재 없다(`ffmpeg` 디코드 1패스 안의 몇 줄 벡터 연산으로 추가 가능).
- **적용 대상**: `pipeline/posthoc_semantic_qa.py` 내 컷 내부 4×3 그리드 1-frame spike 감시(단, 계획된 `whip_pan` / `portal_crash_zoom` / 컷 경계 2프레임은 예외 처리하여 오탐 `0%` 유지).

---

## 4. "고정 레퍼런스·에셋 + 전체 파이프라인 마스터 문서" 필수 구조화 항목 권고안

[`@YouTube_CEO`](conversation://b57c97a8-6324-4c31-a2bb-16b25e28dd55)가 수립 중인 [`master_pipeline_and_locked_assets_bible_plan.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/artifacts_archive/01_YouTube_CEO/master_pipeline_and_locked_assets_bible_plan.md) (`docs/LOCKED_ASSETS_AND_REFERENCES_BIBLE.md` + `docs/ALL_ABOUT_BRAIN_MASTER_PIPELINE.md` + `scripts/build_locked_assets_bible.py` + `tests/test_master_docs_and_assets_bible_parity.py`)를 해부한 결과, 구조가 매우 탄탄하며 아래 **5가지 핵심 구조화 항목**을 마스터 바이블에 반드시 포함할 것을 권고한다:

1. **수치화된 스타일 가이드(`Style Guide with Numbers` — `inkbeat-shorts` 핵심 교훈)**:
   - 모든 에이전트·검수자가 모호한 형용사 대신 숫자로 대조할 수 있도록 **단일 수치표** 고정:
     - 팔레트 Hex: 2.5D 비닐 피부 `#F5F2EB`, `Ep #31` 뇌 `#9CA5AC–#C3C9CE` / `#DCDFE3–#ECEFF2`, 시안 혈관 `#27D8FF`, 뇌 배경 `#040711`, 3D 화살표 `#FF2525`, 강조 자막 `#FFE600`, `HookTitle` 강조 `#FFE14A`
     - `R85` CV 정량 기준 (`pipeline/config.py:2389-2395`): `R85_EP31_CORTEX_SAT_MAX=48.0`, `CORTEX_LUMA_MIN=152.0`, `MODE1_LUMA_MIN=135.0`, `MAX_SPARK_CLUSTERS=22`, `MAX_VOID_HALO_P90=40.0`
     - 레이아웃·안전영역: `1080x1920 @ 30fps`, `HookTitle 118pt (MarginV=238, 0.00–2.20s, <=4w/24c)`, `ASS 82pt (outline 5.5, MarginV=510, <=3w)`, `PatrickHand 72–84px`, 히어로 인물 프레이밍 `~35–45%`
     - 오디오/음성: `Siren (el_siren_v4)`, `-14.0 LUFS`, `-1.5 dBTP`, BGM 덕킹 `-21.5 / -16.5 dB`, 인간 컷 `1.90–4.25s`, 뇌 컷 `4.20–6.80s` (`42–58%`)
2. **`Golden Style Canary Sheet` (`Demo / DemoHero / DemoCast` 대응 비주얼 기준 시트)**:
   - `ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg`에 반드시 **`Ep #31` 원조 4장** (`v1/_reference_31_O2CmlKOk/*.png`) + 대표 잠금 슬롯(`J01`, `A01/A02/A14`, `B05/B09`, `D01`, `K03/K05/K06`, `C01b`, `I01/I02`)을 나란히 배치해 모든 검수의 시각 앵커로 삼는다.
3. **`99`슬롯 정본 카탈로그의 '조건화 역할 & 반(反)복제 가드' 열 추가**:
   - `LOCKED_ASSETS_AND_REFERENCES_BIBLE.md`의 99슬롯 표(`v1` 42 + `v1_1` 43 + `v1_2` 14 + 보류 `J04`)에 단순 경로/SHA-256만 적지 말고 아래 2개 열을 추가:
     - **`사용 방식(Role)`**: `Ingredients Style/Cast Anchor Only` vs `Start+End Transition Pair` vs `Turnaround Sheet (Frame-0 금지: B01–B04 등)`
     - **`Semantic ID 변주 규칙`**: 예) `J01` 연속 2편 재사용 금지, 매 편 `R72-R` 실제 기관·전경 소품 교체 필수, `C_v2`는 `spatial_arrow_eligible=True` 전용.
4. **기각 후보(`excluded_reasons`) 및 보류 슬롯(`J04`)의 '네거티브 오답 노트' 영구 보존**:
   - `v1_2/manifest.json`에만 묻혀 있는 **`10`개 기각 사례(`J01 cand_03` 발광 반사, `J03 cand_01` 깨진 VU 미터, `J04` 거대 캡슐 스케일 붕괴+3지 손, `J06 cand_03` HookTitle `-22px` 충돌, `C01b/C02b/C03b` 물리·역주행·옥상 관통 결함)**를 바이블의 **"What Cheap/Wrong Looks Like (절대 기각 기준)"** 섹션에 그대로 박제하면 향후 에이전트·인간 검수 정확도가 크게 올라간다.
5. **토큰 경량화를 위한 `docs/` ↔ `.agents/rules/*.md` 2원 분리 유지**:
   - 대표님이 오늘 지적하신 *".agents/rules/ 파일 하나당 토큰 과다 문제"*를 해결하려면, **사람+바이블용 전체 카탈로그·도표·99슬롯 명세는 `docs/`에 분리 보관**하고(`.agents/rules/*.md`에 중복 복붙 금지), `.agents/rules/*.md`는 `AGENTS.md` 라우팅 하에 짧고 모듈화된 결정론적 실행 규칙만 남기는 구조가 가장 토큰 효율적이다. *(토큰 최적화 아키텍처 상세 계측은 후속 `[DEEP_RESEARCH_TOKEN_OPTIMIZATION_GO]` 태스크에서 정밀 다룸.)*

---

## Verification & Primary-Source Receipts (`R83-7` · `R83-8-V`)

1. **작업 공간 무결성**: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/` 내 파일 생성·수정·삭제 `0`건, Google Flow 호출 `0`건, 브라우저 CDP 호출 `0`건.
2. **검증된 외부 1차 URL**:
   - YouTube 사례 영상: `https://youtu.be/WTqUoZt4k8g` (로컬 추출 자막: `/tmp/yt_WTqUoZt4k8g_clean.txt`, `225`줄)
   - Google Doc 원문: `https://docs.google.com/document/d/17vHdvnLiOMtTQ4Qd5femJvdyG2ycKDOWWN_pI8gb2EI/edit` (로컬 추출: `/tmp/ref_gdoc_17vHdvnLiOMtTQ4Qd5femJvdyG2ycKDOWWN_pI8gb2EI.txt`, `138`줄)
   - `inkbeat-shorts.zip`: `https://drive.google.com/file/d/1MwNc-8kSBqnW0GD3r1js1ScsJRyO0tfa/view?usp=sharing` → `/tmp/inkbeat_teardown/inkbeat-shorts.zip` (`349,569 B`, `SHA-256 = b1af56111e24cb9043f010dbbe360b6f3f0607554e1f3940ac4602b9b9bc949b`, `64`개 파일 해제 확인, 실행 `0`건)
   - Google Research `TIGER`: `https://arxiv.org/abs/2305.05065`
   - Google/YouTube `Semantic IDs Ranking`: `https://arxiv.org/abs/2306.08121`
   - Google DeepMind/YouTube `PLUM`: `https://arxiv.org/abs/2510.07784` (`arXiv HTML`: `https://arxiv.org/html/2510.07784v1`)
   - YouTube 공식 YPP `Inauthentic Content` 정책: `https://support.google.com/youtube/answer/1311392?hl=en`
3. **로컬 워크스페이스 검증 경로**:
   - `pipeline/config.py`, `pipeline/flow_prompt_builder.py`, `pipeline/depiction_rules.py`, `pipeline/flow_diorama_sharded_worker.py`, `pipeline/dynamic_episode_qa.py`, `pipeline/posthoc_semantic_qa.py`, `pipeline/reference_image_qa.py`
   - `tests/test_credit_safe_pipeline.py`
   - `BCI_Shorts_Channel/canonical_assets/{v1,v1_1,v1_2}/manifest.json` (`42 + 43 + 14/15 = 99` 잠금 + `J04` 보류)
   - `.agents/rules/qa_gates_rules.md`, `.agents/rules/camera_choreography_rules.md`, `.agents/skills/youtube-script/SKILL.md`
   - `artifacts_archive/01_YouTube_CEO/master_pipeline_and_locked_assets_bible_plan.md`
4. **서브에이전트 및 VP 1차 검수 영수증 (`R83-8`, `R83-8-V`)**:
   - `flash` 코드베이스·매니페스트 카탈로거 서브에이전트(`15fe0258-e908-4b8d-a28e-accb5a1bc7fb`) 1회 단발성 호출 → VP가 `config.py`, `flow_prompt_builder.py`, `depiction_rules.py`, `dynamic_episode_qa.py`, `posthoc_semantic_qa.py`, `reference_image_qa.py`, `v1_2/manifest.json` 실제 파일 라인·상수·경로(`episode_qa.py` 부재 및 `dynamic_episode_qa.py` 실존 포함)를 직접 대조·검증 완료.
