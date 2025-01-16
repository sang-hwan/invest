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
    trade_logs, decision_logs, meta_info 테이블이 없으면 생성.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # trade_logs 테이블
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

    # decision_logs 테이블
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

    # meta_info 테이블
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT
        );
        """
    )
    
    conn.commit()
    conn.close()

def write_trade_log_db(current_price, rsi, sentiment,
                       action, trade_amount, trade_price,
                       balance, position, reason):
    """
    매수/매도 체결 시 trade_logs 테이블에 기록.
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
    모든 의사결정(buy/sell/hold) 시 decision_logs 테이블에 기록.
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
    trade_logs 테이블에서 가장 최신 레코드의 balance, position을 반환.
    """
    if not os.path.exists(DB_FILE):
        return None

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT balance, position FROM trade_logs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None
    else:
        balance, position = row
        return (balance, position)


# -------- 추가: 감성 점수 로드 함수 -----------
def load_last_sentiment():
    """
    decision_logs 테이블에서 가장 최신 sentiment 값을 반환.
    없으면 None.
    """
    if not os.path.exists(DB_FILE):
        return None

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT sentiment FROM decision_logs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None
    else:
        return float(row[0])  # sentiment가 None이 아니라고 가정, float 변환

# -------- meta_info 테이블을 통한 key-value 저장/불러오기 --------
def save_meta_info(key: str, value: str):
    """
    meta_info 테이블에 key-value를 Upsert.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # upsert: key가 이미 존재하면 update, 아니면 insert
    cur.execute(
        """
        INSERT INTO meta_info (id, key, value)
        VALUES (
            (SELECT id FROM meta_info WHERE key=?),
            ?, ?
        )
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (key, key, str(value))
    )
    conn.commit()
    conn.close()

def load_meta_info(key: str):
    """
    meta_info 테이블에서 key에 해당하는 value를 반환. 없으면 None.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT value FROM meta_info WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None
    else:
        return row[0]
