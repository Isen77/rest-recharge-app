#!/usr/bin/env python3
"""
Rest & Recharge EV Charging Performance Dashboard
Streamlit App — Version 1.0

Architecture:
  - Google Sheets → live data backend
  - streamlit-authenticator → per-user login
  - Plotly → interactive charts
  - Streamlit Community Cloud → free hosting

Monthly Update Workflow:
  1. Receive CSV from Future Energy
  2. Admin logs in → Admin Panel
  3. Upload & map CSV → click "Push to Google Sheets"
  4. All 5 users see live data immediately
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import json

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG  (must be FIRST Streamlit command)
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Rest & Recharge | Performance",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* Remove default top padding */
    .block-container { padding-top: 1.5rem; }

    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e3a5f;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 0.85rem;
        color: #6b7280;
        margin-bottom: 20px;
    }

    /* KPI cards */
    div[data-testid="metric-container"] {
        background: white;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.08);
        border-left: 4px solid #1e6f41;
    }

    /* Sidebar brand */
    .sidebar-brand {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1e3a5f;
        text-align: center;
        padding: 8px 0 4px;
    }
    .sidebar-sub {
        font-size: 0.75rem;
        color: #9ca3af;
        text-align: center;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LOCATION MASTER DATA  (from Excel tracker)
# ══════════════════════════════════════════════════════════════════════════════
LOCATIONS = [
    "Hyatt Place Atlanta-Cobb",
    "Hyatt Place Fort Worth-Hurst",
    "Fairfield Inn & Suites Canton",
    "TownPlace Suites Canton",
    "Homewood Suites Troy",
    "Hampton Inn Detroit-Southgate",
]

LOCATION_CONFIG = {
    "Hyatt Place Atlanta-Cobb":       {"ports": 4, "go_live": "2025-10-20", "capex": 41363},
    "Hyatt Place Fort Worth-Hurst":   {"ports": 2, "go_live": "2025-11-13", "capex": 28976},
    "Fairfield Inn & Suites Canton":  {"ports": 2, "go_live": "2025-12-22", "capex": 28480},
    "TownPlace Suites Canton":        {"ports": 2, "go_live": "2025-12-22", "capex": 25380},
    "Homewood Suites Troy":           {"ports": 4, "go_live": "2025-12-19", "capex": 50763},
    "Hampton Inn Detroit-Southgate":  {"ports": 2, "go_live": "2025-12-12", "capex": 30649},
}

# 10-Year Annual Revenue Targets (from Excel tracker, rows G9:G18)
REVENUE_TARGETS = {
    "Hyatt Place Atlanta-Cobb":       [3248,  6691,  18412, 23599, 36371, 43566, 61473, 62859, 75149, 76964],
    "Hyatt Place Fort Worth-Hurst":   [3248,  6691,  18412, 23599, 36371, 43566, 61473, 62859, 75149, 76964],
    "Fairfield Inn & Suites Canton":  [3248,  6691,  18412, 23599, 36371, 43566, 61473, 62859, 75149, 76964],
    "TownPlace Suites Canton":        [2707,  5576,  15343, 19666, 30309, 36305, 51228, 52382, 62624, 64136],
    "Homewood Suites Troy":           [6497,  13382, 36823, 47198, 72741, 87133, 122946,125717,150299,153927],
    "Hampton Inn Detroit-Southgate":  [3248,  6691,  18412, 23599, 36371, 43566, 61473, 62859, 75149, 76964],
}

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS CONNECTION
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def get_gspread_client():
    """Initialize Google Sheets client from Streamlit secrets."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_info = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception:
        return None


@st.cache_data(ttl=300)   # refresh every 5 minutes
def load_performance_data():
    """Load performance data from Google Sheets; fall back to sample data."""
    client = get_gspread_client()

    if client:
        try:
            sheet_id = st.secrets["sheet_id"]
            spreadsheet = client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet("Performance_Data")
            records = worksheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                df["Revenue"]  = pd.to_numeric(df["Revenue"],  errors="coerce").fillna(0)
                df["Sessions"] = pd.to_numeric(df["Sessions"], errors="coerce").fillna(0)
                df["Year"]     = pd.to_numeric(df["Year"],     errors="coerce").fillna(0).astype(int)
                df["Month"]    = pd.to_numeric(df["Month"],    errors="coerce").fillna(0).astype(int)
                return df, True
        except Exception as e:
            st.warning(f"Google Sheets connected but data load failed: {e}")

    return _sample_data(), False


def _sample_data():
    """Real data from the Excel tracker — used when Google Sheets is not yet configured."""
    records = [
        # Hyatt Place Atlanta-Cobb
        {"Location": "Hyatt Place Atlanta-Cobb",      "Year": 2025, "Month": 8,  "Sessions": 15, "Revenue": 176.81},
        {"Location": "Hyatt Place Atlanta-Cobb",      "Year": 2025, "Month": 9,  "Sessions": 17, "Revenue": 244.66},
        {"Location": "Hyatt Place Atlanta-Cobb",      "Year": 2025, "Month": 10, "Sessions": 28, "Revenue": 294.83},
        {"Location": "Hyatt Place Atlanta-Cobb",      "Year": 2025, "Month": 11, "Sessions": 22, "Revenue": 258.77},
        {"Location": "Hyatt Place Atlanta-Cobb",      "Year": 2025, "Month": 12, "Sessions": 20, "Revenue": 259.97},
        {"Location": "Hyatt Place Atlanta-Cobb",      "Year": 2026, "Month": 1,  "Sessions": 31, "Revenue": 473.00},
        # Hyatt Place Fort Worth-Hurst
        {"Location": "Hyatt Place Fort Worth-Hurst",  "Year": 2025, "Month": 12, "Sessions": 1,  "Revenue": 5.41},
        {"Location": "Hyatt Place Fort Worth-Hurst",  "Year": 2026, "Month": 1,  "Sessions": 8,  "Revenue": 437.13},
        {"Location": "Hyatt Place Fort Worth-Hurst",  "Year": 2026, "Month": 2,  "Sessions": 1,  "Revenue": 45.08},
        # Fairfield Inn & Suites Canton
        {"Location": "Fairfield Inn & Suites Canton", "Year": 2026, "Month": 1,  "Sessions": 8,  "Revenue": 185.04},
        # TownPlace Suites Canton
        {"Location": "TownPlace Suites Canton",       "Year": 2026, "Month": 1,  "Sessions": 8,  "Revenue": 185.04},
        # Homewood Suites Troy
        {"Location": "Homewood Suites Troy",          "Year": 2026, "Month": 1,  "Sessions": 10, "Revenue": 174.02},
        # Hampton Inn Detroit-Southgate
        {"Location": "Hampton Inn Detroit-Southgate", "Year": 2025, "Month": 11, "Sessions": 1,  "Revenue": 11.04},
        {"Location": "Hampton Inn Detroit-Southgate", "Year": 2025, "Month": 12, "Sessions": 3,  "Revenue": 77.62},
        {"Location": "Hampton Inn Detroit-Southgate", "Year": 2026, "Month": 2,  "Sessions": 1,  "Revenue": 29.29},
    ]
    return pd.DataFrame(records)


def upload_to_sheets(new_df: pd.DataFrame) -> tuple[int, int]:
    """Upsert rows into Google Sheets Performance_Data worksheet."""
    client = get_gspread_client()
    if not client:
        raise ConnectionError("Google Sheets not configured. See Setup Guide.")

    sheet_id = st.secrets["sheet_id"]
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet("Performance_Data")

    existing_records = worksheet.get_all_records()
    existing_df = pd.DataFrame(existing_records) if existing_records else pd.DataFrame(
        columns=["Location", "Year", "Month", "Sessions", "Revenue"]
    )

    added, updated = 0, 0
    new_rows_batch = []

    for _, row in new_df.iterrows():
        loc, yr, mo = row["Location"], int(row["Year"]), int(row["Month"])

        if not existing_df.empty:
            mask = (
                (existing_df["Location"] == loc)
                & (existing_df["Year"].astype(int) == yr)
                & (existing_df["Month"].astype(int) == mo)
            )
            if mask.any():
                idx = existing_df[mask].index[0] + 2   # +2: 1 header + 1-indexed
                worksheet.update(
                    f"A{idx}:E{idx}",
                    [[loc, yr, mo, int(row["Sessions"]), round(float(row["Revenue"]), 2)]],
                )
                updated += 1
                continue

        new_rows_batch.append([loc, yr, mo, int(row["Sessions"]), round(float(row["Revenue"]), 2)])
        added += 1

    if new_rows_batch:
        worksheet.append_rows(new_rows_batch)

    st.cache_data.clear()   # force dashboard refresh
    return added, updated


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
def get_op_year(location: str, data_year: int) -> int:
    """Return the operational year number (1-10) for a location in a calendar year."""
    go_live = datetime.strptime(LOCATION_CONFIG[location]["go_live"], "%Y-%m-%d")
    op_year = data_year - go_live.year + 1
    return max(1, min(10, op_year))


def get_annual_target(location: str, year: int) -> float:
    if location not in REVENUE_TARGETS:
        return 0.0
    op_year = get_op_year(location, year)
    return float(REVENUE_TARGETS[location][op_year - 1])


def fmt_usd(value: float) -> str:
    if value >= 1_000:
        return f"${value:,.0f}"
    return f"${value:.2f}"


def pct_label(pct: float) -> str:
    return f"{pct:.1%}"


def status_badge(pct: float) -> str:
    if pct >= 1.0:
        return "✅ On Track"
    if pct >= 0.75:
        return "⚠️ Near Target"
    return "🔴 Behind"


# ══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════
def run_auth() -> tuple:
    """
    Returns (authenticator, user_role).
    Falls back to demo admin mode if config.yaml is not present.
    """
    try:
        import streamlit_authenticator as stauth
        import yaml
        from yaml.loader import SafeLoader

        with open("config.yaml") as f:
            cfg = yaml.load(f, Loader=SafeLoader)

        authenticator = stauth.Authenticate(
            cfg["credentials"],
            cfg["cookie"]["name"],
            cfg["cookie"]["key"],
            cfg["cookie"]["expiry_days"],
        )
        authenticator.login()

        status = st.session_state.get("authentication_status")
        if status is False:
            st.error("❌ Incorrect username or password. Please try again.")
            st.stop()
        elif status is None:
            _render_login_splash()
            st.stop()

        username = st.session_state.get("username", "")
        role = cfg["credentials"]["usernames"].get(username, {}).get("role", "viewer")
        return authenticator, role

    except FileNotFoundError:
        # ── DEMO MODE: no config.yaml found ──────────────────────────────────
        st.session_state.setdefault("name", "Demo Admin")
        st.session_state.setdefault("username", "admin")
        st.session_state.setdefault("authentication_status", True)
        return None, "admin"


def _render_login_splash():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 60px 0 20px;">
            <div style="font-size:3rem;">⚡</div>
            <h1 style="color:#1e3a5f; margin:8px 0 4px;">Rest & Recharge</h1>
            <p style="color:#6b7280;">EV Charging Performance Dashboard</p>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PROGRAM DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_dashboard(df: pd.DataFrame, is_live: bool):
    now = datetime.now()
    yr  = now.year

    st.markdown('<div class="main-header">⚡ Rest & Recharge — Program Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-header">EV Charging Revenue Performance &nbsp;|&nbsp; '
        f'{"🟢 Live Google Sheets" if is_live else "🟡 Demo Mode — Connect Google Sheets to show live data"}'
        f'&nbsp;|&nbsp; Last refreshed: {now.strftime("%b %d, %Y %H:%M")}</div>',
        unsafe_allow_html=True
    )

    # ── Program-level KPIs ────────────────────────────────────────────────────
    yr_df         = df[df["Year"] == yr]
    ytd_revenue   = yr_df["Revenue"].sum()
    ytd_sessions  = int(yr_df["Sessions"].sum())
    total_revenue = df["Revenue"].sum()

    # Pro-rated annual target through current month
    ytd_target = sum(
        (get_annual_target(loc, yr) / 12) * now.month
        for loc in LOCATIONS
    )
    full_yr_target = sum(get_annual_target(loc, yr) for loc in LOCATIONS)
    pct_target = ytd_revenue / ytd_target if ytd_target > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        delta = ytd_revenue - ytd_target
        st.metric("YTD Revenue (Actual)", fmt_usd(ytd_revenue),
                  delta=f"{fmt_usd(abs(delta))} {'ahead' if delta >= 0 else 'behind'} pace")
    with c2:
        st.metric("YTD Revenue Target (Pro-Rated)", fmt_usd(ytd_target))
    with c3:
        color = "normal" if pct_target >= 1 else "inverse"
        st.metric("% of Pro-Rated Target", pct_label(pct_target),
                  delta=f"{(pct_target - 1.0):+.1%} vs target", delta_color=color)
    with c4:
        st.metric("Total YTD Sessions", f"{ytd_sessions:,}")

    st.divider()

    # ── Location Performance Table ────────────────────────────────────────────
    st.subheader("📊 Location Performance Summary")

    rows = []
    for loc in LOCATIONS:
        loc_yr  = df[(df["Location"] == loc) & (df["Year"] == yr)]
        actual  = loc_yr["Revenue"].sum()
        sess    = int(loc_yr["Sessions"].sum())
        target  = get_annual_target(loc, yr)
        pro_target = (target / 12) * now.month
        pct     = actual / pro_target if pro_target > 0 else 0
        variance = actual - pro_target
        rows.append({
            "Location":         loc,
            "YTD Revenue":      fmt_usd(actual),
            "Pro-Rated Target": fmt_usd(pro_target),
            "Annual Target":    fmt_usd(target),
            "% of Target":      pct_label(pct),
            "Variance":         fmt_usd(variance),
            "Sessions":         sess,
            "Status":           status_badge(pct),
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Location": st.column_config.TextColumn("Location", width="large"),
        },
    )

    st.divider()

    # ── Charts Row 1: Monthly Trend + Revenue by Location ─────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("📈 Monthly Revenue Trend")
        monthly = (
            df[df["Year"] == yr]
            .groupby("Month")["Revenue"]
            .sum()
            .reset_index()
            .sort_values("Month")
        )
        monthly["Month_Name"] = monthly["Month"].map(MONTH_NAMES)

        if not monthly.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=monthly["Month_Name"], y=monthly["Revenue"],
                marker_color="#1e6f41",
                text=[fmt_usd(v) for v in monthly["Revenue"]],
                textposition="outside",
            ))
            # Monthly pro-rated target line
            avg_monthly_target = full_yr_target / 12
            fig.add_hline(y=avg_monthly_target, line_dash="dash", line_color="#ef4444",
                          annotation_text=f"Monthly Target: {fmt_usd(avg_monthly_target)}")
            fig.update_layout(
                height=340, margin=dict(t=30, b=10, l=10, r=10),
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(tickformat="$,.0f", gridcolor="#f3f4f6"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data yet for the current year.")

    with col_r:
        st.subheader(f"🏨 YTD Revenue by Location ({yr})")
        loc_rev = [
            {"Short": loc.split()[-1], "Revenue": df[(df["Location"] == loc) & (df["Year"] == yr)]["Revenue"].sum(), "Full": loc}
            for loc in LOCATIONS
        ]
        loc_rev_df = pd.DataFrame(loc_rev).sort_values("Revenue", ascending=True)

        if loc_rev_df["Revenue"].sum() > 0:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                y=loc_rev_df["Short"], x=loc_rev_df["Revenue"],
                orientation="h",
                marker_color="#1e6f41",
                text=[fmt_usd(v) for v in loc_rev_df["Revenue"]],
                textposition="outside",
            ))
            fig2.update_layout(
                height=340, margin=dict(t=30, b=10, l=10, r=10),
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(tickformat="$,.0f", gridcolor="#f3f4f6"),
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data yet for the current year.")

    # ── Charts Row 2: Actual vs Target + % of Target ──────────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.subheader(f"🎯 Actual vs Pro-Rated Target ({yr})")
        actuals, targets_pro, labels = [], [], []
        for loc in LOCATIONS:
            a = df[(df["Location"] == loc) & (df["Year"] == yr)]["Revenue"].sum()
            t = (get_annual_target(loc, yr) / 12) * now.month
            short = loc.split()[-1]
            actuals.append(a); targets_pro.append(t); labels.append(short)

        fig3 = go.Figure()
        fig3.add_trace(go.Bar(name="Actual Revenue", x=labels, y=actuals, marker_color="#1e6f41"))
        fig3.add_trace(go.Bar(name="Pro-Rated Target", x=labels, y=targets_pro, marker_color="#d1d5db"))
        fig3.update_layout(
            barmode="group", height=320,
            margin=dict(t=30, b=10, l=10, r=10),
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(tickformat="$,.0f", gridcolor="#f3f4f6"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_r2:
        st.subheader(f"📉 % of Target by Location ({yr})")
        pct_data = []
        for loc in LOCATIONS:
            a = df[(df["Location"] == loc) & (df["Year"] == yr)]["Revenue"].sum()
            t = (get_annual_target(loc, yr) / 12) * now.month
            pct = (a / t * 100) if t > 0 else 0
            pct_data.append({"Location": loc.split()[-1], "Pct": pct})

        pct_df = pd.DataFrame(pct_data).sort_values("Pct", ascending=True)
        colors = ["#22c55e" if p >= 100 else "#f59e0b" if p >= 75 else "#ef4444" for p in pct_df["Pct"]]

        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            y=pct_df["Location"], x=pct_df["Pct"],
            orientation="h", marker_color=colors,
            text=[f"{v:.1f}%" for v in pct_df["Pct"]],
            textposition="outside",
        ))
        fig4.add_vline(x=100, line_dash="dash", line_color="#1e6f41",
                       annotation_text="Target (100%)")
        fig4.update_layout(
            height=320, margin=dict(t=30, b=10, l=10, r=10),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(ticksuffix="%", gridcolor="#f3f4f6"),
            showlegend=False,
        )
        st.plotly_chart(fig4, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: LOCATION DETAIL
# ══════════════════════════════════════════════════════════════════════════════
def page_location(df: pd.DataFrame, location: str):
    cfg     = LOCATION_CONFIG[location]
    go_live = datetime.strptime(cfg["go_live"], "%Y-%m-%d")
    now     = datetime.now()

    st.markdown(f'<div class="main-header">🏨 {location}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-header">'
        f'Go-Live: {go_live.strftime("%B %d, %Y")} &nbsp;|&nbsp; '
        f'Ports: {cfg["ports"]} &nbsp;|&nbsp; '
        f'CapEx: {fmt_usd(cfg["capex"])}'
        f'</div>',
        unsafe_allow_html=True,
    )

    loc_df = df[df["Location"] == location].copy()
    years_avail = sorted(loc_df["Year"].unique(), reverse=True)

    if not years_avail:
        st.info("No data recorded for this location yet. Use the Admin Panel to upload monthly data.")
        return

    sel_year = st.selectbox("Select Year", years_avail)
    year_df  = loc_df[loc_df["Year"] == sel_year].sort_values("Month")

    ann_target  = get_annual_target(location, sel_year)
    ytd_actual  = year_df["Revenue"].sum()
    pro_target  = (ann_target / 12) * (now.month if sel_year == now.year else 12)
    pct         = ytd_actual / pro_target if pro_target > 0 else 0
    sessions    = int(year_df["Sessions"].sum())

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("YTD Revenue", fmt_usd(ytd_actual))
    with c2: st.metric("Pro-Rated Target", fmt_usd(pro_target))
    with c3:
        st.metric("% of Target", pct_label(pct),
                  delta=f"{(pct-1.0):+.1%}", delta_color="normal" if pct >= 1 else "inverse")
    with c4: st.metric("YTD Sessions", f"{sessions:,}")

    st.divider()

    # Monthly table + bar chart
    col_tbl, col_chart = st.columns([1, 1])

    with col_tbl:
        st.subheader("Monthly Breakdown")
        if not year_df.empty:
            monthly_target = ann_target / 12
            disp = year_df.copy()
            disp["Month"]    = disp["Month"].map(MONTH_NAMES)
            disp["Target"]   = monthly_target
            disp["Variance"] = disp["Revenue"] - monthly_target

            disp["Revenue"]  = disp["Revenue"].apply(lambda x: f"${x:,.2f}")
            disp["Target"]   = disp["Target"].apply(lambda x:  f"${x:,.2f}")
            disp["Variance"] = disp["Variance"].apply(
                lambda x: f"+${x:,.2f}" if x >= 0 else f"-${abs(x):,.2f}"
            )
            disp["Sessions"] = disp["Sessions"].astype(int)

            st.dataframe(
                disp[["Month", "Sessions", "Revenue", "Target", "Variance"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No data recorded yet for this year.")

    with col_chart:
        st.subheader("Monthly Revenue vs Target")
        if not year_df.empty:
            monthly_target = ann_target / 12
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=year_df["Month"].map(MONTH_NAMES), y=year_df["Revenue"],
                name="Actual", marker_color="#1e6f41",
            ))
            fig.add_hline(y=monthly_target, line_dash="dash", line_color="#ef4444",
                          annotation_text=f"Monthly Target: {fmt_usd(monthly_target)}")
            fig.update_layout(
                height=320, margin=dict(t=30, b=10, l=10, r=10),
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(tickformat="$,.0f", gridcolor="#f3f4f6"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    # 10-year ramp chart
    st.divider()
    st.subheader("📅 10-Year Revenue Target Progression")

    target_yrs  = list(range(go_live.year, go_live.year + 10))
    target_vals = REVENUE_TARGETS[location]
    actual_by_yr = loc_df.groupby("Year")["Revenue"].sum()

    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(
        x=target_yrs, y=target_vals,
        mode="lines+markers", name="Annual Target",
        line=dict(color="#6b7280", dash="dash"), marker=dict(size=8),
    ))
    fig5.add_trace(go.Bar(
        x=[y for y in target_yrs if y in actual_by_yr.index],
        y=[actual_by_yr[y] for y in target_yrs if y in actual_by_yr.index],
        name="Actual Revenue", marker_color="#1e6f41",
    ))
    fig5.update_layout(
        height=280, margin=dict(t=20, b=10, l=10, r=10),
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(tickformat="$,.0f", gridcolor="#f3f4f6"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig5, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ADMIN PANEL — CSV UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
def page_admin(df: pd.DataFrame, is_live: bool):
    st.markdown('<div class="main-header">⚙️ Admin Panel — Monthly Data Update</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Upload the monthly CSV from Future Energy to refresh all dashboards</div>',
        unsafe_allow_html=True,
    )

    if not is_live:
        st.warning(
            "⚠️ **Demo Mode** — Google Sheets is not connected yet. "
            "Uploads will be processed and downloadable but NOT persisted. "
            "Follow the **Setup Guide** to connect Google Sheets."
        )

    # ── Expected Format ───────────────────────────────────────────────────────
    with st.expander("📋 Expected CSV Format (click to expand)", expanded=False):
        st.markdown("""
**Your CSV from Future Energy should contain at minimum:**

| Column | Example Values | Notes |
|--------|---------------|-------|
| Location | `Hyatt Place Atlanta-Cobb` | Partial names OK (e.g. "Atlanta") |
| Year | `2026` | 4-digit year |
| Month | `2` | 1–12, OR use a Date column instead |
| Sessions | `31` | Integer count |
| Revenue | `473.00` | Dollar amount, no $ sign needed |

**Alternative:** If you have a single date column (e.g. `2026-02-01` or `February 2026`),
select it in the **Date** column mapping below and leave Year/Month blank.

**Tip:** Column header names don't need to match exactly — you'll map them below.
        """)

    # ── File Upload ───────────────────────────────────────────────────────────
    st.subheader("📤 Step 1: Upload File")
    uploaded = st.file_uploader(
        "Choose your CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        help="Monthly performance report from Future Energy",
    )

    if not uploaded:
        return

    # Read file
    try:
        if uploaded.name.lower().endswith((".xlsx", ".xls")):
            raw_df = pd.read_excel(uploaded)
        else:
            raw_df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return

    st.success(f"✅ File loaded — **{len(raw_df):,} rows**, **{len(raw_df.columns)} columns**")
    with st.expander("Preview raw data", expanded=True):
        st.dataframe(raw_df.head(20), use_container_width=True)

    # ── Column Mapping ────────────────────────────────────────────────────────
    st.subheader("🔗 Step 2: Map Your Columns")
    st.caption("Tell us which columns in your file contain each field.")

    NONE = "(not in file)"
    cols = [NONE] + list(raw_df.columns)

    col_a, col_b = st.columns(2)
    with col_a:
        map_loc      = st.selectbox("Location column *",         cols, index=min(1, len(cols)-1), key="ml")
        map_year     = st.selectbox("Year column",               cols, key="my")
        map_month    = st.selectbox("Month column",              cols, key="mm")
        map_date     = st.selectbox("Date column (alt to Year+Month)", cols, key="md")
    with col_b:
        map_sessions = st.selectbox("Sessions column *",         cols, key="ms")
        map_revenue  = st.selectbox("Revenue column *",          cols, index=min(2, len(cols)-1), key="mr")

    st.caption("* = required")

    # ── Process ───────────────────────────────────────────────────────────────
    st.subheader("🔄 Step 3: Process & Review")

    if st.button("Process File", type="primary"):
        processed, errors = [], []

        for idx, row in raw_df.iterrows():
            try:
                # Location
                if map_loc == NONE:
                    errors.append(f"Row {idx+2}: No location column selected"); continue
                raw_loc = str(row[map_loc]).strip()
                matched = next(
                    (loc for loc in LOCATIONS
                     if any(part.lower() in raw_loc.lower() for part in loc.split() if len(part) > 3)),
                    None,
                )
                if not matched:
                    errors.append(f"Row {idx+2}: Cannot match '{raw_loc}' to a known location"); continue

                # Year + Month
                if map_year != NONE and map_month != NONE:
                    year, month = int(row[map_year]), int(row[map_month])
                elif map_date != NONE:
                    dt = pd.to_datetime(row[map_date])
                    year, month = dt.year, dt.month
                else:
                    errors.append(f"Row {idx+2}: Provide Year+Month columns OR a Date column"); continue

                # Metrics
                revenue  = float(str(row[map_revenue]).replace("$", "").replace(",", "")) if map_revenue != NONE else 0.0
                sessions = float(str(row[map_sessions]).replace(",", ""))                  if map_sessions != NONE else 0.0

                processed.append({
                    "Location": matched,
                    "Year":     year,
                    "Month":    month,
                    "Sessions": int(sessions),
                    "Revenue":  round(revenue, 2),
                })

            except Exception as e:
                errors.append(f"Row {idx+2}: {e}")

        # Show warnings
        if errors:
            with st.expander(f"⚠️ {len(errors)} processing warnings"):
                for e in errors:
                    st.text(e)

        if not processed:
            st.error("No records could be processed. Check your column mappings.")
            return

        proc_df = pd.DataFrame(processed)
        st.session_state["processed_df"] = proc_df

        st.success(f"✅ Successfully processed **{len(proc_df)} records** across **{proc_df['Location'].nunique()} locations**")

        # Summary
        summary = (
            proc_df.groupby("Location")
            .agg(Records=("Revenue", "count"), Total_Revenue=("Revenue", "sum"), Total_Sessions=("Sessions", "sum"))
            .reset_index()
        )
        summary["Total_Revenue"] = summary["Total_Revenue"].apply(fmt_usd)
        st.dataframe(summary, use_container_width=True, hide_index=True)

        with st.expander("Preview all processed records"):
            st.dataframe(proc_df, use_container_width=True, hide_index=True)

    # ── Upload to Sheets / Download ───────────────────────────────────────────
    if "processed_df" in st.session_state:
        proc_df = st.session_state["processed_df"]

        st.subheader("📤 Step 4: Push to Google Sheets")

        col_up, col_dl = st.columns(2)

        with col_up:
            if is_live:
                if st.button("🚀 Push to Google Sheets (updates live dashboard)", type="primary"):
                    with st.spinner("Uploading to Google Sheets…"):
                        try:
                            added, updated = upload_to_sheets(proc_df)
                            st.success(
                                f"✅ Done! **{added} new records added**, **{updated} existing records updated**.\n\n"
                                "All users will see updated data within 5 minutes."
                            )
                            del st.session_state["processed_df"]
                        except Exception as e:
                            st.error(f"Upload failed: {e}")
            else:
                st.info(
                    "📌 Google Sheets not connected. Connect it via the Setup Guide, "
                    "then come back here to push data live."
                )

        with col_dl:
            buf = io.StringIO()
            proc_df.to_csv(buf, index=False)
            st.download_button(
                "⬇️ Download Processed CSV",
                data=buf.getvalue(),
                file_name=f"rr_data_{datetime.now().strftime('%Y%m')}.csv",
                mime="text/csv",
                help="Download the processed data to manually paste into Google Sheets",
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SETUP GUIDE
# ══════════════════════════════════════════════════════════════════════════════
def page_setup():
    st.markdown('<div class="main-header">📚 Setup Guide</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">One-time setup to go from Demo Mode to Live Data — about 30 minutes total</div>', unsafe_allow_html=True)

    st.info("💡 **Currently running in Demo Mode.** Complete these steps to connect live Google Sheets data.")

    st.markdown("""
---
### Step 1 — Create Your Google Sheet (5 min)

1. Go to [sheets.google.com](https://sheets.google.com) and create a new spreadsheet.
2. Name it: **Rest Recharge Performance**
3. Rename the first tab to: **Performance_Data**
4. Add these headers in **Row 1** exactly:

| A | B | C | D | E |
|---|---|---|---|---|
| `Location` | `Year` | `Month` | `Sessions` | `Revenue` |

5. Copy your **Sheet ID** from the URL:
   `https://docs.google.com/spreadsheets/d/`**`YOUR_SHEET_ID`**`/edit`

---

### Step 2 — Create Google API Credentials (10 min)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g., "Rest Recharge App")
3. Enable these two APIs:
   - **Google Sheets API**
   - **Google Drive API**
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
5. Give it a name (e.g., `rest-recharge-reader`), skip optional steps, click **Done**
6. Click on the service account → **Keys** tab → **Add Key → Create New Key → JSON** → Download
7. **Share your Google Sheet** with the service account email (found in the JSON file under `client_email`). Give it **Editor** access.

---

### Step 3 — Deploy to Streamlit Community Cloud (10 min)

1. Create a free account at [github.com](https://github.com) and upload your app files
2. Create a free account at [share.streamlit.io](https://share.streamlit.io)
3. Click **New App** → connect your GitHub repo → select `app.py`
4. In **Advanced Settings → Secrets**, paste this (replacing with your real values):

```toml
sheet_id = "your_google_sheet_id_here"

[gcp_service_account]
type = "service_account"
project_id = "your_project_id"
private_key_id = "abc123..."
private_key = \"\"\"-----BEGIN RSA PRIVATE KEY-----
...paste your private key here...
-----END RSA PRIVATE KEY-----
\"\"\"
client_email = "your-service@your-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```

5. Click **Deploy** — your app will be live at `https://your-app.streamlit.app`!

---

### Step 4 — Set Up User Logins (5 min)

Edit `config.yaml` to add your 5 users. Replace the placeholder passwords with hashed ones.

To generate a password hash, run this in your terminal:
```python
python3 -c "import streamlit_authenticator as s; print(s.Hasher(['YOUR_PASSWORD']).generate()[0])"
```

---

### Monthly Update Workflow (2 min each month)

Once set up, your monthly routine is:

1. 📧 Receive CSV from Future Energy
2. 🔐 Log in to the dashboard as **admin**
3. ⚙️ Click **Admin Panel** in the sidebar
4. 📤 Upload the CSV → map columns → click **Push to Google Sheets**
5. ✅ All users see updated data within 5 minutes — no other action needed!
    """)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
def main():
    # ── Auth ──────────────────────────────────────────────────────────────────
    authenticator, user_role = run_auth()

    name     = st.session_state.get("name", "User")
    username = st.session_state.get("username", "")

    # ── Load Data ──────────────────────────────────────────────────────────────
    df, is_live = load_performance_data()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f'<div class="sidebar-brand">⚡ Rest & Recharge</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-sub">EV Performance Dashboard</div>', unsafe_allow_html=True)

        st.markdown(f"**👤 {name}** &nbsp;·&nbsp; *{user_role.title()}*")
        if is_live:
            st.success("🟢 Live Data")
        else:
            st.warning("🟡 Demo Mode")

        st.divider()

        nav_options = ["📊 Program Dashboard"]
        nav_options += [f"🏨 {loc}" for loc in LOCATIONS]
        if user_role == "admin":
            nav_options += ["⚙️ Admin Panel"]
        nav_options += ["📚 Setup Guide"]

        page = st.radio("Navigate", nav_options, label_visibility="collapsed")

        st.divider()

        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        if authenticator:
            try:
                authenticator.logout("🚪 Logout", "sidebar")
            except Exception:
                pass
        else:
            if st.button("🚪 Logout (Demo)", use_container_width=True):
                for k in ["authentication_status", "name", "username"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # ── Page Router ───────────────────────────────────────────────────────────
    if page == "📊 Program Dashboard":
        page_dashboard(df, is_live)
    elif page == "⚙️ Admin Panel":
        page_admin(df, is_live)
    elif page == "📚 Setup Guide":
        page_setup()
    else:
        for loc in LOCATIONS:
            if page == f"🏨 {loc}":
                page_location(df, loc)
                break


if __name__ == "__main__":
    main()
