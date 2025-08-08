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
    
    # Add label column if it doesn't exist
    try:
        # Check if 'label' column exists
        cursor.execute("PRAGMA table_info(emails)")
        columns = [row[1] for row in cursor.fetchall()]
        if "label" not in columns:
            cursor.execute("ALTER TABLE emails ADD COLUMN label TEXT DEFAULT NULL")
    except sqlite3.OperationalError as e:
        if "duplicate column name: label" in str(e):
            pass  # Already added
        else:
            raise  # Re-raise if it's a different error

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
            has_attachments,
            label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('message_id'),
            data.get('email_account'),
            data.get('date'),
            data.get('sender'),
            data.get('subject'),
            data.get('body'),
            data.get('content_type'),
            data.get('has_attachments'),
            data.get('label')  # Can be None (NULL)
        ))
        conn.commit()
    except Exception as e:
        print(f"[!] Errore nel salvataggio su DB: {e}")
    finally:
        conn.close()
