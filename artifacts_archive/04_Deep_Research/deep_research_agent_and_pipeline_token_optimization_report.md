# `@Deep_Research` 심층 리포트: 에이전트 아키텍처 & 5-Gear 제작 파이프라인 토큰 최적화 마스터 블루프린트

- **작성 주체**: [`@Deep_Research`](conversation://8c666be9-5bad-43d9-b91a-e7ba2b936c62) (Deep Research & Strategy VP)
- **수신 보고 대상**: [`@YouTube_CEO`](conversation://b57c97a8-6324-4c31-a2bb-16b25e28dd55)
- **작업 일시**: `2026-11-21 UTC` (`코드·규칙 직접 수정 0건 · Google Flow 호출 0건 · 브라우저 호출 0건`)

---

## Executive Summary (핵심 실측 요약 & 기대 절감 폭)

우리 `07_Youtube` 워크스페이스와 7-채팅방(`R83 v2`) 실측 감사 결과, **품질 저하 `0%` 조건으로 아래 4대 영역에서 즉각적인 대량 토큰 절감이 가능**하다:

1. **상시 시스템 프롬프트 & 규칙 트리 중복 제거 (`~7,246` tok/turn → `~3,100` tok/turn, `-57%`)**:
   - 현재 매 턴·매 서브에이전트에 **`28,986 B` (`~7,246` tok)**의 `always_on` 규칙(`~/.gemini/config/rules/` 3개 + `AGENTS.md` + `governance_roles.md`)과 **`41`개 스킬 메타데이터**(타 도메인 `apply`, `resume`, `ucl`, `scrape_emails` 등 `20`개 전역 스킬 포함)가 상시 로딩된다.
   - `R83` 7방 거버넌스는 **4개 파일에 `19,958 B`** 분산 중복되어 있고, 취업용 규칙(`job_research_handoff_rule.md`, `2,946 B`)까지 유튜브 방 매 턴에 주입된다.
2. **`.agents/rules/*.md` 세분화 & `AGENTS.md` 매핑 정비 + `production_constants.md` 덤프 제거 (`89,661 B` → `~52,000 B` 총량 축소 · 1회 로딩당 `-65~80%`)**:
   - [`production_constants.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)(`15,185 B`)는 YAML frontmatter가 없고, **파일의 `83.3%`(`12,645 B`)가 값 없이 이름만 나열된 `443`개 심볼 덤프**(나머지 `620`개 상수는 누락)다.
   - `6`개 거대 룰 파일이 전체의 **`60.3%`(`54,059 B`)**를 차지하며, [`AGENTS.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) Section 4 매핑에 **`10`건의 드리프트·누락**과 룰 내부 **수치 모순(`MarginV=521` vs `config.py=510`, 은퇴 앵커 `xray_brain75_master` 재인용 등)**이 확인되었다. `18`개 → **`24`개 마이크로 룰(`1.0–2.8 KB`)**로 세분화하면 필요한 하위 규칙 1개만 정밀 로딩된다.
3. **비전(VLM) 검수 2단계 Coarse-to-Fine + 일회성 샤드 휘발 (`Ep #12` 기준 `69,440–95,976` tok → `~7,200–8,500` tok, `-88~91%`)**:
   - 7개 방 누적 **`807`회 개별 이미지 읽기**(`@Operator` `376` + `@YouTube_CEO` `304` + `@Research` `127`)가 장수 방 컨텍스트와 컴팩팅(`14`회 누적)의 주범이다.
   - Gemini 타일 공식 기반 **`1536x1536` 12-up 시트(`1,032–1,120` tok/시트)** 1차 스크리닝 + 불량 컷만 **`<=384x384` 크롭(`258` tok)** 2차 정밀 검수 + **일회성 `inherit` 비전 샤드 내 완결(`G4` 즉시 종료)**로 전환하면 메인 방 이미지 토큰 잔류가 `0`이 된다.
4. **Python 사전 요약(`--summary` / `slim_out`) + 컴팩트 영수증 핸드오프 (`~100K+` tok 원문 JSON 열람 → `~1.5K` tok, `-95%+`)**:
   - `Ep #12`의 `visual_plan.json`(`139.9 KB`), `flow_all_in_one_prompts.json`(`147.6 KB`), `video_autopsy_report.json`(`98.3 KB`) 등 대용량 JSON 원문 대신 `cli.py` [`cmd_posthoc_qa`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py#L2208-L2223)의 `slim_out` 패턴을 `episode-qa`, `autopsy`, `dossier`에 확대 적용하면 CLI stdout 및 에이전트 컨텍스트 폭증을 차단한다.

---

## 1. 1차 공식 엔지니어링 레퍼런스 핵심 원리 검증 (`HTTP 200` 원문 대조)

| 분야 | 1차 공식 출처 (URL 검증 완료) | 핵심 공학 원리 & 수치 | 우리 시스템 직결 함의 |
|---|---|---|---|
| **Context Engineering & Rot** | Anthropic — [*Effective context engineering for AI agents*](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents) · [*Building effective agents*](https://www.anthropic.com/research/building-effective-agents) | **Context Rot**: 컨텍스트가 길어질수록 모든 모델의 정보 회수율·주의력이 저하됨. 해법은 ① **Progressive Disclosure**(필요 시점 점진 로딩), ② **Compaction**, ③ **Sub-agent Isolation**(탐색·대용량 툴 출력은 서브에이전트가 소화하고 요약만 반환). | 12,142~17,171 스텝짜리 장수 방(`@YouTube_CEO`, `@Operator`)에서 대용량 JSON/이미지를 직접 읽는 행위가 Context Rot의 직접 원인. |
| **3-Level Progressive Disclosure** | Anthropic — [*Equipping agents with Agent Skills*](https://www.anthropic.com/research/equipping-agents-for-the-real-world-with-agent-skills) · [agentskills.io](https://agentskills.io/home) · Antigravity [`agy-customizations/docs/skills.md`](file:///home/canadaofbin/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/skills.md) | **Level 1**: `name`+`description` 메타데이터만 상시 주입. **Level 2**: 해당 작업 시 `SKILL.md` 본문 로딩(권장 간결 유지). **Level 3**: 레거시/상세 참조는 `references/`, 실행기는 `scripts/`로 분리해 조건부 열람. | `youtube-script/SKILL.md`(`12.5 KB`, 52.1%가 `v7`/레거시 혼합)의 `v7`·`Mini-Cortex`·상세 템플릿을 `references/`로 내리면 Level 2 로딩량 절반 이하 축소. |
| **Antigravity 규칙 예산 구조** | Antigravity 내장 스펙 — [`docs/rules.md`](file:///home/canadaofbin/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/rules.md) | 개별 룰 파일 **상한 `24,000 B`**, 전체 `global` + `always_on` 합산 예산 **`20,000` 토큰(`defaultRulesBudget`)** 공유. 초과 시 파일 포인터로 강등됨. `model_decision` 룰은 `description` 매칭 시 온디맨드 로딩. | 현재 상시 로딩은 `~7,246` tok으로 `20,000` tok 예산 안에 있으나, `~4,000` tok 이상이 **타 도메인 규칙 + 4중 중복 거버넌스**로 낭비 중. |
| **Gemini Implicit Caching & 루프 규칙** | Google AI Studio — [*Context caching*](https://aistudio.google.com/docs/caching) | • Gemini 2.5+에서 **Implicit Caching 기본 활성**, 최소 입력 임계치: **Gemini 4 계열(`Carbon/Argon/Neon/Hydrogen`)·3.x `4,096` tok**, Gemini 2.5 `2,048` tok.<br/>• **핵심 루프 규칙 (*Multi-turn and agent loops on Gemini 4*)**: *"새 요청이 **최소 `2,050` 토큰** 이상 추가된 경우에만 직전 요청 전체를 캐시하며, 그보다 작은 증분은 직전 요청의 마지막 `2,050` 토큰을 표준 입력 요율로 재처리한다."*<br/>• 공통 정적 콘텐츠는 반드시 **프롬프트 앞단(prefix)**에 고정. | 1개 툴만 호출하는 짧은 마이크로 턴을 10번 반복하면 매 턴 마지막 `2,050` tok이 캐시 미스 재과금됨 → **병렬 툴 배치(Parallel Tool Batching)** + 정적 프리픽스 불변 유지가 필수. |
| **Gemini 이미지 타일 & 해상도 과금** | Google AI Studio — [*Tokens*](https://aistudio.google.com/docs/tokens) · [*Image understanding*](https://aistudio.google.com/docs/image-understanding) · [*Media resolution*](https://aistudio.google.com/docs/media-resolution) | • **타일 계산**: 가로·세로 모두 **`<= 384 px`이면 단일 `258` 토큰**. 그 이상은 `crop_unit = floor(min(W, H) / 1.5)` / `768x768` 타일로 분할되며 **타일당 `258` 토큰**.<br/>• **Gemini 3/4 `media_resolution`**: `low = 280`, `medium = 560`, **`high` / `unspecified(기본값)` = `1,120`**, `ultra_high = 2,240` tok/이미지. | `1080x1920` 세로 PNG 1장은 `6`타일(`1,548` tok) 또는 기본 `1,120` tok 소모. `<=384x384` 단일 크롭(`258` tok) 또는 `1536x1536` 12-up 시트(`1,032–1,120` tok)와 **`8~12배` 격차**. |
| **멀티에이전트 컨텍스트 격리** | OpenAI Agents SDK — [*Handoffs*](https://openai.github.io/openai-agents-python/handoffs/) · LangChain — [*Context Engineering for Agents*](https://www.langchain.com/blog/context-engineering-for-agents) | **Write / Select / Compress / Isolate** 4대 축. `input_filter` / `nest_handoff_history`처럼 에이전트 경계에서 장황한 중간 스크래치패드·로그를 걸러 **구조화된 최소 계약(Delta Receipt)**만 전달해야 지수적 토큰 폭발을 막음. | 7방 간 `send_message` / `SYSTEM_MESSAGE`가 평균 `1,559–2,781`자(최대 `4,121`자)씩 누적되는 구조를 스키마 영수증(`<=400` tok)으로 압축. |

---

## 2. `07_Youtube` 워크스페이스 7대 토큰 누수원 정밀 실측 감사

### 2.1 실측 현황 총괄표 (모두 직접 파일·로그 계측)

| 누수원 | 실측 규모 (직접 측정 수치) | 구조적 문제 | 추정 토큰 손실 |
|---|---|---|---|
| **① `always_on` 시스템 프롬프트 4중 중복 + 타 프로젝트 오염** | • `~/.gemini/config/rules/` 3개 = `16,771 B` (`~4,192` tok)<br/>  - [`post_compaction_context_recovery_rule.md`](file:///home/canadaofbin/.gemini/config/rules/post_compaction_context_recovery_rule.md) `9,385 B`<br/>  - [`browser_tab_hygiene_rule.md`](file:///home/canadaofbin/.gemini/config/rules/browser_tab_hygiene_rule.md) `4,440 B`<br/>  - [`job_research_handoff_rule.md`](file:///home/canadaofbin/.gemini/config/rules/job_research_handoff_rule.md) `2,946 B`<br/>• [`AGENTS.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) `8,403 B` + [`governance_roles.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/governance_roles.md) `3,812 B`<br/>• 상시 스킬 메타데이터 `41`개 (`global 20` + `builtin 15` + `yt 6`) | • `04_Internship` 취업 규칙(`2,946 B`) + 비유튜브 전역 스킬 `~14`개 설명문이 유튜브 7개 방 및 모든 서브에이전트 매 턴에 상시 주입.<br/>• `R83` 7방 거버넌스가 전역룰(`9,385 B`), `AGENTS.md`(`1,198 B`), `governance_roles.md`(`3,812 B`), `channel_operations_rules.md` L43-62(`5,563 B`) **4곳에 총 `19,958 B` 중복**. | **매 턴 `~3,500–4,200` tok** 순수 중복·오염 상시 과금 |
| **② `.agents/rules/*.md` 거대 복합 파일 & 무가치 덤프** | • `18`개 파일 총 **`89,661 B` (`~22,415` tok)**<br/>• Top 6 거대 파일 = `54,059 B` (`60.3%`): `production_constants.md` (`15,185 B`), `channel_operations_rules.md` (`9,840 B`), `neuro_diorama_pacing_brain_r76_r86.md` (`8,789 B`), `neuro_diorama_v8_world_data_r66_r75.md` (`7,898 B`), `neuro_diorama_core_r56_r65.md` (`6,949 B`), `research_dossier_rules.md` (`5,398 B`) | • [`production_constants.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) L26–30(**`12,645 B`, `83.3%`**)가 값 없이 이름만 나열된 **443개 심볼 덤프** (정작 `config.py` 내 **620개 상수는 누락**, YAML frontmatter도 없음).<br/>• 1개 룰(`R80`/`R81`/`R65` 등)만 확인하려 해도 `1,700–2,500` tok짜리 거대 묶음 파일을 통째로 로딩. | 규칙 조회 1회당 **`~1,200–3,200` tok** 낭비 + 스테일 값으로 인한 재확인 유발 |
| **③ `.agents/skills/*/SKILL.md` 레거시 잔재 & 모순** | • `6`개 스킬 = `34,857 B` (`~8,714` tok)<br/>• [`youtube-script/SKILL.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md) `12,523 B` 중 **`6,519 B` (`52.1%`, 20/57줄)**에 `v7`/`Mini-Cortex` 언급<br/>• [`youtube-produce/SKILL.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-produce/SKILL.md) `6,584 B` 중 **`2,091 B` (`31.8%`)** 레거시/충돌 | • `youtube-script/SKILL.md` L13(`100% narrator, 0 Mini-Cortex`) vs L21·L23(`Hope`/`Laura Mini-Cortex` 지시) **내부 자기모순**.<br/>• `youtube-produce/SKILL.md` L13–14에 은퇴한 `Blender 4.2`·`brain_simulator_3d`·`MarginV=521 64pt`·`eleven_v3 API` 잔존. | 스킬 활성화 1회당 **`~1,600–2,100` tok** 레거시 낭비 |
| **④ 고해상도 개별 이미지 읽기 누적 (`read_file`)** | • 누적 이미지 읽기 **`807`건** (`@Operator` `376`, `@YouTube_CEO` `304`, `@Research` `127`)<br/>• 실측 `Ep #12`: `62`장 `1080x1920` ref PNG (`153.1 MB`) vs `4`장 `1340x1462` `posthoc_viewer_strips` (`1.65 MB`) + `1`장 `1440x520` `dq8` 시트 (`110 KB`) | • `1080x1920` ref 62장 개별 검수 = **`69,440–95,976` tok**.<br/>• 영속 메인 방에서 직접 이미지를 열면 컴팩팅 전까지 매 후속 턴 입력 컨텍스트로 누적 과금. | 편당 VLM **`~60K–88K` tok** 과잉 소모 + 잦은 컴팩팅 유발 |
| **⑤ 장수 채팅방 트랜스크립트 & 아티팩트 목록 팽창** | • 7개 방 합계 **`33,972` 스텝, `71.5 MB`** `transcript.jsonl` (`@Operator` `17,171`스텝/`37.3 MB`/`5`컴팩팅, `@YouTube_CEO` `12,142`스텝/`25.4 MB`/`8`컴팩팅)<br/>• 아티팩트 총 **`811`개** (`@YouTube_CEO` `370` + `80` metadata `36.1 KB`, `@Daily_Report` `229`, `@Operator` `154`)<br/>• 방 간 `SYSTEM_MESSAGE` `2,647`건 (평균 `1,559–2,781`자, 최대 `4,121`자) | • `8,263`개 truncated 스텝 발생(`CEO 2,905 + Operator 4,350`), 복구 시 대용량 `transcript_full.jsonl` 재스캔.<br/>• 완료된 과거 에피소드 아티팩트 370개가 CEO 브레인 디렉터리에 미정리 상태로 잔류. | 턴당 히스토리 유지비 급증 + 컴팩팅 손실·복구 비용 증가 |
| **⑥ `cli.py` 대용량 JSON Stdout 덤프 & Python 오프로딩 누락** | • 실측 `Ep #12` 주요 JSON: `flow_all_in_one_prompts.json` `147.6 KB` (`~36.9K` tok), `visual_plan.json` `139.9 KB` (`~35.0K` tok), `video_autopsy_report.json` `98.3 KB` (`~24.6K` tok), `posthoc_semantic_qa_report.json` `57.6 KB` (`~14.4K` tok), `dynamic_episode_qa_report.json` `31.8 KB` (`~8.0K` tok)<br/>• `cli.py` **66개 서브커맨드** 중 `cmd_posthoc_qa` (`L2208`)만 `slim_out` 적용; `episode-qa`/`autopsy`/`evolve`/`ref-qa`/`dossier`/`kb`는 전체 JSON 출력.<br/>• `research_dossier.py`, `reference_image_qa.py`, `posthoc_semantic_qa.py`에 `--summary`/`--compact`/`--failures-only` CLI 플래그 **`0`건**. | • `episode-qa` 실행 1회당 **`~8,000` tok**, `autopsy` 실행 1회당 **`~24,500` tok**의 원문 JSON이 곧장 에이전트 컨텍스트로 유입됨.<br/>• QA 리뷰 JSON (`25.8–28.7 KB`)을 에이전트가 직접 편집·읽기 시 불필요한 통과 컷 메타까지 반복 처리. | 편당 CLI·JSON 처리 **`~40K–100K` tok** 절감 여지 |
| **⑦ 마이크로 턴 반복에 따른 Gemini 4 캐시 재처리** | • `aistudio.google.com/docs/caching` 공식: 증분 `< 2,050` 토큰이면 직전 **`2,050` 토큰 비캐시 재처리** | • 단일 `read_file` / 단일 `manage_task` / 단일 `grep`을 1턴씩 직렬 실행할 때마다 prefix 끝 `2,050` tok 재과금 + 전체 대화 턴 수 `2~3배` 증가. | 워크플로당 턴 배수 비용 **`+30~50%`** 증가 |

---

### 2.2 `.agents/AGENTS.md` 매핑 정합성 감사표 (전수 발견 `10+`건) & 룰 내 모순

대표님이 직접 지적하신 **"rules 파일 세분화 + `AGENTS.md` 매핑 점검"**에 대한 1:1 감사 결과다.

#### A. [`AGENTS.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) Section 4 (`Complete Rule Index`, L30–L49) 매핑 오류 및 누락
1. **L33 (`R83`)**: `"6-room charter"`로 표기되어 있으나 실제는 **`7`개 채팅방**(`@Deep_Research` 추가) 및 **`R83-8` / `R83-8-V`**(`R83 v2`) 체제.
2. **`production_constants.md` 행 누락**: `.agents/rules/` `18`개 파일 중 유일하게 Section 4 매핑 표에 행이 없고 L4 인라인 링크로만 존재(또한 파일 자체에 `trigger:` frontmatter가 없음).
3. **L37 (`visual_prompt_spec.md`)**: `Dual-Tier Flow (Omni 1.2/1.1 -> Veo Lite)`로 표기 — **스테일**: `config.py:115-121`과 `AGENTS.md` L13 모두 `Omni 1.1` 은퇴·폴백 금지를 선언.
4. **L41 (`R14-A, R46, R47` → `scene_depiction_rules.md`, `cast_depiction_rules.md`)**: **`R46`은 두 파일 어디에도 존재하지 않음**(은퇴 아카이브 전용). 반대로 `cast_depiction_rules.md`는 `R56, R66, R68, R85`를, `scene_depiction_rules.md`는 `R14-A, R47, R68, R86`을 다룸.
5. **L42 (`brain_depiction_rules.md`)**: 실제 본문 소유 규칙인 **`R38, R66, R81, R85, R85-R`**이 Rule IDs 열에서 누락(`R21, R48, R53`만 표기).
6. **L43 (`qa_gates_rules.md`)**: 실제 본문 섹션 2의 **`R62, R64, R85, R85-R, R87`**이 Rule IDs 열에서 누락(`R18-B, R25, R37`만 표기) + 파일 `description:` frontmatter에도 `R85, R87` 누락.
7. **L46 (`reference_depiction_rules.md`)**: 본문 섹션 2–3의 **`R72-R, R85, R87`** (Lock 3 Canonical 100슬롯) 누락.
8. **L47 (`camera_choreography_rules.md`)**: `R68/R70/R71/R73` 행에 잘못 묶여 있으며, 실제 소유 규칙인 **`R77, R82`**가 누락.
9. **L48 (`neuro_diorama_pacing_brain_r76_r86.md`)**: 파일명·H1·`description:` frontmatter는 모두 `r76_r86`인데 본문 L45–49에 `Rule R87`(`1,590 B`)이 끼어 들어감.
10. **Section 3 (L28) 스킬 누락**: Gear 5 표에 [`.agents/skills/qa-scheduler/SKILL.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/qa-scheduler/SKILL.md) 및 `qa-scheduler`, `studio-watchdog`, `studio-settings` 명령이 빠져 있으며, Gear 4 (L27) Tier-1 열에 `DQ_Smooth`, `DQ_Border`, `DQ_R85`, `DQ_R87`, `P_R87`이 누락.

#### B. 룰·스킬 내부의 `pipeline/config.py` 수치 충돌 (즉시 정리 필요)
| 잘못된 룰/스킬 기술 | 실제 [`pipeline/config.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) 진실값 | 영향 파일 |
|---|---|---|
| `MarginV = 521` / `<= 2 words` / `64pt` | **`EXPRESSIVE_V8_SUBTITLE_MARGIN_V = 510`**, **`FONT_SIZE = 82`**, **`MAX_WORDS = 3`** (`config.py:1316-1322`) | `audio_assembly_rules.md:12`, `neuro_diorama_core_r56_r65.md:24`, `neuro_diorama_v8_world_data_r66_r75.md:15`, `youtube-produce/SKILL.md:14` |
| `xray_brain75_master.png`, `ref_r78m_cut05/06` 활성 사용 | **`R85_RETIRED_DERIVATIVE_BRAIN_ANCHORS`** (`config.py:2342`, 은퇴됨) | `neuro_diorama_pacing_brain_r76_r86.md:19`, `reference_depiction_rules.md:13` |
| `v1_2` stays `"candidate"` | `v1_2/manifest.json` **`status: "locked"`** (`14` 승인 + `J04` 보류) | `reference_depiction_rules.md:22` |
| `"4 US Opening Modes"` (`paradox_question` default) | **`8`개 모드** (`EXPRESSIVE_V8_US_NATIVE_OPENING_MODES`), 기본값 **`immediate_brain_shock`** (`config.py:771-782`) | `neuro_diorama_v8_world_data_r66_r75.md:41` |
| `Hope`/`Laura Mini-Cortex` + `brain_simulator_3d` (`Blender 4.2`) | Solo `Siren` `0` cameo + `100%` Google Flow Ep #31 (`0%` Blender 화면 렌더) | `youtube-script/SKILL.md:21,23,44,48`, `youtube-produce/SKILL.md:13` |

#### C. 제안하는 `.agents/rules/*.md` 세분화 아키텍처 (`18`파일 `89.7 KB` → `24`개 마이크로 룰 `~52 KB`, 로딩 1회당 `<= 700` tok)

현재 6개 거대 파일을 역할·단계별 `1.0–2.8 KB` 단위로 쪼개고, `AGENTS.md`는 **"정확한 트리거 라우터(`<= 5.5 KB`)"** 역할만 수행하도록 재설계한다:

| 현재 거대/중복 파일 (현재 크기) | 세분화 재편 제안 (모두 `trigger: model_decision` — `governance_roles.md`만 `always_on`) | 목표 크기 | 절감·효과 |
|---|---|---|---|
| `production_constants.md` (`15,185 B`) | **L26–30 `12.6 KB` 심볼 덤프 삭제**, Active Core Locks 표(`~2.5 KB`)만 남기고 `trigger: model_decision` + `description:` 추가 (전체 상수는 `config.py` grep 직접 참조) | **`~2.5 KB`** | **`-83%`** (조회당 `~3,160` tok 절약) |
| `channel_operations_rules.md` (`9,840 B`) | ① `project_layout_and_storage.md` (`R8–R12, R19, R28–29`, FUSE, Flow방) **+ ② `R83` 섹션(`5.5 KB`) 완전 삭제**(`governance_roles.md` 단일화) | **`~3.8 KB`** | **`-61%`** (`R83` 중복 제거) |
| `governance_roles.md` (`3,812 B`, `always_on`) | 유일한 프로젝트 `always_on` 거버넌스 문서(`R83-1..8` 통합)로 압축 유지 — 전역 `post_compaction_context_recovery_rule.md`의 7방 중복 표는 제거하고 `07_Youtube` 내 이 파일만 참조 | **`~3.2 KB`** | 전역 4중 중복 **`-65%`** |
| `neuro_diorama_pacing_brain_r76_r86.md` (`8,789 B`) | ① `v8_pacing_and_acting_r76_r82.md` (`R76, R77, R79-M, R82` 타이밍·연기)<br/>② `r87_hook_and_conditional_arrows.md` (`R80, R87-H, R87-A`)<br/>③ `r86_semantic_beat_card.md` (`R86` 비트카드 계약)<br/>④ `r81_patrickhand_callouts.md` (`R81` 오버레이) *(뇌 규칙 `R78-M/R85`는 `brain_depiction_rules.md`로 합류해 중복 제거)* | 각 **`1.5–2.2 KB`** | 작업별 `8.8 KB` 대신 **`1.8 KB`만 로딩 (`-79%`)** |
| `neuro_diorama_v8_world_data_r66_r75.md` (`7,898 B`) | ① `v8_world_and_us_narration_r68_r73.md` (`R68, R68-D, R73`)<br/>② `data_stamp_and_anatomy_overlays_r70_r71.md` (`R70-M, R71`)<br/>③ `open_world_drone_and_real_refs_r72.md` (`R72, R72-R`)<br/>*(레거시 `R66, R67` Track A는 `legacy_v7_porcelain_reenactment.md`로 격리)* | 각 **`1.5–2.4 KB`** | `v8` 제작 시 `v7`·`R67` 로딩 **`0` tok** |
| `neuro_diorama_core_r56_r65.md` (`6,949 B`) | ① `qa_dq_triage_and_gate2_r62_r64.md` (`R62` DQ1–13, `R64` Gate 2)<br/>② `thumbnail_r65_v4.md` (`R65 v4` 썸네일 & `TQ` 게이트)<br/>③ `edl_titles_and_core_r56_r61.md` (`R56–R61` 정리본) | 각 **`1.4–2.5 KB`** | 썸네일 작업 시 **`1.4 KB`만 로딩 (`-80%`)** |
| 전역 `~/.gemini/config/rules/` (`16,771 B`) | • `job_research_handoff_rule.md`(`2,946 B`) → `04_Internship/.agents/rules/`로 이동 (`07_Youtube` 상시 로딩 `0`!)<br/>• `post_compaction_context_recovery_rule.md`(`9,385 B`) → 7방 표/Ep31 중복 제거한 **범용 `~1.5 KB` 복원 원칙**만 남김 (나머지는 `07_Youtube/governance_roles.md`가 소유) | 전역 총 **`~6.0 KB`** | **모든 방·모든 서브에이전트 매 턴 `-2,690` tok** |

---

## 3. 비전(VLM) 검수(`@Research` Gate 1/2 · `@YouTube_CEO` Gate 3) 무손실 최적화 설계

Gemini 공식 토큰 계산([`aistudio.google.com/docs/tokens`](https://aistudio.google.com/docs/tokens), [`media-resolution`](https://aistudio.google.com/docs/media-resolution))과 실측 `Ep #11 / #12` 해상도를 대입하면 다음과 같다:

| 검수 대상 | 현행 방식 (실측) | Gemini 타일 / `media_resolution` 토큰 소모 | 최적화 2단계 방식 (`Coarse-to-Fine + Ephemeral Shard`) | 최적화 후 토큰 & 절감률 |
|---|---|---|---|---|
| **Gate 1 (`reference_images/`, ~62장)** | `1080x1920` PNG 개별 `read_file` (또는 `@Research` 내 직접 누적) | `62 × 1,548` = **`95,976` tok** (타일 `2×3`×`258`)<br/>*또는* `62 × 1,120` = **`69,440` tok** (`high` 상한) | **Stage 1**: Python으로 **`1536×1536` (`4×3` = `12`컷/시트, 패널 `384px`) 정사각 시트 `6`장** 생성 → 일회성 `inherit` 비전 샤드에서 판정 (`6 × 1,032~1,120`)<br/>**Stage 2**: 이상 의심/반려 `~3`장만 **`<=384×384` 얼굴/텍스트 크롭** (`258` tok) 또는 원본 확인 | **`~6,966–7,500` tok** (**`-89% ~ -92%`**), 메인 방 잔류 **`0` tok** |
| **Gate 2 (`posthoc_viewer_strips/`, ~4시트 + `dq8`)** | 이미 `1340×1462` 시트(`4`장) + `dq8`(`1`장)를 사용 중이나, **영속 `@Research` 메인 방 히스토리에 이미지 누적** | 1회 호출: `5 × 1,032` = `5,160` tok. **문제는 후속 턴마다 메인 방 프리픽스에 이미지가 남아 재처리/컴팩팅 유발** | ① `posthoc_viewer_strips` 가로세로를 **`<=1536×1536` 타일 정렬 규격**으로 유지 + ② 실제 시각 판정은 **일회성 `inherit` 샤드(`12–15`컷/샤드)에서 수행 후 샤드 즉시 `kill`** + ③ `@Research` VP는 `REJECT`/`DQ8 HIGH` 크롭(`<=384×384`, `258` tok)만 `R83-8-V` 재검수 | **1회 검수 비용 동일 + 메인 방 영속 이미지 누적 `-85%+`** (`127`→`<20`회/반려 전용) |
| **CEO Gate 3 (`@YouTube_CEO`, 누적 `304`회)** | CEO가 매 에피소드·리메이크마다 직접 다수의 PNG/시트를 `read_file` | `8`번의 컴팩팅 중 상당 부분이 비전 컨텍스트 누적으로 발생 | CEO는 **`@Research`가 첨부한 최종 1장(합격 보드 또는 `<=384px` 반려 증적 크롭 `1~2`장)** + 결정론적 Python CV 대시보드 수치만 독립 확인 (`Verify Before Relay`) | CEO 비전 토큰 **`-75~85%`**, 컴팩팅 주기 대폭 연장 |

---

## 4. 멀티에이전트 토폴로지 · 캐시 · Python 오프로딩 경계 설계

### 4.1 3계층 핸드오프 압축 계약 (`CEO ↔ Domain VP ↔ Ephemeral Subagent`)
- 현재 7개 방 간 `SYSTEM_MESSAGE` 평균 `1,559–2,781`자(최대 `4,121`자)에 이르는 산문형 보고를 **고정 `<= 25`줄 / `<= 400` 토큰 `Delta Receipt` 포맷**으로 표준화:
  - 필수 5필드: `STATUS [PASS/REJECT/BLOCKED]` | `TARGET (project_id / scope)` | `CHANGED_FILES (paths + SHA/lines)` | `VERIFY_CMD (1줄 수치)` | `ARTIFACT_PATH` (상세 내용·표는 반드시 아티팩트/JSON 파일 경로로 오프로딩).
- **병렬 툴 배치 원칙 (`Gemini 4 2,050-tok 루프 규칙` 대응)**: 파일 5개 읽기나 CLI 점검 3건은 한 턴에 병렬 호출해 턴 수(`N`)를 `1/3`로 줄이고, 각 턴의 신규 토큰이 `2,050` 토큰 경계에서 비효율적 재처리를 반복하는 마이크로 턴을 억제한다.

### 4.2 모델 등급 라우팅 & Python 결정론적 오프로딩 경계 (`Code-First Offloading`)
1. **반복 JSON/텍스트 파싱·생성 = 100% Python 오프로딩 (`LLM 토큰 0`)**:
   - **QA 사전 다이제스트 (`main.py qa-summary --project <id>`)**: `video_autopsy_report.json` (`98.3 KB`), `posthoc_semantic_qa_report.json` (`57.6 KB`), `dynamic_episode_qa_report.json` (`31.8 KB`) 3개(`188 KB` = `~47K` tok)를 직접 읽는 대신, **실패 게이트·경고·결함 컷 인덱스만 `25`줄(`~1.2 KB`)로 압축 출력**하는 결정론적 요약기 추가.
   - **CLI `--compact` / `slim_out` 확대**: [`pipeline/cli.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py)의 `cmd_posthoc_qa` (`L2208`) `slim_out` 패턴을 `episode-qa` (`L2026`), `autopsy` (`L654`), `evolve` (`L671`), `ref-qa` (`L2303`), `dossier audit-media/seed`에 전면 확대(기본 슬림 출력, 상세 필요 시 `--full` 옵션).
   - **고정 에셋/바이블 문서 자동 생성**: `scripts/build_locked_assets_bible.py`로 `99`슬롯 카탈로그·SHA-256 검증 자동화(LLM 수작업 작성 `0` tok).
   - **아티팩트 디렉터리 수명주기 정리**: `@YouTube_CEO`(`370`개), `@Daily_Report`(`229`개), `@Operator`(`154`개)의 완료된 구형 아티팩트를 `artifacts_archive/` 동기화 확인 후 구버전 스냅샷 정리(컨텍스트 내 아티팩트 인덱스 메타데이터 크기 `36 KB` → `< 5 KB` 축소).

---

## 5. 정량적 토큰 절감 로드맵 (`Tier S / Tier A / Tier B`)

> 아래 수치는 `07_Youtube` 실측 바이트(`1 tok ≈ 4 B` 영어/마크다운 기준, 이미지는 Gemini `tokens`/`media-resolution` 공식 기준)에서 산출했으며, **직접 측정치 vs 개선 추정치**를 명시한다.

| 우선순위 | 최적화 항목 | 현재 추정 토큰 (실측 기반) | 개선 후 토큰 | 예상 절감률 | 품질 리스크 | 적용 대상 파일 · 아키텍처 |
|---|---|---:|---:|:---:|:---:|---|
| **Tier S-1** | **전역/프로젝트 `always_on` 중복 해소 & `04_Internship` 분리 + `41`개 타도메인 스킬 정리** | `~7,246` tok/턴 (`28,986 B` 상시 룰 + 타도메인 스킬 설명) | `~3,100` tok/턴 | **`-57%`** *(매 턴 × 전 방 × 전 서브에이전트)* | **0** | `~/.gemini/config/rules/` (`job_research_handoff_rule.md` 이동, `post_compaction` 축소), `.agents/rules/channel_operations_rules.md` (`R83` 제거), `.agents/rules/governance_roles.md` |
| **Tier S-2** | **`.agents/rules/*.md` 세분화(`18→24`파일) + `production_constants.md` 12.6KB 덤프 제거 + `AGENTS.md` 정합화** | 규칙 1회 로딩 `~1,800–3,796` tok (전체 `22,415` tok) | 작업당 `~400–650` tok (`production_constants` `635` tok) | **`-65% ~ -83%`** | **0** *(오히려 스테일 모순 제거로 정확도 ↑)* | `.agents/AGENTS.md`, `.agents/rules/production_constants.md`, `neuro_diorama_*.md` 3종 분할, `reference_depiction_rules.md` 등 스테일 수정 |
| **Tier S-3** | **Gate 1/2/3 `2-Stage Vision` (`1536x1536` 12-up 시트 + `<=384px` 크롭 + 일회성 `inherit` 샤드 휘발)** | Gate 1: `69K–96K` tok / 편<br/>메인 방 이미지 잔류 `807`회 누적 | Gate 1: `~7K–7.5K` tok / 편<br/>메인 방 이미지 누적 **`-85%+`** | **`-88% ~ -91%`** | **0** *(반려·DQ8 컷은 고해상도/크롭 재확인 + `R83-8-V` 유지)* | `pipeline/reference_image_qa.py` (`1536x1536` 시트 생성기), `@Research` Gate 1/2 샤딩 워크플로, `@YouTube_CEO` Gate 3 |
| **Tier A-1** | **CLI `slim_out` 전면화 + `main.py qa-summary` 결정론적 다이제스트 (Python 오프로딩)** | `~47K–100K` tok / 편 (대용량 JSON 읽기 + stdout 덤프) | `~1.5K–3.0K` tok / 편 | **`-94% ~ -96%`** | **0** *(전체 JSON은 디스크 보존, `--full`로 필요 시 열람)* | `pipeline/cli.py` (`episode-qa`, `autopsy`, `evolve`, `ref-qa`, `dossier`, `kb`), `pipeline/research_dossier.py`, `reference_image_qa.py` |
| **Tier A-2** | **`.agents/skills/*/SKILL.md` 레거시 `v7` `references/` 분리 & 내부 모순 해소** | `youtube-script` `3,130` tok + `youtube-produce` `1,646` tok | `~1,500` tok + `~1,100` tok | **`-33% ~ -52%`** | **0** | `.agents/skills/youtube-script/SKILL.md` + `references/legacy_v7.md`, `.agents/skills/youtube-produce/SKILL.md` |
| **Tier A-3** | **7방 간 `Delta Receipt (<=400 tok)` 핸드오프 계약 표준화** | `SYSTEM_MESSAGE` `avg 1,559–2,781`자 (`max 4,121`자) × `2,647`회 | `<= 1,200–1,600`자 (`~300–400` tok) | **`-40% ~ -55%`** | **Low** *(상세 증적은 아티팩트 경로로 링크해 `R83-7` 준수)* | `.agents/rules/governance_roles.md` (`R83-7` 포맷 경량화), 7개 웹 UI 방 보고 규약 |
| **Tier B-1** | **정적 프리픽스 고정 + 병렬 툴 배치 + 완료 아티팩트 아카이브 정리** | `CEO 370`·`Daily_Report 229` 아티팩트 인덱스 + 소형 순차 턴 | 활성 세션 아티팩트 `< 50`개 유지 + 턴 수 `-30~40%` | **`-25% ~ -40%`** *(턴/캐시 복합 절감)* | **0** | `scripts/sync_artifacts_archive.py` + 운영 주기(`/compact` 임계 관리), 에이전트 툴 배치 습관 |

---

## Verification & Primary-Source Receipts (`R83-7` · `R83-8-V`)

1. **작업 공간 무결성**: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/` 및 `~/.gemini/config/` 내 파일 수정·생성·삭제 `0`건, Flow/브라우저 호출 `0`건.
2. **검증된 외부 1차 URL (`HTTP 200` 직접 확인)**:
   - `https://www.anthropic.com/research/effective-context-engineering-for-ai-agents`
   - `https://www.anthropic.com/research/building-effective-agents`
   - `https://www.anthropic.com/research/equipping-agents-for-the-real-world-with-agent-skills`
   - `https://agentskills.io/home`
   - `https://aistudio.google.com/docs/caching`
   - `https://aistudio.google.com/docs/image-understanding`
   - `https://aistudio.google.com/docs/tokens`
   - `https://aistudio.google.com/docs/media-resolution`
   - `https://openai.github.io/openai-agents-python/handoffs/`
   - `https://www.langchain.com/blog/context-engineering-for-agents`
3. **로컬 실측 대상 경로**:
   - `~/.gemini/antigravity-cli/builtin/skills/agy-customizations/{SKILL.md,docs/rules.md,docs/skills.md}`
   - `~/.gemini/config/rules/{browser_tab_hygiene_rule.md,job_research_handoff_rule.md,post_compaction_context_recovery_rule.md}`
   - `07_Youtube/.agents/{AGENTS.md,chatrooms.json}` + `.agents/rules/*.md` (`18`개) + `.agents/skills/*/SKILL.md` (`6`개)
   - `07_Youtube/pipeline/{config.py,cli.py,posthoc_semantic_qa.py,reference_image_qa.py,research_dossier.py}`
   - `07_Youtube/BCI_Shorts_Channel/projects/{v8_ep11_open_label_placebo_pain,v8_ep12_doorway_effect_memory}/`
   - `~/.gemini/antigravity-cli/brain/<7개 방>/.system_generated/logs/transcript.jsonl`
4. **서브에이전트 및 VP 1차 검수 영수증 (`R83-8`, `R83-8-V`)**:
   - `flash` 룰·스킬 세분화 감사 서브에이전트(`d303f7c1-5819-4dd8-8216-e16b01c7d55f`) 1회 실행 후 즉시 종료(`kill`) → VP가 `AGENTS.md`, `audio_assembly_rules.md`, `cast_depiction_rules.md`, `scene_depiction_rules.md`, `brain_depiction_rules.md`, `visual_prompt_spec.md`, `youtube_studio_operations.md`, `camera_choreography_rules.md`, `reference_depiction_rules.md`, `research_dossier_rules.md`, `neuro_diorama_*.md`, `youtube-produce/SKILL.md`, `pipeline/config.py`, `pipeline/cli.py`를 직접 열어 전수 수치·불일치(`MarginV=521`, `xray_brain75_master`, `R46` 부재, `production_constants.md` 12.6KB 심볼 덤프 등) 검증 완료.
