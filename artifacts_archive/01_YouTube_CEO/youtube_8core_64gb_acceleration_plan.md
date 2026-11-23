# `07_Youtube` 파이프라인 4대 가속 업그레이드 마스터 설계서 (v2 승인 확정본 · 4대 엔지니어링 가드 반영)

인프라 업그레이드 계획서([spot_vm_upgrade_plan.md](file:///home/canadaofbin/.gemini/antigravity-cli/brain/26cbcfa1-543d-42d6-9518-196480c3704e/spot_vm_upgrade_plan.md))의 확정 스펙(**`c3d-highmem-8` Spot · 4세대 AMD EPYC Genoa 8 vCPU AVX-512 · 64GB RAM · Swap 0GB · `hyperdisk-balanced` 125GB · `shared-chrome` `--shm-size=12g`**) 및 **실전 코드 레벨 4대 엔지니어링 가드(연쇄 발견 5개 지점 포함)** 를 전수 검증·반영한 최종 실행 명세서입니다.

> [!IMPORTANT]
> **Spot 선점 무결성 & 크로스-디바이스(`EXDEV`) 무결성 원칙**
> 1. `/dev/shm/aab_scratch` (`tmpfs`, 22GB 하드 LRU 캡)에는 **재생성 가능한 중간 프레임·세그먼트·스테이징 사본만 배치**합니다.
> 2. 완료된 산출물(`flow_native_clips/*.mp4`, `brain_simulator_clips/*.mp4`, `04_audio/audio_master.wav`, `05_assembly/final_shorts_1080x1920.mp4`, 각종 영수증 JSON)을 `/dev/shm`(`tmpfs`)에서 영구 스토리지(`fuse.rclone` / `ext4`)로 커밋할 때는 **절대 직접 `os.replace()`를 호출하지 않고**, 반드시 대상 디렉터리 내 형제 임시 파일로 복사 후 동일 마운트 안에서 원자적 교체하는 **`atomic_commit_from_scratch(shm_src, dst)`** 만 사용합니다.

---

## 1. 하드웨어 전환 및 64GB 메모리·코어 예산 배분 설계

| 자원 영역 | 기존 (`e2-custom-4-12288`) | 신규 (`c3d-highmem-8` Spot) | 파이프라인 할당 정책 |
| :--- | :--- | :--- | :--- |
| **CPU 코어 / 명령어** | 4 vCPU 구형 Xeon (~2.2GHz) | **8 vCPU AMD Genoa (~3.7GHz, AVX-512)** | 단독 모드 **`cpu_budget=8`** / 오버래핑 모드 **Flow 2코어 + 로컬 조립·블렌더 `cpu_budget=6`** 명시적 인자 전달 |
| **Host `/dev/shm` 램디스크** | 5.9 GB (미사용, `/tmp` SSD 병목) | **32.0 GB 자동 마운트** (`tmpfs`) | `/dev/shm/aab_scratch`에 **최대 `22 GB` 하드 LRU 캡** 적용 (`20,000+ MB/s`) |
| **`shared-chrome` 컨테이너** | `--shm-size=4g` (멀티탭 압박) | **`--shm-size=12g`** (`--disable-dev-shm-usage` 제거, 프로필 로컬 이전은 인프라 측 처리) | Google Flow 5탭 동시 생성 + Studio 탭 WebGL/비디오 디코드 여유 확보 (실점유 `~3~5 GB`) |
| **Python + Blender + FFmpeg** | 12 GB 한계로 Swap 5.7GB 스래싱 | **피크 RSS `~10~14 GB`** (Swap `0 GB`) | Blender 3~4프로세스(`~3.2 GB`) + FFmpeg/OpenCV 6~8워커(`~4.5 GB`) + Whisper AVX-512(`~1.2 GB`) |
| **OS Page Cache & 여유분** | 0 GB (상시 고갈) | **`~16~20 GB` 상시 여유 확보** | `rclone` FUSE 읽기 버퍼 및 커널 페이지 캐시로 흡수 (OOM 원천 차단) |

---

## 2. 4대 엔지니어링 가드 실코드 팩트체크 및 연쇄 보강 명세

지적해주신 4개 항목을 실제 코드 라인 단위로 대조한 결과 **4개 모두 100% 정확한 실제 런타임 장애/병목 요인**임을 확인했으며, 동일 원리로 연결된 **추가 연쇄 지점 5곳**까지 함께 고정했습니다.

### Guard 1. Cross-Device `os.replace()` (`Errno 18 EXDEV`) 원천 차단 *(Workstream A)*
- **실코드 검증 결과 (`100% 정확`)**:
  - Linux 커널의 `rename(2)`(`os.replace`)는 동일 마운트(`st_dev`) 내에서만 동작하므로 `/dev/shm/aab_scratch`(`tmpfs`) -> `/home/canadaofbin/gdrive`(`fuse.rclone`) 또는 `/tmp`(`ext4`) 직접 호출 시 즉시 `OSError: [Errno 18] Invalid cross-device link`가 발생합니다.
  - [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L4339-L4352)의 `_atomic_copy_file`이 이미 `shutil.copy2(src, dst_sibling_tmp)` + 5회 재시도 `os.replace(dst_sibling_tmp, dst)` 표준 패턴을 구현하고 있습니다.
- **구현 고정 사양 + 연쇄 보강**:
  1. `pipeline/media_cache.py`에 공용 **`atomic_commit_from_scratch(src: Path, dst: Path, *, suffix: str | None = None)`** 를 승격 정의:
     - `src.stat().st_dev == dst.parent.stat().st_dev`이면 즉시 `os.replace(src, dst)` (동일 `/dev/shm` 내부 0초 커밋).
     - 마운트가 다르면(`tmpfs -> fuse/ext4`) `tmp_dst = dst.with_name(f".tmp_{os.getpid()}_{threading.get_ident()}_{dst.name}")`로 `shutil.copy2` 후 재시도 `os.replace(tmp_dst, dst)` 수행 및 실패 시 `tmp_dst.unlink(missing_ok=True)` 보장.
  2. **연쇄 보강 1A ([anatomy_label_overlay.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_label_overlay.py#L1458-L1480) & [data_stamp_overlay.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/data_stamp_overlay.py#L1372-L1397))**:
     - `anatomy_label_overlay.py:1458`은 현재 출력 임시 MP4를 FUSE 위에 직접 인코딩하고 있고, `data_stamp_overlay.py:1397`은 비원자적 `shutil.copy2`로 덮어쓰고 있습니다 -> 두 모듈 모두 **인코딩 출력은 `/dev/shm/aab_scratch` 내부로 뽑은 뒤 `atomic_commit_from_scratch(tmp_out, video_out)`으로 커밋**하도록 통일합니다.
  3. **연쇄 보강 1B ([diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L5394))**:
     - `_segment_cache_dir`(`cache_p`)와 조립 임시 폴더(`td_path`)를 **둘 다 `/dev/shm/aab_scratch`** 하위에 두어 동일 `tmpfs` 내 `os.link(cache_p, out_p)` 하드링크가 `0.001ms` 무복사(Zero-Copy)로 동작하게 유지합니다.

### Guard 2. `media_cache.py` 등 `/dev/shm` 스크래치 경로 인식 확대 *(Workstream A)*
- **실코드 검증 결과 (`100% 정확 + 추가 3곳 포착`)**:
  - [media_cache.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/media_cache.py#L102) `_file_stat_fingerprint`는 `str(resolved).startswith("/tmp")`만 경계 CRC32 고속 경로로 인정하고 있습니다.
  - [media_cache.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/media_cache.py#L162) `_should_persist_sha_for_path`는 `tempfile.gettempdir()`(`/tmp`)만 제외하고 있어, `/dev/shm` 파일 해싱 시마다 FUSE의 `persistent_sha256_cache.json`에 불필요한 `fcntl.flock` 경합과 휘발성 경로 오염을 유발합니다.
- **구현 고정 사양 + 연쇄 보강 3곳**:
  1. 공용 판별 함수 **`is_ephemeral_scratch_path(path: Path) -> bool`** 도입: `resolved_s.startswith(("/tmp/", "/dev/shm/")) or resolved_s in ("/tmp", "/dev/shm")` (+ `tempfile.gettempdir()`, `AAB_SPEED_CACHE_DIR` 포함).
  2. 적용 지점 5곳 일괄 패치:
     - `media_cache.py:102` (`_file_stat_fingerprint` 고속 경계 CRC32 활성)
     - `media_cache.py:162` (`_should_persist_sha_for_path` -> `False` 반환으로 FUSE flock/오염 완전 차단)
     - **연쇄 보강 2A — [media_cache.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/media_cache.py#L286) (`stage_local_file`)**: 이미 `/dev/shm`에 있는 파일을 `staged/`로 중복 복사하지 않고 즉시 `(resolved, fast_file_sha256(resolved))` 반환!
     - **연쇄 보강 2B — [media_integrity.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/media_integrity.py#L512) & [flow_live_single_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_live_single_worker.py#L1279)**: `not str(path).startswith("/tmp")` 조건을 `not is_ephemeral_scratch_path(path)`로 교체해 `/dev/shm` 파일을 느린 `/tmp` SSD로 역복사하는 현상 차단!

### Guard 3. 재사용 워커 프로세스 동적 코어 거버너(`6 -> 8 vCPU`) 명시적 인자화 *(Workstream B)*
- **실코드 검증 결과 (`100% 정확 + Whisper 싱글톤 함정 추가 포착`)**:
  - [diorama_pipeline_runner.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_pipeline_runner.py#L270)는 `ProcessPoolExecutor(max_workers=1, mp_context=mp_ctx)` 워커 프로세스 1개를 배치 내내 재사용합니다.
  - 따라서 `L115`의 `os.environ.setdefault("OMP_NUM_THREADS", ...)`는 첫 에피소드 이후 절대 변경되지 않으며, OpenMP(`libgomp`)/OpenBLAS 런타임 역시 프로세스 최초 로드 시점 이후 환경변수를 다시 읽지 않습니다.
- **구현 고정 사양 + 연쇄 보강**:
  1. 워커 프로세스 부팅 시 내부 라이브러리 스레드는 **`OMP_NUM_THREADS="1"`, `MKL_NUM_THREADS="1"`, `OPENBLAS_NUM_THREADS="1"`, `cv2.setNumThreads(1)`** 로 고정하여 중첩 스레드 폭발을 막고, 실제 병렬도는 파이썬/서브프로세스 풀 크기인 명시적 인자 **`cpu_budget: int`** 로 100% 제어합니다.
  2. 명시적 인자 체인 관통:
     - `run_diorama_pipeline`: 제출 시점에 `eff_budget = 6 if (flow_queue or active_flow_running) else 8` 산출 -> `_assembly_worker_entry(project_id, voice_preset, prosody_mode, cpu_budget=eff_budget)` 전달.
     - `finalize_and_verify_diorama_project(..., cpu_budget=cpu_budget)` -> `assemble_diorama_project(..., cpu_budget=cpu_budget)` (`n_workers = cpu_budget`, `xfade n_workers = cpu_budget`) 및 `dynamic_episode_qa` / `posthoc_semantic_qa` (`cpu_budget` 워커 풀).
  3. **연쇄 보강 3A ([voice_fallback.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/voice_fallback.py#L192-L203) `_WHISPER_MODEL` 싱글톤)**:
     - 기존 전역 `_WHISPER_MODEL`은 최초 생성 시점의 `cpu_threads`로 영구 고정되므로 `_whisper_model(cpu_threads: int | None = None)`으로 시그니처를 확장하여 요청 스레드 수(`6` -> `8`) 승격 시 기존 인스턴스를 교체 재생성(메모리 중복 없이 1개만 유지)하도록 보강합니다.

### Guard 4. Level A 오버래핑 분기(Fork) 시점을 `TTS + 마스터 EDL 확정 직후`로 고정 *(Workstream B)*
- **실코드 검증 결과 (`100% 정확 + `xfade` 오버랩 프레임 일치 검증 완료`)**:
  - [brain_simulator_blender.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/brain_simulator_blender.py#L350) · [L991](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/brain_simulator_blender.py#L991) 확인 결과, 3D 드론 궤적(`u = f_idx / (n_frames - 1)`), 신경 신호 이동·단절 타이밍, 그리고 `R71` 해부학 콜아웃이 참조하는 `<stem>_camera_track.json`이 모두 **`30fps` 기준 정확한 `n_frames`** 에 종속됩니다.
  - 또한 [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L5347)에서 `xfade` 전환 구간이 있는 컷은 `req_raw_f = eff_f + ov_f_k + 1` 프레임을 요구하므로, TTS 이전에 대략적인 초수로 렌더링하면 조립 단계(`L4331`)에서 프레임 부족 예외나 트래킹 오차가 발생할 수 있습니다.
- **구현 고정 사양 (정밀 4단계 시퀀스)**:
  ```mermaid
  sequenceDiagram
      participant Orch as 메인 오케스트레이터
      participant Audio as Step 1: TTS + 마스터 EDL 확정
      participant Flow as Branch 1: Google Flow (휴먼 컷, <=5탭)
      participant Blend as Branch 2: Blender 병렬 풀 (3x2=6 vCPU)
      participant Asm as Step 3: 6~8코어 고속 조립 + 5대 QA

      Orch->>Audio: synthesize_continuous_diorama_track + P6 게이트 + dry-run EDL 확정
      Audio-->>Orch: 04_audio/audio_master.wav + 컷별 정확한 req_n_frames(eff_f + ov_f_k + 안전여유) 확정
      par 동시 분기 (Fork Point T0)
          Orch->>Flow: grammar != "brain_simulator_3d" 휴먼 컷만 Flow 생성
      and
          Orch->>Blend: grammar == "brain_simulator_3d" 컷을 확정 req_n_frames로 병렬 렌더링
      end
      Flow-->>Orch: 휴먼 클립 완료
      Blend-->>Orch: 뇌 시뮬레이터 클립 + camera_track.json + SQ1-6 완료
      Orch->>Asm: preserve_audio_master=True로 TTS 재실행 없이 즉시 8코어 조립·검수
  ```
  1. **Step 1 (Fork 직전 확정)**: `synthesize_continuous_diorama_track` + 사전 `P6` 오디오 게이트 통과 -> `04_audio/audio_master.wav` 저장 후, `build_crosscut_edl(..., allow_virtual_unrendered_clips=True)`로 **각 `brain_simulator_3d` 컷의 정확한 `req_n_frames = eff_f + ov_f_k + 6`(안전 꼬리 여유 6프레임 포함, `src_start_sec=0.0`, `src_end_sec=eff_f/30.0`)** 를 계산해 `05_assembly/edl_timing_lock.json`에 기록합니다.
  2. **Step 2 (동시 Fork)**:
     - **Google Flow 워커 (`flow_diorama_sharded_worker.py`)**: `grammar == "brain_simulator_3d"` 컷은 Flow 제출 대상에서 자동 제외(탭·시간 낭비 0%)하고 휴먼 컷만 생성합니다.
     - **Blender 병렬 풀 (`brain_simulator_blender.py`)**: 확정된 `req_n_frames`(`30fps`)로 7~10개 뇌 컷을 `3 workers × 2 threads`(`LP_NUM_THREADS=2`, `-t 2`)로 `/dev/shm/aab_scratch`에서 병렬 렌더링 후 `atomic_commit_from_scratch`로 `03_visuals/brain_simulator_clips/`에 커밋합니다.
  3. **Step 3 (Join & 무중복 조립)**: 두 분기가 합류하면 `assemble_diorama_project(..., preserve_audio_master=True)`를 호출해 TTS/Whisper 재합성(약 15~25초)을 완전히 생략하고 곧바로 6~8워커 세그먼트 인코딩으로 진입합니다.

---

## 3. Workstream A / B 최종 구현 작업 분배표 (`@Operator` · `@Headquarters`)

### Workstream A — `@Operator` (`1f9808d4-ebac-4b58-a570-45c8f1f00a85`)
1. **`pipeline/hardware_profile.py` 신설 + [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) 상수 등록**:
   - `resolve_cpu_budget(explicit_budget: int | None = None, overlapped: bool = False) -> int` (`8` 단독 / `6` 오버래핑, 저사양 테스트 환경 자동 클램프).
   - `AAB_SHM_SCRATCH_ROOT = "/dev/shm/aab_scratch"`, `AAB_SHM_MAX_BYTES = 22 * 1024**3`.
2. **[media_cache.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/media_cache.py) 램디스크 전환 + Guard 1·2 핵심 헬퍼 구현**:
   - `get_ram_scratch_root()`, `ram_tempdir(prefix)`, `enforce_ram_scratch_budget()`, **`atomic_commit_from_scratch(src, dst)`**, **`is_ephemeral_scratch_path(path)`** 구현.
   - `L80` `get_speed_cache_dir()`, `L102` `_file_stat_fingerprint`, `L162` `_should_persist_sha_for_path`, `L286` `stage_local_file` 패치 및 LRU 한도(`staged` 8GB, `segments` 6GB, `tts_npz` 2.5GB, `posthoc_cv` 2GB) 상향.
   - `media_integrity.py:512`, `flow_live_single_worker.py:1279`에 `is_ephemeral_scratch_path` 적용.
3. **8코어 스레드 봉인 해제 & 스크래치 전환 + Guard 3 하위 인자 연결**:
   - `diorama_assembler.py` (`L3571, 3650, 3883, 4003, 4655, 4754, 5151, 5153, 5507`): `cpu_budget` 인자 수용, `ram_tempdir` 적용, 세그먼트 FFmpeg `-threads` 적정 배분, `recut_diorama_cuts` 병렬화.
   - `voice_fallback.py` (`L38, 122, 192-203, 553`): `_whisper_model(cpu_threads)` 동적 승격 지원 + `ram_tempdir`.
   - `flow_diorama_sharded_worker.py` (`L1143, 3344`), `data_stamp_overlay.py` (`L1302, 1397`), `anatomy_label_overlay.py` (`L1406, 1458, 1480`), `thumbnail_studio.py` (`L2417`), `elevenlabs_tts.py` (`L335`), `dynamic_episode_qa.py` (`L2624`), `knowledge_hub.py` (`L959`), `studio/reporter.py` (`L430`) 일괄 적용.
4. **단위 테스트 (`tests/test_hardware_ramdisk_and_guards.py`)**:
   - Cross-device `EXDEV` 시뮬레이션(`os.replace` `Errno 18` mock) 시 `atomic_commit_from_scratch` 정상 원자적 커밋 검증, `/dev/shm` 경로 FUSE SHA 캐시 무오염 검증, `cpu_budget` `6 -> 8` 동적 변경 검증.

### Workstream B — `@Headquarters` (`8c7f8d97-664d-4d6b-9ef8-b17e721354f9`)
1. **[brain_simulator_blender.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/brain_simulator_blender.py) 멀티컷 병렬 렌더러 구현**:
   - `render_brain_simulator_clip`: `ram_tempdir` 프레임 생성 + `LP_NUM_THREADS=threads`, `OMP_NUM_THREADS=threads`, Blender `-t <threads>`, FFmpeg `-threads <threads> -preset fast` + `atomic_commit_from_scratch` 커밋 + `sim_spec_sha256` 해시 기록.
   - `render_project_brain_simulator_clips_parallel(project_dir, *, edl_frame_map, cpu_budget=8, threads_per_worker=2, force=False)`: `max_workers = max(1, cpu_budget // threads_per_worker)` (`8코어 -> 4×2`, `6코어 -> 3×2`) 병렬 실행 및 `SQ1~SQ6` 통과분 `0.0초` 해시 스킵.
2. **Guard 3·4 반영 2단계 오버래핑 오케스트레이터 ([diorama_pipeline_runner.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_pipeline_runner.py) · [diorama_batch_orchestrator.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_batch_orchestrator.py) · [flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py))**:
   - **Guard 4**: `lock_episode_audio_and_edl_frames(project_dir)`로 TTS + `P6` 게이트 + 가상 마스터 EDL 프레임(`req_n_frames`)을 선확정한 직후, Flow 휴먼 컷 생성(`grammar != "brain_simulator_3d"`)과 백그라운드 Blender 병렬 풀(`cpu_budget=6 -> 3×2`)을 동시 Fork -> 합류 즉시 `preserve_audio_master=True`로 무중복 고속 조립.
   - **Guard 3**: `_assembly_worker_entry(..., cpu_budget: int)` 명시적 인자 전달로 Flow 진행 중엔 `cpu_budget=6`, Flow 종료(마지막 에피소드) 시 즉시 `cpu_budget=8` 자동 승격.
   - `cli.py`에 `main.py brain-sim`, `main.py hw-bench`, `main.py diorama-batch` 파이프라인 기본화(`--sequential` 옵션 보존) 연결.
3. **단위·통합 테스트 (`tests/test_blender_parallel_and_overlap.py`) + 재부팅 후 실측 벤치마크**:
   - 확정 `req_n_frames` 일치 검증, `3×2` / `4×2` 스레드 매핑 검증, 재부팅된 `c3d-highmem-8` 환경에서 실제 Blender 병렬 + 8코어 조립 전후 속도 실측 리포트 산출.
