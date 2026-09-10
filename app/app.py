import streamlit as st
import pandas as pd
import db

st.set_page_config(page_title="HCP Targeting & Call Planning", layout="wide")

st.title("HCP Targeting & Call Planning System")
st.caption(
    "Requirements-to-Design case study — BRD → Technical Design Doc → working implementation. "
    "Segmentation is a transparent weighted formula (70% volume, 30% growth), not a black-box model — "
    "see the Technical Design Doc for why."
)

with st.expander("Design docs (BRD & Technical Design Document)"):
    st.markdown(
        "- [Business Requirements Document](https://github.com/Dhayalramesh/hcp-targeting-case-study/blob/main/docs/01_BRD.md)\n"
        "- [Technical Design Document](https://github.com/Dhayalramesh/hcp-targeting-case-study/blob/main/docs/02_TECHNICAL_DESIGN.md)\n"
        "- [Full schema](https://github.com/Dhayalramesh/hcp-targeting-case-study/blob/main/sql/schema.sql)\n"
        "- [Segmentation scoring SQL](https://github.com/Dhayalramesh/hcp-targeting-case-study/blob/main/sql/scoring.sql)"
    )

territories_df = db.get_territories()
territory_options = ["All territories"] + territories_df["territory_name"].tolist()
territory_name_to_id = dict(zip(territories_df["territory_name"], territories_df["territory_id"]))

tab1, tab2, tab3, tab4 = st.tabs(["Rep View", "Manager View", "Coverage", "Decline Alerts"])

# ---------------- Rep View ----------------
with tab1:
    st.subheader("Prioritized HCP list")
    col1, col2 = st.columns(2)
    with col1:
        sel_territory = st.selectbox("Territory", territory_options, key="rep_territory")
    with col2:
        sel_tier = st.selectbox("Tier", ["All tiers", "A", "B", "C", "D"], key="rep_tier")

    tid = territory_name_to_id.get(sel_territory) if sel_territory != "All territories" else None
    tier = sel_tier if sel_tier != "All tiers" else None

    scores_df = db.get_hcp_scores(territory_id=tid, tier=tier)

    if scores_df.empty:
        st.info("No HCPs match this filter.")
    else:
        display_df = scores_df[[
            "hcp_name", "specialty", "territory_name", "tier",
            "latest_volume", "growth_pct_3mo", "composite_score", "recommended_call_interval_days"
        ]].rename(columns={
            "hcp_name": "HCP",
            "specialty": "Specialty",
            "territory_name": "Territory",
            "tier": "Tier",
            "latest_volume": "Latest Rx Volume",
            "growth_pct_3mo": "3mo Growth %",
            "composite_score": "Composite Score",
            "recommended_call_interval_days": "Recommended Call Interval (days)",
        })
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Latest Rx Volume": st.column_config.NumberColumn(format="%d"),
                "3mo Growth %": st.column_config.NumberColumn(format="%.1f%%"),
                "Composite Score": st.column_config.NumberColumn(format="%.2f"),
                "Recommended Call Interval (days)": st.column_config.NumberColumn(format="%d"),
            },
        )
        st.caption(
            f"{len(display_df)} HCPs shown · Composite score = 0.7×volume quartile + 0.3×growth quartile, "
            "within territory (see Technical Design Doc §5.2)."
        )

# ---------------- Manager View ----------------
with tab2:
    st.subheader("Territory roll-up")
    summary_df = db.get_territory_summary()
    st.dataframe(
        summary_df.rename(columns={
            "territory_name": "Territory",
            "total_hcps": "Total HCPs",
            "tier_a_count": "Tier A HCPs",
            "avg_coverage_pct": "Avg Coverage %",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total HCPs": st.column_config.NumberColumn(format="%d"),
            "Tier A HCPs": st.column_config.NumberColumn(format="%d"),
            "Avg Coverage %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    st.subheader("Coverage by tier (all territories)")
    tier_df = db.get_coverage_by_tier()
    if not tier_df.empty:
        st.bar_chart(tier_df.set_index("tier")["avg_coverage_pct"])
        st.caption("Target: >80% coverage for Tier A/B, per BRD success metrics.")

# ---------------- Coverage ----------------
with tab3:
    st.subheader("Call coverage vs. recommended, by HCP")
    sel_territory_cov = st.selectbox("Territory", territory_options, key="cov_territory")
    tid_cov = territory_name_to_id.get(sel_territory_cov) if sel_territory_cov != "All territories" else None

    coverage_df = db.get_coverage_summary(territory_id=tid_cov)
    if coverage_df.empty:
        st.info("No data for this territory.")
    else:
        display_cov = coverage_df[[
            "hcp_name", "territory_name", "tier", "calls_last_90_days",
            "recommended_calls_90_days", "coverage_pct"
        ]].rename(columns={
            "hcp_name": "HCP",
            "territory_name": "Territory",
            "tier": "Tier",
            "calls_last_90_days": "Actual Calls (90d)",
            "recommended_calls_90_days": "Recommended Calls (90d)",
            "coverage_pct": "Coverage %",
        })

        # cast to plain float so styling comparisons work cleanly
        display_cov["Coverage %"] = display_cov["Coverage %"].astype(float)
        display_cov["Actual Calls (90d)"] = display_cov["Actual Calls (90d)"].astype(int)
        display_cov["Recommended Calls (90d)"] = display_cov["Recommended Calls (90d)"].astype(int)

        def highlight_low(val):
            if isinstance(val, (int, float)) and val < 60:
                return "background-color: #f8d7da"
            return ""

        st.dataframe(
            display_cov.style.applymap(highlight_low, subset=["Coverage %"]).format({
                "Coverage %": "{:.1f}%",
                "Actual Calls (90d)": "{:d}",
                "Recommended Calls (90d)": "{:d}",
            }),
            use_container_width=True,
            hide_index=True,
        )
        under_covered = (coverage_df["coverage_pct"].astype(float) < 60).sum()
        st.caption(f"{under_covered} HCPs are under 60% of recommended coverage, highlighted above.")

# ---------------- Decline Alerts ----------------
with tab4:
    st.subheader("Tier A/B HCPs with 2 consecutive months of declining Rx volume")
    st.caption("Flags a prescribing drop before it shows up in quarterly numbers — BRD success metric: <2 week detection.")
    alerts_df = db.get_decline_alerts()
    if alerts_df.empty:
        st.success("No decline alerts for high-priority HCPs right now.")
    else:
        display_alerts = alerts_df.drop(columns=["hcp_id"]).rename(columns={
            "hcp_name": "HCP",
            "territory_name": "Territory",
            "tier": "Tier",
            "two_months_ago_volume": "2 Months Ago",
            "last_month_volume": "Last Month",
            "current_month_volume": "Current Month",
        })
        st.dataframe(
            display_alerts,
            use_container_width=True,
            hide_index=True,
            column_config={
                "2 Months Ago": st.column_config.NumberColumn(format="%d"),
                "Last Month": st.column_config.NumberColumn(format="%d"),
                "Current Month": st.column_config.NumberColumn(format="%d"),
            },
        )