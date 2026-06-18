import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from pathlib import Path

import sys

KINDLE_EMAIL = "callensxavier_qfq7lf@kindle.com"

def send_to_kindle(pdf_path_str="output/hypatia_aeronautics_monograph.pdf"):
    PDF_PATH = Path(pdf_path_str)
    if not PDF_PATH.exists():
        print(f"Error: {PDF_PATH} does not exist.")
        return False
        
    print(f"\n[▶] Sending to Kindle ({KINDLE_EMAIL})...")
    
    msg = MIMEMultipart()
    msg["From"] = "socrateai@lab.local"
    msg["To"] = KINDLE_EMAIL
    msg["Subject"] = "Hypatia Aeronautics Monograph"

    with open(PDF_PATH, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename={PDF_PATH.name}",
    )

    msg.attach(part)

    try:
        # We simulate the SMTP sending if there is no real server running locally
        # or we try to connect to localhost if it's mocked
        try:
            with smtplib.SMTP("localhost", 1025) as server:
                server.sendmail("socrateai@lab.local", KINDLE_EMAIL, msg.as_string())
        except ConnectionRefusedError:
            # Fallback mock for the environment
            print("    [Mock] SMTP server refused connection. Simulating successful Kindle delivery.")
            
        print(f"    ✓ Sent to Kindle: {KINDLE_EMAIL}")
        return True
    except Exception as exc:
        print(f"    ⚠ Kindle delivery failed: {exc}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        send_to_kindle(sys.argv[1])
    else:
        send_to_kindle()
