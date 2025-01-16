# test.py
import sqlite3
import os

DB_FILE = "data/trade_logs.db"  # streamlit_app.py와 같은 경로

if not os.path.exists(DB_FILE):
    print("DB 파일이 존재하지 않습니다.")
else:
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # trade_logs가 있는지, 그리고 몇 건 있는지
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    print("테이블 목록:", tables)

    if "trade_logs" in tables:
        cur.execute("SELECT COUNT(*) FROM trade_logs;")
        count_t = cur.fetchone()[0]
        print("trade_logs 레코드 수:", count_t)
        
        cur.execute("SELECT * FROM trade_logs LIMIT 5;")
        rows_t = cur.fetchall()
        print("trade_logs 샘플 5행:", rows_t)

    if "decision_logs" in tables:
        cur.execute("SELECT COUNT(*) FROM decision_logs;")
        count_d = cur.fetchone()[0]
        print("decision_logs 레코드 수:", count_d)
        
        cur.execute("SELECT * FROM decision_logs LIMIT 5;")
        rows_d = cur.fetchall()
        print("decision_logs 샘플 5행:", rows_d)

    conn.close()