"""Small SQLite log of every check, so we can look back at mistakes.

By default we don't keep the message itself, only a masked copy with digits
hidden (account numbers, OTPs, amounts).
"""
import json
import re
import sqlite3
import time
import uuid

from .config import DB_PATH, LOG_RAW_TEXT


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.execute(
        "CREATE TABLE IF NOT EXISTS checks ("
        " id TEXT PRIMARY KEY, created REAL, dialect TEXT, source TEXT,"
        " text TEXT, verdict TEXT, rule TEXT, trace TEXT)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS feedback ("
        " check_id TEXT, created REAL, note TEXT)"
    )
    return c


def mask(text):
    return re.sub(r"\d", "#", text or "")


def save_check(result, dialect, source):
    check_id = uuid.uuid4().hex[:12]
    text = result["extracted"]["text"]
    with _conn() as c:
        c.execute(
            "INSERT INTO checks VALUES (?,?,?,?,?,?,?,?)",
            (check_id, time.time(), dialect, source, text if LOG_RAW_TEXT else mask(text),
             result["verdict"], result["rule"], json.dumps(result["trace"], ensure_ascii=False)),
        )
    return check_id


def save_feedback(check_id, note):
    with _conn() as c:
        c.execute("INSERT INTO feedback VALUES (?,?,?)", (check_id, time.time(), note[:500]))


def recent_feedback(limit=50):
    with _conn() as c:
        rows = c.execute(
            "SELECT f.check_id, f.note, c.verdict, c.rule, c.text FROM feedback f "
            "LEFT JOIN checks c ON c.id = f.check_id ORDER BY f.created DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(zip(["check_id", "note", "verdict", "rule", "text"], r)) for r in rows]
