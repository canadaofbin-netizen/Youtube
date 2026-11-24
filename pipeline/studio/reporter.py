"""ALL ABOUT BRAIN — Daily YouTube Studio Traffic-Light Growth Reporter (`reporter.py`)."""

from pipeline.studio.reporter_scrape import *
from pipeline.studio.reporter_scrape import _StudioScrapeMixin, _clean_str, _extract_slot_date_time, _is_inactive_queue_status, _load_published_legacy_topics, _two_prop_z_score
from pipeline.studio.reporter_analytics import _StudioAnalyticsMixin
from pipeline.studio.reporter_charts import _StudioChartsMixin


class StudioAnalyticsReporter(_StudioScrapeMixin, _StudioAnalyticsMixin, _StudioChartsMixin):
    """
    Collects all YouTube Studio analytics & pipeline queue data, compares against
    the prior daily snapshot, generates PNG chart dashboards, and renders
    the normalized 5-section Markdown Daily Growth Report.
    """

    def __init__(
        self,
        cdp_port: int = DEFAULT_CDP_PORT,
        reports_dir: Path = DAILY_REPORTS_DIR,
        projects_dir: Path | None = None,
        queue_file: Path | None = None,
        short_link_graph_file: Path | None = None,
    ):
        self.cdp_port = cdp_port
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir = projects_dir
        self.queue_file = queue_file
        self.short_link_graph_file = short_link_graph_file
        self.session = WhaleSessionController(cdp_port=cdp_port)

    def render_markdown_report(
        self,
        data: dict[str, Any],
        charts_filename: str,
        section_charts: dict[str, str] | None = None,
    ) -> str:
        """
        Renders a streamlined, zero-redundancy, multi-horizon Traffic Light Daily Report:
        - Banner 0: 1-Line Executive Summary Banner (no duplicate table)
        - Section 1: Unified Volume & 3-Stage Feed Exposure Funnel (Shown in feed -> Views -> Engaged Views)
        - Section 2: Retention with Recent Cohort Split (All vs Recent 3 vs Latest), Swiped % removed, and Inter-Quartile Drop-Off (Delta Q)
        - Section 3: High-Signal Daily Traffic & Geo Only (Shorts Feed % & US/Tier-1 %, noisy 28d search terms & age split deferred to Weekly)
        - Section 4: Seed & Queue Mini-Tracker + Bottleneck Diagnosis & 5-Gear Pipeline Calibration
        - Section 5: Next 7-Day Growth Roadmap & Targets
        """
        inv = data["inventory_summary"]
        ck = data["channel_kpis"]
        rk = data["retention_kpis"]
        r_quarts = data.get("retention_quartiles", [])
        cs = self._compute_recent_cohort_and_history_stats(data)
        has_7d = cs["has_7d"]
        has_3d = cs["has_3d"]
        snap_7d = cs["snap_7d"]
        snap_3d = cs["snap_3d"]

        sec_imgs = section_charts or {
            "sec1": "sec1_channel_growth.png",
            "sec2": "sec2_video_retention_performance.png",
            "sec3": "sec3_traffic_audience_growth.png",
            "sec4": "sec4_schedule_inventory.png",
        }

        dates_7d = data["trend_7d"]["dates"]
        d7_label = dates_7d[0] if dates_7d else "-"
        d3_label = dates_7d[3] if len(dates_7d) > 3 else "-"

        views_now = int(ck["views_24h"])
        views_prev = int(ck["views_prev"])
        views_dod_diff = views_now - views_prev
        views_dod_pct = (views_dod_diff / max(1, views_prev)) * 100.0

        viewed_now = float(rk["viewed_pct"])
        viewed_prev = float(rk["viewed_prev_pct"])
        viewed_dod_diff = viewed_now - viewed_prev
        viewed_gap = viewed_now - 70.0

        shown_prev = cs["shown_prev"]
        shown_now = cs["shown_now"]
        shown_dod_diff = shown_now - shown_prev
        shown_dod_pct = (shown_dod_diff / max(1, shown_prev)) * 100.0

        engaged_prev = cs["engaged_prev"]
        engaged_now = cs["engaged_now"]
        if engaged_now is not None and engaged_prev is not None:
            engaged_dod_diff = engaged_now - engaged_prev
            engaged_dod_pct = (engaged_dod_diff / max(1, engaged_prev)) * 100.0
            engaged_now_lbl = f"{engaged_now:,}"
            engaged_prev_lbl = f"{engaged_prev:,}"
            engaged_dod_lbl = f"{engaged_dod_diff:+,}"
            engaged_dod_cell = f"**`{engaged_dod_diff:+,}` (`{engaged_dod_pct:+.1f}%`)**"
        else:
            engaged_dod_diff = 0
            engaged_dod_pct = 0.0
            engaged_now_lbl = f"{engaged_now:,}" if engaged_now is not None else "N/A"
            engaged_prev_lbl = f"{engaged_prev:,}" if engaged_prev is not None else "-"
            engaged_dod_lbl = "N/A"
            engaged_dod_cell = "`unscraped`"

        subs_now = int(ck["subscribers_total"])
        subs_prev = int(ck["subscribers_prev"])
        subs_dod_diff = subs_now - subs_prev
        subs_per_1k = (subs_now / max(1, views_now)) * 1000.0
        subs_per_1k_prev = (subs_prev / max(1, views_prev)) * 1000.0

        wh_now = float(ck["watch_hours_24h"])
        wh_prev = float(ck["watch_hours_prev"])
        wh_dod_diff = wh_now - wh_prev
        wh_dod_pct = (wh_dod_diff / max(0.1, wh_prev)) * 100.0

        rt48_now = int(ck["realtime_48h_views"])
        rt48_prev = int(ck["realtime_48h_prev"])
        rt48_diff = rt48_now - rt48_prev
        rt48_pct = (rt48_diff / max(1, rt48_prev)) * 100.0
        rt48_samples = [rt48_prev, rt48_now]
        if snap_3d:
            rt48_samples.append(int(snap_3d["realtime_48h"]))
        if snap_7d:
            rt48_samples.append(int(snap_7d["realtime_48h"]))
        rt48_peak = max(rt48_samples)
        rt48_avg = int(round(sum(rt48_samples) / max(1, len(rt48_samples))))

        avd_now = float(rk["avd_seconds"])
        avd_prev = float(rk["avd_prev_seconds"])
        avg_len = float(rk["avg_video_length_sec"])

        apv_now = float(rk["apv_pct"])
        apv_prev = float(rk["apv_prev_pct"])
        apv_dod_diff = apv_now - apv_prev
        apv_gap = apv_now - 60.0

        recent_viewed = cs["recent_viewed"]
        recent_avd = cs["recent_avd"]
        recent_apv = cs["recent_apv"]
        recent_len = cs["recent_len"]
        recent_q = cs["recent_q"]
        latest_rec = cs["latest_rec"]
        prev_rec = cs["prev_rec"]

        lat_hook_s = (
            f"{float(latest_rec.get('viewed_pct', 0.0)):.1f}%"
            if (latest_rec and float(latest_rec.get("viewed_pct", 0.0)) > 0)
            else "-"
        )
        prv_hook_s = (
            f"{float(prev_rec.get('viewed_pct', 0.0)):.1f}%"
            if (prev_rec and float(prev_rec.get("viewed_pct", 0.0)) > 0)
            else "-"
        )
        lat_avd_s = f"{float(latest_rec.get('avd_seconds', 0.0)):.1f}s" if latest_rec else "-"
        prv_avd_s = f"{float(prev_rec.get('avd_seconds', 0.0)):.1f}s" if prev_rec else "-"
        lat_apv_s = f"{float(latest_rec.get('apv_pct', 0.0)):.1f}%" if latest_rec else "-"
        prv_apv_s = f"{float(prev_rec.get('apv_pct', 0.0)):.1f}%" if prev_rec else "-"

        # Historical 7d / 3d formatted cells ("-" / "collecting" when <7 snapshots exist; "`outlier`" when K-unit corrupted)
        if has_3d and snap_3d:
            v_3d_cell = f"{int(snap_3d['views']):,}" if snap_3d.get("views") is not None else "`outlier`"
            shown_3d_cell = f"{int(cs['shown_3d'] or 0):,}" if snap_3d.get("views") is not None else "`outlier`"
            eng_3d_cell = f"{int(cs['engaged_3d'] or 0):,}"
            wh_3d_cell = f"{float(snap_3d['watch_hours']):.1f}h"
            if snap_3d.get("subscribers") is not None and snap_3d.get("views") is not None:
                s3_subs = int(snap_3d["subscribers"])
                s3_p1k = (s3_subs / max(1, int(snap_3d["views"]))) * 1000.0
                subs_3d_cell = f"{s3_subs:,} (`{s3_p1k:.2f}`)"
            else:
                subs_3d_cell = "`outlier`"
            rt48_3d_cell = f"{int(snap_3d['realtime_48h']):,}"
        else:
            v_3d_cell = "-"
            shown_3d_cell = "-"
            eng_3d_cell = "-"
            wh_3d_cell = "-"
            subs_3d_cell = "-"
            rt48_3d_cell = "-"

        ts_map = {t["short_name"]: t for t in data["traffic_sources"]}
        sf_rec = ts_map.get("Shorts Feed", {"pct": 0.0, "prev_pct": 0.0, "views": 0})
        sf_dod_diff = float(sf_rec["pct"]) - float(sf_rec["prev_pct"])

        us_geo = next((g for g in data["geographies"] if g["country"] == "US"), {"pct": 0.0, "prev_pct": 0.0})
        tier1_geos = [g for g in data["geographies"] if g["country"] in ("US", "UK", "CA", "AU")]
        tier1_now = round(sum(float(g["pct"]) for g in tier1_geos), 1)
        tier1_prev = round(sum(float(g["prev_pct"]) for g in tier1_geos), 1)
        us_dod_diff = float(us_geo["pct"]) - float(us_geo["prev_pct"])
        tier1_dod_diff = tier1_now - tier1_prev

        if has_7d and snap_7d and snap_7d.get("views") is not None and snap_7d.get("subscribers") is not None:
            v_7d_val = int(snap_7d["views"])
            wh_7d_val = float(snap_7d["watch_hours"])
            subs_7d_val = int(snap_7d["subscribers"])
            shown_7d_val = int(cs["shown_7d"] or 0)
            eng_7d_val = int(cs["engaged_7d"] or 0)
            viewed_7d_val = float(snap_7d["viewed_pct"])
            avd_7d_val = float(snap_7d["avd_seconds"])
            apv_7d_val = float(snap_7d["apv_pct"])
            sf_7d_val = float(snap_7d["shorts_feed_pct"])
            us_7d_val = float(snap_7d["us_pct"])
            t1_7d_val = float(snap_7d["tier1_pct"])

            views_7d_gain = views_now - v_7d_val
            views_7d_pct = (views_7d_gain / max(1, v_7d_val)) * 100.0
            shown_7d_gain = shown_now - shown_7d_val
            eng_7d_gain = (engaged_now - eng_7d_val) if engaged_now is not None else 0
            eng_7d_pct = (eng_7d_gain / max(1, eng_7d_val)) * 100.0
            wh_7d_gain = wh_now - wh_7d_val
            wh_7d_pct = (wh_7d_gain / max(0.1, wh_7d_val)) * 100.0
            subs_7d_gain = subs_now - subs_7d_val
            s7_p1k = (subs_7d_val / max(1, v_7d_val)) * 1000.0

            shown_7d_cell = f"{shown_7d_val:,}"
            v_7d_cell = f"{v_7d_val:,}"
            eng_7d_cell = f"{eng_7d_val:,}"
            wh_7d_cell = f"{wh_7d_val:.1f}h"
            subs_7d_cell = f"{subs_7d_val:,} (`{s7_p1k:.2f}`)"
            rt48_7d_cell = f"{int(snap_7d['realtime_48h']):,}"

            shown_7d_delta_cell = f"`{shown_7d_gain:+,}` (`{shown_7d_gain / 6.0:.0f}/d`)"
            views_7d_delta_cell = f"**`{views_7d_gain:+,}` (`{views_7d_gain / 6.0:+.0f}/d`)**"
            eng_7d_delta_cell = f"**`{eng_7d_gain:+,}` (`{eng_7d_gain / 6.0:+.0f}/d`)**" if engaged_now is not None else "`unscraped`"
            wh_7d_delta_cell = f"**`{wh_7d_gain:+.1f}h` (`{wh_7d_gain / 6.0:+.1f}h/d`)**"
            subs_7d_delta_cell = f"**`{subs_7d_gain:+d}` (`{subs_7d_gain / 6.0:+.1f}/d`)**"
            rt48_7d_delta_cell = f"**`Avg {rt48_avg:,}`** (`Peak {rt48_peak:,}`)"

            views_sig_cell = f"🟢 `{views_7d_pct:+.1f}%`"
            eng_sig_cell = f"🟢 `{eng_7d_pct:+.1f}%`" if engaged_now is not None else "🟡 `unscraped`"
            wh_sig_cell = f"🟢 `{wh_dod_pct:+.1f}%`" if wh_7d_val <= 0 else f"🟢 `{wh_7d_pct:+.1f}%`"

            viewed_7d_cell = f"{viewed_7d_val:.1f}%"
            avd_7d_cell = f"{avd_7d_val:.1f}s"
            apv_7d_cell = f"{apv_7d_val:.1f}%"
            apv_drop_cell = f"`7d {apv_now - apv_7d_val:+.1f}%p` (`1d {apv_dod_diff:+.1f}%p`)"

            sf_7d_cell = f"{sf_7d_val:.1f}%"
            sf_7d_delta_cell = f"**`{float(sf_rec['pct']) - sf_7d_val:+.1f}%p`** (`{sf_dod_diff:+.1f}%p`)"
            geo_7d_cell = f"{us_7d_val:.1f}% / {t1_7d_val:.1f}%"
            geo_7d_delta_cell = f"**`{float(us_geo['pct']) - us_7d_val:+.1f}%p / {tier1_now - t1_7d_val:+.1f}%p`** (`{us_dod_diff:+.1f}%p / {tier1_dod_diff:+.1f}%p`)"

            pulse_subs_lbl = f"{subs_now:,} ({subs_7d_gain:+d})"
            pulse_wh_lbl = f"{wh_now:.1f}h ({wh_7d_gain:+.1f}h)"
            w1_t1 = f"`Shown {shown_7d_gain:+,}` · `Views {views_7d_gain:+,}`"
            w1_t2 = f"`Viewed {viewed_now - viewed_7d_val:+.1f}%p` · `APV {apv_now - apv_7d_val:+.1f}%p`"
            w1_t3 = f"`US {float(us_geo['pct']) - us_7d_val:+.1f}%p` · `Subs {subs_7d_gain:+d}`"
        else:
            shown_7d_cell = "-"
            v_7d_cell = "-"
            eng_7d_cell = "-"
            wh_7d_cell = "-"
            subs_7d_cell = "-"
            rt48_7d_cell = "-"

            shown_7d_delta_cell = "`collecting`"
            views_7d_delta_cell = "`collecting`"
            eng_7d_delta_cell = "`collecting`"
            wh_7d_delta_cell = "`collecting`"
            subs_7d_delta_cell = "`collecting`"
            rt48_7d_delta_cell = f"`collecting` (`Peak {rt48_peak:,}`)"

            views_sig_cell = f"🟢 `{views_dod_pct:+.1f}%`"
            eng_sig_cell = f"🟢 `{engaged_dod_pct:+.1f}%`" if engaged_now is not None else "🟡 `unscraped`"
            wh_sig_cell = f"🟢 `{wh_dod_pct:+.1f}%`"

            viewed_7d_cell = "-"
            avd_7d_cell = "-"
            apv_7d_cell = "-"
            apv_drop_cell = f"`7d collecting` (`1d {apv_dod_diff:+.1f}%p`)"

            sf_7d_cell = "-"
            sf_7d_delta_cell = f"`collecting` (`{sf_dod_diff:+.1f}%p`)"
            geo_7d_cell = "-"
            geo_7d_delta_cell = f"`collecting` (`{us_dod_diff:+.1f}%p / {tier1_dod_diff:+.1f}%p`)"

            pulse_subs_lbl = f"{subs_now:,} (1d {subs_dod_diff:+d})"
            pulse_wh_lbl = f"{wh_now:.1f}h (1d {wh_dod_diff:+.1f}h)"
            w1_t1 = "`collecting (<7d)`"
            w1_t2 = "`collecting (<7d)`"
            w1_t3 = "`collecting (<7d)`"

        # Quartiles Q1-Q4 with Inter-Quartile Drop-Off (Delta Q) & Cohort Split
        q_w1_list = snap_7d["quartiles"] if (snap_7d and len(snap_7d.get("quartiles") or []) >= 4) else None
        q_targets = [70.0, 65.0, 62.0, 60.0]
        q_clip_notes = [
            "Clips 1–2",
            "⚠️ **Clips 3–5**",
            "⚠️ **Clips 6–8**",
            "Clips 9–10",
        ]
        q_rows = []
        prev_q_all = 100.0
        prev_q_rec = 100.0
        for idx_q, q in enumerate(r_quarts):
            q_now = float(q["today_pct"])
            q_prv = float(q["prev_pct"])
            q_w1_cell = f"{float(q_w1_list[idx_q]):.1f}%" if (q_w1_list and idx_q < len(q_w1_list)) else "-"
            q_rec = recent_q[idx_q] if idx_q < len(recent_q) else q_now
            q_lat_s = (
                f"{float(latest_rec.get(f'ret_q{idx_q + 1}_pct', q_now)):.1f}%"
                if latest_rec
                else "-"
            )
            q_prv_s = (
                f"{float(prev_rec.get(f'ret_q{idx_q + 1}_pct', 0.0)):.1f}%"
                if prev_rec
                else "-"
            )
            drop_all = q_now - prev_q_all
            drop_rec = q_rec - prev_q_rec
            prev_q_all = q_now
            prev_q_rec = q_rec
            step_lbl = "0%→Q1" if idx_q == 0 else f"Q{idx_q}→Q{idx_q + 1}"
            q_t = q_targets[idx_q] if idx_q < len(q_targets) else 60.0
            q_g_all = q_now - q_t
            q_g_rec = q_rec - q_t
            q_dot = "🟢" if q_now >= q_t else ("🟡" if q_now >= q_t - 10.0 else "🔴")
            q_rec_dot = "🟢" if q_rec >= q_t else ("🟡" if q_rec >= q_t - 10.0 else "🔴")
            q_rows.append(
                f"| **{q['quartile']}** | {q_w1_cell} | {q_prv:.1f}% | **{q_now:.1f}%** | **{q_rec:.1f}%** | `{q_lat_s} / {q_prv_s}` | `{step_lbl}: {drop_all:+.1f}%p` (`Rec {drop_rec:+.1f}%p`) · {q_clip_notes[idx_q]} | `{q_t:.0f}%` | {q_dot} `{q_g_all:+.1f}%p` / {q_rec_dot} `{q_g_rec:+.1f}%p` |"
            )

        q1_val = float(r_quarts[0]["today_pct"]) if r_quarts else 0.0
        q2_val = float(r_quarts[1]["today_pct"]) if len(r_quarts) > 1 else 0.0
        q3_val = float(r_quarts[2]["today_pct"]) if len(r_quarts) > 2 else 0.0
        q4_val = float(r_quarts[-1]["today_pct"]) if r_quarts else 0.0
        q1_q3_drop = q3_val - q1_val

        data_mode = data.get("data_source_mode", "LOCAL_SNAPSHOT_BASELINE")
        snapshot_json_rel = f"BCI_Shorts_Channel/reports/daily/{data['report_date']}_studio_metrics.json"
        prov_sha = data.get("provenance_sha256", "N/A")

        # 5-Axis Executive Traffic Light Assessment for Section 0
        s1_pass = views_dod_diff >= 500 or subs_dod_diff >= 1
        s1_dot = "🟢" if s1_pass else ("🟡" if views_dod_diff >= 0 else "🔴")
        s1_note = "가파른 우상향" if s1_pass else "노출 탄력 점검"

        s2_pass = viewed_now >= 70.0
        s2_dot = "🟢" if s2_pass else ("🟡" if viewed_now >= 65.0 else "🔴")
        s2_note = "목표선 돌파" if s2_pass else f"전체 기준 목표 대비 {viewed_gap:+.1f}%p (최근 3편 {recent_viewed:.1f}%)"

        s3_pass = apv_now >= 60.0
        s3_dot = "🟢" if s3_pass else ("🟡" if apv_now >= 50.0 else "🔴")
        s3_note = "최상위권 유지" if s3_pass else "중반부 클립 이탈 보정 필요"

        s4_pass = float(us_geo["pct"]) >= 45.0 and float(sf_rec["pct"]) >= 70.0
        s4_dot = "🟢" if s4_pass else "🟡"
        s4_note = "북미 알고리즘 안착" if s4_pass else "영어권/피드 비중 확대 필요"

        pv_records = list(data.get("per_video_records") or [])
        sl_summary = dict(data.get("short_link_summary") or {})
        pub_cohorts = [r for r in pv_records if str(r.get("status", "")).lower() == "published"] or pv_records
        pid_to_cohort_num: dict[str, int] = {
            str(r.get("project_id", "")): idx_c + 1
            for idx_c, r in enumerate(pub_cohorts)
        }
        pub_total_cnt = len(pub_cohorts)
        linked_cnt = int(
            sl_summary.get("related_verified_count", sum(1 for r in pub_cohorts if r.get("related_verified")))
        )
        playlist_cnt = int(
            sl_summary.get("playlist_verified_count", sum(1 for r in pub_cohorts if r.get("playlist_verified")))
        )
        starved_cohorts = [
            (idx_c + 1, r)
            for idx_c, r in enumerate(pub_cohorts)
            if r.get("measured", True) and int(r.get("views", 0)) < 50 and int(r.get("impressions", 0)) <= 100
        ]
        starved_cnt = len(starved_cohorts)
        ring_complete = bool(pub_total_cnt > 0 and linked_cnt >= pub_total_cnt)

        sched_cnt = int(inv.get("scheduled_count", 0))
        sched_days = round(sched_cnt / 2.0, 1)
        s5_pass = bool(ring_complete and starved_cnt == 0 and sched_cnt >= 2)
        s5_dot = "🔴" if (starved_cnt > 0 or sched_cnt == 0) else ("🟢" if s5_pass else "🟡")
        s5_curr = (
            f"**Related {linked_cnt}/{pub_total_cnt}** · **시드 대기 {starved_cnt}편** · **예약 {sched_cnt}개**"
            if pub_total_cnt > 0
            else f"**예약 {sched_cnt}개**"
        )
        if not ring_complete and pub_total_cnt > 0:
            s5_note = f"**Related Video 연결({linked_cnt}/{pub_total_cnt}) 및 프라임 슬롯 예약 필요**"
        elif starved_cnt > 0 and sched_cnt == 0:
            s5_note = f"**시드 순환 링 활성({linked_cnt}/{pub_total_cnt}) · 미확산 {starved_cnt}편 관찰 및 예약 보충 필요**"
        elif starved_cnt > 0:
            s5_note = f"**시드 순환 링 활성({linked_cnt}/{pub_total_cnt}) · 미확산 코호트 {starved_cnt}편 전이 관찰**"
        elif sched_cnt == 0:
            s5_note = "**시드 링 정상 · 향후 프라임 슬롯 예약 보충 필요**"
        else:
            s5_note = f"**Related {linked_cnt}/{pub_total_cnt} 순환 링 & 예약 큐 정상**"

        s0_alert_suffix = (
            f" · ⚠️ 시드 미확산 {starved_cnt}건 / 예약 {sched_cnt}건"
            if (starved_cnt > 0 or sched_cnt == 0)
            else f" · Related {linked_cnt}/{pub_total_cnt} 가동"
        )
        if not ring_complete and pub_total_cnt >= 2:
            action_1line = (
                f"**Gear 5**에서 `studio-link --action apply`로 공개 쇼츠 `{pub_total_cnt}`편의 "
                f"**`Related Video` 시드 구조 순환 링(`{linked_cnt}/{pub_total_cnt}`)**을 즉시 연결하고, "
                f"클립 3~8 구간(`Q1→Q3 {q1_q3_drop:+.1f}%p`) 컷 전환 속도를 높입니다."
            )
        else:
            action_1line = (
                f"**Gear 5** `Related Video` 시드 순환 링(`{linked_cnt}/{pub_total_cnt}`) 전이 효율을 추적하면서, "
                f"v8 통과 파일럿을 프라임 슬롯(`12:00 ET` / `20:00 ET`)에 보충하고 클립 3~8 구간(`Q1→Q3 {q1_q3_drop:+.1f}%p`) 전환 밀도를 높입니다."
            )

        cohort_rows: list[str] = []
        for idx_c, rec_c in enumerate(pub_cohorts):
            dur_lbl = int(round(float(rec_c.get("duration_seconds", 85.0))))
            pub_slot_lbl = str(
                rec_c.get("published_slot_str")
                or f"{str(rec_c.get('date', ''))[5:]} {rec_c.get('time_et', '12:00')}"
            )
            try:
                gen_et_raw = str(data.get("generated_at_et", "")).replace(" ET", "").strip()
                if gen_et_raw.startswith(str(data["report_date"])) and len(gen_et_raw) >= 16:
                    dt_rep = datetime.strptime(gen_et_raw[:16], "%Y-%m-%d %H:%M")
                else:
                    dt_rep = datetime.strptime(f"{data['report_date']} 12:00", "%Y-%m-%d %H:%M")
                dt_pub_c = datetime.strptime(
                    f"{rec_c.get('date', data['report_date'])} {rec_c.get('time_et', '12:00')}",
                    "%Y-%m-%d %H:%M",
                )
                elapsed_h = max(1, int(round((dt_rep - dt_pub_c).total_seconds() / 3600.0)))
                elapsed_lbl = f"+{elapsed_h}h"
            except Exception:
                elapsed_lbl = "+24h"

            c_measured = bool(rec_c.get("measured", True))
            c_views = int(rec_c.get("views", 0))
            c_imp = int(rec_c.get("impressions", 0))
            shown_to_views_lbl = f"`{c_imp:,} → {c_views:,}`" if c_measured else "`Pending`"
            if not c_measured:
                tts_lbl = f"`Indexing ({elapsed_lbl})`"
            elif c_views >= 250:
                tts_lbl = "`Seeded (<24h)`"
            elif c_views >= 50:
                tts_lbl = "`Search / Niche`"
            else:
                tts_lbl = f"`Unseeded ({elapsed_lbl})`"

            tgt_pid = str(rec_c.get("related_target_project_id", ""))
            tgt_num = pid_to_cohort_num.get(tgt_pid)
            if rec_c.get("related_verified") and tgt_num:
                rel_lbl = f"`✅ → Cohort #{tgt_num}`"
            elif rec_c.get("related_verified"):
                rel_lbl = "`✅ Linked`"
            elif tgt_num:
                rel_lbl = f"`Plan → Cohort #{tgt_num}`"
            elif c_views >= 250:
                rel_lbl = "`Anchor (Unlinked)`"
            else:
                rel_lbl = "`Unlinked`"

            act_var = str(rec_c.get("active_variant", "A"))
            ctr_c = float(rec_c.get("ctr_pct", 0.0))
            if not c_measured:
                z_lbl = "`Scheduled`"
            elif c_views >= 50:
                z_lbl = f"`Var {act_var} ({ctr_c:.1f}%)`"
            else:
                z_lbl = "`Hold`"

            delta_c = int(rec_c.get("views_delta_num", 0))
            if not c_measured:
                sig_lbl = f"🟡 `Wait {elapsed_lbl}`"
            elif c_views >= 250:
                sig_lbl = f"🟢 `{delta_c:+,}/1d`"
            elif c_views >= 50:
                sig_lbl = f"🟡 `{delta_c:+,}/1d`"
            else:
                sig_lbl = f"🔴 `Shown {c_imp:,}`"

            cohort_rows.append(
                f"| **Cohort #{idx_c + 1} (`{dur_lbl}s`)** | `{pub_slot_lbl}` (`{elapsed_lbl}`) | "
                f"{shown_to_views_lbl} | {tts_lbl} | {rel_lbl} | {z_lbl} | {sig_lbl} |"
            )
        if not cohort_rows:
            cohort_rows.append(
                "| **Cohort #1 (`85s`)** | `Pending` (`0h`) | `Pending` | `Indexing` | `Unlinked` | `Scheduled` | 🔴 `Shown 0` |"
            )

        if starved_cohorts:
            first_st_num, first_st_rec = starved_cohorts[0]
            first_st_imp = int(first_st_rec.get("impressions", 0))
            if ring_complete:
                bn1_row = (
                    f"| 🔴 | **Cohort #{first_st_num} Seed Rescue (`{starved_cnt}` starved)** | "
                    f"`Shown {shown_dod_diff:+,}` (`#{first_st_num}: {first_st_imp:,}`) | "
                    f"Feed concentration on top anchors | "
                    f"**Gear 5**: `Related Video` ring active (`{linked_cnt}/{pub_total_cnt}`) + queue next v5 Short |"
                )
            else:
                bn1_row = (
                    f"| 🔴 | **Cohort #{first_st_num} Seed Delay** | "
                    f"`Shown {shown_dod_diff:+,}` (`#{first_st_num}: {first_st_imp:,}`) | "
                    f"Anchor traffic not yet bridged via `Related Video` | "
                    f"**Gear 5**: Run `studio-link --action apply` (`{linked_cnt}/{pub_total_cnt}`) |"
                )
        else:
            bn1_row = (
                f"| {'🟢' if sched_cnt >= 2 else '🔴'} | **Prime-Slot Staging Buffer** | "
                f"`Scheduled {sched_cnt}` (`Linked {linked_cnt}/{pub_total_cnt}`) | "
                f"{'Healthy multi-cohort seed distribution' if sched_cnt >= 2 else 'Upcoming scheduled slot buffer is empty'} | "
                f"**Gear 5**: Maintain `12:00 ET` / `20:00 ET` buffer + `Related Video` ring |"
            )

        pass_cnt = sum([1 if s1_pass else 0, 1 if s2_pass else 0, 1 if s3_pass else 0, 1 if s4_pass else 0, 1 if s5_pass else 0])
        overall_dot = "🟢" if pass_cnt >= 4 else ("🟡" if pass_cnt >= 3 else "🔴")
        overall_label = "순항 중" if pass_cnt >= 4 else ("점검 필요" if pass_cnt >= 3 else "경고")
        rec_hook_dot = "🟢" if recent_viewed >= 70.0 else ("🟡" if recent_viewed >= 60.0 else "🔴")
        rec_avd_dot = "🟢" if recent_avd >= 25.0 else ("🟡" if recent_avd >= 18.0 else "🔴")
        rec_apv_dot = "🟢" if recent_apv >= 60.0 else ("🟡" if recent_apv >= 50.0 else "🔴")

        reg_alert = data.get("retention_regression_alert")
        if not isinstance(reg_alert, dict):
            reg_alert = self.detect_retention_regression_alert(
                pv_records,
                report_date=str(data.get("report_date") or ""),
                generated_at_et=str(data.get("generated_at_et") or ""),
            )
        reg_alert_block = ""
        if reg_alert.get("triggered"):
            reg_banner = str(reg_alert.get("banner") or "⚠️ [RETENTION_REGRESSION_ALERT]")
            reg_alert_block = f"\n> [!CAUTION]\n> **{reg_banner}**\n"

        report_md = f"""# 🚦 ALL ABOUT BRAIN — Daily Growth Report ({data['report_date']})
{reg_alert_block}
## 🚦 0. 오늘의 채널 종합 진단: **{overall_dot} {overall_label} (핵심 {pass_cnt}/5 통과{s0_alert_suffix})**

> **🚦 0. Executive Growth Pulse (7d)**: 🟢 **Subs** `{pulse_subs_lbl}` ｜ 🟢 **Shown→Views→Engaged** `{shown_now:,} → {views_now:,} → {engaged_now_lbl} ({shown_dod_diff:+,}/{views_dod_diff:+,}/{engaged_dod_lbl})` ｜ 🟢 **Watch** `{pulse_wh_lbl}` ｜ {s2_dot} **3s Hook** `{viewed_now:.1f}% (Rec {recent_viewed:.1f}%)` ｜ 🟢 **APV** `{apv_now:.1f}% ({avd_now:.1f}s)` ｜ 🟡 **48h** `{rt48_now:,} ({rt48_pct:+.1f}%)`

| 진단 영역 | 상태 | 현재 수치 (전일 대비) | 기준 (Gate) | 한줄 진단 |
| :--- | :---: | :---: | :---: | :--- |
| **① 노출·구독 성장** | {s1_dot} | **Views {views_now:,}** (`{views_dod_pct:+.1f}%`) · **Subs {subs_now:,}** (`{subs_dod_diff:+d}`) | 일 `+500` | {s1_note} |
| **② 초반 3초 훅** | {s2_dot} | **{viewed_now:.1f}%** (최근 3개 **{recent_viewed:.1f}%**) | `>= 70%` | {s2_note} |
| **③ 끝까지 시청률** | {s3_dot} | **{apv_now:.1f}%** (`평균 {avd_now:.1f}s`) | `>= 60%` | {s3_note} |
| **④ 북미·피드 타겟** | {s4_dot} | **미국 {us_geo['pct']:.1f}%** · **피드 {sf_rec['pct']:.1f}%** | `US >= 45%` | {s4_note} |
| **⑤ 시드·예약 큐** | {s5_dot} | {s5_curr} | `24h 내 시드` | {s5_note} |

> **💡 오늘의 핵심 1줄 액션**: {action_1line}

---

## 1. Volume & Exposure Funnel

![Section 1: Channel Exposure Funnel & Growth]({sec_imgs['sec1']})

| Metric | 7d Ago (`{d7_label}`) | 3d Ago (`{d3_label}`) | Yesterday (`{data['previous_report_date']}`) | **Today (`{data['report_date']}`)** | **1d Δ** | **7d Δ (`MA`)** | Gate | Signal |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Shown in feed** | {shown_7d_cell} | {shown_3d_cell} | {shown_prev:,} | **{shown_now:,}** | **`{shown_dod_diff:+,}` (`{shown_dod_pct:+.1f}%`)** | {shown_7d_delta_cell} | `+500/d` | 🟡 `{shown_dod_diff:+,}` |
| **Views (`Viewed`)** | {v_7d_cell} | {v_3d_cell} | {views_prev:,} | **{views_now:,}** | **`{views_dod_diff:+,}` (`{views_dod_pct:+.1f}%`)** | {views_7d_delta_cell} | `>=70%` | {views_sig_cell} |
| **Engaged Views** | {eng_7d_cell} | {eng_3d_cell} | {engaged_prev_lbl} | **{engaged_now_lbl}** | {engaged_dod_cell} | {eng_7d_delta_cell} | `>=55%` | {eng_sig_cell} |
| **Watch Time (`h`)** | {wh_7d_cell} | {wh_3d_cell} | {wh_prev:.1f}h | **{wh_now:.1f}h** | `{wh_dod_diff:+.1f}h ({wh_dod_pct:+.1f}%)` | {wh_7d_delta_cell} | `>0h` | {wh_sig_cell} |
| **Subscribers (`/1K`)** | {subs_7d_cell} | {subs_3d_cell} | {subs_prev:,} (`{subs_per_1k_prev:.2f}`) | **{subs_now:,}** (`{subs_per_1k:.2f}`) | `{subs_dod_diff:+d} ({(subs_dod_diff/max(1,subs_prev))*100:+.1f}%)` | {subs_7d_delta_cell} | `>=2.50` | 🟢 `{subs_per_1k:.2f}/1K` |
| **Realtime 48h (`60m`)** | {rt48_7d_cell} | {rt48_3d_cell} | {rt48_prev:,} | **{rt48_now:,}** (`{f"{int(ck['realtime_60m_views']):,}" if ck.get("realtime_60m_views") is not None else "unscraped"}`) | **`{rt48_diff:+,}` (`{rt48_pct:+.1f}%`)** | {rt48_7d_delta_cell} | `>={rt48_avg:,}` | 🟡 `{rt48_pct:+.1f}%` |

---

## 2. Retention & Cohort Drop-Off (`ΔQ`)

![Section 2: Retention Cohort Split & Drop-Off]({sec_imgs['sec2']})

| Metric | 7d Ago | Yesterday | **All** | **Recent 3** | **Latest / Next** | **Drop-Off (`ΔQ`)** | Gate | Signal (`All` / `Rec`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
| **3s Hook (`Viewed %`)** | {viewed_7d_cell} | {viewed_prev:.1f}% | **{viewed_now:.1f}%** | **{recent_viewed:.1f}%** | `{lat_hook_s} / {prv_hook_s}` | `100%→3s: -{100.0 - viewed_now:.1f}%p` (`Rec -{100.0 - recent_viewed:.1f}%p`) | `70%` | {s2_dot} `{viewed_gap:+.1f}%p` / {rec_hook_dot} `{recent_viewed - 70.0:+.1f}%p` |
| **AVD (`s`)** | {avd_7d_cell} | {avd_prev:.1f}s | **{avd_now:.1f}s** | **{recent_avd:.1f}s** | `{lat_avd_s} / {prv_avd_s}` | `Len {avg_len:.1f}s` (`Rec {recent_len:.1f}s`) | `25s` | 🟢 `{avd_now - 25.0:+.1f}s` / {rec_avd_dot} `{recent_avd - 25.0:+.1f}s` |
| **APV (`%`)** | {apv_7d_cell} | {apv_prev:.1f}% | **{apv_now:.1f}%** | **{recent_apv:.1f}%** | `{lat_avd_s if False else lat_apv_s} / {prv_apv_s}` | {apv_drop_cell} | `60%` | {s3_dot} `{apv_gap:+.1f}%p` / {rec_apv_dot} `{recent_apv - 60.0:+.1f}%p` |
{chr(10).join(q_rows)}

---

## 3. Traffic & Geographies

![Section 3: High-Signal Traffic & Tier-1 Share]({sec_imgs['sec3']})

| Metric | 7d Ago (`{d7_label}`) | Yesterday (`{data['previous_report_date']}`) | **Today (`{data['report_date']}`)** | **7d Δ (`1d Δ`)** | Gate | Signal |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Shorts Feed (`%`)** | {sf_7d_cell} | {sf_rec['prev_pct']:.1f}% | **{sf_rec['pct']:.1f}%** (`{sf_rec['views']:,}`) | {sf_7d_delta_cell} | `>=70%` | 🟢 `{sf_rec['pct'] - 70.0:+.1f}%p` |
| **US / Tier-1 (`%`)** | {geo_7d_cell} | {us_geo['prev_pct']:.1f}% / {tier1_prev:.1f}% | **{us_geo['pct']:.1f}% / {tier1_now:.1f}%** | {geo_7d_delta_cell} | `45% / 55%` | 🟢 `{us_geo['pct'] - 45.0:+.1f}%p / {tier1_now - 55.0:+.1f}%p` |

---

## 4. Seed & Queue Tracker + Pipeline Calibration

> **Queue & Operations Health**: 🌐 **Published** `{inv.get('published_count', 0)}` ｜ 📅 **Scheduled** `{sched_cnt} ({sched_days:.1f}d)` ｜ 🔒 **`Unlisted (Staged)`** `{inv.get('unlisted_staged_count', 0)}` ｜ 🔗 **Related Ring** `{linked_cnt}/{pub_total_cnt}` ｜ 🛠️ **Quarantine** `{inv.get('quarantine_count', 0)}`

| Cohort | Published (`Elapsed`) | `Shown → Views` | `Time-to-Seed` | `Related Video` | `Z-Test` | Signal |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
{chr(10).join(cohort_rows)}

![Section 4: Channel KPI Gap vs Target Gate]({sec_imgs['sec4']})

| Signal | Bottleneck | Metric | Cause | Pipeline Action |
| :---: | :--- | :---: | :--- | :--- |
{bn1_row}
| 🟡 | **Mid-Clip Drop (`Q1→Q3`)** | `{q1_q3_drop:+.1f}%p` (`-{q1_val - q2_val:.1f}%p / -{q2_val - q3_val:.1f}%p`) | Pacing drag in Clips 3–8 (`{avg_len:.0f}s`) | **Gear 2/3**: `0.28s` pre-pivot hold, `<=18w/clip`, 4-color cutaway |
| 🟡 | **Cumulative Hook (`All`)** | `All {viewed_now:.1f}%` vs `Rec {recent_viewed:.1f}%` | Early cohort hook dilution | **Gear 2**: Lock `<=12w` case hook (`>=80%` Viewed) |

---

## 5. 7-Day Targets (`W+1`)

| Axis | 7d Trend | Current (`All / Rec`) | **W+1 Target** | Focus |
| :--- | :---: | :---: | :---: | :--- |
| **① Funnel & Seed** | {w1_t1} | `{shown_now:,} → {views_now:,} ({engaged_now_lbl})` | **`Shown +800/d` · `Seed <=24h` (`5,000+`)** | Multi-video seeding via `Related Video` chain |
| **② Retention (`ΔQ`)** | {w1_t2} | `{viewed_now:.1f}% / {apv_now:.1f}%` (`{recent_viewed:.1f}% / {recent_apv:.1f}%`) | **`All Viewed >=72%` · `Q1→Q3 <=-5.0%p`** | Compress Clips 3–8 drop (`{q1_q3_drop:+.1f}%p → -5.0%p`) |
| **③ Market & Subs** | {w1_t3} | `US {us_geo['pct']:.1f}% · T1 {tier1_now:.1f}%` (`{subs_now:,} · {subs_per_1k:.2f}/1K`) | **`US >=55%` · `T1 >=62%` (`Subs 20+`)** | Habit, memory & sleep neural circuit topics |

---
> **🔐 Provenance**: `{snapshot_json_rel}` | **Dashboard**: `{charts_filename}` | **Mode**: `{data_mode}` | **SHA-256**: `{prov_sha}`
"""
        return report_md

    def render_video_detail_report(
        self,
        data: dict[str, Any],
        video_charts_filename: str,
    ) -> str:
        """
        Renders the standalone Per-Video Detailed Report (`YYYY-MM-DD_video_detail_report.md`):
        - Section 0: All-Videos Traffic-Light Matrix + Comparison Chart
        - Section 1: Deep-Dive Diagnostic Cards for every published video (Cohort #1..#N)
        - Section 2: Upcoming Scheduled / Staged Queue Status
        """
        pv_records = list(data.get("per_video_records") or [])
        pub_cohorts = [r for r in pv_records if str(r.get("status", "")).lower() == "published"] or pv_records
        ab_by_pid = {str(a.get("project_id", "")): a for a in (data.get("ab_test_rows") or [])}
        upcoming = list(data.get("upcoming_schedule") or [])
        inv = data.get("inventory_summary") or {}

        pid_to_cohort_num: dict[str, int] = {
            str(r.get("project_id", "")): idx_c + 1
            for idx_c, r in enumerate(pub_cohorts)
        }

        green_cnt = 0
        yellow_cnt = 0
        red_cnt = 0
        matrix_rows: list[str] = []
        detail_cards: list[str] = []

        top_views_rec = max(pub_cohorts, key=lambda r: int(r.get("views", 0)), default=None)
        top_avd_rec = max(pub_cohorts, key=lambda r: float(r.get("avd_seconds", 0.0)), default=None)
        top_delta_rec = max(pub_cohorts, key=lambda r: int(r.get("views_delta_num", 0)), default=None)

        for idx_c, r in enumerate(pub_cohorts):
            c_num = idx_c + 1
            pid = str(r.get("project_id", ""))
            vid = str(r.get("video_id", ""))
            title = str(r.get("title") or pid)
            url = str(r.get("shorts_url") or (f"https://www.youtube.com/shorts/{vid}" if vid else ""))
            title_md = f"[{title}]({url})" if url else title
            short_title = title if len(title) <= 38 else title[:35] + "..."
            short_title_md = f"[{short_title}]({url})" if url else short_title

            pillar = str(r.get("pillar") or DEFAULT_FALLBACK_PILLAR)
            dur = float(r.get("duration_seconds", 85.0))
            clips = int(r.get("clip_count", 10))
            words = int(r.get("word_count", 0))
            prof_raw = str(r.get("production_profile", ""))
            if prof_raw == "neuro_diorama" or dur >= 140.0:
                fmt_badge = f"v6 Diorama (`{dur:.0f}s`)"
                fmt_detail = f"Schema v6 Neuro-Diorama (`{dur:.1f}s` · `{clips}클립` · `{words}w`)"
            elif dur < 55.0:
                fmt_badge = f"Legacy Short (`{dur:.0f}s`)"
                fmt_detail = f"초기 단축 포맷 (`{dur:.1f}s` · `{clips}클립` · `{words}w`)"
            elif prof_raw == "shorts_v5":
                fmt_badge = f"v5 Spine (`{dur:.0f}s`)"
                fmt_detail = f"Schema v5 10-Clip Spine (`{dur:.1f}s` · `{clips}클립` · `{words}w`)"
            else:
                fmt_badge = f"10-Clip (`{dur:.0f}s`)"
                fmt_detail = f"10-Clip Full Spine (`{dur:.1f}s` · `{clips}클립` · `{words}w`)"

            pub_slot_lbl = str(
                r.get("published_slot_str")
                or f"{str(r.get('date', ''))[5:]} {r.get('time_et', '12:00')}"
            )
            try:
                gen_et_raw = str(data.get("generated_at_et", "")).replace(" ET", "").strip()
                if gen_et_raw.startswith(str(data["report_date"])) and len(gen_et_raw) >= 16:
                    dt_rep = datetime.strptime(gen_et_raw[:16], "%Y-%m-%d %H:%M")
                else:
                    dt_rep = datetime.strptime(f"{data['report_date']} 12:00", "%Y-%m-%d %H:%M")
                dt_pub_c = datetime.strptime(
                    f"{r.get('date', data['report_date'])} {r.get('time_et', '12:00')}",
                    "%Y-%m-%d %H:%M",
                )
                elapsed_h = max(1, int(round((dt_rep - dt_pub_c).total_seconds() / 3600.0)))
                elapsed_lbl = f"+{elapsed_h}h"
            except Exception:
                elapsed_lbl = "+24h"

            measured = bool(r.get("measured", True))
            imp = int(r.get("impressions", 0))
            views = int(r.get("views", 0))
            v_prev = int(r.get("views_prev", 0))
            delta_v = int(r.get("views_delta_num", 0))
            growth_pct = float(r.get("views_growth_pct", 0.0))
            wh = float(r.get("watch_hours", 0.0))
            subs = int(r.get("subs_gained", 0))
            subs_per_1k = (subs / max(1, views)) * 1000.0 if views > 0 else 0.0
            likes = int(r.get("likes", 0))
            comments = int(r.get("comments", 0))
            shares = int(r.get("shares", 0))
            top_tr = str(r.get("top_traffic") or "Shorts 피드")

            vw_pct = float(r.get("viewed_pct", 0.0))
            sw_pct = float(r.get("swiped_pct", 0.0))
            avd_s = float(r.get("avd_seconds", 0.0))
            apv_pct = float(r.get("apv_pct", 0.0))
            rq1 = float(r.get("ret_q1_pct", 0.0))
            rq2 = float(r.get("ret_q2_pct", 0.0))
            rq3 = float(r.get("ret_q3_pct", 0.0))
            rq4 = float(r.get("ret_q4_pct", 0.0))
            ctr_pct = float(r.get("ctr_pct", 0.0))

            # Traffic light classification per video
            if not measured:
                v_dot = "🟡"
                v_status_short = f"집계 대기 ({elapsed_lbl})"
                yellow_cnt += 1
            elif views >= 250:
                v_dot = "🟢"
                green_cnt += 1
                if delta_v >= 50:
                    v_status_short = f"시드 가속 중 ({delta_v:+,}/1d)"
                else:
                    v_status_short = "주력 시드 앵커"
            elif views >= 50:
                v_dot = "🟡"
                yellow_cnt += 1
                if vw_pct < 50.0:
                    v_status_short = "검색 유지 · 초반 훅 병목"
                else:
                    v_status_short = "1차 시드 탐색"
            else:
                v_dot = "🔴"
                red_cnt += 1
                v_status_short = f"시드 대기 (Shown {imp:,})"

            hook_dot = "🟢" if vw_pct >= 70.0 else ("🟡" if vw_pct >= 65.0 else "🔴")
            apv_dot = "🟢" if apv_pct >= 60.0 else ("🟡" if apv_pct >= 50.0 else "🔴")

            tgt_pid = str(r.get("related_target_project_id", ""))
            tgt_num = pid_to_cohort_num.get(tgt_pid)
            if r.get("related_verified") and tgt_num:
                rel_lbl = f"`✅ → #{tgt_num}`"
                rel_detail = f"✅ 활성 (`→ Cohort #{tgt_num}` · `{tgt_pid}`)"
            elif r.get("related_verified"):
                rel_lbl = "`✅ Linked`"
                rel_detail = f"✅ 활성 (`{tgt_pid or '연결 완료'}`)"
            else:
                rel_lbl = "`Unlinked`"
                rel_detail = "⚠️ 미연결 (`studio-link` 실행 필요)"

            matrix_rows.append(
                f"| **#{c_num}** | {short_title_md} | {fmt_badge} | `{pub_slot_lbl}` (`{elapsed_lbl}`) | "
                f"`{imp:,} → {views:,}` (`{delta_v:+,}`) | {hook_dot} `{vw_pct:.1f}%` | "
                f"{apv_dot} `{avd_s:.1f}s` (`{apv_pct:.1f}%`) | `{wh:.1f}h` · `+{subs}` | {rel_lbl} | {v_dot} `{v_status_short}` |"
            )

            # Quartile step deltas
            dq_0_1 = rq1 - 100.0
            dq_1_2 = rq2 - rq1
            dq_2_3 = rq3 - rq2
            dq_3_4 = rq4 - rq3
            if prof_raw == "neuro_diorama" or dur >= 140.0:
                mid_steps = [
                    ("Q1→Q2 (Act 2–3)", dq_1_2),
                    ("Q2→Q3 (Act 4)", dq_2_3),
                    ("Q3→Q4 (Act 5–6)", dq_3_4),
                ]
            elif clips <= 5:
                mid_steps = [
                    ("Q1→Q2 (클립 2)", dq_1_2),
                    ("Q2→Q3 (클립 3)", dq_2_3),
                    (f"Q3→Q4 (클립 4–{max(4, clips)})", dq_3_4),
                ]
            else:
                mid_steps = [
                    ("Q1→Q2 (클립 3–5)", dq_1_2),
                    ("Q2→Q3 (클립 6–8)", dq_2_3),
                    ("Q3→Q4 (클립 9–10)", dq_3_4),
                ]
            worst_step_name, worst_step_val = min(mid_steps, key=lambda x: x[1])
            best_step_name, best_step_val = max(mid_steps, key=lambda x: x[1])
            if best_step_val > 0.5:
                dq_summary = f"반등 구간 `{best_step_name} ({best_step_val:+.1f}%p)` · 주요 낙폭 `{worst_step_name} ({worst_step_val:+.1f}%p)`"
            else:
                dq_summary = f"초반 진입 `0%→Q1 ({dq_0_1:+.1f}%p)` · 중후반 최대 낙폭 `{worst_step_name} ({worst_step_val:+.1f}%p)`"

            ab_info = ab_by_pid.get(pid, {})
            act_var = str(r.get("active_variant", "A"))
            ab_verdict = str(ab_info.get("verdict") or f"Variant {act_var} 활성")
            doi_val = str(r.get("doi") or "Verified")
            doi_pin = str(r.get("doi_pinned") or "✅ Pinned")
            hook_txt = str(r.get("hook_sentence") or "").strip()
            hook_display = f"`\"{hook_txt}\"`" if hook_txt else "`(스크립트 첫 문장 확인)`"

            # Dynamic data-driven root cause & tailored action
            if not measured:
                diag_text = f"게시 후 `{elapsed_lbl}` 경과 상태로 YouTube Studio 리텐션·노출 DOM 집계가 아직 반영되기 전입니다."
                act_text = "초기 24h 시드 보호 구간(Rule R30-B) 동안 메타데이터 수정을 삼가고 첫 피드 노출 진입을 대기합니다."
            elif views >= 250 and delta_v >= 50:
                hook_eval = (
                    f"초반 3초 훅(`Viewed {vw_pct:.1f}%`)이 목표선(`70%`)에 근접(`{vw_pct - 70.0:+.1f}%p`)하며"
                    if vw_pct < 70.0
                    else f"초반 3초 훅(`Viewed {vw_pct:.1f}%`)이 목표(`70%`)를 상회하고"
                )
                diag_text = (
                    f"{hook_eval}, `{dur:.1f}s` 장척 포맷에서 평균 `{avd_s:.1f}s`(`APV {apv_pct:.1f}%`, `Q4 {rq4:.1f}%`)라는 압도적 체류 시간을 기록해 "
                    f"전일 대비 **`{delta_v:+,}` (`{growth_pct:+.1f}%`)** 실시간 피드 확장을 견인 중입니다 (단일 영상 시청시간 `{wh:.1f}h`, 구독 `+{subs}`)."
                )
                act_text = (
                    f"현재 급상승 피드 파동이 진행 중이므로 제목·썸네일 수정을 보류해 알고리즘 모멘텀을 보호하고, "
                    f"`Related Video`(`→ Cohort #{tgt_num or '?'}`)를 통한 시드 대기 코호트 유입 전이율을 모니터링합니다."
                )
            elif views >= 250:
                diag_text = (
                    f"초반 3초 훅 **`Viewed {vw_pct:.1f}%`** (`목표 대비 {vw_pct - 70.0:+.1f}%p`) 및 평균 시청 지속시간 **`{avd_s:.1f}s` (`APV {apv_pct:.1f}%`)**로 "
                    f"누적 조회 **`{views:,}`** · 시청시간 **`{wh:.1f}h`** · 구독 **`+{subs}`**(`{subs_per_1k:.1f}/1K`)를 창출한 채널 핵심 앵커 영상입니다."
                )
                act_text = (
                    f"`Related Video`(`→ Cohort #{tgt_num or '?'}`) 앵커 브릿지를 유지해 저노출 코호트로 시청자를 흘려보내고, "
                    f"본 영상의 검증된 `10클립 + 구체적 임상 사례 훅` 공식을 동일 `{pillar}` 필러 차기작에 복제합니다."
                )
            elif views >= 50 and dur >= 60.0 and apv_pct >= 60.0:
                diag_text = (
                    f"게시 후 `{elapsed_lbl}` 경과 시점에 `Shown {imp:,} → Views {views:,}`(`{delta_v:+,}/1d`) 1차 Shorts 피드 시드가 가동 중이며, "
                    f"`{dur:.1f}s` 장척 포맷에서 평균 **`{avd_s:.1f}s` (`APV {apv_pct:.1f}%`, `Q2 {rq2:.1f}%`)**의 높은 체류율과 시청시간 `{wh:.1f}h`를 기록하고 있습니다."
                )
                act_text = (
                    f"초기 24h 시드 확장 구간이므로 메타데이터 수정을 보류해 2차 피드 확산을 유도하고, "
                    f"차기 디오라마 에피소드는 첫 문장 `\"Imagine...\"` 대신 즉각적 물리 행동 훅(Rule R57-H)을 적용해 `Viewed >= 72%`로 끌어올립니다."
                )
            elif views >= 50:
                diag_text = (
                    f"누적 `{views:,}` 중 `{top_tr}` 비중이 높으며, 초기 `{dur:.1f}s` 단축 포맷과 개념 선행형 첫 문장으로 인해 "
                    f"Shorts 피드 노출 시 초반 스와이프 이탈(`Swiped {sw_pct:.1f}%`, `Viewed {vw_pct:.1f}%`)이 발생해 2차 피드 시드가 제한되었습니다."
                )
                act_text = (
                    f"에버그린 검색 유입 창구로 유지하되(`Related Video → Cohort #{tgt_num or '?'}`), "
                    f"동일 `{pillar}` 필러 후속편은 반드시 `85s+` 장척 포맷과 첫 3초 즉각적 시각 행동 훅으로 제작해 `Viewed >= 75%`를 확보합니다."
                )
            else:
                diag_text = (
                    f"초기 표본 리텐션(`Viewed {vw_pct:.1f}%` · `AVD {avd_s:.1f}s` · `APV {apv_pct:.1f}%`) 자체는 양호하나, "
                    f"상위 앵커 영상들에 채널 피드 노출이 집중되면서 아직 1차 피드 테스트 노출(`Shown {imp:,}`)이 열리지 않은 시드 대기 상태입니다."
                )
                act_text = (
                    f"상위 앵커 영상에서 연결된 `Related Video` 순환 링을 통해 초기 고관여 시청자 시드를 수혈하며, "
                    f"알고리즘 인덱싱 교란 방지를 위해 불필요한 메타데이터 재수정은 지양하고 1차 피드 배정을 대기합니다."
                )

            detail_cards.append(
                f"""### Cohort #{c_num} · {title_md} — {v_dot} `{v_status_short}`

> **스펙 & 운영 메타**: `{pid}` (`{vid}`) ｜ 📂 `{pillar}` ｜ 🎞️ {fmt_detail} ｜ 📅 `{r.get('date')} {r.get('time_et')} ET` (`{elapsed_lbl}`) ｜ 📄 DOI `{doi_val}` ({doi_pin})

| 구분 | 노출 (`Shown`) | 조회 (`Views` / `1d Δ`) | 시청시간 (`Watch`) | 구독 (`Subs`) | 반응 (`좋아요/댓글/공유`) | 주 유입원 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **퍼널·성장** | `{imp:,}` | **`{views:,}`** (`{delta_v:+,}` / `{growth_pct:+.1f}%`) | **`{wh:.2f}h`** | `+{subs}` (`{subs_per_1k:.1f}/1K`) | `{likes} / {comments} / {shares}` | `{top_tr}` |

| 구분 | 3초 훅 (`Viewed / Swiped`) | 평균 시청 (`AVD / APV`) | `Q1 (25%)` | `Q2 (50%)` | `Q3 (75%)` | `Q4 (100%)` | 구간 이탈 요약 (`ΔQ`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **리텐션** | {hook_dot} **`{vw_pct:.1f}%`** / `{sw_pct:.1f}%` | {apv_dot} **`{avd_s:.1f}s`** (`{apv_pct:.1f}%`) | `{rq1:.1f}%` | `{rq2:.1f}%` (`{dq_1_2:+.1f}%p`) | `{rq3:.1f}%` (`{dq_2_3:+.1f}%p`) | `{rq4:.1f}%` (`{dq_3_4:+.1f}%p`) | {dq_summary} |

- **오프닝 훅 문장**: {hook_display}
- **스튜디오 연결 & Z-Test**: `Related Video` {rel_detail} ｜ 썸네일 `{ab_verdict}` (`CTR {ctr_pct:.1f}%`)
- **원인 진단**: {diag_text}
- **맞춤 액션**: {act_text}"""
            )

        if not matrix_rows:
            matrix_rows.append(
                "| **#1** | (공개 영상 없음) | - | - | `0 → 0` | - | - | `0.0h` | - | 🟡 `대기` |"
            )

        top_v_str = (
            f"`Cohort #{pid_to_cohort_num.get(str(top_views_rec['project_id']), 1)}` (`{int(top_views_rec['views']):,}`)"
            if top_views_rec
            else "-"
        )
        top_avd_str = (
            f"`Cohort #{pid_to_cohort_num.get(str(top_avd_rec['project_id']), 1)}` (`{float(top_avd_rec['avd_seconds']):.1f}s`)"
            if top_avd_rec
            else "-"
        )
        top_dl_str = (
            f"`Cohort #{pid_to_cohort_num.get(str(top_delta_rec['project_id']), 1)}` (`{int(top_delta_rec['views_delta_num']):+,}/1d`)"
            if top_delta_rec
            else "-"
        )

        if upcoming:
            up_rows = [
                "| 예약 일시 (`ET`) | 슬롯 | 프로젝트 ID | 제목 | 필러 | 상태 |",
                "| :---: | :---: | :--- | :--- | :---: | :---: |",
            ]
            for u in upcoming:
                up_rows.append(
                    f"| `{u.get('date')} {u.get('time_et')}` | Slot {u.get('slot_id')} (`{u.get('slot_name', '')}`) | "
                    f"`{u.get('project_id')}` | {u.get('title')} | `{u.get('pillar')}` | `{u.get('status')}` |"
                )
            upcoming_block = "\n".join(up_rows)
        else:
            vac_cnt = int(inv.get("vacant_slot_count", 0))
            upcoming_block = (
                f"> ⚠️ **현재 예약 대기(`Scheduled`) 영상 `0`건** (빈 프라임 슬롯 `{vac_cnt}`개 대기 중) — "
                f"차기 v5/v6 검증 완료 에피소드를 `12:00 ET` / `20:00 ET` 프라임 슬롯에 배정하세요."
            )

        data_mode = data.get("data_source_mode", "LOCAL_SNAPSHOT_BASELINE")
        snapshot_json_rel = f"BCI_Shorts_Channel/reports/daily/{data['report_date']}_studio_metrics.json"
        prov_sha = data.get("provenance_sha256", "N/A")

        detail_md = f"""# 🎬 ALL ABOUT BRAIN — 개별 영상 세부 보고서 ({data['report_date']})

## 🚦 0. 전 영상 신호등 요약 매트릭스 (총 `{len(pub_cohorts)}`편)

> **📊 포트폴리오 현황**: 🟢 **시드 돌파·가속** `{green_cnt}편` ｜ 🟡 **검색·탐색 유지** `{yellow_cnt}편` ｜ 🔴 **1차 시드 대기** `{red_cnt}편` ｜ 🏆 **최다 조회** {top_v_str} ｜ ⏱️ **최장 체류** {top_avd_str} ｜ 🚀 **일간 급상승** {top_dl_str}

![Per-Video Performance & Retention Breakdown]({video_charts_filename})

| 코호트 | 영상 제목 (링크) | 포맷 | 게시 (`경과`) | `Shown → Views` (`1d Δ`) | 3초 훅 (`Viewed`) | 평균 시청 (`AVD / APV`) | 시청시간 · 구독 | `Related` | 종합 신호 |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
{chr(10).join(matrix_rows)}

---

## 🔍 1. 영상별 심층 진단 카드 (`Cohort #1 ~ #{max(1, len(pub_cohorts))}`)

{chr(10).join([c + chr(10) + chr(10) + "---" for c in detail_cards]) if detail_cards else "공개된 영상이 없습니다."}

## 📅 2. 예약 대기 & 스테이징 큐 현황 (`Scheduled Queue`)

{upcoming_block}

---
> **🔐 Provenance**: `{snapshot_json_rel}` | **Video Charts**: `{video_charts_filename}` | **Mode**: `{data_mode}` | **SHA-256**: `{prov_sha}`
"""
        return detail_md

    def generate_daily_report(
        self,
        report_date: str | None = None,
        compare_date: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Collects daily studio metrics, saves the raw JSON snapshot, renders both:
        1) Channel Executive Report (`YYYY-MM-DD_daily_studio_report.md` & `LATEST_DAILY_REPORT.md`)
        2) Video-by-Video Detail Report (`YYYY-MM-DD_video_detail_report.md` & `LATEST_VIDEO_DETAIL_REPORT.md`)
        along with their respective standalone PNG chart suites.
        """
        import shutil
        from pipeline.cdp_tab_lease import acquire_shared_flock, get_aab_locks_dir

        lock_file_path = get_aab_locks_dir() / "aab_studio_report.lock"
        lock_fp = acquire_shared_flock(lock_file_path)

        try:
            metrics = self.collect_daily_metrics(
                report_date=report_date,
                compare_date=compare_date,
                dry_run=dry_run,
            )
            r_date = metrics["report_date"]

            self.reports_dir.mkdir(parents=True, exist_ok=True)
            json_check_path = self.reports_dir / f"{r_date}_studio_metrics.json"
            if (
                not dry_run
                and metrics.get("data_source_mode") != "LIVE_CDP_DOM"
                and json_check_path.exists()
            ):
                try:
                    existing_m = json.loads(json_check_path.read_text(encoding="utf-8"))
                    if existing_m.get("data_source_mode") == "LIVE_CDP_DOM":
                        metrics = existing_m
                except Exception:
                    pass
        finally:
            if lock_fp is not None:
                try:
                    import fcntl

                    fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                lock_fp.close()

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        is_default_dir = self.reports_dir.resolve() == DAILY_REPORTS_DIR.resolve()
        if is_default_dir:
            REPORTS_ROOT_DIR.mkdir(parents=True, exist_ok=True)
            latest_charts_target = LATEST_CHARTS_FILE
            latest_report_target = LATEST_REPORT_FILE
            latest_video_charts_target = LATEST_VIDEO_DETAIL_CHARTS_FILE
            latest_video_report_target = LATEST_VIDEO_DETAIL_REPORT_FILE
            latest_chart_rel = f"daily/{r_date}_studio_charts.png"
            latest_video_chart_rel = f"daily/{r_date}_video_detail_charts.png"
            latest_sec_charts = {
                "sec1": f"daily/{r_date}_sec1_channel_growth.png",
                "sec2": f"daily/{r_date}_sec2_video_retention_performance.png",
                "sec3": f"daily/{r_date}_sec3_traffic_audience_growth.png",
                "sec4": f"daily/{r_date}_sec4_schedule_inventory.png",
            }
        else:
            latest_charts_target = self.reports_dir / "LATEST_STUDIO_CHARTS.png"
            latest_report_target = self.reports_dir / "LATEST_DAILY_REPORT.md"
            latest_video_charts_target = self.reports_dir / "LATEST_VIDEO_DETAIL_CHARTS.png"
            latest_video_report_target = self.reports_dir / "LATEST_VIDEO_DETAIL_REPORT.md"
            latest_chart_rel = f"{r_date}_studio_charts.png"
            latest_video_chart_rel = f"{r_date}_video_detail_charts.png"
            latest_sec_charts = {
                "sec1": f"{r_date}_sec1_channel_growth.png",
                "sec2": f"{r_date}_sec2_video_retention_performance.png",
                "sec3": f"{r_date}_sec3_traffic_audience_growth.png",
                "sec4": f"{r_date}_sec4_schedule_inventory.png",
            }

        json_path = self.reports_dir / f"{r_date}_studio_metrics.json"
        md_path = self.reports_dir / f"{r_date}_daily_studio_report.md"
        charts_path = self.reports_dir / f"{r_date}_studio_charts.png"
        video_md_path = self.reports_dir / f"{r_date}_video_detail_report.md"
        video_charts_path = self.reports_dir / f"{r_date}_video_detail_charts.png"

        # Render overview PNG chart, per-section standalone PNG charts, and per-video comparison PNG chart
        self.render_dashboard_charts_png(metrics, charts_path)
        sec_paths = self.render_section_charts_png(metrics, self.reports_dir, prefix=r_date)
        self.render_video_detail_charts_png(metrics, video_charts_path)
        shutil.copy2(charts_path, latest_charts_target)
        shutil.copy2(video_charts_path, latest_video_charts_target)

        daily_sec_charts = {k: p.name for k, p in sec_paths.items()}

        # Render Channel Executive Markdown report
        daily_md = self.render_markdown_report(
            metrics,
            charts_filename=charts_path.name,
            section_charts=daily_sec_charts,
        )
        latest_md = self.render_markdown_report(
            metrics,
            charts_filename=latest_chart_rel,
            section_charts=latest_sec_charts,
        )

        # Render Per-Video Detailed Markdown report
        daily_video_md = self.render_video_detail_report(
            metrics,
            video_charts_filename=video_charts_path.name,
        )
        latest_video_md = self.render_video_detail_report(
            metrics,
            video_charts_filename=latest_video_chart_rel,
        )

        json_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(daily_md, encoding="utf-8")
        latest_report_target.write_text(latest_md, encoding="utf-8")
        video_md_path.write_text(daily_video_md, encoding="utf-8")
        latest_video_report_target.write_text(latest_video_md, encoding="utf-8")

        return {
            "report_date": r_date,
            "previous_report_date": metrics["previous_report_date"],
            "json_path": str(json_path),
            "charts_path": str(charts_path),
            "section_charts_paths": {k: str(v) for k, v in sec_paths.items()},
            "latest_charts_path": str(latest_charts_target),
            "markdown_path": str(md_path),
            "latest_report_path": str(latest_report_target),
            "video_detail_charts_path": str(video_charts_path),
            "latest_video_detail_charts_path": str(latest_video_charts_target),
            "video_detail_markdown_path": str(video_md_path),
            "latest_video_detail_report_path": str(latest_video_report_target),
            "master_prompt_path": str(MASTER_PROMPT_FILE),
            "metrics": metrics,
        }

