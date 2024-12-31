import streamlit as st
import pandas as pd
import datetime
import altair as alt

# Replace with your actual Google Sheets CSV URL
google_sheets_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTuyGRVZuafIk2s7moScIn5PAUcPYEyYIOOYJj54RXYUeugWmOP0iIToljSEMhHrg_Zp8Vab6YvBJDV/pub?output=csv"

@st.cache_data(ttl=0)  # Caching har baar bypass hoga
def load_data(url):
    # Read the CSV and use the first row as the header
    data = pd.read_csv(url, header=0)
    data.columns = data.columns.str.strip().str.lower()  # Normalize column names

    # Ensure 'date' column exists
    date_col_candidates = [col for col in data.columns if 'date' in col.lower()]
    if date_col_candidates:
        data['date'] = pd.to_datetime(data[date_col_candidates[0]], errors='coerce')

    # Convert relevant columns to numeric
    numeric_cols = ['nav', 'day change', 'day change %', 'nifty50 value', 'current value', 'nifty50 change %',
                    'dd', 'dd_n50', 'portfolio value', 'absolute gain', 'nifty50']
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col].astype(str).str.replace(',', '').str.replace('%', ''), errors='coerce')

    # Calculate drawdown if not already present
    if 'dd' not in data.columns and 'nav' in data.columns:
        data['dd'] = data['nav'] - data['nav'].cummax()

    # Replace NaN values with 0
    data.fillna(0, inplace=True)
    return data

# Load data
data = load_data(google_sheets_url)

# Fetch Portfolio Value, Nifty50 Value, and Day Change explicitly
portfolio_value_raw = data.iloc[0, 0]  # Portfolio value from cell [0,0]
nifty50_value_raw = data.iloc[0, 2]   # Nifty50 value from cell [0,2]
day_change_raw = data.iloc[2, 0]      # Day Change from cell [0,3]

# Convert to numeric
portfolio_value = pd.to_numeric(portfolio_value_raw, errors='coerce')
nifty50_value = pd.to_numeric(nifty50_value_raw, errors='coerce')
day_change = pd.to_numeric(day_change_raw, errors='coerce')

# Date filter
st.sidebar.markdown("#### Filter by Date Range")
start_date = st.sidebar.date_input("Start Date", value=data['date'].min())
end_date = st.sidebar.date_input("End Date", value=data['date'].max())

# Filter data by date
filtered_data = data[(data['date'] >= pd.Timestamp(start_date)) & (data['date'] <= pd.Timestamp(end_date))]

# Display metrics
if filtered_data.empty:
    st.error("No data available for the selected date range.")
else:
    # Display metrics with consistent spacing and alignment
    col1, col2, col3, col4 = st.columns([3, 2, 2, 3])  # Equal column widths for symmetry

    with col1:
        st.metric("Total Account Value   ", f"₹{portfolio_value:,.0f}")
    with col2:
        st.metric("Day Change", f"₹{day_change:,.0f}", f"{filtered_data['day change %'].iloc[-1]:,.2f}%")
    with col3:
        st.metric("NIFTY50 Benchmark", f"{nifty50_value:,.0f}")
    with col4:
        if len(filtered_data) > 30:
            month_change = filtered_data['current value'].iloc[-1] - filtered_data['current value'].iloc[-30]
            month_change_percent = (month_change / filtered_data['current value'].iloc[-30] * 100) if \
                filtered_data['current value'].iloc[-30] != 0 else 0
            st.metric("Month Change", f"₹{month_change:,.0f}", f"{month_change_percent:.2f}%")
        else:
            st.metric("Month Change", "Insufficient Data")

    st.write("### Model Live Chart")
    nav_chart = alt.Chart(filtered_data).mark_line().encode(
        x='date:T',
        y=alt.Y('nav:Q', scale=alt.Scale(zero=False)),  # Use NAV for the chart
        color=alt.value('#1f77b4')
    ).properties(width=700, height=400)
    benchmark_chart = alt.Chart(filtered_data).mark_line().encode(
        x='date:T',
        y=alt.Y('nifty50 value:Q', scale=alt.Scale(zero=False)),
        color=alt.value('red')
    ).properties(width=700, height=400)
    st.altair_chart(nav_chart + benchmark_chart)

    st.write("### Drawdown Live Chart")
    drawdown_chart = alt.Chart(filtered_data).mark_line().encode(
        x='date:T',
        y=alt.Y('dd:Q', scale=alt.Scale(zero=False)),
        color=alt.value('#ff7f0e')
    ).properties(width=700, height=400)
    st.altair_chart(drawdown_chart)

# Performance Calculation
st.sidebar.write("### Model Performance")
return_type = st.sidebar.radio("Select Return Type", ['Inception', 'Yearly', 'Monthly', 'Weekly', 'Daily'], index=1)

def calculate_performance(return_type):
    latest_value = filtered_data['nav'].iloc[-1]  # Use NAV for performance calculation
    if return_type == 'Inception':
        inception_value = filtered_data['nav'].iloc[0]
        return (latest_value - inception_value) / inception_value * 100
    elif return_type == 'Yearly':
        past_date = filtered_data['date'].max() - pd.DateOffset(years=1)
        yearly_data = filtered_data[filtered_data['date'] >= past_date]
        if not yearly_data.empty:
            year_start_value = yearly_data['nav'].iloc[0]
            return (latest_value - year_start_value) / year_start_value * 100
    elif return_type == 'Monthly':
        past_date = filtered_data['date'].max() - pd.DateOffset(months=1)
        monthly_data = filtered_data[filtered_data['date'] >= past_date]
        if not monthly_data.empty:
            month_start_value = monthly_data['nav'].iloc[0]
            return (latest_value - month_start_value) / month_start_value * 100
    elif return_type == 'Weekly':
        past_date = filtered_data['date'].max() - pd.DateOffset(weeks=1)
        weekly_data = filtered_data[filtered_data['date'] >= past_date]
        if not weekly_data.empty:
            week_start_value = weekly_data['nav'].iloc[0]
            return (latest_value - week_start_value) / week_start_value * 100
    else:  # Daily
        past_date = filtered_data['date'].max() - pd.DateOffset(days=1)
        daily_data = filtered_data[filtered_data['date'] >= past_date]
        if not daily_data.empty:
            day_start_value = daily_data['nav'].iloc[0]
            return (latest_value - day_start_value) / day_start_value * 100

# Display performance in sidebar
performance = calculate_performance(return_type)
if performance is not None:
    st.sidebar.write(f"{return_type} Performance: {performance:.2f}%")
