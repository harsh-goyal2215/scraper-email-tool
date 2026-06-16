import io
import sqlite3
from flask import Flask, request, send_file, render_template_string
from config import Config

app = Flask(__name__)

# Transparent 1x1 pixel GIF bytes
PIXEL_BYTES = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'

def update_status(token, new_status):
    """Updates the status of an email campaign recipient in SQLite."""
    try:
        conn = sqlite3.connect(Config.DB_PATH)
        cursor = conn.cursor()
        
        # If the user is unsubscribing, they should override any state
        if new_status == 'unsubscribed':
            cursor.execute(
                "UPDATE sent_emails SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE token = ?",
                (new_status, token)
            )
        else:
            # For opens, only update if the current status is 'sent' (i.e. first open)
            cursor.execute(
                "UPDATE sent_emails SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE token = ? AND status = 'sent'",
                (new_status, token)
            )
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database update failed: {e}")
        return False

@app.route('/')
def home():
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Campaign Tracker</title>
            <style>
                body { font-family: sans-serif; text-align: center; padding: 50px; background-color: #f7f9fa; color: #333; }
                h1 { color: #0066cc; }
            </style>
        </head>
        <body>
            <h1>Tracking Server Active</h1>
            <p>Ready to capture email opens and opt-out requests.</p>
        </body>
        </html>
    """)

@app.route('/track')
def track():
    """
    Captures email open actions.
    Updates the email's state in the SQLite database.
    """
    token = request.args.get('t')
    email = request.args.get('e')
    
    if token:
        print(f"Registering email open: {email} (Token: {token})")
        update_status(token, 'opened')
        
    return send_file(io.BytesIO(PIXEL_BYTES), mimetype='image/gif')

@app.route('/unsubscribe')
def unsubscribe():
    """
    Opt-out endpoint for email campaigns.
    """
    token = request.args.get('t')
    
    success = False
    if token:
        success = update_status(token, 'unsubscribed')
        
    html_page = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Unsubscribe Confirmation</title>
        <style>
            body { font-family: 'Helvetica Neue', Arial, sans-serif; text-align: center; padding: 100px 20px; background-color: #fafbfc; color: #444; }
            .card { max-width: 480px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #eee; }
            h2 { color: #d9534f; margin-bottom: 20px; }
            p { font-size: 16px; line-height: 1.6; color: #666; }
            .icon { font-size: 48px; color: #d9534f; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="card">
            {% if success %}
                <div class="icon">✓</div>
                <h2>Unsubscribed Successfully</h2>
                <p>You have been removed from our mailing list. You will not receive any further communication from this campaign.</p>
            {% else %}
                <div class="icon">⚠</div>
                <h2>Invalid Request</h2>
                <p>We could not process your unsubscribe request. The token might be invalid or expired.</p>
            {% endif %}
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html_page, success=success)

def run_server(host='0.0.0.0', port=5000):
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    run_server()
