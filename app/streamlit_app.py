# streamlit_app.py
import os
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

DB_FILE = "data/trade_logs.db"

@st.cache_data
def load_data(table_name: str, limit: int = 1000):
    """
    주어진 table_name에 대해 SQLite에서 데이터를 읽어 DataFrame으로 반환.
    최근 limit 건만 가져오도록 쿼리 제한.
    """
    conn = sqlite3.connect(DB_FILE)
    query = f"""
        SELECT * FROM {table_name}
        ORDER BY id DESC
        LIMIT {limit}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df

def display_trade_logs(df_trades: pd.DataFrame):
    """
    Trade Logs(체결 내역) 페이지 구성
    """
    st.subheader("체결 내역 (Trade Logs)")

    if df_trades.empty:
        st.warning("Trade Logs 데이터가 없습니다.")
        return

    st.write(f"표시 중: 최근 {len(df_trades)} 건")

    # (1) 데이터 필터링
    action_filter = st.selectbox("Action 필터", ["All", "buy", "sell"])
    if action_filter != "All":
        df_trades = df_trades[df_trades["action"] == action_filter]

    # (2) 날짜 필터 (옵션)
    min_date, max_date = df_trades["timestamp"].min(), df_trades["timestamp"].max()
    selected_range = st.slider(
        "기간 선택",
        min_value=min_date.to_pydatetime(),
        max_value=max_date.to_pydatetime(),
        value=(min_date.to_pydatetime(), max_date.to_pydatetime()),
        format="YYYY-MM-DD HH:mm"
    )
    start_date, end_date = selected_range
    df_trades = df_trades[
        (df_trades["timestamp"] >= pd.to_datetime(start_date)) &
        (df_trades["timestamp"] <= pd.to_datetime(end_date))
    ]

    # (3) 화면 표시
    st.dataframe(df_trades.tail(100))  # 화면에는 최대 100건만

    # (4) 매매 요약: "초기 재산", "현재 재산", "수익률"
    first_row = df_trades.iloc[0]
    latest_row = df_trades.iloc[-1]

    initial_asset = first_row["balance"] + first_row["position"] * first_row["current_price"]
    current_asset = latest_row["balance"] + latest_row["position"] * latest_row["current_price"]
    profit = current_asset - initial_asset
    profit_ratio = (profit / initial_asset) * 100 if initial_asset != 0 else 0.0

    st.write("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("초기 재산", f"{initial_asset:,.2f}원")
    col2.metric("현재 재산", f"{current_asset:,.2f}원", f"{profit:,.2f}")
    col3.metric("수익률 (%)", f"{profit_ratio:,.2f}%")

def display_decision_logs(df_decision: pd.DataFrame):
    """
    Decision Logs(의사결정 내역) 페이지 구성
    """
    st.subheader("의사결정 이력 (Decision Logs)")

    if df_decision.empty:
        st.warning("Decision Logs 데이터가 없습니다.")
        return

    st.write(f"표시 중: 최근 {len(df_decision)} 건")

    # 데이터 표시
    st.dataframe(df_decision.tail(100))

    # 의사결정 빈도
    st.subheader("Decision Frequency")
    decision_counts = df_decision["decision"].value_counts()
    st.bar_chart(decision_counts)

    # 세부 지표 탭
    tab_rsi, tab_senti = st.tabs(["RSI 차트", "Sentiment 차트"])

    with tab_rsi:
        if "rsi" in df_decision.columns:
            fig_rsi = px.line(
                df_decision, x="timestamp", y="rsi",
                title="RSI Over Time"
            )
            st.plotly_chart(fig_rsi, use_container_width=True)
        else:
            st.info("rsi 컬럼이 없습니다.")

    with tab_senti:
        if "sentiment" in df_decision.columns:
            fig_senti = px.line(
                df_decision, x="timestamp", y="sentiment",
                title="Sentiment Over Time"
            )
            st.plotly_chart(fig_senti, use_container_width=True)
        else:
            st.info("sentiment 컬럼이 없습니다.")

def display_analysis_chart(df_trades: pd.DataFrame):
    """
    추가 분석(차트) 탭
    """
    if df_trades.empty:
        st.warning("Trade Logs 데이터가 없습니다.")
        return

    st.subheader("추가 분석 (Price & RSI)")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_trades["timestamp"],
        y=df_trades["current_price"],
        mode='lines',
        name='Price'
    ))
    if "rsi" in df_trades.columns:
        fig.add_trace(go.Scatter(
            x=df_trades["timestamp"],
            y=df_trades["rsi"],
            mode='lines',
            name='RSI',
            yaxis='y2',
            line=dict(dash='dot', color='red')
        ))

    fig.update_layout(
        title="Price & RSI",
        yaxis=dict(title="Price"),
        yaxis2=dict(
            title="RSI",
            overlaying="y",
            side="right",
            range=[0, 100]
        )
    )
    st.plotly_chart(fig, use_container_width=True)

def main():
    st.set_page_config(
        page_title="Paper Trading Dashboard",
        page_icon=":bar_chart:",
        layout="wide"
    )

    st.title("Paper Trading Logs Dashboard :chart_with_upwards_trend:")
    st.markdown("---")

    # ====== 새로고침 버튼 ======
    if st.button("데이터 새로고침"):
        st.cache_data.clear()  # 캐시 초기화
        st.rerun()  # 페이지 재실행

    # 상단 Tab 구성
    tabs = st.tabs(["Trade Logs", "Decision Logs", "분석(차트)"])

    # 최근 5,000건만 불러옴
    df_trades = load_data("trade_logs", limit=5000)
    df_decision = load_data("decision_logs", limit=5000)

    with tabs[0]:
        display_trade_logs(df_trades)

    with tabs[1]:
        display_decision_logs(df_decision)

    with tabs[2]:
        display_analysis_chart(df_trades)

    st.markdown("---")
    st.info("데이터는 페이퍼 트레이딩 기준으로 기록되며, 실제 시세 및 시장 상황과 다를 수 있습니다.")

if __name__ == "__main__":
    main()
