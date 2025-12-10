import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import altair as alt

# Config
API_BASE = "https://api.nikohealth.com"  # Verify this
API_KEY = st.secrets.get("NIKO_API_KEY", "your_api_key_here")  # Use Streamlit secrets for security
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

st.title("NikoHealth Denials Management Dashboard")
st.sidebar.header("Filters")
date_range = st.sidebar.date_input("Date Range", [datetime.now() - timedelta(days=30), datetime.now()])
payer_filter = st.sidebar.text_input("Payer Filter (optional)")

@st.cache_data(ttl=300)  # Cache for 5 min
def fetch_denials(start_date, end_date, payer=None):
    params = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "limit": 500
    }
    if payer:
        params["payer_id"] = payer  # Adjust param name as per API
    
    response = requests.get(f"{API_BASE}/v2/payments", headers=HEADERS, params=params)
    if response.status_code == 200:
        data = response.json()["data"]  # Assume paginated response
        df = pd.DataFrame(data)
        # Filter for denials (customize based on schema)
        df = df[(df["status"] == "denied") | (df["adjustment_amount"] > 0)]
        df["date"] = pd.to_datetime(df["created_at"])
        df["denial_amount"] = abs(df["adjustment_amount"].fillna(0))
        return df
    else:
        st.error(f"API Error: {response.status_code} - {response.text}")
        return pd.DataFrame()

# Fetch data
df = fetch_denials(date_range[0], date_range[1], payer_filter)

if not df.empty:
    # Key Metrics
    col1, col2, col3 = st.columns(3)
    total_denials = len(df)
    total_amount = df["denial_amount"].sum()
    denial_rate = (total_denials / len(df)) * 100 if len(df) > 0 else 0  # Rough rate; refine with total claims fetch

    with col1:
        st.metric("Total Denials", total_denials)
    with col2:
        st.metric("Total Denied Amount", f"${total_amount:,.2f}")
    with col3:
        st.metric("Denial Rate (%)", f"{denial_rate:.1f}%")

    # Denials Table
    st.subheader("Denials Details")
    df_display = df[["date", "patient_id", "payer_name", "denial_reason", "denial_amount", "invoice_id"]].sort_values("date", ascending=False)
    st.dataframe(df_display, use_container_width=True)

    # Trends Chart: Denials by Week
    df_weekly = df.resample("W", on="date")["denial_amount"].sum().reset_index()
    chart = alt.Chart(df_weekly).mark_line().encode(
        x="date:T",
        y=alt.Y("denial_amount:Q", title="Denied Amount ($)")
    ).properties(width=600, height=300)
    st.altair_chart(chart, use_container_width=True)

    # Top Reasons Pie Chart
    top_reasons = df["denial_reason"].value_counts().head(5).reset_index()
    top_reasons.columns = ["Reason", "Count"]
    pie = alt.Chart(top_reasons).mark_arc().encode(
        theta=alt.Theta("Count:Q"),
        color=alt.Color("Reason:N", legend=alt.Legend(title="Denial Reason"))
    )
    st.altair_chart(pie, use_container_width=True)

    # Action Buttons (e.g., Export or Appeal)
    if st.button("Export Denials CSV"):
        df.to_csv("denials_export.csv", index=False)
        st.success("Exported! Download from your local folder.")
    
    # Integrate Document Download (example for first denial)
    if not df.empty:
        sample_id = df.iloc[0]["invoice_id"]
        if st.button(f"Download EOB for Invoice {sample_id}"):
            doc_response = requests.get(f"{API_BASE}/v1/document-management/{sample_id}/download", headers=HEADERS)
            if doc_response.status_code == 200:
                st.download_button("Download EOB PDF", doc_response.content, f"eob_{sample_id}.pdf")
            else:
                st.error("Download failed.")

else:
    st.info("No denials found in the selected range. Try broadening the date filter.")
