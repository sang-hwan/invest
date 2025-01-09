# streamlit_app.py
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

DB_FILE = "trade_logs.db"

def load_data(table_name="trade_logs"):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def main():
    st.title("Paper Trading Logs Dashboard")

    st.write("## Trade Logs (체결 내역)")
    df_trades = load_data("trade_logs")
    st.write(f"총 체결 로그 수: {len(df_trades)}")
    st.dataframe(df_trades.head(50))

    # 가격/잔고 차트 등은 기존 로직 그대로.

    st.write("## Decision Logs (의사결정 이력)")
    df_decision = load_data("decision_logs")
    st.write(f"총 의사결정 로그 수: {len(df_decision)}")
    st.dataframe(df_decision.head(50))

    # 필요하다면 df_decision 기반 차트도 추가 가능
    # 예: decision별 count, 혹은 시간이 지날수록 RSI, sentiment, decision 변화 등
    st.subheader("Decision Frequency")
    decision_counts = df_decision["decision"].value_counts()
    st.bar_chart(decision_counts)

if __name__ == "__main__":
    main()
