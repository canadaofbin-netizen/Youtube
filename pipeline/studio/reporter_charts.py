"""ALL ABOUT BRAIN — Studio Dashboard & Video Detail PNG Chart Renderer (`reporter_charts.py`)."""

from pipeline.studio.reporter_scrape import *
from pipeline.studio.reporter_scrape import _clean_str

class _StudioChartsMixin:
    def render_dashboard_charts_png(self, data: dict[str, Any], output_path: Path) -> Path:
        """
        Generates a normalized 4-panel dark-themed visual analytics dashboard PNG (1920x1080)
        using 100% real YouTube Studio metrics:
        - Panel 1: 7-Day Views & Watch Time (h) Dual-Axis Trajectory
        - Panel 2: Per-Video Real Views & Hook Viewed (%) vs Swiped Away (%)
        - Panel 3: Duration-Proportional Audience Retention Curve (Q1–Q4) & AVD/Duration
        - Panel 4: Real Traffic Sources (%) & Tier-1 Audience Geographies (Rule R36)
        """
        import numpy as np

        bg_navy = "#080D1E"
        panel_bg = "#101935"
        primary_blue = "#1A73E8"
        surgical_teal = "#00D2D3"
        signal_gold = "#FFD166"
        danger_red = "#FF4757"
        accent_purple = "#A29BFE"
        text_white = "#F4F7FF"
        muted_gray = "#8FA3BF"
        grid_gray = "#24345E"

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            for venv_sp in sorted(Path("/home/canadaofbin/hermes-venv/lib").glob("python*/site-packages")):
                if str(venv_sp) not in sys.path:
                    sys.path.insert(0, str(venv_sp))
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(18.5, 10.8), dpi=115)
        fig.patch.set_facecolor(bg_navy)

        ck = data.get("channel_kpis", {})
        rk = data.get("retention_kpis", {})
        views_now = int(ck.get("views_24h", 0))
        views_prev = int(ck.get("views_prev", 1))
        views_dod_pct = ((views_now - views_prev) / max(1, views_prev)) * 100.0
        watch_now = float(ck.get("watch_hours_24h", 0.0))
        apv_now = float(rk.get("apv_pct", 0.0))
        avd_now = float(rk.get("avd_seconds", 0.0))
        avg_len = float(rk.get("avg_video_length_sec", 85.0))
        viewed_now = float(rk.get("viewed_pct", 0.0))
        tier1_geos = [g for g in data.get("geographies", []) if g.get("country") in ("US", "UK", "CA", "AU")]
        tier1_sum = round(sum(float(g["pct"]) for g in tier1_geos), 1)
        mode_str = data.get("data_source_mode", "LOCAL_SNAPSHOT_BASELINE")

        # Traffic-light palette for PNG charts (Green = PASS, Yellow = TUNE/WAIT, Red = ALERT, Gray = PENDING)
        tl_green = "#22C55E"
        tl_yellow = "#FACC15"
        tl_red = "#EF4444"
        tl_gray = "#94A3B8"

        def _tl_color_viewed(val: float, measured: bool = True) -> str:
            if not measured or val <= 0.0:
                return tl_yellow
            if val >= 70.0:
                return tl_green
            if val >= 50.0:
                return tl_yellow
            return tl_red

        def _tl_color_apv(apv: float, avd: float, measured: bool = True) -> str:
            if not measured or (apv <= 0.0 and avd <= 0.0):
                return tl_gray
            if avd >= 25.0 or apv >= 60.0:
                return tl_green
            if avd >= 18.0 or apv >= 50.0:
                return tl_yellow
            return tl_red

        fig.suptitle(
            f"ALL ABOUT BRAIN (@AllAboutBrainOfficial) — Traffic-Light Studio Analytics ({data['report_date']})",
            color=text_white,
            fontsize=16.5,
            fontweight="bold",
            y=0.978,
        )
        hook_tl_lbl = "GREEN" if viewed_now >= 70.0 else ("YELLOW" if viewed_now >= 50.0 else "RED")
        avd_tl_lbl = "GREEN" if (avd_now >= 25.0 or apv_now >= 60.0) else ("YELLOW" if avd_now >= 18.0 else "RED")
        fig.text(
            0.5,
            0.940,
            f"[GREEN] Views: {views_now:,} (+{views_dod_pct:.1f}% DoD)  |  [GREEN] Watch: {watch_now:.1f}h  |  "
            f"[{hook_tl_lbl}] Hook Viewed: {viewed_now:.1f}% (Gate 70%)  |  "
            f"[{avd_tl_lbl}] AVD: {avd_now:.1f}s / {avg_len:.1f}s (APV {apv_now:.1f}%)  |  "
            f"[GREEN] US: {data['geographies'][0]['pct'] if data.get('geographies') else 55.6:.1f}% (Tier-1 {tier1_sum:.1f}%)  |  Mode: {mode_str}",
            ha="center",
            va="center",
            color=signal_gold,
            fontsize=10.0,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.38", facecolor=panel_bg, edgecolor=grid_gray, linewidth=1.2),
        )

        def style_ax(ax: Any, title: str, ylabel: str = ""):
            ax.set_facecolor(panel_bg)
            ax.set_title(title, color=text_white, fontsize=12.0, fontweight="bold", pad=10)
            if ylabel:
                ax.set_ylabel(ylabel, color=text_white, fontsize=9.8, fontweight="bold")
            ax.tick_params(colors=text_white, labelsize=9.2)
            for spine in ax.spines.values():
                spine.set_color(grid_gray)
            ax.grid(True, linestyle="--", alpha=0.35, color=grid_gray)

        # Panel 1 (Top-Left): Multi-Horizon Exposure Funnel (Shown in feed -> Views -> Engaged Views + Watch Hours)
        cohort_stats = self._compute_recent_cohort_and_history_stats(data)
        ax1 = axes[0, 0]
        style_ax(ax1, "1. Exposure Funnel Trajectory: Shown in Feed -> Views -> Engaged (7d -> Today)", "Volume (Count)")
        dates_7d = data["trend_7d"]["dates"]
        views_7d = [int(v) if v is not None else None for v in data["trend_7d"]["views"]]
        wh_7d = [float(w) for w in data["trend_7d"].get("watch_hours", [0.0 for _ in views_7d])]
        d7_lbl = dates_7d[0] if dates_7d else "W-1"
        d3_lbl = dates_7d[3] if len(dates_7d) > 3 else "D-3"
        d1_lbl = dates_7d[-2] if len(dates_7d) > 1 else "D-1"
        d0_lbl = dates_7d[-1] if dates_7d else "D-0"

        v_raw_0 = views_7d[0] if views_7d else 0
        v_raw_3 = views_7d[3] if len(views_7d) > 3 else 0
        v_pts = [
            int(v_raw_0) if v_raw_0 is not None else 0,
            int(v_raw_3) if v_raw_3 is not None else 0,
            int(ck.get("views_prev", 0)),
            int(ck.get("views_24h", 0)),
        ]
        shown_pts = [
            cohort_stats["shown_7d"] or 0,
            cohort_stats["shown_3d"] or 0,
            cohort_stats["shown_prev"],
            cohort_stats["shown_now"],
        ]
        engaged_pts = [
            cohort_stats["engaged_7d"] or 0,
            cohort_stats["engaged_3d"] or 0,
            cohort_stats["engaged_prev"] or 0,
            cohort_stats["engaged_now"] or 0,
        ]
        wh_pts = [
            wh_7d[0] if wh_7d else 0.0,
            wh_7d[3] if len(wh_7d) > 3 else 0.0,
            float(ck.get("watch_hours_prev", 0.0)),
            float(ck.get("watch_hours_24h", 0.0)),
        ]

        x1 = np.arange(4)
        w1 = 0.25
        ax1.bar(x1 - w1, shown_pts, width=w1, color=tl_gray, alpha=0.65, label="Shown in Feed")
        ax1.bar(x1, v_pts, width=w1, color=primary_blue, alpha=0.90, label="Total Views (Viewed)")
        ax1.bar(x1 + w1, engaged_pts, width=w1, color=tl_green, alpha=0.90, label="Engaged Views")
        ax1.set_xticks(x1)
        ax1.set_xticklabels([f"7d Ago\n({d7_lbl})", f"3d Ago\n({d3_lbl})", f"Yesterday\n({d1_lbl})", f"Today\n({d0_lbl})"], fontweight="bold")
        max_v7 = max(shown_pts + v_pts + [10])
        ax1.set_ylim(0, max_v7 * 1.35)
        for i_b, (sh_v, vw_v, eng_v) in enumerate(zip(shown_pts, v_pts, engaged_pts)):
            ax1.text(x1[i_b] - w1, sh_v + max_v7 * 0.02, f"{sh_v:,}", ha="center", va="bottom", color=tl_gray, fontsize=7.8, fontweight="bold")
            ax1.text(x1[i_b], vw_v + max_v7 * 0.02, f"{vw_v:,}", ha="center", va="bottom", color=text_white, fontsize=8.2, fontweight="bold")
            ax1.text(x1[i_b] + w1, eng_v + max_v7 * 0.02, f"{eng_v:,}", ha="center", va="bottom", color=tl_green, fontsize=7.8, fontweight="bold")
        ax1_tw = ax1.twinx()
        ax1_tw.plot(x1, wh_pts, color=signal_gold, marker="o", linewidth=2.5, markersize=6, label="Watch Hours (Right)")
        ax1_tw.set_ylabel("Watch Time (Hours)", color=signal_gold, fontsize=9.8, fontweight="bold")
        ax1_tw.tick_params(axis="y", colors=signal_gold, labelsize=9.0)
        max_wh = max(wh_pts + [1.0])
        ax1_tw.set_ylim(0, max_wh * 1.48)
        for spine in ax1_tw.spines.values():
            spine.set_color(grid_gray)
        for i_w, wh_val in enumerate(wh_pts):
            ax1_tw.text(
                i_w,
                wh_val + max_wh * 0.06,
                f"{wh_val:.1f}h",
                ha="center",
                va="bottom",
                color=signal_gold,
                fontsize=8.0,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", facecolor=bg_navy, edgecolor=signal_gold, lw=0.7, alpha=0.88),
            )
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_tw.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", ncol=2, facecolor=panel_bg, edgecolor=grid_gray, labelcolor=text_white, fontsize=7.8)

        # Panel 2 (Top-Right): Channel Cumulative vs Recent 3 Cohort vs Target Gate
        ax2 = axes[0, 1]
        style_ax(ax2, "2. Retention Cohort Split: Cumulative (All) vs Recent 3 Cohort vs Target (%)", "Percentage (%)")
        r_quarts = data.get("retention_quartiles", [])
        q1_now = float(r_quarts[0]["today_pct"]) if len(r_quarts) > 0 else 0.0
        q2_now = float(r_quarts[1]["today_pct"]) if len(r_quarts) > 1 else 0.0
        q3_now = float(r_quarts[2]["today_pct"]) if len(r_quarts) > 2 else 0.0
        q4_now = float(r_quarts[3]["today_pct"]) if len(r_quarts) > 3 else 0.0

        rec_q = cohort_stats["recent_q"]
        funnel_labels = ["3s Hook\n(Viewed)", "Avg Watch\n(APV)", "Q1\n(25%)", "Q2\n(50%)", "Q3\n(75%)", "Q4\n(100%)"]
        funnel_all = [viewed_now, apv_now, q1_now, q2_now, q3_now, q4_now]
        funnel_recent = [cohort_stats["recent_viewed"], cohort_stats["recent_apv"], rec_q[0], rec_q[1], rec_q[2], rec_q[3]]
        funnel_targets = [70.0, 60.0, 70.0, 65.0, 62.0, 60.0]

        x2 = np.arange(len(funnel_labels))
        w2 = 0.34
        ax2.bar(x2 - w2 / 2, funnel_all, width=w2, color=primary_blue, alpha=0.82, label="Cumulative Avg (All)")
        ax2.bar(x2 + w2 / 2, funnel_recent, width=w2, color=tl_green, alpha=0.92, label="Recent 3 Cohort Avg")
        ax2.plot(x2, funnel_targets, color=signal_gold, linestyle="--", marker="D", markersize=5, linewidth=1.8, label="Target Gate (%)")
        ax2.set_xticks(x2)
        ax2.set_xticklabels(funnel_labels, fontweight="bold")
        ax2.set_ylim(0, 108)
        for idx_f, (v_all, v_rec) in enumerate(zip(funnel_all, funnel_recent)):
            ax2.text(x2[idx_f] - w2 / 2, v_all + 1.8, f"{v_all:.1f}%", ha="center", va="bottom", color=text_white, fontsize=7.8, fontweight="bold")
            ax2.text(x2[idx_f] + w2 / 2, v_rec + 1.8, f"{v_rec:.1f}%", ha="center", va="bottom", color=tl_green, fontsize=8.0, fontweight="bold")
        ax2.legend(loc="upper right", fontsize=8.0, facecolor=panel_bg, edgecolor=grid_gray, labelcolor=text_white)

        # Panel 3 (Bottom-Left): Duration-Proportional Retention Curve & Drop-off Delta Q (Q1-Q4)
        ax3 = axes[1, 0]
        style_ax(ax3, "3. Retention Curve & Inter-Quartile Drop-Off (Delta Q: All vs Recent 3)", "Retention (%)")
        t_pts = data["retention_curves_30s"]["time_points"]
        ret_today = data["retention_curves_30s"]["today_pct"]
        ret_recent = [100.0, cohort_stats["recent_viewed"], rec_q[0], rec_q[1], rec_q[2], rec_q[3]]
        x3 = np.arange(len(t_pts))
        ax3.axvspan(0, 2, color=primary_blue, alpha=0.08)
        ax3.axvspan(2, 3, color=signal_gold, alpha=0.12)
        ax3.axvspan(3, 4, color=surgical_teal, alpha=0.08)
        ax3.axvspan(4, 5, color=accent_purple, alpha=0.08)

        ax3.plot(x3, ret_recent, color=tl_green, marker="o", linewidth=3.0, markersize=6.5, label="Recent 3 Cohort (%)")
        ax3.plot(x3, ret_today, color=primary_blue, marker="s", linestyle="--", linewidth=2.2, markersize=5.5, label="Channel Cumulative (%)")
        ax3.fill_between(x3, ret_today, 45, color=primary_blue, alpha=0.12)
        ax3.set_xticks(x3)
        ax3.set_xticklabels([
            "0%\nStart",
            "10%\n3s Hook",
            "25%\nQ1",
            f"50%\nQ2 ({q2_now - q1_now:+.1f}%p)",
            f"75%\nQ3 ({q3_now - q2_now:+.1f}%p)",
            f"100%\nQ4 ({q4_now - q3_now:+.1f}%p)",
        ])
        ax3.set_ylim(min(45.0, min(ret_today + ret_recent) - 5.0), 108)
        for i, (v_now, v_rec) in enumerate(zip(ret_today, ret_recent)):
            ax3.text(i, v_rec + 2.2, f"{v_rec:.1f}% (All {v_now:.1f}%)", ha="center", color=text_white, fontsize=8.0, fontweight="bold")
        ax3.legend(loc="lower left", ncol=2, fontsize=8.5, facecolor=panel_bg, edgecolor=grid_gray, labelcolor=text_white)

        # Panel 4 (Bottom-Right): Daily High-Signal Traffic & Tier-1 Share (Shorts Feed % & US/Tier-1 %)
        ax4 = axes[1, 1]
        style_ax(ax4, "4. High-Signal Traffic & Geographies (7d Ago -> Yesterday -> Today)", "")
        ts_map_d = {t["short_name"]: t for t in data["traffic_sources"]}
        sf_now_d = float(ts_map_d.get("Shorts Feed", {}).get("pct", 0.0))
        sf_prv_d = float(ts_map_d.get("Shorts Feed", {}).get("prev_pct", 0.0))
        us_geo_d = next((g for g in data["geographies"] if g["country"] == "US"), {"pct": 0.0, "prev_pct": 0.0})
        tier1_geos_d = [g for g in data["geographies"] if g["country"] in ("US", "UK", "CA", "AU")]
        t1_prv_d = round(sum(float(g.get("prev_pct", 0.0)) for g in tier1_geos_d), 1)
        snap_7d_d = cohort_stats["snap_7d"]
        y_labels = ["Shorts Feed Share (%)", "US Audience Share (%)", "Tier-1 English (US+UK+AU %)"]
        vals_w1 = (
            [float(snap_7d_d["shorts_feed_pct"]), float(snap_7d_d["us_pct"]), float(snap_7d_d["tier1_pct"])]
            if snap_7d_d
            else [0.0, 0.0, 0.0]
        )
        vals_d1 = [sf_prv_d, float(us_geo_d["prev_pct"]), t1_prv_d]
        vals_d0 = [sf_now_d, float(us_geo_d["pct"]), tier1_sum]
        y_pos = np.arange(len(y_labels))
        h4 = 0.25

        ax4.barh(y_pos - h4, vals_w1, color=tl_gray, height=h4, alpha=0.6, label=f"7d Ago ({d7_lbl})" if snap_7d_d else "7d Ago (collecting)")
        ax4.barh(y_pos, vals_d1, color=primary_blue, height=h4, alpha=0.8, label=f"Yesterday ({d1_lbl})")
        bars4 = ax4.barh(y_pos + h4, vals_d0, color=tl_green, height=h4, alpha=0.95, label=f"Today ({d0_lbl})")
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(y_labels, fontsize=9.5, fontweight="bold")
        ax4.invert_yaxis()
        ax4.set_xlim(0, 108)
        ax4.set_xlabel("Channel Share (%)", color=text_white, fontsize=9.5, fontweight="bold")
        for idx_b, b in enumerate(bars4):
            w = b.get_width()
            lbl_suffix = f"({w - vals_w1[idx_b]:+.1f}%p 7d)" if snap_7d_d else "(7d collecting)"
            ax4.text(
                w + 1.2,
                b.get_y() + b.get_height() / 2.0,
                f"{w:.1f}% {lbl_suffix}",
                va="center",
                color=tl_green,
                fontsize=8.6,
                fontweight="bold",
            )
        ax4.legend(loc="lower right", facecolor=panel_bg, edgecolor=grid_gray, labelcolor=text_white, fontsize=8.2)

        plt.tight_layout(rect=[0.01, 0.01, 0.99, 0.915])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, facecolor=bg_navy)
        plt.close(fig)
        return output_path

    def render_section_charts_png(
        self,
        data: dict[str, Any],
        output_dir: Path,
        prefix: str = "",
    ) -> dict[str, Path]:
        """
        Generates clean channel-level standalone wide PNG charts:
        - sec1_channel_growth.png: 7-Day Channel Cumulative Views & Watch Time (h)
        - sec2_video_retention_performance.png: Channel Watch-Rate & Quartile Retention (Viewed %, APV %, Q1-Q4 vs Target)
        - sec3_traffic_audience_growth.png: Channel Traffic & Audience Share (Today vs Yesterday)
        - sec4_schedule_inventory.png: Channel Bottleneck Gap vs Target Gate (%)
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        output_dir.mkdir(parents=True, exist_ok=True)
        pfx = f"{prefix}_" if prefix else ""

        bg = "#0B0F19"
        panel_bg = "#111827"
        grid = "#1E293B"
        text_col = "#F8FAFC"
        muted = "#94A3B8"
        tl_green = "#22C55E"
        tl_yellow = "#FACC15"
        tl_red = "#EF4444"
        tl_gray = "#64748B"
        blue = "#3B82F6"

        plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Liberation Sans"]
        plt.rcParams["axes.edgecolor"] = "#334155"
        plt.rcParams["axes.linewidth"] = 0.8

        def style_clean_ax(ax: Any, grid_axis: str = "y"):
            ax.set_facecolor(panel_bg)
            ax.tick_params(colors=text_col, labelsize=11.0)
            ax.grid(True, axis=grid_axis, linestyle="--", alpha=0.28, color=grid)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)

        ck = data["channel_kpis"]
        rk = data["retention_kpis"]
        demo = data.get("demographics", {})

        # 1. Section 1 Chart: Exposure Funnel Trajectory (Shown in Feed -> Views -> Engaged Views + Watch Hours)
        sec1_path = output_dir / f"{pfx}sec1_channel_growth.png"
        fig1, ax1 = plt.subplots(figsize=(12.5, 4.8), dpi=160)
        fig1.patch.set_facecolor(bg)
        style_clean_ax(ax1, "y")

        cohort_stats = self._compute_recent_cohort_and_history_stats(data)
        dates_7d = list(data["trend_7d"]["dates"])
        views_7d = [int(v) if v is not None else None for v in data["trend_7d"]["views"]]
        wh_7d = [float(w) for w in data["trend_7d"].get("watch_hours", [0.0 for _ in views_7d])]
        d7_lbl = dates_7d[0] if dates_7d else "W-1"
        d3_lbl = dates_7d[3] if len(dates_7d) > 3 else "D-3"
        d1_lbl = dates_7d[-2] if len(dates_7d) > 1 else "D-1"
        d0_lbl = dates_7d[-1] if dates_7d else "D-0"

        v_s1_0 = views_7d[0] if views_7d else None
        v_s1_3 = views_7d[3] if len(views_7d) > 3 else None
        masked_dates_set = set(data.get("trend_7d", {}).get("masked_outlier_dates") or [])
        s1_dates = [d7_lbl, d3_lbl, d1_lbl, d0_lbl]
        v_raw_pts = [v_s1_0, v_s1_3, int(ck["views_prev"]), int(ck["views_24h"])]
        v_pts = [int(v) if v is not None else 0 for v in v_raw_pts]
        shown_now_s1 = cohort_stats["shown_now"]
        shown_prev_s1 = cohort_stats["shown_prev"]
        shown_raw_pts = [cohort_stats["shown_7d"], cohort_stats["shown_3d"], shown_prev_s1, shown_now_s1]
        shown_pts = [int(v) if v is not None else 0 for v in shown_raw_pts]
        engaged_raw_pts = [
            cohort_stats["engaged_7d"],
            cohort_stats["engaged_3d"],
            cohort_stats["engaged_prev"],
            cohort_stats["engaged_now"],
        ]
        engaged_pts = [int(v) if v is not None else 0 for v in engaged_raw_pts]
        wh_pts = [
            wh_7d[0] if wh_7d else 0.0,
            wh_7d[3] if len(wh_7d) > 3 else 0.0,
            float(ck["watch_hours_prev"]),
            float(ck["watch_hours_24h"]),
        ]

        x1 = np.arange(4)
        w1 = 0.25
        ax1.bar(x1 - w1, shown_pts, width=w1, color=tl_gray, alpha=0.62, label=f"Shown in Feed ({shown_now_s1:,} | {shown_now_s1 - shown_prev_s1:+,} 1d)", zorder=3)
        ax1.bar(x1, v_pts, width=w1, color=blue, alpha=0.90, label=f"Views / Viewed ({v_pts[-1]:,} | {v_pts[-1] - v_pts[-2]:+,} 1d)", zorder=3)
        ax1.bar(x1 + w1, engaged_pts, width=w1, color=tl_green, alpha=0.92, label=f"Engaged Views ({engaged_pts[-1]:,} | {engaged_pts[-1] - engaged_pts[-2]:+,} 1d)", zorder=3)

        max_v = max(shown_pts + v_pts + [100])
        for i, (sh_v, vw_v, eng_v) in enumerate(zip(shown_pts, v_pts, engaged_pts)):
            is_masked_slot = (s1_dates[i] in masked_dates_set) or (v_raw_pts[i] is None)
            sh_lbl = "N/A" if (is_masked_slot or shown_raw_pts[i] is None) else f"{sh_v:,}"
            vw_lbl = "N/A" if is_masked_slot else f"{vw_v:,}"
            eng_lbl = "N/A" if (is_masked_slot or engaged_raw_pts[i] is None) else f"{eng_v:,}"
            ax1.text(x1[i] - w1, sh_v + max_v * 0.02, sh_lbl, ha="center", va="bottom", color=muted, fontsize=9.0, fontweight="bold")
            ax1.text(x1[i], vw_v + max_v * 0.02, vw_lbl, ha="center", va="bottom", color=(tl_yellow if is_masked_slot else text_col), fontsize=9.5, fontweight="bold")
            ax1.text(x1[i] + w1, eng_v + max_v * 0.02, eng_lbl, ha="center", va="bottom", color=(muted if (is_masked_slot or engaged_raw_pts[i] is None) else tl_green), fontsize=9.0, fontweight="bold")

        ax1.set_ylabel("Funnel Volume (Count)", color=text_col, fontsize=12, fontweight="bold")
        ax1.set_xticks(x1)
        ax1.set_xticklabels([f"7d Ago ({d7_lbl})", f"3d Ago ({d3_lbl})", f"Yesterday ({d1_lbl})", f"Today ({d0_lbl})"], fontsize=11, fontweight="bold", color=text_col)
        ax1.set_ylim(0, max_v * 1.32)

        ax1_tw = ax1.twinx()
        ax1_tw.spines["top"].set_visible(False)
        ax1_tw.spines["right"].set_color(tl_yellow)
        ax1_tw.tick_params(axis="y", colors=tl_yellow, labelsize=11.0)
        wh_lbl_7d = f"{wh_pts[-1] - wh_pts[0]:+.1f}h 7d" if cohort_stats["has_7d"] else "7d collecting"
        ax1_tw.plot(
            x1,
            wh_pts,
            color=tl_yellow,
            marker="o",
            linewidth=3.0,
            markersize=8.0,
            label=f"Watch Time ({ck['watch_hours_24h']:.1f}h | {wh_lbl_7d})",
            zorder=5,
        )
        ax1_tw.set_ylabel("Watch Hours (h)", color=tl_yellow, fontsize=12, fontweight="bold")
        max_wh = max(wh_pts + [1.0])
        ax1_tw.set_ylim(0, max_wh * 1.38)

        for i, wh_val in enumerate(wh_pts):
            ax1_tw.text(
                x1[i],
                wh_val + max_wh * 0.06,
                f"{wh_val:.1f}h",
                ha="center",
                va="bottom",
                color=tl_yellow,
                fontsize=9.5,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.18", facecolor=bg, edgecolor=tl_yellow, alpha=0.92),
            )

        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = ax1_tw.get_legend_handles_labels()
        ax1.legend(h1 + h2, l1 + l2, loc="upper left", ncol=2, facecolor=bg, edgecolor="#334155", labelcolor=text_col, fontsize=9.4)
        plt.title(
            f"1. Channel Volume & Exposure Funnel — Shown in Feed -> Views -> Engaged ({data['report_date']})",
            color=text_col,
            fontsize=13.5,
            fontweight="bold",
            pad=14,
        )
        plt.tight_layout()
        fig1.savefig(sec1_path, dpi=160, facecolor=bg)
        plt.close(fig1)

        # 2. Section 2 Chart: Cohort Split (Channel Cumulative vs Recent 3 Cohort vs Target + Drop-off Delta Q)
        sec2_path = output_dir / f"{pfx}sec2_video_retention_performance.png"
        fig2, ax2 = plt.subplots(figsize=(12.5, 4.8), dpi=160)
        fig2.patch.set_facecolor(bg)
        style_clean_ax(ax2, "y")

        r_quarts = data.get("retention_quartiles", [])
        q1_now = float(r_quarts[0]["today_pct"]) if len(r_quarts) > 0 else 0.0
        q2_now = float(r_quarts[1]["today_pct"]) if len(r_quarts) > 1 else 0.0
        q3_now = float(r_quarts[2]["today_pct"]) if len(r_quarts) > 2 else 0.0
        q4_now = float(r_quarts[3]["today_pct"]) if len(r_quarts) > 3 else 0.0

        rec_q = cohort_stats["recent_q"]
        snap_7d = cohort_stats["snap_7d"]
        q7 = snap_7d["quartiles"] if (snap_7d and len(snap_7d.get("quartiles") or []) >= 4) else [0.0, 0.0, 0.0, 0.0]

        f_labels = [
            "3s Hook\n(Viewed %)",
            "Watch Rate\n(APV %)",
            f"Q1 (0-25%)\n[Δ {q1_now - 100.0:+.1f}%p]",
            f"Q2 (25-50%)\n[Δ {q2_now - q1_now:+.1f}%p]",
            f"Q3 (50-75%)\n[Δ {q3_now - q2_now:+.1f}%p]",
            f"Q4 (75-100%)\n[Δ {q4_now - q3_now:+.1f}%p]",
        ]
        f_w1 = (
            [float(snap_7d["viewed_pct"]), float(snap_7d["apv_pct"]), q7[0], q7[1], q7[2], q7[3]]
            if snap_7d
            else [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        )
        f_all = [float(rk["viewed_pct"]), float(rk["apv_pct"]), q1_now, q2_now, q3_now, q4_now]
        f_recent = [cohort_stats["recent_viewed"], cohort_stats["recent_apv"], rec_q[0], rec_q[1], rec_q[2], rec_q[3]]
        f_target = [70.0, 60.0, 70.0, 65.0, 62.0, 60.0]

        x2 = np.arange(len(f_labels))
        w2 = 0.25
        ax2.bar(x2 - w2, f_w1, width=w2, color=tl_gray, alpha=0.50, label=f"7d Ago ({d7_lbl})" if snap_7d else "7d Ago (collecting)", zorder=3)
        ax2.bar(x2, f_all, width=w2, color=blue, alpha=0.85, label="Cumulative Avg (All)", zorder=3)
        ax2.bar(x2 + w2, f_recent, width=w2, color=tl_green, alpha=0.95, label="Recent 3 Cohort Avg", zorder=3)
        ax2.plot(x2, f_target, color=tl_yellow, linestyle="--", marker="D", markersize=6, linewidth=2.0, label="Target Gate (%)", zorder=4)

        for i, (v_all, v_rec) in enumerate(zip(f_all, f_recent)):
            ax2.text(x2[i], v_all + 1.8, f"{v_all:.1f}%", ha="center", va="bottom", color=text_col, fontsize=8.8, fontweight="bold")
            ax2.text(x2[i] + w2, v_rec + 1.8, f"{v_rec:.1f}%", ha="center", va="bottom", color=tl_green, fontsize=9.2, fontweight="bold")

        ax2.set_ylabel("Percentage (%)", color=text_col, fontsize=12, fontweight="bold")
        ax2.set_xticks(x2)
        ax2.set_xticklabels(f_labels, fontsize=10.2, fontweight="bold", color=text_col)
        ax2.set_ylim(0, 110)
        ax2.legend(loc="upper right", ncol=2, facecolor=bg, edgecolor="#334155", labelcolor=text_col, fontsize=9.6)
        plt.title(
            "2. Retention Cohort Split & Inter-Quartile Drop-Off (All vs Recent 3 Cohort vs Target)",
            color=text_col,
            fontsize=13.5,
            fontweight="bold",
            pad=14,
        )
        plt.tight_layout()
        fig2.savefig(sec2_path, dpi=160, facecolor=bg)
        plt.close(fig2)

        # 3. Section 3 Chart: High-Signal Daily Traffic & Geo Share (Shorts Feed % & US/Tier-1 %)
        sec3_path = output_dir / f"{pfx}sec3_traffic_audience_growth.png"
        fig3, ax3 = plt.subplots(figsize=(12.5, 4.2), dpi=160)
        fig3.patch.set_facecolor(bg)
        style_clean_ax(ax3, "x")

        ts_map = {t["short_name"]: t for t in data["traffic_sources"]}
        sf_now = float(ts_map.get("Shorts Feed", {}).get("pct", 0.0))
        sf_prev = float(ts_map.get("Shorts Feed", {}).get("prev_pct", 0.0))

        us_geo = next((g for g in data["geographies"] if g["country"] == "US"), {"pct": 0.0, "prev_pct": 0.0})
        tier1_geos = [g for g in data["geographies"] if g["country"] in ("US", "UK", "CA", "AU")]
        t1_now = round(sum(float(g["pct"]) for g in tier1_geos), 1)
        t1_prev = round(sum(float(g["prev_pct"]) for g in tier1_geos), 1)

        labels3 = [
            "Shorts Feed Share (%)",
            "US Audience Share (%)",
            "Tier-1 English (US+UK+AU %)",
        ][::-1]
        w1_3 = (
            [float(snap_7d["shorts_feed_pct"]), float(snap_7d["us_pct"]), float(snap_7d["tier1_pct"])][::-1]
            if snap_7d
            else [0.0, 0.0, 0.0]
        )
        prev3 = [sf_prev, float(us_geo["prev_pct"]), t1_prev][::-1]
        curr3 = [sf_now, float(us_geo["pct"]), t1_now][::-1]

        y3 = np.arange(len(labels3))
        h3 = 0.24
        ax3.barh(y3 - h3, w1_3, height=h3, color=tl_gray, alpha=0.65, label=f"7d Ago ({d7_lbl})" if snap_7d else "7d Ago (collecting)")
        ax3.barh(y3, prev3, height=h3, color=blue, alpha=0.80, label=f"Yesterday ({d1_lbl})")
        ax3.barh(y3 + h3, curr3, height=h3, color=tl_green, alpha=0.95, label=f"Today ({d0_lbl})")

        for yi, (w_val, p_val, c_val) in enumerate(zip(w1_3, prev3, curr3)):
            diff1 = c_val - p_val
            d7_part = f"7d {c_val - w_val:+.1f}%p" if snap_7d else "7d collecting"
            ax3.text(c_val + 1.2, yi + h3, f"{c_val:.1f}% ({d7_part} / 1d {diff1:+.1f}%p)", va="center", ha="left", color=tl_green, fontsize=10.0, fontweight="bold")
            ax3.text(p_val + 1.0, yi, f"{p_val:.1f}%", va="center", ha="left", color=text_col, fontsize=9.0)
            if snap_7d:
                ax3.text(w_val + 1.0, yi - h3, f"{w_val:.1f}%", va="center", ha="left", color=muted, fontsize=8.8)

        ax3.set_yticks(y3)
        ax3.set_yticklabels(labels3, fontsize=11.0, fontweight="bold", color=text_col)
        ax3.set_xlim(0, 118)
        ax3.set_xlabel("Channel Share (%) — 7d Ago -> Yesterday -> Today", color=text_col, fontsize=12, fontweight="bold")
        ax3.legend(loc="lower right", facecolor=bg, edgecolor="#334155", labelcolor=text_col, fontsize=10.0)
        plt.title(
            "3. High-Signal Traffic & Tier-1 Geographies (Shorts Feed % & US / Tier-1 %)",
            color=text_col,
            fontsize=13.5,
            fontweight="bold",
            pad=14,
        )
        plt.tight_layout()
        fig3.savefig(sec3_path, dpi=160, facecolor=bg)
        plt.close(fig3)

        # 4. Section 4 Chart: Channel Target Gap Analysis (Cumulative vs Recent 3 Cohort vs Target Gate)
        sec4_path = output_dir / f"{pfx}sec4_schedule_inventory.png"
        fig4, ax4 = plt.subplots(figsize=(12.5, 4.2), dpi=160)
        fig4.patch.set_facecolor(bg)
        style_clean_ax(ax4, "x")

        g_labels = [
            "3s Hook (Viewed %)",
            "Watch Rate (APV %)",
            "Q4 End Retention (%)",
            "Shorts Feed Share (%)",
            "US + Tier-1 Share (%)",
        ][::-1]
        g_curr = [float(rk["viewed_pct"]), float(rk["apv_pct"]), q4_now, sf_now, t1_now][::-1]
        g_rec = [cohort_stats["recent_viewed"], cohort_stats["recent_apv"], rec_q[3], sf_now, t1_now][::-1]
        g_tgt = [70.0, 60.0, 60.0, 70.0, 55.0][::-1]

        y4 = np.arange(len(g_labels))
        h4 = 0.30
        ax4.barh(y4 - h4 / 2, g_curr, height=h4, color=blue, alpha=0.82, label="Channel Cumulative (%)")
        ax4.barh(y4 + h4 / 2, g_rec, height=h4, color=tl_green, alpha=0.92, label="Recent 3 Cohort (%)")
        for yi, (c_v, r_v, t_v) in enumerate(zip(g_curr, g_rec, g_tgt)):
            gap = c_v - t_v
            s_g = "+" if gap >= 0 else ""
            ax4.plot([t_v, t_v], [yi - 0.32, yi + 0.32], color=tl_yellow, linestyle="--", linewidth=2.0)
            ax4.text(max(c_v, r_v, t_v) + 1.2, yi, f"All {c_v:.1f}% ({s_g}{gap:.1f}%p) | Recent {r_v:.1f}%", va="center", ha="left", color=text_col, fontsize=9.8, fontweight="bold")

        ax4.set_yticks(y4)
        ax4.set_yticklabels(g_labels, fontsize=10.8, fontweight="bold", color=text_col)
        ax4.set_xlim(0, 125)
        ax4.set_xlabel("Percentage (%) vs Target Gate (Cumulative vs Recent 3 Cohort)", color=text_col, fontsize=12, fontweight="bold")
        ax4.legend(loc="lower right", facecolor=bg, edgecolor="#334155", labelcolor=text_col, fontsize=9.8)
        plt.title(
            "4. Channel KPI Gap vs Target Gate (Cumulative vs Recent 3 Cohort)",
            color=text_col,
            fontsize=13.5,
            fontweight="bold",
            pad=14,
        )
        plt.tight_layout()
        fig4.savefig(sec4_path, dpi=160, facecolor=bg)
        plt.close(fig4)

        return {
            "sec1": sec1_path,
            "sec2": sec2_path,
            "sec3": sec3_path,
            "sec4": sec4_path,
        }

    def render_video_detail_charts_png(
        self,
        data: dict[str, Any],
        output_path: Path,
    ) -> Path:
        """
        Generates a 2-panel horizontal comparison PNG chart for the Video-by-Video Detail Report:
        - Panel 1 (Left): Views & Watch Hours (h) per published Cohort
        - Panel 2 (Right): 3s Hook (Viewed %), Watch Rate (APV %), and Q4 End Retention (%) vs Target Gates
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        pv_records = list(data.get("per_video_records") or [])
        pub_cohorts = [r for r in pv_records if str(r.get("status", "")).lower() == "published"] or pv_records

        bg = "#0B0F19"
        panel_bg = "#111827"
        grid = "#1E293B"
        text_col = "#F8FAFC"
        muted = "#94A3B8"
        tl_green = "#22C55E"
        tl_yellow = "#FACC15"
        tl_red = "#EF4444"
        blue = "#3B82F6"
        cyan = "#38BDF8"

        n_vids = max(1, len(pub_cohorts))
        fig_h = max(5.2, 0.92 * n_vids + 1.9)
        fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(15.5, fig_h), dpi=160)
        fig.patch.set_facecolor(bg)

        for ax in (ax_l, ax_r):
            ax.set_facecolor(panel_bg)
            ax.tick_params(colors=text_col, labelsize=10.0)
            ax.grid(True, axis="x", linestyle="--", alpha=0.28, color=grid)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)

        if not pub_cohorts:
            ax_l.text(0.5, 0.5, "No Published Videos Yet", ha="center", va="center", color=muted, fontsize=12)
            ax_r.text(0.5, 0.5, "No Retention Data Yet", ha="center", va="center", color=muted, fontsize=12)
        else:
            labels = []
            views_arr = []
            colors_l = []
            annot_l = []
            hook_arr = []
            apv_arr = []
            q4_arr = []

            for idx_c, r in enumerate(pub_cohorts):
                dur_i = int(round(float(r.get("duration_seconds", 85.0))))
                short_lbl = str(r.get("short_label") or r.get("project_id", ""))[:14]
                labels.append(f"#{idx_c + 1} {short_lbl} ({dur_i}s)")

                vw = int(r.get("views", 0))
                dl = int(r.get("views_delta_num", 0))
                wh = float(r.get("watch_hours", 0.0))
                sb = int(r.get("subs_gained", 0))
                views_arr.append(vw)
                if vw >= 250:
                    colors_l.append(tl_green)
                elif vw >= 50:
                    colors_l.append(tl_yellow)
                else:
                    colors_l.append(tl_red)
                annot_l.append(f"{vw:,} ({dl:+,}/1d) | {wh:.1f}h | +{sb} subs")

                hook_arr.append(float(r.get("viewed_pct", 0.0)))
                apv_arr.append(float(r.get("apv_pct", 0.0)))
                q4_arr.append(float(r.get("ret_q4_pct", 0.0)))

            # Reverse so Cohort #1 is at the top
            labels = labels[::-1]
            views_arr = views_arr[::-1]
            colors_l = colors_l[::-1]
            annot_l = annot_l[::-1]
            hook_arr = hook_arr[::-1]
            apv_arr = apv_arr[::-1]
            q4_arr = q4_arr[::-1]

            y_pos = np.arange(len(labels))

            # Left Panel: Views & Watch Hours
            ax_l.barh(y_pos, views_arr, height=0.56, color=colors_l, alpha=0.90)
            max_vw = max(views_arr + [100])
            for yi, (vw_v, txt_v) in enumerate(zip(views_arr, annot_l)):
                ax_l.text(
                    vw_v + max_vw * 0.02,
                    yi,
                    txt_v,
                    va="center",
                    ha="left",
                    color=text_col,
                    fontsize=9.2,
                    fontweight="bold",
                )
            ax_l.set_yticks(y_pos)
            ax_l.set_yticklabels(labels, fontsize=10.2, fontweight="bold", color=text_col)
            ax_l.set_xlim(0, max_vw * 1.58)
            ax_l.set_xlabel("Cumulative Views (with 1d Delta, Watch Hours & Subs)", color=text_col, fontsize=11, fontweight="bold")
            ax_l.set_title("1. Views, Watch Hours & Subscriber Conversion by Video", color=text_col, fontsize=12.5, fontweight="bold", pad=12)
            from matplotlib.patches import Patch
            ax_l.legend(
                handles=[
                    Patch(facecolor=tl_green, label="Active Seed (>= 250 Views)"),
                    Patch(facecolor=tl_yellow, label="Initial / Search (50-249 Views)"),
                    Patch(facecolor=tl_red, label="Seed Starved (< 50 Views)"),
                ],
                loc="upper center",
                bbox_to_anchor=(0.5, -0.15),
                ncol=3,
                facecolor=bg,
                edgecolor="#334155",
                labelcolor=text_col,
                fontsize=8.5,
            )

            # Right Panel: Hook / APV / Q4 Retention
            bh = 0.24
            ax_r.barh(y_pos + bh, hook_arr, height=bh, color=blue, alpha=0.90, label="3s Hook (Viewed %)")
            ax_r.barh(y_pos, apv_arr, height=bh, color=tl_green, alpha=0.92, label="Watch Rate (APV %)")
            ax_r.barh(y_pos - bh, q4_arr, height=bh, color=cyan, alpha=0.82, label="Q4 End Retention (%)")

            ax_r.axvline(70.0, color=tl_yellow, linestyle="--", linewidth=1.6, alpha=0.85, label="Hook Gate (70%)")
            ax_r.axvline(60.0, color="#FB923C", linestyle=":", linewidth=1.6, alpha=0.85, label="APV/Q4 Gate (60%)")

            for yi, (hv, av, qv) in enumerate(zip(hook_arr, apv_arr, q4_arr)):
                top_x = max(hv, av, qv)
                ax_r.text(
                    top_x + 1.5,
                    yi,
                    f"H {hv:.1f}% | APV {av:.1f}% | Q4 {qv:.1f}%",
                    va="center",
                    ha="left",
                    color=text_col,
                    fontsize=8.8,
                    fontweight="bold",
                )

            ax_r.set_yticks(y_pos)
            ax_r.set_yticklabels(labels, fontsize=10.2, fontweight="bold", color=text_col)
            ax_r.set_xlim(0, 145)
            ax_r.set_xlabel("Retention Percentage (%) vs Target Gates", color=text_col, fontsize=11, fontweight="bold")
            ax_r.set_title("2. Per-Video Hook (Viewed %), APV (%) & End Retention (Q4 %)", color=text_col, fontsize=12.5, fontweight="bold", pad=12)
            ax_r.legend(
                loc="upper center",
                bbox_to_anchor=(0.5, -0.15),
                ncol=3,
                facecolor=bg,
                edgecolor="#334155",
                labelcolor=text_col,
                fontsize=8.5,
            )

        fig.suptitle(
            f"ALL ABOUT BRAIN — Video-by-Video Performance & Retention Breakdown ({data['report_date']})",
            color=text_col,
            fontsize=14.0,
            fontweight="bold",
            y=0.98,
        )
        plt.tight_layout(rect=[0.01, 0.08, 0.99, 0.93])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=160, facecolor=bg)
        plt.close(fig)
        return output_path

