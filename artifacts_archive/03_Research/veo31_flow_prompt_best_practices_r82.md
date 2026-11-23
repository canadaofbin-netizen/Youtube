# 최신 Google Flow / Veo 3.1 영상 생성 프롬프트 베스트 프랙티스 & 파이프라인 4대 문법 이식 설계서

## 1. 검증된 공식 · 엔지니어링 레퍼런스 출처 (`search_web` 실측 URL)

1. **Google Cloud 공식 블로그 (`Veo 3.1 Ultimate Prompting Guide`)**: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1
2. **Google Cloud 공식 비디오 생성 프롬프트 가이드**: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide
3. **Google AI Studio 공식 Veo 문서 (`Image-to-Video` & `Reference/Frame` 제어)**: https://aistudio.google.com/docs/veo
4. **Google DeepMind 공식 Veo 모델 사양**: https://deepmind.google/models/veo/
5. **Fal.ai Veo 3 카메라 문법 & 피직스 엔지니어링 가이드**: https://fal.ai/learn/devs/veo3-prompt-guide-master-google-video-generation
6. **Google GenAI Veo Prompting Reference (`cnemri/google-genai-skills`)**: https://github.com/cnemri/google-genai-skills/blob/main/skills/veo-use/references/prompting.md

---

## 2. 외부 공식 가이드에서 도출한 5대 핵심 원리 (현재 우리 프롬프트 버그와 직결!)

> [!IMPORTANT]
> **발견 1 — `Image-to-Video` `Delta-Only` 법칙 (`VIDEO_FRAMES` 시작 키프레임 잠금 시 정적 외형 재묘사 금지)**:
> Google Cloud 공식 가이드와 AI Studio Veo 문서는 **시작 키프레임(`VIDEO_FRAMES`)을 넣었을 때 이미지에 이미 그려진 정적 복장·배경·얼굴 외형을 길게 다시 설명하면 모션 에너지가 죽거나 모델이 혼란을 일으킨다**고 명시합니다. 그런데 현재 우리 `Ep #10~#12` 프롬프트(예: `Ep #10 C01`: `"The 2.5D middle-aged sleeper man in a burgundy cotton cardigan seated on the bed edge first the 2.5D sleeper man in a burgundy cotton cardigan lifts..."`)는 `_prepend_concise_cast_subject` 중복 결합으로 **정적 주어·복장을 두 번 반복(`first ...`)**하면서 앞단 28단어 토큰 예산을 잠식하고 있습니다!

| # | 공식 Veo 3.1 / Flow 원리 | 출처 핵심 요지 | 우리 파이프라인(`flow_prompt_builder.py`) 진단 |
|---|---|---|---|
| **1** | **앞단 가중치 법칙 (`[Camera Vector] + [Subject] + [Single Crisp Action] + [Physical Consequence]`)** | Veo 계열은 **첫 20~30단어에 가장 높은 어텐션 가중치**를 부여함. 추상 부사(`"dramatically"`, `"meaningfully"`) 대신 구체 물리 동사(`"unclips"`, `"presses"`, `"squeezes"`) 1~2개만 배치. | `_prepend_concise_cast_subject`가 이미 주어가 있는 `action` 앞에 또 `cast`를 붙여 `"The 2.5D woman ... first the 2.5D woman ..."` 중복 발생 → **즉시 중복 제거 필요**. |
| **2** | **`Image-to-Video` 델타(변화량) 집중 원칙 (`Delta-Only Prompting`)** | `single_start_frame_lock=True`일 때는 옷·벽 색깔 재서술을 줄이고 **`[시작 자세에서 목표 자세로의 물리 변화 + 카메라 궤적]`**만 지시해야 `2~3초` 내 즉각 동작이 터짐. | `context_split=True` 경로에서 `cast` 수식어를 **최대 6~8단어 식별자**(`"The burgundy-cardigan sleeper man"`)로 압축하면 초기 모션 반응 속도가 대폭 상승함. |
| **3** | **단일 축 카메라 벡터 법칙 (`Single-Axis Camera Trajectory`)** | 한 컷에 복합 회전(`"orbit while zooming and tilting"`)을 섞으면 기하 왜곡·90° 급회전이 발생함. 반드시 **단일 축 + 각도 상한**(`"Poised 6-degree coronal micro-parallax"`)만 지정. | `R82` 단독·양측 뇌 컷에서 `"Sweeping 3D lateral orbit"`(예: `Ep #12 C16`) 같은 광각 회전어가 남아 있으면 `90°` 스핀 위험 존재 → **`"Poised steady <plane> glide under 8 degrees of single-plane micro-parallax"`**로 통일. |
| **4** | **인-씬 가짜 글자(`Plaque/Label`) 억제 긍정 치환법** | 인라인 텍스트에서는 `"no text"` 부정어 단독 사용보다 **`"completely blank unlabeled stone architrave, smooth sign-free facade"`**처럼 표면 재질을 긍정문으로 잠글 때 가짜 간판 생성률이 최저임. | 캠퍼스 항공 드론샷(`C03`)과 `R80` 탑다운 샷에서 건물 박공(pediment)에 가짜 대학 영문 현판이 생기는 현상을 `"smooth blank unlabeled stone frieze"`로 원천 봉쇄 가능. |
| **5** | **스톱모션·택타일 물성 키워드 (`Tactile Miniature & Vinyl Specifiers`)** | 2.5D 비닐 피규어·건축 컷어웨이에서는 `"matte vinyl surface"`, `"crisp step-snap increment"`, `"architectural scale cutaway"`, `"sharp sunlight drop shadow"`가 CGI 부유감을 없애고 접지감을 고정함. | 휴먼 `Clean Hold` 구간과 `R80` `#FF2525` 입체 화살표 컷에 물리 재질·접지 그림자 구문을 표준 접미사로 고정하면 부유 현상이 사라짐. |

---

## 3. 우리 파이프라인 4대 문법별 즉시 이식 프롬프트 템플릿

### 문법 ① 대학/연구기관 30m 상공 항공 드론 & 창문 컷어웨이 (`R82-3` 캠퍼스 브릿지)
- **적용 위치**: [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py) (`drone_aerial_approach` + `architectural_cutaway_portal`)
- **핵심 교정**: `C03` 항공 드론 프롬프트에서 **1인칭 근접 캐릭터 산책 묘사를 완전히 분리**하고(`tiny distant scale figures in courtyard below`만 허용), 무표지 박공(`blank unlabeled stone frieze`)을 명시합니다.
- **즉시 사용 가능한 표준 프롬프트 쌍**:
  - **`Cut A` (`C03` — 30m 상공 캠퍼스 항공 드론 어프로치, `2.2~2.8s`)**:
    > `High-altitude 3D aerial approach descending smoothly at a 35-degree angle over sunlit treetops straight toward {institution_architecture_desc} with completely blank unlabeled stone facades, as tiny miniature lab-coat figures cross the wide courtyard below in crisp morning daylight with strong roof-edge parallax.`
  - **`Cut B` (`C04` — 외벽→창문 단면 컷어웨이 진입, `2.2~2.9s`)**:
    > `Continuous forward-gliding 3D sweep skimming past {exterior_column_or_window_frame} straight into the bright architectural cutaway {lab_room_desc}, where {concise_subject} {crisp_setup_verb_phrase} with grounded floor contact shadows.`

### 문법 ② `2.0~3.0s` 고속 2비트 2.5D 비닐 캐릭터 액팅 (`R79-M` / `R82-1`)
- **적용 위치**: [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L1654-L1690) (`_prepend_concise_cast_subject` & `_compose_expressive_v8_context_split_scene`)
- **핵심 코드/프롬프트 교정 (`first ...` 중복 버그 제거)**:
  - `act_clause`가 이미 `"the 2.5d"` 또는 캐릭터 주어 명사로 시작하거나 내부에 `"first the 2.5d"` 구문을 포함할 경우 `_prepend_concise_cast_subject`가 주어를 중복 전치하지 않도록 정규화하고, `VIDEO_FRAMES` 단일 시작 프레임 모드에서는 `[카메라 단일 벡터] + [6~8단어 압축 주어] + [즉각 물리 동사 (0.4~0.8s)] + [물리 결과 & 2D 잉크 스냅 정지]` 어순을 강제합니다.
- **표준 템플릿 (`18~34`단어 델타 집중형)**:
  > `Eye-level medium push-in locked to the opening frame. The {wardrobe_anchor} {role_noun} briskly {ballistic_prop_verb_clause}, settling into a crisp stationary hold as bold 2D charcoal-black ink brows snap into {step_snap_expression} on the smooth matte cream-white vinyl head.`

### 문법 ③ 단독 & `A vs B` 양측 비교 3D 뇌 시뮬레이터 (`R78-M` / `R81` / `R82-2,4`)
- **적용 위치**: [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L2295-L2306) (`r78m_flow_prompt`)
- **핵심 교정**:
  - `Ep #12 C16`처럼 `"Sweeping 3D lateral orbit"`라고 쓰면 Veo/Omni가 뇌를 `45°~90°` 돌려버려 `R81` 해부학 지시선이 페이드아웃되거나 좌우 뇌가 겹칩니다.
  - 모든 단독 뇌 컷은 **`under 12 degrees of single-plane micro-parallax`**로, 모든 `side_by_side_brain_compare=True` 컷은 **`under 6 degrees of subtle front-coronal micro-parallax keeping both entire whole brains completely inside the frame margins`**로 고정합니다.
- **`A vs B` 양측 뇌 비교 표준 프롬프트 템플릿 (`Ep #10 C19`, `Ep #11 C18`, `Ep #12 C16` 공용)**:
  > `Vertical full-bleed 3D scientific visualization locked seamlessly to the opening keyframe. Poised wide front-coronal 3D side-by-side dual-brain comparison under 6 degrees of subtle single-plane micro-parallax, keeping both entire translucent cool matte silver-gray whole brains completely inside the left and right frame margins over pure dark studio slate: on the left, the {group_a_label} brain displays {region_a_active_state_desc}; on the right, the {group_b_label} brain displays {region_b_contrasting_state_desc}. Maintain clean central separation, blank dark upper header space, and zero floating labels.`

### 문법 ④ `R80` 3D 입체 `#FF2525` 공간 화살표 디오라마 (`spatial_3d_arrow_diorama`)
- **적용 위치**: [spatial_arrow_guide.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/spatial_arrow_guide.py#L263-L299) (`build_r80_flow_scene_clause`)
- **핵심 교정**: Veo 3.1 물리 가이드의 택타일 물성 법칙을 반영해 화살표가 화면 위에 뜬 2D UI 스티커로 변질되지 않도록 **`"rigid solid matte-crimson 3D architectural block resting flush on the ground plane casting sharp dark directional sunlight shadows"`** 물성 구문과 무표지 도로/바닥(`"unmarked asphalt and blank stone roofs"`)을 고정합니다.
- **표준 템플릿 (`topdown_arrow` 컷)**:
  > `Vertical 90-degree bird's-eye top-down glide tracking {vehicle_or_actor_desc} moving briskly along a rigid solid matte-crimson 3D extruded directional arrow block resting flush on the unmarked ground plane and casting sharp dark directional sunlight drop shadows across blank unlabeled miniature architecture.`
