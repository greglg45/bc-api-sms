import os
import re
import sqlite3
from datetime import datetime


__all__ = [
    "parse_dbm",
    "get_signal_level",
    "ensure_logs_table",
    "log_request",
    "validate_request",
    "get_last_update_date",
    "footer_html",
]


def parse_dbm(value):
    if value is None:
        return None
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else None


def get_signal_level(rsrp: int) -> int:
    if rsrp is None:
        return 0
    if rsrp >= -80:
        return 5
    if rsrp >= -90:
        return 4
    if rsrp >= -100:
        return 3
    if rsrp >= -110:
        return 2
    if rsrp >= -120:
        return 1
    return 0


def ensure_logs_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS logs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "timestamp TEXT,"
        "phone TEXT,"
        "sender TEXT,"
        "message TEXT,"
        "response TEXT)"
    )
    cols = [row[1] for row in conn.execute("PRAGMA table_info(logs)")]
    if "sender" not in cols:
        conn.execute("ALTER TABLE logs ADD COLUMN sender TEXT")


def log_request(db_path, recipients, sender, text, response):
    conn = sqlite3.connect(db_path)
    ensure_logs_table(conn)
    conn.execute(
        "INSERT INTO logs(timestamp, phone, sender, message, response) VALUES (?,?,?,?,?)",
        (datetime.utcnow().isoformat(), ",".join(recipients), sender, text, response),
    )
    conn.commit()
    conn.close()


def validate_request(data):
    recipients = data.get("to")
    sender = data.get("from")
    text = data.get("text")

    if isinstance(sender, str):
        sender = sender.strip()

    if not isinstance(recipients, list) or not recipients:
        raise ValueError("'to' must be a non-empty list")
    for number in recipients:
        if not isinstance(number, str) or not re.fullmatch(r"\+?\d+", number):
            raise ValueError("invalid phone number in 'to'")
    if not isinstance(sender, str) or not sender:
        raise ValueError("'from' must be a non-empty string")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("'text' must be a non-empty string")
    return recipients, sender, text.strip()


def get_last_update_date() -> str:
    path = os.path.join(os.path.dirname(__file__), os.pardir, "docs", "mise-a-jour.md")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.lstrip().startswith("-"):
                    m = re.search(r"\*\*(.+?)\*\*", line)
                    if m:
                        return m.group(1)
    except Exception:
        pass
    return datetime.utcnow().strftime("%d/%m/%Y")


def footer_html() -> str:
    date = get_last_update_date()
    return (
        "<footer class='text-center mt-4'>"
        f"Dernière mise à jour : {date} - &copy; DSI Baudinchateauneuf"
        "</footer>"
    )
