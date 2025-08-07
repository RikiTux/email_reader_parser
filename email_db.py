import sqlite3
from datetime import datetime

DB_PATH = "emails.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT UNIQUE,
        email_account TEXT,
        date TEXT,
        sender TEXT,
        subject TEXT,
        body TEXT,
        content_type TEXT,
        has_attachments BOOLEAN
    )
    """)
    conn.commit()
    conn.close()

def insert_email(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT OR IGNORE INTO emails (
            message_id,
            email_account,
            date,
            sender,
            subject,
            body,
            content_type,
            has_attachments
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['message_id'],
            data['email_account'],
            data['date'],
            data['sender'],
            data['subject'],
            data['body'],
            data['content_type'],
            data['has_attachments']
        ))
        conn.commit()
    except Exception as e:
        print(f"[!] Errore nel salvataggio su DB: {e}")
    finally:
        conn.close()
