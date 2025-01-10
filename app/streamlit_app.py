# streamlit_app.py
import streamlit as st
import sqlite3
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

import plotly.express as px
import plotly.graph_objects as go

DB_FILE = "data/trade_logs.db"

@st.cache_data
def load_data(table_name: str):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df

def main():
    st.title("Paper Trading Logs Dashboard")
    st.markdown("---")

    # 사이드바 메뉴
    menu = ["Trade Logs", "Decision Logs", "분석(차트)"]
    choice = st.sidebar.selectbox("메뉴 선택", menu)

    # 공통 데이터 로드
    df_trades = load_data("trade_logs")
    df_decision = load_data("decision_logs")

    # 날짜 필터링을 위한 범위 설정
    if not df_trades.empty and not df_decision.empty:
        min_date = min(df_trades["timestamp"].min(), df_decision["timestamp"].min())
        max_date = max(df_trades["timestamp"].max(), df_decision["timestamp"].max())
    elif not df_trades.empty:
        min_date = df_trades["timestamp"].min()
        max_date = df_trades["timestamp"].max()
    elif not df_decision.empty:
        min_date = df_decision["timestamp"].min()
        max_date = df_decision["timestamp"].max()
    else:
        min_date = pd.to_datetime("2020-01-01")
        max_date = pd.to_datetime("2025-01-01")

    st.sidebar.markdown("#### 날짜 필터")
    start_date = st.sidebar.date_input("시작일", value=min_date)
    end_date = st.sidebar.date_input("종료일", value=max_date)

    # 실제 필터 적용
    if not df_trades.empty:
        df_trades = df_trades[
            (df_trades["timestamp"] >= pd.to_datetime(start_date)) &
            (df_trades["timestamp"] <= pd.to_datetime(end_date))
        ]
    if not df_decision.empty:
        df_decision = df_decision[
            (df_decision["timestamp"] >= pd.to_datetime(start_date)) &
            (df_decision["timestamp"] <= pd.to_datetime(end_date))
        ]

    if choice == "Trade Logs":
        st.subheader("체결 내역(Trade Logs)")
        st.write(f"총 체결 로그 수: {len(df_trades)}")
        st.dataframe(df_trades.tail(100))

        # 간단 수익 계산
        if not df_trades.empty:
            initial_balance = df_trades["balance"].iloc[0]
            latest_row = df_trades.iloc[-1]
            final_balance = latest_row["balance"] + latest_row["position"] * latest_row["current_price"]
            profit = final_balance - initial_balance

            st.write(f"**초기 잔고**: {initial_balance:.2f}")
            st.write(f"**최종 잔고(추정)**: {final_balance:.2f}")
            st.write(f"**추정 수익**: {profit:.2f}")
        else:
            st.warning("Trade Logs 데이터가 없습니다.")

    elif choice == "Decision Logs":
        st.subheader("의사결정 이력(Decision Logs)")
        st.write(f"총 의사결정 로그 수: {len(df_decision)}")
        st.dataframe(df_decision.tail(100))

        if not df_decision.empty:
            st.subheader("Decision Frequency")
            decision_counts = df_decision["decision"].value_counts()
            st.bar_chart(decision_counts)

            # RSI & Sentiment
            tabs = st.tabs(["RSI 차트", "Sentiment 차트"])
            with tabs[0]:
                if "rsi" in df_decision.columns:
                    fig_rsi = px.line(df_decision, x="timestamp", y="rsi", title="RSI Over Time")
                    st.plotly_chart(fig_rsi, use_container_width=True)
                else:
                    st.info("rsi 컬럼이 없습니다.")

            with tabs[1]:
                if "sentiment" in df_decision.columns:
                    fig_senti = px.line(df_decision, x="timestamp", y="sentiment", title="Sentiment Over Time")
                    st.plotly_chart(fig_senti, use_container_width=True)
                else:
                    st.info("sentiment 컬럼이 없습니다.")
        else:
            st.warning("Decision Logs 데이터가 없습니다.")

    else:
        st.subheader("분석(차트)")

        if df_trades.empty:
            st.warning("Trade Logs 데이터가 없습니다.")
            return

        tab_main, tab_bs, tab_sent = st.tabs(["Price/RSI 차트", "매수/매도 시점", "Sentiment"])

        # (1) Price & RSI 차트
        with tab_main:
            st.write("**Price & RSI 시계열**")
            if "rsi" not in df_trades.columns:
                st.info("Trade Logs에 rsi 컬럼이 없습니다.")
            else:
                fig = go.Figure()
                # Price
                fig.add_trace(go.Scatter(
                    x=df_trades["timestamp"],
                    y=df_trades["current_price"],
                    mode='lines',
                    name='Price',
                    line=dict(color='blue')
                ))
                # RSI
                fig.add_trace(go.Scatter(
                    x=df_trades["timestamp"],
                    y=df_trades["rsi"],
                    mode='lines',
                    name='RSI',
                    yaxis='y2',
                    line=dict(color='red', dash='dot')
                ))

                fig.update_layout(
                    title="Price & RSI Over Time",
                    xaxis=dict(domain=[0.1, 0.9]),
                    yaxis=dict(title="Price", side="left"),
                    yaxis2=dict(
                        title="RSI",
                        overlaying="y",
                        side="right",
                        range=[0, 100]
                    ),
                    legend=dict(orientation="h")
                )
                st.plotly_chart(fig, use_container_width=True)

        # (2) 매수/매도 시점
        with tab_bs:
            st.write("**매수/매도 시점 차트**")
            buys = df_trades[df_trades["action"] == "buy"]
            sells = df_trades[df_trades["action"] == "sell"]

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=df_trades["timestamp"],
                y=df_trades["current_price"],
                mode='lines',
                name='Price',
                line=dict(color='black')
            ))
            fig2.add_trace(go.Scatter(
                x=buys["timestamp"],
                y=buys["current_price"],
                mode='markers',
                name='Buy',
                marker=dict(color='green', symbol='triangle-up', size=10)
            ))
            fig2.add_trace(go.Scatter(
                x=sells["timestamp"],
                y=sells["current_price"],
                mode='markers',
                name='Sell',
                marker=dict(color='red', symbol='triangle-down', size=10)
            ))

            fig2.update_layout(
                title="Buy/Sell Points",
                xaxis_title="Time",
                yaxis_title="Price",
            )
            st.plotly_chart(fig2, use_container_width=True)

        # (3) Sentiment 시계열
        with tab_sent:
            st.write("**Sentiment 시계열**")
            if df_decision.empty:
                st.info("Decision Logs 데이터가 없습니다.")
            else:
                if "sentiment" not in df_decision.columns:
                    st.info("sentiment 컬럼이 없습니다.")
                else:
                    fig3 = px.line(
                        df_decision, x="timestamp", y="sentiment",
                        title="Sentiment Over Time",
                        markers=True
                    )
                    fig3.add_hline(y=0.0, line_dash="dash", line_color="gray")
                    st.plotly_chart(fig3, use_container_width=True)


if __name__ == "__main__":
    main()
