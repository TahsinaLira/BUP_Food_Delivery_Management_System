"""
mailer.py  —  tiny email helper for the password-reset OTP.

Behaviour:
  * If SMTP settings are configured (in .env), it sends a REAL email.
  * If they are NOT configured — OR if sending fails for any reason — it prints
    the email to the terminal instead, so the reset flow never crashes and the
    feature still works during development/demo with zero setup.
Uses only Python's built-in smtplib (no extra packages).
"""
import smtplib
import ssl
from email.message import EmailMessage
from flask import current_app


def _print_to_terminal(to_addr, subject, body, reason):
    print("\n" + "=" * 56)
    print(f"  [DEV MODE] {reason} — e-mail printed here:")
    print(f"  To      : {to_addr}")
    print(f"  Subject : {subject}")
    print("  " + body.replace("\n", "\n  "))
    print("=" * 56 + "\n")


def send_email(to_addr, subject, body):
    cfg = current_app.config
    host = cfg.get("SMTP_HOST")
    user = cfg.get("SMTP_USER")
    pw = cfg.get("SMTP_PASS")
    sender = cfg.get("SMTP_FROM") or user

    # ---- Not configured -> print to terminal (dev/demo mode) ----
    if not (host and user and pw):
        _print_to_terminal(to_addr, subject, body, "SMTP not configured")
        return False

    # ---- Configured -> try to send a real email ----
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(body)

    port = int(cfg.get("SMTP_PORT", 587))
    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context) as s:
                s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as s:
                s.starttls(context=context)
                s.login(user, pw)
                s.send_message(msg)
        return True
    except Exception as e:
        # Never let an email problem crash the password-reset request.
        _print_to_terminal(to_addr, subject, body, f"SMTP send failed ({e})")
        return False
