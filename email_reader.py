import imaplib
import email
import ssl
import socket
import asyncio
import os
import json
from assets.load_env_variable import load_env_variable
from email_db import insert_email, init_db
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

import sys
import threading
import time

WATCHED_FILES = [
    os.path.abspath(__file__),  # this .py file
    os.path.abspath(".env"),    # .env file
]

restart_required = False

def get_mtimes(paths):
    return {path: os.path.getmtime(path) for path in paths if os.path.exists(path)}

def restart_script():
    print("\n🔄 Restarting script due to file change...\n")
    python = sys.executable
    os.execv(python, [python] + sys.argv)

def start_file_watcher(interval=2):
    def watcher():
        initial_mtimes = get_mtimes(WATCHED_FILES)

        while True:
            time.sleep(interval)
            current_mtimes = get_mtimes(WATCHED_FILES)
            for path in WATCHED_FILES:
                if path in current_mtimes and current_mtimes[path] != initial_mtimes.get(path):
                    print(f"\n📁 Change detected in: {path}")
                    globals()["restart_required"] = True
                    return
    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()

class EmailReader:
    def __init__(self, email_name, server, email_address, password):
        self.server = server
        self.email_name = email_name
        self.email_address = email_address
        self.password = password
        self.mail = None

    def connetti(self):
        try:
            self.mail = imaplib.IMAP4_SSL(self.server)
            self.mail.login(self.email_address, self.password)
            print(f"✅ Connessione IMAP riuscita per {self.email_name}.")
        except Exception as e:
            print(f"[!] Errore durante la connessione per {self.email_name}: {e}")
            self.mail = None

    def disconnetti(self):
        if self.mail:
            try:
                self.mail.logout()
                print(f"🔌 Disconnesso correttamente {self.email_name}.")
            except Exception as e:
                print(f"[!] Errore durante il logout di {self.email_name}: {e}")

    @staticmethod
    def html_to_text_preserving_structure(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for bold in soup.find_all(['b', 'strong']):
            bold.insert_before('**')
            bold.insert_after('**')

        for italic in soup.find_all(['i', 'em']):
            italic.insert_before('*')
            italic.insert_after('*')

        for tag in soup.find_all(['br', 'p', 'div', 'li', 'tr']):
            tag.insert_before('\n')

        for tag in soup(['script', 'style']):
            tag.decompose()

        text = soup.get_text()

        lines = [line.rstrip() for line in text.splitlines()]
        lines = [line for line in lines if line.strip() != '']
        return '\n'.join(lines)
    
    def leggi_email(self):
        if not self.mail:
            print(f"⚠️ Nessuna connessione IMAP attiva per {self.email_name}.")
            return

        try:
            self.mail.select("inbox")
            _, data = self.mail.search(None, "UNSEEN")
            email_ids = data[0].split()

            for eid in email_ids:
                try:
                    _, msg_data = self.mail.fetch(eid, "(BODY.PEEK[])")
                    if not msg_data or not isinstance(msg_data[0], tuple) or not msg_data[0][1]:
                        print(f"[!] Errore: messaggio malformato o vuoto per ID {eid}")
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                except Exception as fetch_err:
                    print(f"DEBUG: msg_data = {msg_data}")
                    print(f"[!] Errore durante il fetch dell'email ID {eid}: {fetch_err}")
                    continue

                subject = msg["subject"]
                from_ = msg["from"]
                body = None
                html_body = None

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition") or "")
                        if "attachment" in content_disposition:
                            continue

                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset()

                        if payload:
                            try:
                                decoded = payload.decode(charset or 'utf-8', errors='replace')
                            except Exception:
                                decoded = payload.decode('latin-1', errors='replace')

                            if content_type == "text/plain" and not body:
                                body = decoded
                            elif content_type == "text/html" and not html_body:
                                html_body = decoded
                else:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset()
                    try:
                        decoded = payload.decode(charset or 'utf-8', errors='replace')
                    except Exception:
                        decoded = payload.decode('latin-1', errors='replace')

                    if msg.get_content_type() == "text/plain":
                        body = decoded
                    elif msg.get_content_type() == "text/html":
                        html_body = decoded

                # Fallback: if no plain text, convert HTML to text
                if not body and html_body:
                    try:
                        body = self.html_to_text_preserving_structure(html_body)
                    except Exception:
                        body = html_body  # fallback raw HTML if parsing fails

                print(f"\n📧 [{self.email_name}] Nuova email da: {from_}")
                print(f"📝 Oggetto: {subject}")
                print(f"✉️ Corpo:\n{body}")
                print("=" * 50)
                
                message_id = msg.get("Message-ID", "")
                date_raw = msg.get("Date")
                date = parsedate_to_datetime(date_raw).isoformat() if date_raw else None
                has_attachments = any(part.get("Content-Disposition", "").startswith("attachment")
                                    for part in msg.walk() if part.get_content_maintype() != "multipart")
                content_type = msg.get_content_type()

                email_data = {
                    "message_id": message_id,
                    "email_account": self.email_name,
                    "date": date,
                    "sender": from_,
                    "subject": subject,
                    "body": body,
                    "content_type": content_type,
                    "has_attachments": has_attachments
                }

                insert_email(email_data)

        except (imaplib.IMAP4.abort, imaplib.IMAP4.error, ssl.SSLError, socket.error) as e:
            print(f"[!] Errore durante la lettura per {self.email_name}: {e}")

async def controlla_account(account):
    reader = EmailReader(account["name"], account["server"], account["email"], account["password"])
    await asyncio.to_thread(reader.connetti)
    await asyncio.to_thread(reader.leggi_email)
    await asyncio.to_thread(reader.disconnetti)
    
async def main_loop(accounts, intervallo=60):
    try:
        while True:
            print("\n🔄 Controllo email per tutti gli account...\n")
            tasks = [controlla_account(acc) for acc in accounts]
            await asyncio.gather(*tasks)

            # ✅ Check for restart request
            if globals().get("restart_required"):
                print("🕒 Graceful restart requested after file change.")
                restart_script()

            await asyncio.sleep(intervallo)
    except asyncio.CancelledError:
        print("\n⛔ Script interrotto manualmente.")

accounts_str = load_env_variable("ACCOUNTS")
try:
    accounts = json.loads(accounts_str)
except json.JSONDecodeError as e:
    print(f"[!] Errore nel parsing JSON degli account: {e}")
    exit(1)

if __name__ == "__main__":
    start_file_watcher()
    init_db()
    try:
        asyncio.run(main_loop(accounts, intervallo=30))
    except KeyboardInterrupt:
        print("\n🛑 Interruzione da tastiera (Ctrl+C)")
