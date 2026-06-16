import os
import uuid
import sqlite3
import time
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from jinja2 import Template
from config import Config

def init_db():
    """Initializes the SQLite database schema if not already present."""
    Config.initialize_dirs()
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    # Create the logging and tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            subject TEXT,
            status TEXT,
            token TEXT UNIQUE,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def send_email_smtp(to, subject, body_html):
    """Sends a personalized HTML email via standard SMTP (TLS)."""
    host = Config.SMTP_HOST
    port = Config.SMTP_PORT
    user = Config.SMTP_USER
    password = Config.SMTP_PASSWORD

    if not user or not password:
        raise ValueError("SMTP Credentials are empty. Set them in your environment/.env file.")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = user
    msg['To'] = to
    
    # Attach HTML payload
    msg.attach(MIMEText(body_html, 'html'))

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)

def send_email_mailgun(to, subject, body_html):
    """Sends an email using the Mailgun HTTP REST API."""
    api_key = Config.MAILGUN_API_KEY
    domain = Config.MAILGUN_DOMAIN

    if not api_key or not domain:
        raise ValueError("Mailgun API key or Domain is empty. Set them in your environment/.env file.")

    url = f"https://api.mailgun.net/v3/{domain}/messages"
    auth = ("api", api_key)
    data = {
        "from": f"Campaign Manager <mailgun@{domain}>",
        "to": to,
        "subject": subject,
        "html": body_html
    }
    
    res = requests.post(url, auth=auth, data=data, timeout=12)
    res.raise_for_status()
    return res.json()

def render_email(lead, sender_name, template_str, custom_msg):
    """Compiles email templates dynamically using Jinja2."""
    t = Template(template_str)
    return t.render(
        first_name=lead.get('first_name', ''),
        last_name=lead.get('last_name', ''),
        company=lead.get('company', ''),
        title=lead.get('title', ''),
        sender_name=sender_name,
        custom_message=custom_msg
    )

def add_tracking_and_unsubscribe(html_body, email, token):
    """
    Appends transparent tracking pixel and legal unsubscribe footer link to email content.
    """
    # 1. Open Tracking Pixel
    pixel_url = f"{Config.TRACKING_SERVER_URL}/track?t={token}&e={email}"
    pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none;" alt="" />'
    
    # 2. Unsubscribe link
    unsub_url = f"{Config.TRACKING_SERVER_URL}/unsubscribe?t={token}"
    unsub_html = (
        f'<br><hr style="border:none;border-top:1px solid #eee;margin:20px 0;" />'
        f'<p style="font-size:11px;color:#888;font-family:sans-serif;text-align:center;">'
        f'You received this email from {Config.SMTP_USER or "us"}.<br>'
        f'If you wish to stop receiving emails, you can <a href="{unsub_url}" style="color:#0066cc;">unsubscribe here</a>.'
        f'</p>'
    )
    
    return html_body + pixel_html + unsub_html

def bulk_send(leads, subject_template, body_template, sender_name, method='smtp', custom_message="", progress_callback=None):
    """
    Sends personalized, tracked emails to a collection of leads with built-in rate limiting.
    Logs each transaction status directly to SQLite.
    """
    conn = init_db()
    cursor = conn.cursor()
    total = len(leads)
    
    for i, lead in enumerate(leads):
        email = lead.get('email', '').strip()
        if not email or '@' not in email:
            continue
            
        token = uuid.uuid4().hex
        
        # 1. Render subject template if it contains Jinja placeholders
        subj_tmpl = Template(subject_template)
        subject = subj_tmpl.render(company=lead.get('company', ''))
        
        # 2. Render HTML body template
        body = render_email(lead, sender_name, body_template, custom_message)
        
        # 3. Add tracking pixel and unsubscribe links
        tracked_body = add_tracking_and_unsubscribe(body, email, token)
        
        status = 'sent'
        try:
            # 4. Dispatch email
            if method.lower() == 'mailgun':
                send_email_mailgun(email, subject, tracked_body)
            else:
                send_email_smtp(email, subject, tracked_body)
                
            # Log successful send in DB
            cursor.execute(
                'INSERT INTO sent_emails (email, subject, status, token) VALUES (?, ?, ?, ?)',
                (email, subject, 'sent', token)
            )
            conn.commit()
            print(f"Successfully sent email to {email}")
            
        except Exception as e:
            status = f"failed: {str(e)[:50]}"
            # Log failure in DB
            cursor.execute(
                'INSERT INTO sent_emails (email, subject, status, token) VALUES (?, ?, ?, ?)',
                (email, subject, status, token)
            )
            conn.commit()
            print(f"Failed to send to {email}: {e}")
            
        if progress_callback:
            progress_callback(i + 1, total, email, status)
            
        # Polite delay to prevent SMTP block / spam trigger
        if i < total - 1:
            delay = random.uniform(3.0, 8.0)
            time.sleep(delay)
            
    conn.close()
