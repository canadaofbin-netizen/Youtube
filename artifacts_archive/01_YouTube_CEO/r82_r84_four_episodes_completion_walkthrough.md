# `Rule R82 + Rule R84` 전역 파이프라인 구축 및 4편(`Ep #9 ~ #12`) 완공 보고서

> [!IMPORTANT]
> **전체 완공 핵심 요약 (`2026-11-17`)**
> 1. **4편 전량 `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/` 최상위 폴더 정렬 배치 완료**:
>    - [final_shorts_v8_ep09_maguire_london_taxi_hippocampus_r82.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep09_maguire_london_taxi_hippocampus_r82.mp4) (`84.67s`, `23컷`, `71.05 MB`)
>    - [final_shorts_v8_ep10_sleep_pill_brain_wash_r82.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep10_sleep_pill_brain_wash_r82.mp4) (`80.67s`, `24컷`, `67.07 MB`)
>    - [final_shorts_v8_ep11_open_label_placebo_pain_r82.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep11_open_label_placebo_pain_r82.mp4) (`79.97s`, `24컷`, `61.83 MB`)
>    - [final_shorts_v8_ep12_doorway_effect_memory_r82.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep12_doorway_effect_memory_r82.mp4) (`77.13s`, `23컷`, `66.36 MB`)
> 2. **`Rule R84` 메디컬 반절개 & 점선 기준선 부피 대조 엔진 전역 탑재 (`v8_ep13+` 자동 강제)**:
>    - `neuro_atlas_mni152.npz`(`299,769` 실제 인간 MRI 폴리곤) + `Blender 4.2 Cycles` `EXACT Boolean` 외과 절개 + `AgX` 무광 서브서피스 PBR(`0%` 네온/번개, `0.0 px` 지시선 오차) 전환으로 4편 총 `32`개 뇌 컷에서 **Google Flow 크레딧 `0` 소모 (`768` 크레딧 절감)**.
> 3. **전수 QA 100% 통과**: 4편 모두 `SQ1–SQ6 8/8 PASS`, `ref-qa 100.0`, `episode-qa 20/20 PASS`, `posthoc-qa 96.9~97.0 (weak 0)`, `autopsy PASS`, `verify 100% INTACT`.

---

## 1. 4편 핵심 뇌 반절개 & `2.5x` 상/하 흰색 점선 기준선(`1.0x`) 대조 검증 시트

````carousel
![Ep #9 런던 택시 드라이버 — 해마 반절개 & Taxi(+33%) vs Bus 상하 점선 부피 비교](./ep09_r84_remake_23cuts_proof_brain_zoom.jpg)
<!-- slide -->
![Ep #10 수면제 뇌 세척 — 시상·뇌간 반절개 & Natural(+24%) vs Zolpidem(50% 억제) 점선 비교](./ep10_r84_remake_24cuts_proof_brain_zoom.jpg)
<!-- slide -->
![Ep #11 오픈라벨 플라시보 — 심부 섬엽(Insula) 반절개 & Placebo(-18% 진정) vs No Pill 점선 비교](./ep11_r84_remake_24cuts_proof_brain_zoom.jpg)
<!-- slide -->
![Ep #12 문지방 기억 리셋 — 두정엽·해마 반절개 & Same Room(+18% 유지) vs Doorway 점선 비교](./ep12_r84_remake_23cuts_proof_brain_zoom.jpg)
````

---

## 2. 4편 전체 컷(`23~24컷`) 컨택트 시트

````carousel
![Ep #9 전체 23컷 컨택트 시트 (UCL 상공 드론 C03-04 + R80 화살표 + R84 해마 반절개)](./ep09_r84_remake_23cuts_proof.jpg)
<!-- slide -->
![Ep #10 전체 24컷 컨택트 시트 (코펜하겐 대학 상공 드론 C03-04 + R84 뇌간·시상 반절개)](./ep10_r84_remake_24cuts_proof.jpg)
<!-- slide -->
![Ep #11 전체 24컷 컨택트 시트 (하버드 의대 상공 드론 C03-04 + R84 섬엽·뇌간 반절개)](./ep11_r84_remake_24cuts_proof.jpg)
<!-- slide -->
![Ep #12 전체 23컷 컨택트 시트 (노틀담 골든돔 상공 드론 C03-04 + R84 해마·전전두엽 반절개)](./ep12_r84_remake_23cuts_proof.jpg)
````

---

## 3. 에피소드별 최종 QA 스코어보드

| 에피소드 | 분량 / 컷수 | `SQ1–SQ6` (3D 해부) | `ref-qa` | `episode-qa` | `posthoc-qa` (`weak`) | `verify` 무결성 |
|---|---|---|---|---|---|---|
| **Ep #9** (`런던 택시 해마`) | `84.67s` / `23`컷 | `8/8 PASS` | `100.0` | `20/20 PASS` | **`96.9`** (`0`) | `202/202 INTACT` |
| **Ep #10** (`수면제 뇌 세척`) | `80.67s` / `24`컷 | `8/8 PASS` | `100.0` | `20/20 PASS` | **`97.0`** (`0`) | `196/196 INTACT` |
| **Ep #11** (`오픈라벨 플라시보`) | `79.97s` / `24`컷 | `8/8 PASS` | `100.0` | `20/20 PASS` | **`96.9`** (`0`) | `184/184 INTACT` |
| **Ep #12** (`문지방 효과 기억`) | `77.13s` / `23`컷 | `8/8 PASS` | `100.0` | `20/20 PASS` | **`96.9`** (`0`) | `175/175 INTACT` |
