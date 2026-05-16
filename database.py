# ============================================================
# database.py
# SQLite 기반 분석 결과 저장 모듈
# ============================================================

import sqlite3
import json
from datetime import datetime

DB_PATH = "stock_analysis.db"


def init_db():
    """DB 초기화 — 앱 시작 시 1회 호출"""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # 분석 결과 테이블
    c.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker         TEXT    NOT NULL,
            name           TEXT,
            analyzed_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            current_price  REAL,
            fair_value     REAL,
            discount_rate  REAL,
            total_score    INTEGER,
            grade          TEXT,
            scores_json    TEXT,
            reasons_good   TEXT,
            reasons_bad    TEXT
        )
    """)

    # 관심 종목 테이블
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            ticker   TEXT PRIMARY KEY,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_analysis(ticker: str, name: str, current_price: float,
                  fair_value: float, discount_rate: float,
                  total_score: int, grade: str,
                  scores: dict, good: list, bad: list):
    """분석 결과 저장"""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("""
        INSERT INTO analysis_results
        (ticker, name, current_price, fair_value, discount_rate,
         total_score, grade, scores_json, reasons_good, reasons_bad)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        ticker, name, current_price, fair_value, discount_rate,
        total_score, grade,
        json.dumps(scores, ensure_ascii=False),
        json.dumps(good,   ensure_ascii=False),
        json.dumps(bad,    ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def get_history(ticker: str, limit: int = 20) -> list:
    """특정 종목의 분석 히스토리"""
    conn    = sqlite3.connect(DB_PATH)
    c       = conn.cursor()
    c.execute("""
        SELECT analyzed_at, current_price, fair_value, total_score, grade
        FROM   analysis_results
        WHERE  ticker = ?
        ORDER  BY analyzed_at DESC
        LIMIT  ?
    """, (ticker, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_latest_all() -> list:
    """모든 종목의 최신 분석 결과"""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("""
        SELECT ticker, name, current_price, fair_value, discount_rate,
               total_score, grade, analyzed_at
        FROM   analysis_results
        WHERE  analyzed_at = (
            SELECT MAX(a2.analyzed_at)
            FROM   analysis_results a2
            WHERE  a2.ticker = analysis_results.ticker
        )
        ORDER  BY total_score DESC
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def add_watchlist(ticker: str):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)",
        (ticker.upper(),)
    )
    conn.commit()
    conn.close()


def remove_watchlist(ticker: str):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    conn.close()


def get_watchlist() -> list:
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT ticker FROM watchlist ORDER BY added_at DESC")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows
