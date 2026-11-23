# 3D 뇌 시뮬레이터 프레임 단위 작동 보고서 & `TRUkQ1wbV2E` 기반 `Siren` 단독 5단 톤·피치 연출 계획서

- **뇌 단독 3D 시뮬레이터 시연 영상 (`41.6초`, `8컷`, 최상위 폴더 배치 완료)**: [final_brain_only_simulator_showcase.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_brain_only_simulator_showcase.mp4)
- **화면 끊김·드론 기체 제거 완료 본편 (`Ep #8 v3`, 최상위 폴더 배치 완료)**: [final_shorts_v8_ep08_r77_fixed.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep08_r77_fixed.mp4)

> [!IMPORTANT]
> **결론 먼저 말씀드립니다 — 앞으로 성우는 100% `Siren` 단독(`1인 체제`)으로 고정합니다.**  
> 기존에 다른 성우(`Laura`·`Hope`·`Brian`)를 끼워 넣어 하던 '놀람·의문·반전 리액션'은 성우를 바꾸지 않고, 아래 분석한 **`TRUkQ1wbV2E`(188만 조회수 유튜버)의 1인 다역 피치·톤 조절 기법**을 그대로 이식해 **`Siren` 한 명이 문장마다 톤과 음높이(피치)를 달리하며 연기**하도록 개편합니다.

---

## Part 1. 참고 유튜버(`TRUkQ1wbV2E`) 피치·톤 실측 해부 & `Siren` 단독 적용 계획 (`Rule R78-V`)

### 1-1. "아, 이 유튜버는 혼자 말하면서 이렇게 지루함을 없앴구나!" (실제 음성 파형·기본주파수 `F0` 계측 결과)

`TRUkQ1wbV2E`(`61.0초`, 24시간 `188만` 조회수) 원본 오디오를 `20ms` 프레임 단위로 기본주파수(`F0 Hz` → 본인 평상시 음높이 대비 **반음 `Semitone, ST` 변화량**)와 성량(`dB`), 발화 속도(`WPM`)로 정밀 측정한 결과, **성우는 단 1명인데 5가지 뚜렷한 피치·톤 기어**를 교차 사용하고 있었습니다.

![TRUkQ1wbV2E 유튜버의 1인 피치·톤 변화 실측 vs 현재 Solo Siren 피치 곡선 비교](./truk_pitch_tone_contour_vs_siren.png)

| `TRUkQ1wbV2E`의 5단 톤 모드 | 실제 대사 구간 예시 | 실측 피치 변화 (`ST`) | 성량·속도 변화 | 시청자 뇌가 느끼는 효과 (기존 다중 성우 대체 역할) |
|---|---|---:|---|---|
| **① `brisk_story`**<br>(기본 이야기 질주) | *"He loaded the shotgun with gold..."* (`0.0~3.3s`) | **`+0.09 ST`** (기준음 `182Hz`) | `-13.3 dB` · `240~275 WPM` | 군더더기 없이 사건을 빠르게 밀고 나가는 기본 내레이터 톤 |
| **② `surprised_lift`**<br>(놀람 · 시청자 대변 질문) | *"So, we're shooting gold into a gold mine?"* (`6.6s`)<br>*"Why would anyone shoot gold into a wall?"* (`37.2s`) | **`+1.59 ~ +2.73 ST` 상승** | `-13.4 dB` · `168~208 WPM` | **핵심 비결 1**: 시청자가 속으로 *"잠깐, 왜 저래?"* 하고 놀랄 타이밍에 **본인 목소리 피치를 `+2.7반음` 높여 살짝 어이없다는 듯 되묻습니다.** (기존 보조 성우 `foil`/`Mini-Cortex` 역할을 100% 대체!) |
| **③ `insider_reveal`**<br>(비밀 귀띔 · 원리 해명) | *"You see, it's called salting."* (`9.1~10.7s`) | **`+1.07 ST`** | **`-16.7 dB` (`-3.4dB` 낮춤)** · `150 WPM` | 질문 직후 볼륨을 살짝 줄이고 속도를 늦춰 *"사실 이게 뭐냐면요"* 하고 귀에 쏙 들어오게 핵심 원리를 짚어줌 |
| **④ `hushed_suspense`**<br>(위기 · 단서 포착 저음) | *"But under his magnifying glass, every flake is flat."* (`30.6s`) | **`-2.74 ST` 하강** | **`-17.0 dB` (`-3.7dB` 낮춤)** · `180 WPM` | 결정적 결함(우리 영상에서는 **뇌 신경선이 끊어진 순간**)에서 피치를 `-2.7반음` 낮추고 조용히 말해 긴장감 조성 |
| **⑤ `deadpan_drop`**<br>(충격 결론 저음 툭 떨어뜨리기) | *"That's insane. ... Completely insane."* (`39.5~43.0s`) | **`-3.82 ST` 급하강** | `-17.5 dB` · **`86~120 WPM` 반속** | **핵심 비결 2**: 느낌표(`!`)로 소리 지르는 대신, 직전 `+2.7 ST` 질문에서 **`-3.8 ST` 중저음(`총 6.5반음 낙차`)**으로 뚝 떨어뜨리며 천천히 말해 소름과 임팩트를 만듦 |

---

### 1-2. 우리 `Solo Siren`에 그대로 이식하는 설계안 (`Rule R78-V: Solo-Siren 5-Tone Acting Engine`)

현재 우리 [elevenlabs_tts.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/elevenlabs_tts.py#L175-L195)는 `brisk`(태그 없음 `""`)와 `stamp`(`"[measured, deliberate voice]"`) 단 2가지만 쓰고 `stability`도 `0.50` 고정이라 `Siren`의 연기 폭이 절반만 열려 있었습니다. 이를 아래 **이중 제어(`ElevenLabs v4 감정 태그 + 문장별 Stability 가변 + F0 반음 검증`)**로 업그레이드합니다.

| 우리 기어 이름 (`prosody_gear`) | [elevenlabs_tts.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/elevenlabs_tts.py) `v4` 인라인 연기 태그 *(자막엔 자동 제거)* | `stability` 설정 | 목표 피치 변화 (`Siren` 기준음 `225Hz` 대비) | 우리 뇌과학 대본 적용 타이밍 예시 |
|---|---|---:|---|---|
| **`brisk`** | *(기본 내레이션 태그 없음 — 깔끔한 구어체 질주)* | `0.48` | `0.0 ST` (`190~205 WPM`) | 눈→시각피질→얼굴감지기 정상 신호 이동 설명 구간 |
| **`surprised_lift`** | `"[surprised, intrigued questioning tone]"` | **`0.32`** *(억양 폭 개방)* | **`+1.6 ~ +2.8 ST` 상승** | 훅 질문 & 반전 전환 (*"Wait—what happened when Mom stepped out and called him on the phone?"*) |
| **`insider_reveal`** | `"[warm, conversational leaning-in tone]"` | `0.42` | `+0.8 ST` · 성량 `-2.5 dB` | 뇌 진입 직전 2단계 원리 정리 (*"You see, knowing your mom's face takes two steps..."*) |
| **`hushed_suspense`** | `"[quiet, tense hushed voice]"` | `0.38` | **`-1.8 ~ -2.8 ST` 하강** | 신경선 단절 순간 (*"...but here, that wire is cut."*) |
| **`deadpan_drop`** | `"[low, serious deadpan voice]"` | `0.46` | **`-2.5 ~ -3.5 ST` 하강** | 마지막 충격 결론 (*"...his brain bought the only story left: an imposter."*) |

- **음질 무손실 안전장치 (`prosody-qa` `P11` 게이트)**:
  1. 문장 간 문맥 연결(`previous_request_ids` / `next_request_ids`, [elevenlabs_tts.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/elevenlabs_tts.py#L444-L453))은 동일 성우 `Siren` 100%이므로 끊김 없이 자연스럽게 이어집니다.
  2. 합성 직후 자동으로 각 문장의 실제 `F0` 반음(`ST`)을 계측하여, `surprised_lift` 문장이 평상시보다 최소 `+1.2 ST` 이상 올라갔는지, `hushed_suspense`/`deadpan_drop` 문장이 `-1.2 ST` 이하로 차분히 내려갔는지 검증합니다.

---

## Part 2. 3D 뇌 시뮬레이터 — 프레임 단위(`F1 → F2 → F3 → F4`) 작동 보고서

방금 렌더링 완료된 뇌 단독 시연본([final_brain_only_simulator_showcase.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_brain_only_simulator_showcase.mp4), `41.6초`, `8컷`)이 **실제 프레임 단위로 어떻게 움직이며 뇌 작동 원리와 협력/단절을 보여주는지** 각 컷마다 `4장`(`12% 진입 → 38% 신호 출발 → 64% 신경다발 주행 → 88% 목표 부위 도착/차단`)씩 추출한 실제 사진입니다.

### 전체 8컷 한눈에 보기 요약 보드
![MNI152 3D 뇌 시뮬레이터 v2 단독 8컷 종합 보드](./brain_only_simulator_v2_8cut_showcase_proof.png)

---

### 컷별 4프레임 연속 동작 상세 해부 (`Cut 01` ~ `Cut 08`)

#### 1) `Cut 01` (`0.00~3.97s`) & `Cut 02` (`3.97~8.00s`) — 전체 두상 속 위치 안내 & '얼굴 인식 2단계' 정상 협력 기준선 제시
- **시각 설계 의도**: 본격적인 해부학 추적 전에 반투명 3D 인간 두상(앞쪽 눈·코 방향과 뒤통수 방향이 한눈에 보임) 속에서 **① 측두엽 아랫면 얼굴 감지기(`Fusiform Face Area`, 파란색)**와 **② 안쪽 깊은 감정 중추(`Amygdala`, 붉은색)**의 정확한 3D 위치·모양을 먼저 보여주고, 정상 뇌에서는 노란 신호 구슬이 두 부위를 부드럽게 잇는 모습을 `3D 궤도 드론(global_system_orbit_drone)`으로 비춥니다.
- **`Siren` 적용 톤**: `Cut 01` **`surprised_lift`** (호기심 자극 질문 `+2.0 ST`) → `Cut 02` **`insider_reveal`** (*"You see, knowing your mom's face takes two steps..."* 친절한 기준선 귀띔).

````carousel
![Cut 01 4프레임 진행 (0.00~3.97s): 반투명 두상 속 얼굴 감지기(Fusiform) 위치 확립 및 지시선 드로잉](./brain_sim_cut_01_4frame_strip.png)
<!-- slide -->
![Cut 02 4프레임 진행 (3.97~8.00s): 정상 뇌의 2단계 협력 — 얼굴 감지기(파란색)에서 감정 중추 편도체(붉은색)로 노란 신호 구슬 전달](./brain_sim_cut_02_4frame_strip.png)
````

---

#### 2) `Cut 03` (`8.00~12.73s`) & `Cut 04` (`12.73~17.63s`) — 감각기관(`눈`)에서 시신경을 타고 뒤통수 시각피질 → 얼굴 감지기로 협력 주행
- **프레임별 작동 (`Cut 03` `sensory_to_brain_drone`)**:
  - **`F1 (12%)`**: 앞쪽 **3D 안구(`Eyes`, 황토색)** 두 개와 시신경 다발이 선명히 보이고, 뒤통수 `제1시각피질(Primary Visual Cortex)`은 아직 은은한 상태입니다.
  - **`F2 (38%) → F3 (64%)`**: 드론 카메라가 두상 옆면으로 부드럽게 선회하면서, **노란 신경 신호 캡슐들이 눈에서 출발해 시신경교차·시상을 거쳐 뒤통수 끝까지 실시간으로 달려갑니다.**
  - **`F4 (88%)`**: 신호가 도착하자 뒤통수 `시각피질` 전체가 선명한 매트 코랄색으로 점화됩니다 (`0.0px` 오차로 지시선 링이 부위를 계속 따라다님).
- **프레임별 작동 (`Cut 04` `circuit_cooperation_drone`)**:
  - 뒤통수 `시각피질(파란색)`이 받아낸 시각 정보를 아래쪽 길쭉한 `방추형 얼굴영역(Fusiform Face Area, 붉은색)`으로 넘겨주며 엄마 얼굴을 100% 일치시킵니다.
- **`Siren` 적용 톤**: `Cut 03`·`Cut 04` 모두 경쾌하고 명쾌한 **`brisk`** 스토리 진행 톤.

````carousel
![Cut 03 4프레임 진행 (8.00~12.73s): 3D 안구(Eyes) 출발 -> 시신경 주행 -> 뇌 뒤쪽 제1시각피질(Primary Visual Cortex) 점화](./brain_sim_cut_03_4frame_strip.png)
<!-- slide -->
![Cut 04 4프레임 진행 (12.73~17.63s): 시각피질(파란색)에서 측두엽 아랫면 얼굴 감지기(Fusiform, 붉은색)로 신호 전달 및 100% 얼굴 매칭](./brain_sim_cut_04_4frame_strip.png)
````

---

#### 3) `Cut 05` (`17.63~24.13s`) & `Cut 06` (`24.13~29.57s`) — 결정적 병리 메커니즘: 신경선 단절(`── ✕ ──`)과 무감정(`Zero Warmth`) 발생
- **프레임별 작동 (`Cut 05` `pathway_severed`)**:
  - **`F1 (12%) → F2 (38%)`**: 카메라가 측두엽 깊숙이 클로즈업 드론 진입하며 `얼굴 감지기(파란색)`에서 출발한 노란 신호를 비춥니다.
  - **`F3 (64%) → F4 (88%)`**: 신호가 백질 신경로 중간의 **붉은 3D 물리 단절 마커(`✕`)에 부딪혀 그대로 멈추고**, 바로 옆 **감정 중추 `편도체(Amygdala)`는 불이 켜지지 않은 채 차가운 회색(`Offline Slate`)으로 죽어 있는 모습**을 명확히 대조합니다.
- **`Cut 06` 결과 확인 + 정밀 보완 포인트**:
  - 엄마 얼굴은 보이지만(`Fusiform` 활성) 따뜻함이 `0`인 상태(`Amygdala` 암전)를 보여줍니다. *(※ 아래 3장 검수 메모처럼 현재 `Cut 06` 지시선이 `Fusiform`에 `Signal Offline`으로 표기된 부분을 **`Amygdala (Emotional Center · Zero Warmth)`**를 정확히 가리키도록 즉시 교정합니다!)*
- **`Siren` 적용 톤**: `Cut 05` **`hushed_suspense`** (선이 끊어진 순간 `-2.5 ST` 조용한 긴장 저음) → `Cut 06` **`brisk`** (인과 귀결 설명).

````carousel
![Cut 05 4프레임 진행 (17.63~24.13s): 얼굴 감지기(파란색) -> 3D 단절 지점(붉은 X)에서 신호 정지 -> 편도체(회색 암전 유지)](./brain_sim_cut_05_4frame_strip.png)
<!-- slide -->
![Cut 06 4프레임 진행 (24.13~29.57s): 시각 인식은 켜져 있으나 감정 중추가 꺼져 '얼굴은 엄마인데 온기가 0'인 상태 조망](./brain_sim_cut_06_4frame_strip.png)
````

---

#### 4) `Cut 07` (`29.57~35.10s`) & `Cut 08` (`35.10~41.60s`) — 전화 목소리 우회 회로: `내이 달팽이관 → 청각피질 → 편도체` 점화 vs `전전두엽` 현실검증 실패
- **프레임별 작동 (`Cut 07` `sensory_to_brain_drone`)**:
  - **`F1 (12%) → F4 (88%)`**: 귀 안쪽 **실제 나선형 3D 달팽이관·반고리관(`Inner Ear`, 황토색)**에서 소리 신호 구슬이 출발해 청신경을 타고 바로 위 **`청각피질(Auditory Cortex, 붉은색)`**로 올라가며 점화시키는 과정을 측면 클로즈업 드론샷으로 선명히 보여줍니다.
- **`Cut 08` 최종 통합 메커니즘 + 정밀 보완 포인트**:
  - 대사(*"That sound wire to your amygdala still works—so her voice feels like Mom, while damage up front calls her a fake."*)와 100% 일치하도록, 현재 `Auditory -> Prefrontal`로 연결된 `Cut 08` 회로를 **`Auditory Cortex ──▶ Amygdala (Emotional Center · Warmth Fires!)` 정상 연결 + 앞쪽 이마 뒤 `Prefrontal Cortex (Reality-Checker · Damaged/Dark)` 동시 대조 뷰**로 정밀 교정합니다.
- **`Siren` 적용 톤**: `Cut 07` **`surprised_lift`** (전화가 걸려오는 반전 생동감) → `Cut 08` **`deadpan_drop`** (마지막 퍼즐이 맞춰지는 묵직한 저음 결론).

````carousel
![Cut 07 4프레임 진행 (29.57~35.10s): 귀 안쪽 3D 나선형 달팽이관(Inner Ear) -> 청신경 -> 청각피질(Auditory Cortex) 신호 도달](./brain_sim_cut_07_4frame_strip.png)
<!-- slide -->
![Cut 08 4프레임 진행 (35.10~41.60s): 청각 우회로 점화 및 이마 뒤 전전두엽(Prefrontal Cortex) 현실 검증 회로 대조](./brain_sim_cut_08_4frame_strip.png)
````

---

## Part 3. 프레임 전수 검수로 잡아낸 최종 정밀 교정 & 실행 계획 (승인 시 즉시 반영)

프레임 단위 검수를 통해 확인된 아래 **3가지 마무리 디테일**을 함께 반영하여 완성도를 100%로 끌어올립니다.

1. **`Rule R78-V` (`Solo Siren` 5단 톤·피치 연기 엔진) 코드 탑재**:
   - [elevenlabs_tts.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/elevenlabs_tts.py) 및 [prosody.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prosody.py)에 `TRUkQ1wbV2E` 실측 기반 5종 기어(`brisk`, `surprised_lift`, `insider_reveal`, `hushed_suspense`, `deadpan_drop`)의 `eleven_v4` 감정 연기 태그 + 문장별 가변 `stability`(`0.32~0.48`) + `F0` 반음 편차 검증(`P11`)을 추가합니다.
2. **뇌 시뮬레이터 라벨·회로 1:1 정밀 일치 교정 (`Cut 02, 05, 06, 08`)**:
   - 라벨 부제에서 어색했던 `"Emotional Alarm"` / `"Impulse Brake"` 문구를 문맥에 맞는 **`"Emotional Center"` (감정 중추)** / **`"Reality-Checker"` (현실 검증 중추)**로 일괄 교체합니다.
   - `Cut 06` 지시선이 `Amygdala (Emotional Center · Zero Warmth)`를 직접 가리키게 수정하고, `Cut 08`이 `Auditory Cortex ──▶ Amygdala` 활성 경로와 암전된 `Prefrontal Cortex`를 동시에 보여주도록 정밀 보정합니다.
3. **시연본 & 본편 재합성 및 스튜디오 스테이징 마무리**:
   - 위 5단 `Siren` 톤 연기 + 뇌 라벨 정밀 교정을 적용해 [final_brain_only_simulator_showcase.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_brain_only_simulator_showcase.mp4)와 [final_shorts_v8_ep08_r77_fixed.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep08_r77_fixed.mp4)를 업데이트하고 YouTube Studio 예약 교체까지 마무리합니다.
