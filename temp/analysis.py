# analysis.py
import sqlite3
import pandas as pd

DB_FILE = "trade_logs.db"

def load_logs():
    """
    SQLite에서 trade_logs 테이블 읽어서 DataFrame으로 반환
    """
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM trade_logs", conn)
    conn.close()
    return df

def main():
    df = load_logs()
    print("=== 최근 5개 로그 ===")
    print(df.tail())

    # 예시: 날짜/시간 컬럼을 datetime 타입으로 변환
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 간단 통계
    buy_trades = df[df["action"] == "buy"]
    sell_trades = df[df["action"] == "sell"]
    print("총 로그 수:", len(df))
    print("매수 횟수:", len(buy_trades))
    print("매도 횟수:", len(sell_trades))

    # 예시로 RSI와 sentiment 분포를 확인
    print("RSI 평균:", df["rsi"].mean())
    print("sentiment 평균:", df["sentiment"].mean())

    # 간단 차트 그리기
    # (인터렉티브 환경에서 plt.show() 해야 보임)
    import matplotlib.pyplot as plt
    plt.figure(figsize=(10,5))
    plt.plot(df["timestamp"], df["current_price"], label="Price")
    plt.title("Current Price Over Time")
    plt.legend()
    plt.show()

if __name__ == "__main__":
    main()
