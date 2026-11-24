# `'신비한 건축사전'` × `'@심리학고양이'` 썸네일 통합 포렌식 해부 및 `ALL ABOUT BRAIN (v8)` 이식·코드 감사 최종 보고서

> [!IMPORTANT]
> **핵심 요약 (Zero-Guessing 실측 검증)**
> 1. **데이터 실측 범위**:
>    - **채널 A (`신비한 건축사전`, `@신비한_건축사전_1` / `UCeEM8XgdgUyaWE1Z6_5sHbQ`)**: 구독자 **82.5만**, 공개 롱폼 **101편** (`37,445,678`뷰) + 공개 쇼츠 **500편** (`349,136,900`뷰, 합산 **3.86억 뷰**).
>    - **채널 B (`@심리학고양이`, `UCaJkv4faBajjsDGq2YPJN0A`)**: 구독자 **40.4만**, `/videos` 전체 **190편** 중 **일반 공개 롱폼 156편** (`42,391,257`뷰) + **멤버십 전용(`subscriber_only`) 22~34편**, **쇼츠(`/shorts`) 0편**.
>    - **실물 자산 및 코드 대조**: 상위 히트작 및 최신작 **실제 썸네일 원본 33종**([`thumb_benchmark_media/`](./thumb_benchmark_media)), 본편 H.264 MP4 전 프레임(`uUN1Bw0elY8` `2,893f`, `YOXXmgy-02s` `2,811f`), 그리고 우리 채널(`@AllAboutBrainOfficial`)의 [`pipeline/thumbnail_studio.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py), [`pipeline/anatomy_label_overlay.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_label_overlay.py), [`pipeline/config.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py), [`pipeline/studio/uploader.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py) 및 `Ep #4` · `Ep #5` 실물 산출물을 전수 검증했습니다.
> 2. **쇼츠 썸네일 기술 포렌식 결론**:
>    - `'신비한 건축사전'`의 쇼츠(`9:16`)는 외부 커스텀 썸네일(`sardefault.jpg` = `HTTP 404`, `0/500편`)을 전혀 쓰지 않으며, `500편` 전수 엔드포인트 분포가 **`oar1.jpg` `159편 [31.8%]` (`~17%` 지점) : `oar2.jpg` `162편 [32.4%]` (`~50%` 지점) : `oar3.jpg` `161편 [32.2%]` (`~80%` 지점)** 으로 동적 순환 노출됩니다(1분 간격 2회 수집 시 `31.7%`가 실시간 슬롯 교체). 즉, 이 채널이 최고 **652만 뷰**를 기록하는 비결은 **영상의 `17%`·`50%`·`80%` 어느 시점이 뽑혀도 완성된 인포그래픽 썸네일이 되도록 본편 전 구간(`평균 2.06초/컷`)을 '3D 절개 단면도 + `#FF2525` 입체 빨간 화살표/치수선 + 중앙 1줄 번인 자막'으로 연출했기 때문**입니다.
>    - 반면 **우리 채널(`@AllAboutBrainOfficial`)은 [`pipeline/studio/uploader.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py#L1689-L1695)가 업로드 위저드의 숨겨진 `input[type='file']`에 `thumbnail_var_A.png`를 직접 주입하여, 공개 쇼츠 5편 전수에서 커스텀 `sardefault.jpg`(`1080×1920`, `MAE = 1.10`)가 `oar1/2/3` 순환을 덮어쓰고 `/shorts` 선반(`405×608` `2:3` 크롭, `y = 150..1770`, `MAE = 3.34`)에 100% 고정 노출**되고 있습니다.
> 3. **현행 [`pipeline/thumbnail_studio.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py) (`R65 v4`) 코드 감사 결과 (총 5건의 실측 결함 적발)**:
>    - **결함 1 (기하학 크롭 잘림)**: [`L1963-L1965`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L1963-L1965)에서 `TQ4` 상단 안전영역 `safe_y_lo`를 `150px`에서 `20px`로 완화해, 유튜브 쇼츠 선반 `2:3` 크롭(`y = 150..1770`) 시 `Ep #4` 상단 라벨(`y = 77..188`)의 **`65.8%`**와 `Ep #5` 상단 라벨(`y = 91..174`)의 **`71.1%`**가 잘려 나갑니다.
>    - **결함 2 (프롬프트 빌더 스키마 키 불일치 버그)**: `Ep #4` · `Ep #5`의 [`visual_plan.json`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep04_patient_sm_fearless_amygdala/03_visuals/visual_plan.json#L33-L46)은 `thumbnail_profile`, `top_human_action`, `bottom_human_action`, `target_anatomy` 키를 정의하고 있으나, [`build_r65_v4_in_skull_split_prompt()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L801-L803)는 `profile`, `top_trigger_scene`, `bottom_trigger_scene`만 읽도록 코딩되어 있어 **실제 실행 시 독사·호흡마스크·깃털·로봇팔 등 에피소드 핵심 묘사가 100% 증발하고 제네릭 문구로 폴백**됩니다.
>    - **결함 3 (`Variant B·C` 반쪽 라벨 버그)**: [`L1623-L1625`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L1623-L1625)에서 폴백 프레임일 때 하단 라벨을 생략하고 상단 라벨(`NO FEAR`, `BY MYSELF`)만 `y = 56..162`(`2:3` 크롭 시 **`88.7%` 잘림**)에 단독 스탬핑합니다.
>    - **결함 4 (키아트 정규화 점수 `0.5` 붕괴 버그)**: [`_load_cached_keyart_candidates()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L1018)가 단일 키아트(`keyart_01.png`)에 대해 단독으로 `_finalize_candidate_scores()`를 호출해 `normalized_scores` 4개 축이 전부 `0.5`로 붕괴된 채 본편 후보군과 합산([`L2425`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L2425))됩니다.
>    - **결함 5 (`16:9` 롱폼 렌더러 미연동 및 `@심리학고양이` 다크 보이드 아키타입 부재)**: [`render_longform_4k_thumbnails()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L2589-L2794)는 여전히 구형 `v7` 단문 1측면 배치에 머물러 있으며, 쇼츠 역시 `THUMB_V4_MIN_MEAN_LUMA = 105.0`으로 밝은 배경만 강제해 `@심리학고양이`의 최고 클릭 무기인 **`#000000` 칠흑 보이드(`Luma Std >= 80`)** 와 `v8` 2.5D 캐릭터 연극성을 활용할 수 없습니다.

---

## 1. 채널 특정 및 전수·표본 데이터셋 요약 (`신비한 건축사전` & `@심리학고양이`)

### 1.1 두 레퍼런스 채널 전수 스펙 비교

| 비교 항목 | 채널 A: `신비한 건축사전` | 채널 B: `@심리학고양이` (`심리학 고양이`) | 전략적 시사점 (`ALL ABOUT BRAIN` 대비) |
|---|---|---|---|
| **공식 핸들 / 채널 ID** | `@신비한_건축사전_1` / `UCeEM8XgdgUyaWE1Z6_5sHbQ` | `@심리학고양이` / `UCaJkv4faBajjsDGq2YPJN0A` | 두 채널 모두 한국어 기반이나 시각 문법은 언어 무관 직관형 |
| **구독자 규모** | **825,000명** | **404,000명** | 단기간 고밀도 시각 브랜딩으로 대형 팬덤 구축 |
| **주력 포맷 비중** | **쇼츠 `9:16` (`500편`, 조회수 비중 `90.3%`)** + **롱폼 `16:9` (`101편`, `9.7%`)** 병행 | **100% 롱폼 `16:9`** (일반 공개 **`156편`** + 멤버십 전용 `22~34편` = 총 `190편`) — **`/shorts` 탭 `0편`** | `신비한 건축사전`은 쇼츠→롱폼 투트랙, `@심리학고양이`는 순수 브라우즈(홈 피드) CTR 특화 |
| **누적 조회수 (수집 표본)** | 합산 **386,582,578회** (쇼츠 `349,136,900` + 롱폼 `37,445,678`) | **42,391,257회** (일반 공개 롱폼 `156편` 합산) | 쇼츠 확산력(`신비한 건축사전`) + 홈 화면 클릭 유도력(`@심리학고양이`) |
| **평균 / 중앙값 조회수** | • **쇼츠(`n=500`)**: 평균 **698,273회** / 중앙값 **473,000회**<br>• **롱폼(`n=101`)**: 평균 **370,749회** / 중앙값 **164,000회** | • **공개 롱폼(`n=156`)**: 평균 **271,738회** / 중앙값 **90,000회** | `신비한 건축사전` 쇼츠는 중앙값 자체가 47.3만 뷰에 달하는 초고타율 |
| **최고 조회수 / 100만 뷰 타율** | • **쇼츠**: 최고 **6,519,767회** / 100만+ **99편 (`19.8%`)**<br>• **롱폼**: 최고 **4,166,406회** / 100만+ **6편 (`5.9%`)** | • **공개 롱폼**: 최고 **5,050,291회** / 100만+ **9편 (`5.8%`)** | 쇼츠 5편 중 1편이 100만 뷰 돌파 (`91~179초` 중장편 쇼츠) |
| **영상 길이 분포** | • **쇼츠**: 상위 10편 기준 **`91~179초` (평균 `124.7초`)**<br>• **롱폼**: 평균 **`350.0초` (`5분 50초`)**, 중앙값 `341.0초` (`182~683초`) | • **공개 롱폼**: 평균 **`514.4초` (`8분 34초`)**, 중앙값 `481.5초` (`140~4,788초`) | 우리 채널 `v8` 쇼츠(`62~118초`, 상한 `120.0초`)와 `신비한 건축사전` 쇼츠(`91~179초`)가 동일한 중장편 스토리텔링 체급이며 동일한 Google Veo/Flow 계열 AI 엔진 사용 |

---

### 1.2 수집 완료된 상위 히트작 썸네일 갤러리 (총 33종)

아티팩트 미디어 디렉터리([`thumb_benchmark_media/`](./thumb_benchmark_media))에 원본 33종([`arch_dict/`](./thumb_benchmark_media/arch_dict) 20종, [`psych_cat/`](./thumb_benchmark_media/psych_cat) 13종) 및 비교 그리드 5종이 저장되어 있습니다.

````carousel
![채널 A: 신비한 건축사전 롱폼 Top 8 (16:9) — 3D 아이소메트릭 절개 단면도 + 레드/시안 포인터 + 대각선 Z-패턴 2청크 카피](../01_YouTube_CEO/thumb_benchmark_media/arch_dict_top_grid.jpg)
<!-- slide -->
![채널 A: 신비한 건축사전 쇼츠 Top 8 (9:16, 397만~652만 뷰) — 노란색 박스가 실제 유튜브 쇼츠 선반 2:3 크롭(405x608, y=150..1770) 노출 영역](../01_YouTube_CEO/thumb_benchmark_media/arch_dict_shorts_top_grid.jpg)
<!-- slide -->
![채널 B: @심리학고양이 역대 Top 10 + 최신작 — 60~82% #000000 칠흑 블랙 보이드 + 단일 역설 오브제/1:1 뇌 스캔 + 하단 초거대 2어절 카피](../01_YouTube_CEO/thumb_benchmark_media/psych_cat_full12_grid.jpg)
<!-- slide -->
![쇼츠 썸네일 기술 포렌식 대조 — 신비한 건축사전(본편 중간 프레임 oar2, MAE=4.69) vs ALL ABOUT BRAIN(커스텀 업로드 sardefault 실제 작동 입증, MAE=1.10)](../01_YouTube_CEO/thumb_benchmark_media/shorts_forensic_comparison.jpg)
````

#### (1) `신비한 건축사전` 롱폼 (`16:9`) 조회수 Top 10 실측 목록
| 순위 | Video ID | 조회수 | 길이 | 업로드일 | 영상 제목 | 썸네일 카피 (좌상단 ↘ 우하단) | 핵심 시각 장치 (3D 단면 + 포인터) | 원본 파일 |
|---:|---|---:|---:|---|---|---|---|---|
| **1** | `ws1Clj0vOAM` | **4,166,406** | `399s` | `2026-08-11` | 아파트 30층 높이 쓰레기 산, 서울은 결국 치우지 못했습니다 | `30층 높이` ↘ `쓰레기 산` | 하늘공원 직육면체 케이크 지층 절개 단면 (억새밭 아래 쓰레기 적층 노출) | [`long_01_ws1Clj0vOAM.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_01_ws1Clj0vOAM.jpg) |
| **2** | `YoEcE0bx4nU` | **2,193,847** | `316s` | `2026-10-24` | JYP가 755억 땅을 사 놓고 사옥을 못 짓는 이유 | `공원이 사라진 순간` ↘ `755억 사옥 포기` | `50:50` 좌우 분할 비교 + 초록 `✓` (일조권 통과) vs 빨간 `✕` (아파트 그림자 레이저 침범) | [`long_02_YoEcE0bx4nU.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_02_YoEcE0bx4nU.jpg) |
| **3** | `hIrHtuowVpA` | **1,344,799** | `338s` | `2026-09-15` | 폐버스는 왜 집이 될 수 없을까 — 8평 넓이가 집이 못 되는 공학적 이유 | `폭 2.5m 한계` ↘ `거주 불가` | 어두운 스튜디오 속 폐버스 3D 반투명 X-ray 투시 + `#FF2525` 빨간 치수선(`2.5m`, `1.9m`) | [`long_03_hIrHtuowVpA.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_03_hIrHtuowVpA.jpg) |
| **4** | `HWKCzhznydQ` | **1,182,217** | `350s` | `2026-09-08` | 경복궁 경회루 연못, 600년 전 왜 물을 빼지 않고 가둬버렸을까 | `600년 전` ↘ `물을 가둔 이유` | 경회루 건물 절반 + 연못 수중 돌기둥·바닥 지층 3D 아쿠아 단면 절개 | [`long_04_HWKCzhznydQ.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_04_HWKCzhznydQ.jpg) |
| **5** | `m6GgxUdlEMo` | **1,061,857** | `683s` | `2026-08-12` | 한강이 겨울에도 안 마르는 진짜 이유, 물속에 있습니다 | `왜 안 마를까?` ↘ `물속의 비밀` | 한강 수중보(잠실수중보) 전후 수위 낙차 3D 수중 단면도 | [`long_05_m6GgxUdlEMo.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_05_m6GgxUdlEMo.jpg) |
| **6** | `G8eMsslphAM` | **1,025,527** | `296s` | `2026-08-16` | 석촌호수는 지금도 새고 있습니다 — 매일 2천 톤 | `바닥이` ↘ `새는 그릇` | 롯데월드 석촌호수 지하 단면 절개 + `#00D4FF` 네온 시안 누수 물줄기 균열 | [`long_06_G8eMsslphAM.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_06_G8eMsslphAM.jpg) |
| **7** | `4YKa2ykMOY4` | **996,804** | `324s` | `2026-09-13` | 서울시가 깐 '비 마시는 보도블록', 6개월 만에 전부 막힌 이유 | `시공 직후` / `6개월 후` ↘ `완전 막힘` | `50:50` 좌우 단면 대조 (시안 물줄기 통과 vs 진흙 공극 막힘) | [`long_07_4YKa2ykMOY4.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_07_4YKa2ykMOY4.jpg) |
| **8** | `IdytVoYCVMs` | **996,089** | `343s` | `2026-10-25` | 잠실 주경기장이 6만 석 중에 1만 8천 석만 여는 이유 | `6만 석인데` ↘ `18,000석만 오픈` | 경기장 조감도 위 빨간 `✕` (`60,000` 폐쇄 구역) vs 민트 하이라이트(`18,000`) | [`long_08_IdytVoYCVMs.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_08_IdytVoYCVMs.jpg) |
| **9** | `zjQhx8zj7oE` | **981,650** | `321s` | `2026-10-31` | 잠실 야구장 자리에 호텔을 붙이는 진짜 이유 | `야구장 옆에` ↘ `호텔 짓는 이유` | 돔구장 + 결합형 호텔 3D 매스 조감도 & 시야선 | [`long_09_zjQhx8zj7oE.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_09_zjQhx8zj7oE.jpg) |
| **10** | `PsCEMjEi3-A` | **943,465** | `379s` | `2026-09-14` | 하루 498만 톤의 시커먼 물, 서울은 이걸 안 거릅니다 | `안 거르고` ↘ `미생물에 맡김` | 지하 하수처리장 수조 3D 단면도 | [`long_10_PsCEMjEi3-A.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/long_10_PsCEMjEi3-A.jpg) |

#### (2) `신비한 건축사전` 쇼츠 (`9:16`) 조회수 Top 10 실측 목록
| 순위 | Video ID | 조회수 | 길이 | 업로드일 | 쇼츠 제목 | 수집 시점 엔드포인트 (`oar1/2/3` 순환) | 인비디오 프레임 시각 구성 (번인 자막 + 3D 포인터) | 원본 파일 |
|---:|---|---:|---:|---|---|---|---|---|
| **1** | `uUN1Bw0elY8` | **6,519,767** | `97s` | `2026-07-30` | 한강이 강이 아니라 호수인 이유 | `oar2.jpg` (`t=56.20s`, `58.3%`) | 강을 가로막은 **새빨간 3D 수중보 하이라이트** + 중앙 번인 자막 `"되지 않냐고요?"` | [`short_01_uUN1Bw0elY8.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_01_uUN1Bw0elY8.jpg) |
| **2** | `YOXXmgy-02s` | **5,980,110** | `94s` | `2026-07-29` | 서울 한복판 억새밭, 사실은 쓰레기 9200만 톤 위에 떠 있습니다 | `oar2.jpg` (`t=40.60s`, `43.3%`) | 갈라진 땅 틈새로 치솟는 **메탄가스 화염 클로즈업** + 중앙 자막 `"불이 붙었습니다."` | [`short_02_YOXXmgy-02s.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_02_YOXXmgy-02s.jpg) |
| **3** | `t2Dgbt8NIns` | **5,269,600** | `116s` | `2026-08-03` | 산꼭대기인데 우물이 80개, 남한산성 물은 어디서 왔을까 | `oar3.jpg` | 산 전체를 케이크처럼 잘라낸 **3D 지형 절개 단면 + 시안 수맥 + 빨간 표고 스탬프** + 자막 `"성 안에 모인 물은"` | [`short_03_t2Dgbt8NIns.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_03_t2Dgbt8NIns.jpg) |
| **4** | `geJgA80UK60` | **4,289,582** | `160s` | `2026-08-29` | 네팔 홍수 현장에 걸린 그 둑, 중국은 18년 전에 사람 손으로 먼저 터뜨렸습니다 | `oar2.jpg` ↔ `oar1.jpg` *(순환 확인)* | 협곡 수면 위로 쏟아지는 **다중 3D 입체 빨간 화살표 군집** + 중앙 자막 `"그 자리는 절벽 사이라"` | [`short_04_geJgA80UK60.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_04_geJgA80UK60.jpg) |
| **5** | `qn3GA6ZmLyI` | **4,185,280** | `134s` | `2026-08-08` | 바닥을 아무리 두껍게 해도 아파트 층간소음이 안 잡히는 진짜 이유 | `oar2.jpg` | 아파트 거실 바닥 콘크리트 슬래브 **3D 단면 절개 + 쇠공 추락 + 붉은 레이저/치수선(`30cm`)** + 자막 `"쿵"` | [`short_05_qn3GA6ZmLyI.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_05_qn3GA6ZmLyI.jpg) |
| **6** | `ostLZ4fcWmk` | **4,150,120** | `179s` | `2026-08-24` | 서울 한강은 올림픽 때문에 4년 만에 뚝딱 만든 강입니다 | `oar2.jpg` | 수로 위를 전진하는 **거대 3D 입체 빨간 화살표 행렬** + 자막 `"서해 썰물 때"` | [`short_06_ostLZ4fcWmk.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_06_ostLZ4fcWmk.jpg) |
| **7** | `X8dWzt0bEHw` | **4,139,265** | `121s` | `2026-08-04` | 강화도는 원래 섬 하나가 아니었습니다, 사람이 붙인 겁니다 | `oar2.jpg` | 상단 거대 2글자 헤드라인 **`"곡선"`** + 갯벌 위 **휘어진 3D 입체 빨간 화살표** + 자막 `"슬쩍 미끄러지게끔."` | [`short_07_X8dWzt0bEHw.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_07_X8dWzt0bEHw.jpg) |
| **8** | `Ht6FCXabKYM` | **3,965,960** | `91s` | `2026-07-29` | 경복궁 마당은 평평해 보이지만 사실 평평하지 않습니다 | `oar3.jpg` | 궁궐과 마당 지반을 비스듬히 자른 **3D 경사 단면도 + 빨간 높이 치수 태그(`38.42cm`, `14cm`)** | [`short_08_Ht6FCXabKYM.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_08_Ht6FCXabKYM.jpg) |
| **9** | `7FfGUSUArn8` | **3,919,417** | `92s` | `2026-07-29` | 비만 오면 사라지던 모래벌판을 110일 만에 도시로 만든 방법 | `oar3.jpg` | 여의도 윤중제 제방 3D 단면도 | [`short_09_7FfGUSUArn8.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_09_7FfGUSUArn8.jpg) |
| **10** | `yHgZqcaGmws` | **3,908,219** | `123s` | `2026-08-09` | 해운대 백사장을 붙잡고 있는 물속의 둑 | `oar2.jpg` | 해운대 바닷속 수중 방파제 3D 단면 + 파도 화살표 | [`short_10_yHgZqcaGmws.jpg`](../01_YouTube_CEO/thumb_benchmark_media/arch_dict/short_10_yHgZqcaGmws.jpg) |

#### (3) `@심리학고양이` 롱폼 (`16:9`) 역대 Top 10 + 최신작 실측 목록
| 구분 | Video ID | 조회수 | 길이 | 업로드일 | 영상 제목 | 썸네일 카피 | 핵심 시각 문법 (칠흑 보이드 + 역설 오브제/아카이브) | 원본 파일 |
|---:|---|---:|---:|---|---|---|---|---|
| **Top 1** | `aRiFY2Nm9Ng` | **5,050,291** | `493s` | `2024-01-01` | 당신이 사실 2명인 이유 (feat. 노벨상) | **`(무문자 0자)`** | 실제 분리뇌(Split-Brain) 환자 양손 동시 그림 실험 아카이브 사진 + 좌우 블랙 마스킹 | [`top_01_aRiFY2Nm9Ng.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_01_aRiFY2Nm9Ng.jpg) |
| **Top 2** | `X71gvsqMk4k` | **2,458,770** | `482s` | `2026-02-05` | 손해보며 살아야 하는 이유 | **`손해의 역설`** (하단 전폭 백색) | `#000000` 칠흑 배경(`61.1%`) + **반으로 찢어진 5만원권 지폐 1장** | [`top_02_X71gvsqMk4k.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_02_X71gvsqMk4k.jpg) |
| **Top 3** | `1Y1UTkjMG00` | **2,451,595** | `579s` | `2026-10-29` | 빨리 자려고 할수록 손해보는 이유 | **`수면의 역설`** (하단 전폭 백색) | `#000000` 칠흑 배경(`68.9%`) + **좌우 1:1 쌍둥이 아날로그 시계 (빨간 20분 vs 파란 5분)** | [`top_03_1Y1UTkjMG00.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_03_1Y1UTkjMG00.jpg) |
| **Top 4** | `6skfikfyY_M` | **2,184,840** | `480s` | `2026-10-15` | 당신이 생각보다 호감인 이유 | **`호감의 역설`** (하단 전폭 백색) | `#000000` 칠흑 배경(`68.8%`) + **구겨진 흰 종이 한가운데 그려진 빨간 하트** | [`top_04_6skfikfyY_M.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_04_6skfikfyY_M.jpg) |
| **Top 5** | `mDPZwjqlsmk` | **2,008,611** | `539s` | `2023-11-27` | 하버드대 뇌과학자의 깨달음 | **`(무문자 0자)`** | TED 강연장에서 **실제 인간 뇌 표본을 두 손에 든 질 볼트 테일러 박사** 클로즈업 (`Dark 69.0%`) | [`top_05_mDPZwjqlsmk.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_05_mDPZwjqlsmk.jpg) |
| **Top 6** | `q7txH0EJW-M` | **1,380,756** | `489s` | `2025-04-17` | (실화) 1분마다 새로 태어나는 남자 | **`(실제 일기)`** | 선행성 기억상실증 환자 클라이브 웨어링의 **수십 줄 취소선 일기장 원본 스캔** | [`top_06_q7txH0EJW-M.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_06_q7txH0EJW-M.jpg) |
| **Top 7** | `_XJy5FqDrTs` | **1,354,336** | `575s` | `2026-01-29` | 99%가 인생을 낭비하는 이유 | **`익숙한 지옥`** (하단 전폭 백색) | `#000000` 어두운 배경(`68.8%`) + 바위를 밀어 올리는 시지프스 고전 회화 누끼 | [`top_07__XJy5FqDrTs.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_07__XJy5FqDrTs.jpg) |
| **Top 8** | `Lv3QwcAcDnA` | **1,333,406** | `490s` | `2025-03-27` | 하버드대에서 밝힌 「삶에 여유가 없을수록 꼭 해야하는 1가지」 | `노력할수록 실패하는 이유` / **`결핍의 역설`** (적색) | `#000000` 칠흑 배경(`82.1%`) + **고개 숙인 순백색 인간 실루엣** + 좌우 독백 소문자 | [`top_08_Lv3QwcAcDnA.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_08_Lv3QwcAcDnA.jpg) |
| **Top 9** | `YkNReIcwlaI` | **1,245,169** | `903s` | `2025-01-13` | 삶이라는 게임에서 승리하는 법 | **`전부 틀렸습니다`** | 어두운 서재(`79.8%`) + 정면 응시 연구자 + 양옆 양자택일 질문(`성공에 집착?` vs `욕망에 초연?`) | [`top_09_YkNReIcwlaI.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_09_YkNReIcwlaI.jpg) |
| **Top 10** | `rojH_j1MgBI` | **1,062,151** | `547s` | `2026-02-12` | 숏폼 중독이 무서운 진짜 이유 | `학계의 정설` vs `실제 모습` / **`숏폼의 배신`** | `#000000` 칠흑 배경(`67.5%`) + **좌우 1:1 뇌 PET 스캔 히트맵 비교** (`Colorfulness 76.9`) | [`top_10_rojH_j1MgBI.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/top_10_rojH_j1MgBI.jpg) |
| **Recent 1** | `OFOul1qwy5E` | `61,304` | `3063s` | `2026-11-05` | 평생 눈치따위 보지 않은 남자 | `모두가 미워한 남자` / **`프로이트`** (적색) | `#000000` 칠흑 배경(`67.1%`) + 흑백 프로이트 초상 위 노란 물감 흘러내림 | [`recent_01_OFOul1qwy5E.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/recent_01_OFOul1qwy5E.jpg) |
| **Recent 2** | `-vqfqeix_IE` | `317,550` | `677s` | `2026-10-22` | 화를 참지도 터뜨리지도 않는 법 | **`분노의 역설`** (하단 전폭 백색) | `#000000` 칠흑 배경(`76.7%`) + **수증기를 뿜는 새빨간 유리 주전자 1개** (`Luma Std 85.0`) | [`recent_02_-vqfqeix_IE.jpg`](../01_YouTube_CEO/thumb_benchmark_media/psych_cat/recent_02_-vqfqeix_IE.jpg) |

---

## 2. 유튜브 쇼츠 기술적 구현 방식 포렌식 판별 (픽셀 단위 전수 대조)

### 2.1 엔드포인트 쿼리 및 본편 H.264 MP4 전 프레임(`oar1/2/3` vs `sardefault`) 실측 결과표

| 검증 대상 영상 | `sardefault.jpg` (커스텀 업로드 슬롯) | `/shorts` 탭 노출 엔드포인트 | `oar1.jpg` 매칭 프레임 (초반 `~17%`) | `oar2.jpg` 매칭 프레임 (중반 `~50%`) | `oar3.jpg` 매칭 프레임 (후반 `~80%`) | 최종 판정 |
|---|---|---|---|---|---|---|
| **`신비한 건축사전` 쇼츠 1위**<br>`uUN1Bw0elY8` (`652만 뷰`, `96.43s`, `2,893f`) | **`HTTP 404 Not Found`** (커스텀 파일 없음; `0.0s` 첫 컷 `MAE=38.22` 불일치) | `oar2.jpg` (세션에 따라 `oar1/2/3` 동적 순환) | **Frame `#486`** (`t = 16.20s`, **`16.8%`** 지점, `MAE = 7.78`) | **Frame `#1686`** (`t = 56.20s`, **`58.3%`** 지점, `MAE = 4.69`) | **Frame `#2536`** (`t = 84.53s`, **`87.7%`** 지점, `MAE = 7.00`) | **(A) + (D)**: 커스텀 업로드 및 0.1초 번인 없이 **본편 `16.8%` / `58.3%` / `87.7%` 3개 시점의 3D 단면·포인터 컷이 `oar1/2/3`로 순환 노출** |
| **`신비한 건축사전` 쇼츠 2위**<br>`YOXXmgy-02s` (`598만 뷰`, `93.70s`, `2,811f`) | **`HTTP 404 Not Found`** (커스텀 파일 없음; `0.0s` 첫 컷 `MAE=42.13` 불일치) | `oar2.jpg` (세션에 따라 `oar1/2/3` 동적 순환) | **Frame `#524`** (`t = 17.47s`, **`18.6%`** 지점, `MAE = 8.72`) | **Frame `#1218`** (`t = 40.60s`, **`43.3%`** 지점, `MAE = 13.29`) | **Frame `#2018`** (`t = 67.27s`, **`71.8%`** 지점, `MAE = 7.03`) | **(A) + (D)**: 본편 `18.6%` / `43.3%` / `71.8%` 컷이 `oar1/2/3`로 생성되며 500편 전체에서 `1:1:1` 비율(`159:162:161`)로 순환 노출 |
| **`ALL ABOUT BRAIN` (`v8`)**<br>`soUNqH7UyKw` (`Marshmallow`, `120.0s`) | **`HTTP 200 OK`** (`318,272 B`, `1080×1920`, `thumbnail_var_A.png`와 **`MAE = 1.10`**) | **`.../vi/soUNqH7UyKw/sardefault.jpg`** (`405×720` 및 `405×608` 크롭, `MAE = 3.34`) | 별도 생성되나 `/shorts` 선반에서는 `sardefault.jpg`가 우선 노출됨 | `oar2.jpg` (`140,199 B`) 존재하나 `sardefault.jpg`에 의해 오버라이드됨 | `oar3.jpg` 오버라이드됨 | **[`uploader.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py#L1689-L1695)가 주입한 전용 커스텀 PNG(`sardefault.jpg`)가 실제 라이브 쇼츠 선반 5편 전수에서 100% 고정 노출 중!** |

### 2.2 기술 포렌식 3대 핵심 인사이트
1. **커스텀 썸네일 미지정 시 유튜브 쇼츠 선반의 `oar1` · `oar2` · `oar3` 동적 순환 메커니즘 규명**:
   - `신비한 건축사전` 쇼츠 500편 전수 조사 결과, `sardefault.jpg`는 단 1편도 없으며 `oar1.jpg`(`159편`, `31.8%`), `oar2.jpg`(`162편`, `32.4%`), `oar3.jpg`(`161편`, `32.2%`), `hq720_1~3.jpg`(`18편`, `3.6%`)로 정확히 3등분되어 있고, 1분 간격 재조회 시 `31.7%`(`95/300편`)의 쇼츠가 다른 `oar` 슬롯을 반환했습니다.
   - 즉, `신비한 건축사전`은 `(B) 0.1초 커버 프레임 번인`이나 `(C) 모바일 앱 텍스트 도구`를 쓰지 않고, **본편의 모든 설명 컷(`~17%` 초반, `~50%` 중반, `~80%` 후반 포함)을 3D 절개 단면도 + `#FF2525` 입체 빨간 화살표/치수선 + 중앙 1줄 자막으로 제작하여 `oar1/2/3` 중 무엇이 노출되든 완성된 인포그래픽 썸네일이 되도록 설계**했습니다.
2. **우리 채널(`@AllAboutBrainOfficial`)의 기술적 우위 (`sardefault.jpg` 커스텀 락 + 본편 인포그래픽 이중 잠금)**:
   - [`pipeline/studio/uploader.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py#L1689-L1695)는 `ytcp-thumbnails-compact-editor-uploader input[type='file']`에 `06_publish/thumbnail_var_A.png`를 직접 주입하여, 공개된 5편 전수(`soUNqH7UyKw`, `jySZ6EL3aYM`, `u5mQNZWNjiw`, `31_O2CmlKOk`, `p4ou90cHt50`)에서 **`sardefault.jpg`가 `oar1/2/3` 순환을 덮어쓰고 대표 썸네일로 고정 서비스**되고 있습니다.
   - 따라서 우리는 **① 쇼츠 선반(`sardefault.jpg`)에는 Google Flow `0-credit` 이미지 엔진(`x4` 배치)으로 뽑은 '전용 초고클릭 키아트'를 고정 노출**하고, 동시에 **② 본편의 `~17%` · `~50%` · `~80%` 구간(`R70` 데이터 스탬프 및 `R71` 유리 뇌 + `#FF2525` 포인터 컷)도 고밀도 단면도로 유지해 인라인 자동재생(Inline Preview) 및 `oar1/2/3` 노출까지 이중 장악**할 수 있습니다.
3. **유튜브 쇼츠 선반의 픽셀 단위 크롭 기하학 (`405×608` = `2:3` 중앙 크롭)**:
   - `soUNqH7UyKw`의 실제 쇼츠 선반 이미지(`405×608`)와 `sardefault.jpg`(`1080×1920` → `405×720` 축소본)를 전 구간 슬라이딩 대조한 결과, **`y0 = 56..664` (`1080×1920` 기준 정확히 `y = 149.3..1770.7`, `MAE = 3.337`)** 구간만 잘라내어 노출하며, 하단 `y = 1520..1770` 위에는 흰색 영상 제목과 조회수를 덮어씁니다.
   - 결론적으로 **쇼츠 썸네일의 모든 텍스트와 핵심 피사체(얼굴·두개골 뇌 단면)는 반드시 `y = 165..1480` 안전영역 안에 배치되어야 합니다.**

---

## 3. 시각 문법 5축 정량·정성 비교 해부 (`OpenCV` 실측)

### 3.1 OpenCV 7대 정량 지표 실측 비교표 (`33종` + 우리 채널 `v8` 변천사)

| 비교 그룹 (`n`) | 평균 밝기 (`Mean Luma`) | 명도 대비 (`Luma Std`, 높을수록 입체·선명) | 채도 평균 (`HSV Sat`) | 색채 풍부도 (`Colorfulness`) | 어두운 배경 비율 (`Luma < 55`) | 밝은 하이라이트 (`Luma > 200`) | 고채도 포인트 (`Accent Pop %`) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`신비한 건축사전` 롱폼 Top 10 (`16:9`)** | `117.7` | **`69.8`** | `58.7` | `30.3` | `24.1%` | **`19.7%`** | `2.0%` (`#FF2525` / `#00D4FF`) |
| **`신비한 건축사전` 쇼츠 Top 10 (`9:16` `oar1/2/3`)** | `119.9` | `42.8` | `50.8` | `34.5` | `7.0%` | `3.2%` | **`3.0%`** (3D 빨간 화살표/수중보) |
| **`@심리학고양이` 역대 Top 10 (`16:9`)** | `76.8` *(블랙 보이드 8편은 `55.0`)* | **`80.5` (최고!)** *(최고 `104.6`)* | `67.2` | `29.4` *(뇌 PET 편 `76.9`)* | **`60.4%`** *(블랙 보이드 8편은 **`70.8%`**)* | **`18.5%`** | **`3.1%`** *(뇌 PET 편 `14.9%`)* |
| **`@심리학고양이` 2026 최신 블랙 보이드 (`OFO..`, `-vq..`)** | `47.7` | **`77.0`** | `51.4` | **`46.2`** | **`71.9%`** | `8.6%` | **`4.8%`** (빨간 주전자 / 노란 물감) |
| **우리 채널 기존 `Pilot #3` (`Marshmallow` `VAR A`, `R65 v1`)** | `75.2` | **`59.4` (최저)** | `123.8` *(황갈색 과포화)* | `29.0` | `46.1%` *(어두운 갈색 벽)* | **`6.0%` (최저)** | **`1.6%` (포인트 전무)** |
| **우리 채널 `Ep #4 · #5` (`R65 v4` 상하 분할 주광 `VAR A`)** | **`181.8 / 183.0`** | **`72.7 / 62.8`** | — | **`51.0 / 43.1`** | 스튜디오 하이키 주광 | 다량 | **`3.8% / 2.2%`** (적색/시안 뇌 활성) |

---

### 3.2 5축 시각 문법 정성 해부

1. **축 1 — 피사체·구도 (Subject & Composition)**:
   - **`신비한 건축사전`**: 상단 30~40%에는 시청자에게 친숙한 일상 외부(아파트, 한강, 경복궁, 폐버스)를 배치하고, 하단 60~70%를 **직육면체 케이크 단면(Isometric Cutaway) 또는 반투명 X-ray**로 절개해 지하 쓰레기층·누수 균열·층간소음 충격파를 노출합니다. 여기에 **① 3D 입체 빨간 화살표(`#FF2525`), ② 빨간 치수 보조선(`2.5m`, `38.42cm`), ③ 초록 `✓` vs 빨간 `✕` 배지** 중 최소 1개를 꽂아 0.3초 만에 시선을 강제 유도합니다.
   - **`@심리학고양이`**: 배경의 `61~82%`를 **순수 `#000000` 칠흑 보이드**로 지워 배경 노이즈를 0%로 만들고, 중앙에 **모순을 품은 단 1개의 오브제**(찢어진 5만원권, 빨간 20분 vs 파란 5분 쌍둥이 시계, 구겨진 종이 속 빨간 하트, 끓는 빨간 유리 주전자, 좌우 1:1 뇌 PET 스캔 히트맵)만 크게 배치합니다. 실제 학술 아카이브 사진 자체가 강렬한 경우(`분리뇌 환자 실험` 505만 뷰, `실제 뇌 표본을 든 뇌과학자` 201만 뷰)에는 글자를 `0자`로 비우고 원본 사진을 풀프레임으로 씁니다.
2. **축 2 — 색채·조명 대비 (Color & Lighting Contrast)**:
   - **`@심리학고양이` (`Luma Std = 80.5`)**: `#000000` 배경(`Luma = 0`)과 중앙 밝은 피사체·하단 백색 타이포(`Luma > 220`)의 극단적 명암 대비로 모바일 피드에서 칼같이 분리되며, **무채색(흑·백) 90% + 단일 원색 포인트(`#FF2020` 레드 또는 시안/그린) 10%** 원칙을 지킵니다.
   - **`신비한 건축사전` (`Luma Std = 69.8`)**: 밝은 지상 주광(`Luma > 200` `19.7%`)과 어두운 지하/수중 단면(`Luma < 55` `24.1%`)의 상하 대비 위에 **보색인 `#FF2525` 코랄 레드(위험·차단·화살표)와 `#00D4FF` 네온 시안(물줄기·에너지 흐름)** 만 포인터 컬러로 사용합니다.
3. **축 3 — 타이포그래피 및 안전영역 기하학 (Typography & Safe Zone)**:
   - **`신비한 건축사전` (`16:9`)**: 총 `7~11자`(`3~5어절`)를 **좌상단(`X=5~35%, Y=8~22%`, 전제·수치) ↘ 중앙 3D 단면 관통 ↘ 우하단(`X=55~95%, Y=75~90%`, 파국적 결과)** 대각선 Z-패턴 2청크로 배치하며, 박스 없이 순백색 채움 + 두꺼운 검정 외곽선만 씁니다.
   - **`@심리학고양이` (`16:9`)**: **하단 중앙 전폭 1줄(`Y=72~90%`, 가로폭의 `70~85%` 점유)** 에 초극태 순백색(80%) 또는 적색(20%) 고딕으로 **단 2어절(`4~6자`, 평균 `4.9자`: `수면의 역설`, `호감의 역설`, `숏폼의 배신`)** 만 박아 넣습니다.
4. **축 4 — 호기심 격차 (Curiosity Gap — 제목 동어반복 금지)**:
   - 두 채널 모두 **영상 제목의 앞구절을 썸네일에 그대로 반복하지 않습니다(`Zero Title-Prefix Repetition`)**.
   - `신비한 건축사전`은 제목이 *"폐버스는 왜 집이 될 수 없을까"* 일 때 썸네일은 **`폭 2.5m 한계` ↘ `거주 불가`**(구체적 수치 전제 + 단호한 판정)로 역할을 나누고, `@심리학고양이`는 제목이 *"빨리 자려고 할수록 손해보는 이유"* 일 때 썸네일은 **`수면의 역설`**(상식을 뒤집는 2어절 낙인)로 압축합니다.

---

## 4. `ALL ABOUT BRAIN (v8)` 현행 코드(`thumbnail_studio.py`) 5대 실측 결함 및 `R65 v4.1` 이식 설계안

### 4.1 현행 `R65 v4` (`Ep #4` · `Ep #5`) 콘택트 시트 실측 검수

````carousel
![Ep #4 R65 v4 콘택트 시트 — 좌하단 160px 쇼츠 선반 프리뷰(노란 박스 y=150..1770) 상단에서 'NO FEAR'(y=77..188)의 윗부분 65.8%가 잘리고, VAR B/C는 'NO FEAR'만 단독 스탬핑되어 88.7%가 잘림](./thumb_benchmark_media/ep04_thumbnail_contact_sheet.png)
<!-- slide -->
![Ep #5 R65 v4 콘택트 시트 — 좌하단 160px 쇼츠 선반 프리뷰(노란 박스 y=150..1770) 상단에서 'BY MYSELF'(y=91..174)의 윗부분 71.1%가 잘리고, VAR B/C는 'BY MYSELF'만 단독 스탬핑되어 88.7%가 잘림](./thumb_benchmark_media/ep05_thumbnail_contact_sheet.png)
````

### 4.2 코드 레벨에서 적발된 5가지 결함 (`claim → code line → exact fix`)

1. **[결함 1 — 최우선] 쇼츠 선반 `2:3` 상단 크롭(`y = 0..150`)에 의한 상단 라벨 `65.8% ~ 71.1%` 절단**:
   - **원인 코드**: [`pipeline/thumbnail_studio.py#L1963-L1965`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L1963-L1965)에서 `if v4_active: safe_y_lo, safe_y_hi = 20, 1495`로 설정해 `THUMB_SHORTS_SHELF_CROP_Y[0]`(`150`) 가드를 해제했고, [`pipeline/config.py#L2032`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L2032)의 `THUMB_V4_TOP_LABEL_Y_RANGE = (40, 360)` 및 [`L815`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L815) 프롬프트(`"upper-left corner"`)가 상단 텍스트를 `y = 56..188`에 배치시켰습니다.
   - **실측 피해**: [`Ep #4 thumbnail_report.json`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep04_patient_sm_fearless_amygdala/06_publish/thumbnail_report.json#L219-L224)에서 `VAR A` `top_chunk_bbox = [50, 77, 437, 188]`(`111px` 중 `y < 150`인 `73px` = **`65.8%` 절단**), [`Ep #5 thumbnail_report.json`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep05_ucl_tickle_delay_robot/06_publish/thumbnail_report.json#L219-L224)에서 `VAR A` `top_chunk_bbox = [52, 91, 509, 174]`(`83px` 중 `y < 150`인 `59px` = **`71.1%` 절단**).
   - **교정 사양**:
     * [`pipeline/config.py#L2032`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L2032): `THUMB_V4_TOP_LABEL_Y_RANGE = (170, 390)`으로 변경.
     * [`pipeline/thumbnail_studio.py#L1964`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L1964): `safe_y_lo = int(THUMB_SHORTS_SHELF_CROP_Y[0])` (`150`)로 복원하여 `y < 150`에 글자가 찍히면 `TQ4_safe_zone_geometry`가 즉시 `FAIL` 처리하도록 잠금.
     * **2계층 분리 원칙 확립**: Flow 이미지 프롬프트에서는 AI가 `y < 150` 데드존에 글자를 굽지 못하도록 `"clean uncluttered upper-left negative space, zero text"`(`include_baked_labels=False`)를 기본값으로 두고, 상·하단 2~3단어 대조 라벨은 파이썬 `render_r65_v4_in_skull_split_overlay()`가 정확한 픽셀 좌표(`top_y = 180..310`, `bot_y = 995..1160`)에 `AABCondensed-Black`으로 스탬핑하도록 일원화.

2. **[결함 2 — 신규 적발] `visual_plan.json` ↔ `build_r65_v4_in_skull_split_prompt()` 스키마 키 불일치로 인한 에피소드 소품·행동 증발**:
   - **원인 코드**: [`pipeline/thumbnail_studio.py#L747`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L747) 및 [`L801-L803`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L801-L803)은 `spec.get("profile")`, `thumb.get("top_trigger_scene")`, `thumb.get("bottom_trigger_scene")`만 읽습니다. 그러나 `Ep #4`([`visual_plan.json#L34-L43`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep04_patient_sm_fearless_amygdala/03_visuals/visual_plan.json#L34-L43))와 `Ep #5`([`visual_plan.json#L34-L43`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep05_ucl_tickle_delay_robot/03_visuals/visual_plan.json#L34-L43))는 `thumbnail_profile`, `top_human_action`, `bottom_human_action`, `target_anatomy` 키를 사용합니다.
   - **교정 사양**:
     * [`is_r65_v4_spec()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L747): `prof = str(spec.get("profile") or spec.get("thumbnail_profile") or "").strip().lower()`로 양쪽 키 모두 인식.
     * [`build_r65_v4_in_skull_split_prompt()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L801-L803): `top_scene = str(thumb.get("top_trigger_scene") or thumb.get("top_human_action") or ...)` 및 `bot_scene = str(thumb.get("bottom_trigger_scene") or thumb.get("bottom_human_action") or ...)`, `target_anatomy = str(thumb.get("target_anatomy") or "")`를 모두 폴백 체인으로 연결.
     * [`generate_zero_credit_thumb_keyart()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L1041): `if len(cached_cands) >= 1:`로 완화해 검증된 단일 키아트 캐시도 안전하게 보존.

3. **[결함 3] `Variant B · C` 폴백 프레임에 상단 반쪽 라벨(`"NO FEAR"`, `"BY MYSELF"`)만 단독 스탬핑되는 문제**:
   - **원인 코드**: [`pipeline/thumbnail_studio.py#L1623-L1625`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L1623-L1625)에서 `if is_fallback_video_frame:`일 때 `bot_lines`를 버리고 `top_lines`만 `y = 56..162`(`2:3` 크롭 시 `88.7%` 잘림)에 찍습니다.
   - **교정 사양**: 단일 본편 프레임(`is_fallback_video_frame=True`)일 때는 반쪽짜리 `top_split_label`만 찍지 말고, `R65 v2` Z-패턴(`top_left_hook` `y = 224` ↘ `#FF2525` 포인터 ↘ `bottom_right_hook` `y = 1320`) 또는 완결된 역설 훅(`"NO FEAR → 1 BREATH PANIC!"` / `hook_text`)을 `y = 185..340` 안전영역 안에 렌더링하도록 분기합니다.

4. **[결함 4 — 신규 적발] 키아트 후보 단독 정규화로 인한 `normalized_scores = 0.5` 붕괴 버그**:
   - **원인 코드**: [`_generate_zero_credit_thumb_keyart_async()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L967) 및 [`_load_cached_keyart_candidates()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L1018)가 `out_cands`끼리만 `_finalize_candidate_scores()`를 수행한 뒤 [`run()`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py#L2425)에서 `frame_candidates`와 단순 리스트 결합을 수행합니다.
   - **교정 사양**: `candidates = keyart_candidates + frame_candidates` 통합 풀 전체에 대해 `_finalize_candidate_scores(candidates)`를 먼저 실행한 뒤 `keyart_candidates`에 우선순위 부스트(`+0.65`)를 가산하도록 순서를 교정합니다.

5. **[결함 5] `@심리학고양이`식 칠흑 보이드(`#000000`) + `v8` 2.5D 캐릭터/뇌 대조 아키타입 및 `16:9` 롱폼 Z-패턴 지원 (`R65 v4.1` 3-Mode 체계)**:

| 아키타입 ID | 결합 공식 (`신비한 건축사전` × `@심리학고양이`) | 최적 적용 에피소드 유형 | 배경 / 대비 목표 | 타이포 & 포인터 배치 (`1080×1920` 안전영역 `y = 165..1480`) |
|---|---|---|---|---|
| **Mode A (`in_skull_cutaway_split_v4`)**<br>*(기본 주력)* | `신비한 건축사전` `#2/#7` 상하 분할 비교 + 두개골 내부 3D 유리 뇌 단면창 + 3D `#FF2525` 화살표 | 인간 행동 반응의 극적인 전후 반전이 핵심인 실험 (`Ep #4` 독사 vs CO2, `Ep #5` 셀프 vs 로봇 간지럼) | 하이키 스튜디오 (`Mean Luma >= 110`, `Luma Std >= 60`) | • 상단 패널 좌상단(`x=56, y=180..310`): `1~3단어` 전제 (`NO FEAR`, `BY MYSELF`)<br>• 하단 패널 좌상단(`x=56, y=995..1160`): `1~3단어` 반전 (`1 BREATH: PANIC!`, `BY ROBOT!`) + 3D 빨간 화살표 |
| **Mode B (`dark_void_paradox_v4`)**<br>*(`@심리학고양이` 결합형)* | `@심리학고양이` `#000000` 칠흑 보이드(`65%+`) + 본편 `v8` 2.5D 익스프레시브 캐릭터/단일 역설 소품 + 좌우 1:1 `R71` 유리 뇌 스캔 대조 | 심리학 패러독스, 습관/도파민/수면 역설, 1:1 뇌 활성 대조가 핵심인 에피소드 | 칠흑 블랙 보이드 (`Dark px >= 60%`, `Luma Std >= 75`) | • 상단(`y=185..290`): 소형 조건 태그 (`NORMAL` vs `OVERLOAD`)<br>• 중앙(`y=320..1180`): 칠흑 배경 위 발광하는 1:1 유리 뇌/역설 오브제 + `#FF2525` 포인터<br>• 하단(`y=1240..1440`, 제목 영역 `y>=1520` 위): 전폭 초극태 2~3단어 역설 카피 (`THE SLEEP PARADOX`, `WILLPOWER LIE`) |
| **Mode C (`isometric_lab_cutaway_v4`)**<br>*(`신비한 건축사전` 정통형)* | `신비한 건축사전` `#1/#3/#5` 3D 아이소메트릭 실험실·장치 절개 단면도 + `#FF2525` 치수 보조선(`+0.2s DELAY`) + 대각선 Z-패턴 2청크 | BCI 임플란트, 실험실 기구 메커니즘, 신경 신호 전달 속도/회로 차단이 핵심인 에피소드 (`16:9` 롱폼 겸용) | 다크/주광 단면 대비 (`Luma Std >= 65`, `Accent Pop >= 2.5%`) | • 좌상단(`x=68, y=215..360`): 수치/전제 청크 (`#FFFFFF`)<br>• 중앙(`y=420..1180`): 3D 실험장치+두개골 단면 + `#FF2525` 치수선/화살표<br>• 우하단(`x_right=1000, y=1260..1445`): 반전 결론 청크 (`#FFE14A`) |
