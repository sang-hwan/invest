# db_utils.py
import sqlite3
import os
from datetime import datetime

DB_FILE = "data/trade_logs.db"

DB_DIR = os.path.dirname(DB_FILE)
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

def init_db():
    """
    trade_logs, decision_logs 테이블이 없으면 생성.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # 기존 trade_logs 테이블
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trade_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            current_price REAL,
            rsi REAL,
            sentiment REAL,
            action TEXT,
            trade_amount REAL,
            trade_price REAL,
            balance REAL,
            position REAL,
            reason TEXT
        );
        """
    )

    # 새로 추가한 decision_logs 테이블
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            current_price REAL,
            rsi REAL,
            sentiment REAL,
            decision TEXT,
            reason TEXT
        );
        """
    )
    
    conn.commit()
    conn.close()

def write_trade_log_db(current_price, rsi, sentiment,
                       action, trade_amount, trade_price,
                       balance, position, reason):
    """
    매수/매도 체결이 발생할 때 trade_logs 테이블에 기록.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO trade_logs 
        (timestamp, current_price, rsi, sentiment,
         action, trade_amount, trade_price, balance,
         position, reason)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            current_price,
            rsi,
            sentiment,
            action,
            trade_amount,
            trade_price,
            balance,
            position,
            reason
        )
    )
    conn.commit()
    conn.close()

def write_decision_log_db(current_price, rsi, sentiment,
                          decision, reason):
    """
    매 분/매 tick마다 'buy', 'sell', 'hold' 의사결정을 기록.
    (단, 실제 체결(매수/매도)은 trade_logs에도 별도로 기록)
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO decision_logs
        (timestamp, current_price, rsi, sentiment,
         decision, reason)
        VALUES (?,?,?,?,?,?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            current_price,
            rsi,
            sentiment,
            decision,
            reason
        )
    )
    conn.commit()
    conn.close()

def load_last_state():
    """
    trade_logs 테이블의 '가장 최신' 레코드를 불러와서
    (balance, position)을 반환한다.
    만약 기록이 하나도 없다면 None을 반환.
    """
    if not os.path.exists(DB_FILE):
        return None  # DB 파일 자체가 없음

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT balance, position FROM trade_logs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None  # 테이블은 있지만 데이터가 없음
    else:
        balance, position = row
        return (balance, position)

