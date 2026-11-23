# 📺 `ALL ABOUT BRAIN` 쇼츠 → 롱폼(`16:9`) 전환 흔적 전수 감사 보고서

워크스페이스 전체를 정밀 스캔한 결과, 처음부터 **"쇼츠만 찍고 끝내는 채널이 아니라, 롱폼 깊이로 도시에(Dossier)를 먼저 구축하고 쇼츠로 검증한 뒤 `8~15분` `16:9` 롱폼으로 확장한다"**는 설계가 **2세대에 걸쳐** 코드와 데이터 곳곳에 심어져 있습니다. (단, 아직 실제 렌더링·업로드까지 완료된 `16:9` 롱폼 영상은 **`0건`**입니다.)

---

## 1. 이미 만들어져 있는 쇼츠 → 롱폼 자산 및 코드 흔적 (6가지)

| 구분 | 실제 위치 | 현재 준비 상태 (디스크·코드 실측) |
| :--- | :--- | :--- |
| **① 8~15분 롱폼 원고 & 챕터 설계도 (`R44`)** | `BCI_Shorts_Channel/research_dossiers/<slug>/` (`02_master_story.md`, `07_longform_outline.json`) | 전체 `105개` 주제 중 **`102개(97.1%)` 작성 완료!** 챕터별로 *"기존 쇼츠에서 재사용할 역할(`reuse_shorts_roles`)"*과 *"롱폼용 추가 촬영 컷(`new_shots_needed`)"*까지 이미 쪼개져 있음 (예: 채널 1위 *Sleepless Night*의 원천 [07_longform_outline.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/research_dossiers/glymphatic_sleep_toxins/07_longform_outline.json) — 11분·7챕터 완비) |
| **② 화면비 중립(`Aspect-Neutral`) 프롬프트 엔진** | [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L1093-L1101), [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py#L363-L373) | 장면 묘사에서 세로 전용 단어를 빼고 `aspect="16:9"` 옵션만 주면 `"16:9 horizontal widescreen"` 가로 구도 프롬프트로 자동 변환되도록 설계됨 |
| **③ 쇼츠 클립 재활용 창고 (`R50`) & 지식 허브 (`R50-B`)** | [asset_manifest.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/asset_manifest.py#L266-L315), [knowledge_hub.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/knowledge_hub.py#L184-L190) | 쇼츠 완성 시 클립별 재사용 정책(`reuse_or_regen_16x9` 등)을 [index.jsonl](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/asset_library/index.jsonl)에 기록하고, 명확도 검증(`R64 >= 82점`)을 통과한 프롬프트(`198개`)·3D 뇌 모델(`190개`)·공간(`122개`)을 롱폼 확장용으로 축적 중 |
| **④ 16:9 4K CTV 조립기 & 롱폼 플랜 빌더** | [longform_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_assembler.py#L40-L195), [longform_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_prompt_builder.py#L34-L149) | `main.py longform-assemble` CLI 탑재 완료 (`3840x2160 @ 24fps`, `-14 LUFS`, 4K 썸네일 `A/B/C` 생성 골격 구현) |
| **⑤ 쇼츠 `Related video` → 부모 롱폼 자동 직결** | [short_linker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/short_linker.py#L896-L910) | `07_longform_outline.json`에 `published_longform_video_id`만 입력되면, 쇼츠 순환 링보다 우선(`Priority 2`)하여 관련 쇼츠들의 하단 클릭 링크를 해당 롱폼으로 직결하도록 구현 완료 |
| **⑥ 일요일 오전 CTV 편성표 & 72h 썸네일 A/B 테스터** | [us_diorama_timetable.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/us_diorama_timetable.py#L54-L96), [ab_tester.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/ab_tester.py#L233-L265) | 미국 거실 TV 골든타임인 일요일 오전 `09:30 ET` (`SUN_CTV_LONG`) 슬롯과 롱폼 전용 72시간 순차 썸네일 Z-검정기(`R32`) 보유 |

---

## 2. 실제 `8~10분` 고퀄리티 롱폼 제작 전에 꼭 알아야 할 현실 갭 (5가지)

기존 흔적을 냉정하게 뜯어본 결과, **원고·아웃라인(`102개`)과 퍼널은 훌륭하지만 실제 영상 제작부는 아직 '초기 뼈대(프로토타입)' 상태**라 아래 5가지를 연결해야 이번 파일럿 쇼츠급 퀄리티의 롱폼이 나옵니다:

1. **기존 쇼츠 클립 그대로 재활용하기보다 `16:9` 네이티브 신규 생성이 훨씬 유리함**:
   * 에셋 창고에 남아 있는 실존 클립 `1,733개` 중 `1,623개`는 이미 폐기한 구형 `lowpoly_pastel_v7` 클립이고, 현행 하이키 포슬린(`porcelain_cinematic_v7`) 클립은 방금 만든 *Strange Situation* `49개`뿐입니다(1위 쇼츠였던 `psych_06` *Sleepless Night*도 초기 원본 클립 폴더가 정리되어 `0개`임).
   * 게다가 세로(`9:16`) 영상을 거실 TV(`16:9`)에 넣으면 좌우 블러 여백이 생겨 다큐 몰입감이 떨어지므로, **Google Flow `0-credit` 모드에서 처음부터 `16:9` 가로 레퍼런스 + 가로 비디오(`90~110컷`)로 뽑는 것**이 비용(`\$0`)은 같으면서 거실 TV 퀄리티는 압도적입니다.
2. **Flow 비디오 생성 워커의 `9:16` 전용 잠금 해제 필요**:
   * 현재 [flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py#L565-L569)의 CV 검수기(`inspect_diorama_clip_cv`)가 세로가 긴 영상(`h > w`)만 통과시키고 가로 영상(`w > h`)은 불량으로 튕겨내며, [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L1400-L1405) 클립 상한도 `65컷`으로 막혀 있어 `16:9` / `90~110컷` 모드를 열어줘야 합니다.
3. **[longform_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_prompt_builder.py) 고도화 필요**:
   * 현재 빌더는 `20~28컷`(약 3분 분량)만 뽑는 스텁 수준이라, `02_master_story.md` + `07_longform_outline.json`을 바탕으로 `1,300~1,800단어`(`8~11분`) 대본과 `90~110컷` 멀티앵글 플랜을 컴파일하도록 확장해야 합니다.
4. **[longform_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_assembler.py) 방송급 마감 패치**:
   * 첫 프레임(`0초`) 검은 암전 시작 버그 수정, 쇼츠에서 검증된 문장 싱크 동적 EDL·2채널 다큐 BGM 덕킹·챕터 타이틀 카드·차별화된 4K 썸네일 3종(`R65`) 결합이 필요합니다.
5. **스튜디오 업로더 롱폼 파일 인식 연결**:
   * [uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py#L125)가 `final_longform_3840x2160.mp4` 및 4K 썸네일을 자동 인식해 일요일 `09:30 ET` 슬롯에 올리도록 분기만 추가하면 전 과정이 자동화됩니다.
