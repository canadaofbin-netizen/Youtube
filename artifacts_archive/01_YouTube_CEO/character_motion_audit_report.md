# 일반 캐릭터 움직임(Motion) 정밀 진단서 — 레퍼런스(`QlDPMzGmYac`) vs 현재 `Ep #8`

> [!IMPORTANT]
> **핵심 수치 요약 (`DISOpticalFlow` 30fps 피사체 순수 움직임 비교)**
> - **레퍼런스 (`QlDPMzGmYac`, 1,112만 뷰)**: 캐릭터·소품 순수 모션(`Subj P90`) **`4.99 ~ 7.66 px/f`**, 순간 타격 가속비(`Burst Ratio`) **`4.7x ~ 10.7x`** (짧고 절도 있는 **준비 → 빠른 스냅 액션 → 깔끔한 정지/표정 반전**)
> - **현재 우리 `Ep #8` 일반 캐릭터 컷 (`C01, C04, C08, C09, C10, C13`)**: 캐릭터 순수 모션 **`0.62 ~ 1.83 px/f` (레퍼런스의 `1/6` 수준)**, 순간 가속비 **`1.2x ~ 2.5x`** → 캐릭터는 마네킹처럼 굳어 있고 카메라만 느리게 줌인하거나, 2D 눈 번짐·지형 관통·비율 붕괴가 발생함

![레퍼런스(QlDPMzGmYac) vs 현재 Ep #8 캐릭터 움직임 비교 진단 시트](./character_motion_audit_vs_QlDPMzGmYac.jpg)

---

## 1. 레퍼런스 영상 (`https://www.youtube.com/shorts/QlDPMzGmYac`) 움직임의 핵심 강점 4가지

동일한 **'둥근 흰색 머리 + 2D 검은 먹물 눈·입 + 단순 의상'** 캐릭터 계열(`Ricks Clips`, *This Shape Saved Roller Coasters*, `63초 / 30fps / 1,112만 조회수`)을 `0.35초` 단위로 분해한 결과입니다:

![레퍼런스 QlDPMzGmYac 0.35초 단위 캐릭터 마이크로 액션 분해](./ref_QlDPMzGmYac_character_micro_beats.jpg)

1. **카메라 대신 '팔·몸통·소품'이 직접 크게 움직임 (`Subj Flow 5.0~7.7 px` vs `Cam Flow 0.5~2.6 px`)**
   - 카메라가 억지로 흔들리거나 줌인하지 않아도 캐릭터가 **해머를 머리 위로 치켜들었다가 내리찍고(`0.1s → 0.8s`)**, **빈 지갑을 두 손으로 확 펼쳐 보이고(`5.2s → 5.6s`)**, **나뭇가지를 양손으로 똑 부러뜨리며(`27.4s`)**, **롤러코스터 좌석에 훌쩍 올라타는(`34.2s → 35.0s`)** 명확한 물리 동작이 매 `1.2 ~ 2.0초`마다 터집니다.
2. **절도 있는 가속·정지 리듬 (`Anticipation → Snappy Action → Clean Hold`, `Burst 6.8x`)**
   - AI 특유의 물속 같은 등속도 슬로우모션이 전혀 없습니다. 동작 자체는 **`0.4 ~ 0.8초` 안에 빠르게 '탁!' 완결**되고, 직후 `0.5 ~ 1.0초`간 시선·포즈를 깔끔하게 홀드해 시청자가 상황을 즉시 읽게 만듭니다.
3. **번지지 않는 '2D 스냅 표정 연기' (`Step-Snap 2D Expression`)**
   - 얼굴이나 눈이 물컹하게 일그러지지 않고, 흰 머리 표면 위에서 **`5.6s` 활짝 웃는 눈·입 → `6.4s` 반눈 일자 입(허탈 표정)**처럼 감정 전환 타이밍에 맞춰 **만화 프레임처럼 0.2초 만에 선명하게 바뀝니다.**
4. **일관된 캐릭터 화면 비중 (`화면 높이의 45% ~ 75%`, 아이레벨 고정)**
   - 언제나 무릎 위 미디엄샷~바스트샷 아이레벨을 유지해 신체 비율이 무너지지 않고 손동작·표정이 모바일에서 한눈에 보입니다.

---

## 2. 현재 `Ep #8` 일반 캐릭터 파트에서 발견된 6대 움직임 문제점 (시각 증상 + 코드 원인)

````carousel
![우리 Ep #8 컷 1~8 프레임 진행 시트](./ep08_all_cuts_motion_part1.jpg)
<!-- slide -->
![우리 Ep #8 컷 9~16 프레임 진행 시트](./ep08_all_cuts_motion_part2.jpg)
````

### ① '마네킹 정지 + 카메라 줌인 착시' (`C01: 0.83px`, `C08: 0.62px`, `C09: 0.86px`)
- **문제 현상**: 캐릭터의 팔·손·몸통은 접착제로 붙인 듯 5초 내내 멈춰 있고(`Peak 1.1 ~ 2.3px`), 카메라만 서서히 줌인(`gentle_push_in`)하며 영상인 척합니다. 특히 `Cut 09`(`38.8~44.1s`)는 `5.27초` 동안 의사도 환자도 손가락 하나 움직이지 않는 사실상의 정지 사진입니다.
- **파이프라인 코드 원인**:
  - [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L1687-L1697) 및 [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py#L2029-L2037)의 **프롬프트 단어 수 절단 버그(`hi_w` truncation)**가 배경 설명을 앞에 배치한 뒤 **정작 핵심 캐릭터 액션 동사(`recoils sharply backward...`, `leans back and folds both arms...`, `places comforting hand...`)를 뒤에서 통째로 잘라버렸습니다.**
  - 실제 Google Flow에 전송된 `C01` 프롬프트([flow_all_in_one_prompts.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r77/03_visuals/flow_all_in_one_prompts.json)):
    `"...a 2.5D young man in a navy jacket across from his older mother in. Silent voice track."` → **동사가 0개인 미완성 문장**이 들어가서 캐릭터가 움직이지 못했습니다.
  - 반대로 `C03, C09, C10, C13, C16`([flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L1772-L1787))은 **주어(`cast`: 누가 행동하는지)를 누락**한 채 `"Sets a framed portrait..."`처럼 동사부터 시작하고 문장 끝을 `"flat unblinking 2D."`, `"catches the."`로 중간 절단했습니다.

### ② '시작 프레임 클라이맥스 함정' (`Start-Frame Climax Trap`)
- **문제 현상**:
  - `Cut 01`(`0.0~5.1s`): 엄마를 보고 놀라 의자를 뒤로 젖히는 액션이 나와야 하는데, 시작 이미지([kf_01_ucsd_sunny_living_ro_pv_start_9x16.png](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r77/03_visuals/reference_images/kf_01_ucsd_sunny_living_ro_pv_start_9x16.png))에서 **이미 의자 앞다리가 공중에 뜬 채 두 손을 들고 비명 지르는 결과 포즈**로 시작합니다. 그 결과 5초 내내 공중에 뜬 의자 위에서 굳어 있는 부자연스러운 AI 영상이 됩니다.
  - `Cut 09`(`38.8~44.1s`): 의사가 엄마 액자를 이젤에 올려놓는 액션인데, 시작 이미지([kf_09_ucsd_polygraph_bench_pv_start_9x16.png](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r77/03_visuals/reference_images/kf_09_ucsd_polygraph_bench_pv_start_9x16.png))에 **이미 액자가 이젤 위에 놓여 있어** 아무 동작도 일어나지 않습니다.

### ③ 2D 먹물 눈 '번짐·녹아내림' AI 아티팩트 (`Cut 04`, `17.6s ~ 18.8s`)
- **문제 현상**: `Cut 04` 프롬프트에 행동 대신 `"as 2D charcoal ink eyes shift"`만 남으면서, Google Flow가 2D 먹물 눈을 문지르듯 변형시키다 **눈 주변이 시커먼 먹물 얼룩처럼 번지고 녹아내리는 심각한 AI 티**가 발생했습니다(게다가 배경 레퍼런스 때문에 주인공 남색 재킷 대신 의사 가운을 입은 인물로 잘못 생성됨).

### ④ 캐릭터 지형 관통 및 거인/소인 비율 붕괴 (`Cut 03`, `Cut 10`, `Cut 13`)
- **문제 현상**:
  - `Cut 03`(`11.1s`): 시작 프레임에서 주인공 하반신이 **콘크리트 화단 블록 내부에 허리까지 파묻힌 채** 걸어 나오며, 문 앞 의사 옆에 설 때 **어린이처럼 키가 의사 절반 크기**로 작아집니다.
  - `Cut 10`(`44.5~47.1s`): 캐릭터가 없는 빈 복도 사진(`ref_loc_ucsd_clinic_glass_walkway_9x16.png`)에 `90도 수직 하강`을 걸어 앞쪽 인물은 거인, 전화기 옆 인물은 유아 크기로 생성되고 후반부 모션이 `83%` 정지(`2ndHalf/1st = 0.17x`)합니다.
  - `Cut 13`(`56.5~61.1s`): 먼 건물 외벽 조감도에서 시작해 첫 2초 동안 캐릭터가 점처럼 작아 행동이 보이지 않습니다.

### ⑤ 배경 고무 왜곡 & 억지 배속/무중력 슬로우모션 (`Cut 03`, `Cut 16`)
- **문제 현상**:
  - `Cut 16`(`71.1~76.9s`): `dolly_zoom_vertigo` 프롬프트의 `"warping background depth"` 문구 때문에 **진찰실 벽과 책상이 젤리처럼 휘어지는 AI 왜곡**이 발생하고, 아들은 팔을 어정쩡하게 벌린 채 느리게 떠오릅니다.
  - `Cut 03`: `7.65초` 분량을 `3.53초`에 우겨 넣으며 `main_speed = 2.16x` 배속이 걸려 걸음걸이가 비정상적으로 빨라진 반면, 나머지 컷들은 `1.0x` 등속도로 느릿하게 떠다닙니다.

### ⑥ 컷당 단일 포즈 유지 시간이 너무 김 (`4.4초 ~ 5.8초` 원컷 버티기)
- **문제 현상**: 레퍼런스는 `1.2 ~ 2.5초`마다 새 동작(손동작 → 소품 반응 → 표정 스냅)이 치고 나가는데, 현재 캐릭터 컷은 동작 하나도 없는 장면을 **`5.0 ~ 5.8초` 동안 길게 끌고 가** 루즈함과 AI 정지감이 배가됩니다.

---

## 3. 요약 비교표

| 항목 | 레퍼런스 (`QlDPMzGmYac`, 1,112만 뷰) | 현재 `Ep #8` 일반 캐릭터 파트 |
|---|---|---|
| **피사체 순수 움직임 (`Subj P90`)** | **`4.99 ~ 7.66 px/f`** (활발한 팔·몸통·소품 액션) | **`0.62 ~ 1.83 px/f`** (마네킹처럼 정지, 카메라만 줌인) |
| **동작 리듬 (`Burst Ratio`)** | **`4.7x ~ 10.7x`** (`준비 → 0.5초 빠른 액션 → 홀드`) | **`1.2x ~ 2.5x`** (가속 없는 슬로우 유영 또는 멈춤) |
| **시작 프레임 설계** | **행동 직전 '준비 자세(State A)'**에서 출발 | **이미 끝난 '결과 자세(State B)'**로 박제 (`C01` 공중 의자, `C09` 이미 놓인 액자) |
| **2D 얼굴·눈 표현** | 번짐 없이 **깔끔하게 '착!' 바뀌는 2D 스냅 표정** | `"eyes shift"`로 인한 **검은 먹물 번짐 현상(`C04`)** 또는 5초 고정 표정 |
| **카메라 구도 & 신체 비율** | 일관된 **아이레벨 미디엄/바스트샷 (화면 45~75%)** | 조감도·원경 남발로 **콘크리트 관통(`C03`), 거인/소인 비율 붕괴(`C10`)**, 벽 왜곡(`C16`) |
| **실제 전송된 Flow 프롬프트** | 주어 + 명확한 2단계 물리 소품 액션 완결 | **단어 수 절단 버그로 동사 소멸(`C01, C04, C08`) / 주어 소멸·문장 절단(`C03, C09, C13`)** |
