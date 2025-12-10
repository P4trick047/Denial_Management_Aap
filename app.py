import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import requests
import os

# --------------------------- CONFIG ---------------------------
st.set_page_config(page_title="NikoHealth Denials Dashboard", layout="wide")
st.title("NikoHealth Denials Management Dashboard")

# Use real API if key exists, otherwise show mock data
API_KEY = st.secrets.get("NIKO_API_KEY", None)
USE_REAL_API = API_KEY is not None

API_BASE = "https://api.nikohealth.com"  # Confirm with NikoHealth if different

# --------------------------- FETCH DATA ---------------------------
@st.cache_data(ttl=600, show_spinner="Fetching denials data...")
def fetch_denials(start_date, end_date, payer=None):
    if USE_REAL_API:
        # === REAL API CALL (uncomment when you have key) ===
        headers = {"Authorization": f"Bearer {API_KEY}"}
        params = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "limit": 1000
        }
        try:
            response = requests.get(f"{API_BASE}/v2/payments", headers=headers, params=params, timeout=20)
            if response.status_code == 200:
                data = response.json().get("data", [])
                df = pd.DataFrame(data)
                # Adjust these columns based on actual NikoHealth response
                df = df[df["status"].str.lower() == "denied"]
                df["date"] = pd.to_datetime(df["created_at"] or df["date"])
                df["denial_amount"] = abs(df["adjustment_amount"].fillna(0))
                return df
            else:
                st.error(f"API Error {response.status_code}: {response.text}")
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Connection error: {e}")
            return pd.DataFrame()
    else:
        # === MOCK DATA (works instantly) ===
        st.warning("Running in demo mode – showing sample data (no API key needed)")
        mock_data = [
            {"id": 101, "patient_id": "PT-1001", "payer_name": "Medicare", "status": "denied", "created_at": "2025-12-09", "adjustment_amount": -425.00, "denial_reason": "CO-97: Duplicate", "invoice_id": "INV-8401"},
            {"id": 102, "patient_id": "PT-1005", "payer_name": "Blue Cross", "status": "denied", "created_at": "2025-12-08", "adjustment_amount": -180.00, "denial_reason": "PR-96: Non-covered", "invoice_id": "INV-8405"},
            {"id": 103, "patient_id": "PT-1012", "payer_name": "Aetna", "status": "denied", "created_at": "2025-12-07", "adjustment_amount": -720.00, "denial_reason": "CO-45: Charge exceeds fee", "invoice_id": "INV-8412"},
            {"id": 104, "patient_id": "PT-1008", "payer_name": "Medicare", "status": "denied", "created_at": "2025-12-06", "adjustment_amount": -310.00, "denial_reason": "CO-16: Missing info", "invoice_id": "INV-8408"},
            {"id": 105, "patient_id": "PT-1020", "payer_name": "UnitedHealthcare", "status": "denied", "created_at": "2025-12-05", "adjustment_amount": -95.00, "denial_reason": "OA-23: Prior payer paid", "invoice_id": "INV-8420"},
        ]
        df = pd.DataFrame(mock_data * 12)  # Repeat for more rows
        df["date"] = pd.to_datetime(df["created_at"])
        df["denial_amount"] = abs(df["adjustment_amount"])
        return df

# --------------------------- SIDEBAR FILTERS ---------------------------
st.sidebar.header("Filters")
default_start = datetime.today() - timedelta(days=30)
default_end = datetime.today()

start_date = st.sidebar.date_input("Start Date", default_start)
end_date = st.sidebar.date_input("End Date", default_end)
payer_filter = st.sidebar.text_input("Payer Name (optional)")

# --------------------------- LOAD DATA ---------------------------
df = fetch_denials(start_date, end_date, payer_filter)

if df.empty:
    st.info("No denials found in the selected date range.")
    st.stop()

# Optional payer filter
if payer_filter:
    df = df[df["payer_name"].astype(str).str.contains(payer_filter, case=False, na=False)]

# --------------------------- KEY METRICS ---------------------------
col1, col2, col3, col4 = st.columns(4)
total_denials = len(df)
total_amount = df["denial_amount"].sum()
avg_denial = df["denial_amount"].mean()
denial_rate = f"{(total_denials / (total_denials + 500)) * 100:.1f}%"  # Rough estimate

with col1:
    st.metric("Total Denials", f"{total_denials:,}")
with col2:
    st.metric("Total Denied Amount", f"${total_amount:,.0f}")
with col3:
    st.metric("Average Denial", f"${avg_denial:,.0f}")
with col4:
    st.metric("Est. Denial Rate", denial_rate)

# --------------------------- CHARTS ---------------------------
st.subheader("Denial Trends")
df_weekly = df.resample("W-Mon", on="date")["denial_amount"].sum().reset_index()
chart_trend = alt.Chart(df_weekly).mark_line(color="#FF6B6B").encode(
    x="date:T",
    y="denial_amount:Q"
).properties(height=300)
st.altair_chart(chart_trend, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Top Denial Reasons")
    reasons = df["denial_reason"].value_counts().head(8).reset_index()
    pie = alt.Chart(reasons).mark_arc().encode(
        theta="count:Q",
        color="denial_reason:N"
    )
    st.altair_chart(pie, use_container_width=True)

with col2:
    st.subheader("Denials by Payer")
    payers = df["payer_name"].value_counts().head(8).reset_index()
    bar = alt.Chart(payers).mark_bar(color="#4ECDC4").encode(
        y=alt.Y("payer_name:N", sort="-x"),
        x="count:Q"
    )
    st.altair_chart(bar, use_container_width=True)

# --------------------------- DETAILED TABLE ---------------------------
st.subheader("Detailed Denials List")
display_cols = ["date", "patient_id", "payer_name", "denial_reason", "denial_amount", "invoice_id"]
df_display = df[display_cols].copy()
df_display["date"] = df_display["date"].dt.strftime("%Y-%b-%d")
df_display["denial_amount"] = df_display["denial_amount"].map("${:,.2f}".format)

st.dataframe(df_display.sort_values("date", ascending=False), use_container_width=True)

# --------------------------- EXPORT & INFO ---------------------------
st.download_button(
    "Export to CSV",
    df.to_csv(index=False),
    "nikohealth_denials.csv",
    "text/csv"
)

if not USE_REAL_API:
    st.info("""
    You're seeing **demo data**.  
    To connect to your real NikoHealth account:
    1. Get your API key from NikoHealth support
    2. Create a file named `.streamlit/secrets.toml` in your repo
    3. Add: `NIKO_API_KEY = "your_real_key_here"`
    """)
