import sys
import time
import sqlite3
import threading
import pandas as pd
import streamlit as st
import requests
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from config import Config
from scraper.web_scraper import bulk_scrape, save_csv
from scraper.linkedin_scraper import search_people, verify_email
from scraper.cleaner import clean_leads
from emailer.sender import bulk_send, init_db, render_email

# Set up page configurations
st.set_page_config(
    page_title="Data Extractor & Email Sender",
    page_icon="✉️",
    layout="wide"
)

# Custom premium styling
st.markdown("""
<style>
    /* Premium font import */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Elegant Title and headers */
    .main-title {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        color: #555;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Modern card container */
    .metric-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 1px solid #f0f0f0;
        text-align: center;
        transition: transform 0.2s ease-in-out;
    }
    .metric-card:hover {
        transform: translateY(-3px);
    }
    .metric-number {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .metric-label {
        font-size: 0.9rem;
        font-weight: 600;
        color: #777;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

# Thread management for Flask Tracking Server
if 'tracker_thread' not in st.session_state:
    st.session_state.tracker_thread = None
if 'tracker_running' not in st.session_state:
    st.session_state.tracker_running = False

def start_flask_server():
    """Starts the Flask tracking microservice in a daemon background thread."""
    from emailer.tracker import app as flask_app
    
    def run_flask():
        try:
            # Run flask on port 5000 without automatic reloader
            flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
        except Exception as e:
            print(f"Flask background launch exception: {e}")
            
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    st.session_state.tracker_thread = t
    st.session_state.tracker_running = True

# Helper: check local Flask tracker port status
def check_tracker_status():
    try:
        res = requests.get("http://localhost:5000/", timeout=1)
        if res.status_code == 200:
            st.session_state.tracker_running = True
            return True
    except requests.exceptions.RequestException:
        pass
    st.session_state.tracker_running = False
    return False

# Initialize folders
Config.initialize_dirs()
init_db()

# Title banner
st.markdown('<div class="main-title">Python Data Extractor & Bulk Email Sender</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Personalized, Tracked, and Rate-Limited Bulk Email Campaign Manager</div>', unsafe_allow_html=True)

# Sidebar - Settings Panel
with st.sidebar:
    st.header("⚙️ Configuration Settings")
    st.markdown("---")
    
    # Tracking Server Controls
    st.subheader("📡 Campaign Tracking Server")
    check_tracker_status()
    if st.session_state.tracker_running:
        st.success("Tracking Server is ACTIVE (Port 5000)")
    else:
        st.warning("Tracking Server is INACTIVE")
        if st.button("🚀 Start Tracking Server"):
            start_flask_server()
            st.success("Server started in the background!")
            time.sleep(1)
            st.rerun()
            
    st.markdown("---")
    st.subheader("📧 SMTP Configuration")
    smtp_host = st.text_input("SMTP Host", value=Config.SMTP_HOST)
    smtp_port = st.number_input("SMTP Port", value=Config.SMTP_PORT, step=1)
    smtp_user = st.text_input("SMTP User (Email)", value=Config.SMTP_USER)
    smtp_pass = st.text_input("SMTP Password", value=Config.SMTP_PASSWORD, type="password")
    
    # Save parameters to Config class instance
    Config.SMTP_HOST = smtp_host
    Config.SMTP_PORT = smtp_port
    Config.SMTP_USER = smtp_user
    Config.SMTP_PASSWORD = smtp_pass

    st.markdown("---")
    st.subheader("📬 Mailgun Settings (Optional)")
    mg_key = st.text_input("Mailgun API Key", value=Config.MAILGUN_API_KEY)
    mg_domain = st.text_input("Mailgun Domain", value=Config.MAILGUN_DOMAIN)
    Config.MAILGUN_API_KEY = mg_key
    Config.MAILGUN_DOMAIN = mg_domain

    st.markdown("---")
    st.subheader("🔑 External APIs & Scraping")
    hunter_key = st.text_input("Hunter.io API Key", value=Config.HUNTER_API_KEY)
    Config.HUNTER_API_KEY = hunter_key
    
    li_username = st.text_input("LinkedIn Username", value=Config.LINKEDIN_USERNAME)
    li_password = st.text_input("LinkedIn Password", value=Config.LINKEDIN_PASSWORD, type="password")
    Config.LINKEDIN_USERNAME = li_username
    Config.LINKEDIN_PASSWORD = li_password

# Tabs Setup
tab_scrape, tab_campaign, tab_analytics = st.tabs([
    "🔍 Lead Scraper & Extractor", 
    "✉️ Email Campaigns", 
    "📊 Analytics & Logs"
])

# ==========================================
# TAB 1: Lead Scraper & Extractor
# ==========================================
with tab_scrape:
    st.header("Search & Extrapolate Lead Contacts")
    
    scrape_source = st.radio("Choose lead generation method:", ["Web URL Scraping", "LinkedIn Keyword Search"], horizontal=True)
    
    scraped_leads = st.session_state.get("scraped_leads", [])
    
    if scrape_source == "Web URL Scraping":
        col_input, col_opts = st.columns([2, 1])
        with col_input:
            urls_text = st.text_area(
                "Enter Target URLs (one per line):", 
                value="https://example.com/contact\nhttps://example.com/team",
                height=120
            )
        with col_opts:
            scrape_type = st.selectbox("Scraping Engine Mode:", ["static", "dynamic"], index=0, 
                                       help="Static is extremely fast. Dynamic executes javascript using headless Playwright.")
            st.info("Dynamic mode is suitable for sites rendering content using React, Angular or Vue SPAs.")
            
        if st.button("🔍 Start Scraping Websites", type="primary"):
            urls = [url.strip() for url in urls_text.split("\n") if url.strip()]
            if urls:
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_container = st.container()
                
                def progress_cb(current, total, data):
                    progress_bar.progress(current / total)
                    status_text.text(f"Scraped website {current}/{total}: {data['source_url']}")
                
                with st.spinner("Executing scraper scripts..."):
                    scraped_leads = bulk_scrape(urls, scrape_type=scrape_type, progress_callback=progress_cb)
                    st.session_state["scraped_leads"] = scraped_leads
                
                st.success(f"Finished scraping. Found {len(scraped_leads)} leads.")
            else:
                st.error("Please insert at least one URL.")
                
    else:  # LinkedIn Keyword Search
        col_kw, col_loc, col_cnt = st.columns([2, 2, 1])
        with col_kw:
            keyword = st.text_input("Job Title / Role Keyword:", value="Marketing Manager")
        with col_loc:
            location = st.text_input("Region / Location:", value="Paris")
        with col_cnt:
            count = st.number_input("Count limit:", min_value=1, max_value=100, value=5, step=1)
            
        if st.button("🔗 Search LinkedIn Profiles", type="primary"):
            with st.spinner("Connecting to LinkedIn gateway..."):
                # Call search
                scraped_leads = search_people(
                    keyword=keyword, 
                    location=location, 
                    count=count, 
                    username=Config.LINKEDIN_USERNAME, 
                    password=Config.LINKEDIN_PASSWORD
                )
            st.success(f"Finished querying. Retrieved {len(scraped_leads)} profiles.")
            
    # Cleaning, deduplication, and export configuration
    if len(scraped_leads) > 0:
        st.subheader("Raw Extracted Results")
        raw_df = pd.DataFrame(scraped_leads)
        st.dataframe(raw_df, use_container_width=True)
        
        st.subheader("Process & Store Clean Leads")
        st.markdown("Clean operations capitalizes names, normalizes email casings, extracts domain companies, and eliminates duplicates.")
        
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("✨ Clean & Save to Leads Database", type="secondary"):
                cleaned = clean_leads(scraped_leads)
                if cleaned:
                    # Save clean leads
                    save_csv(cleaned, Config.LEADS_CSV_PATH)
                    save_csv(cleaned, Config.LEADS_CSV_PATH)
                    st.write("CLEANED LEADS:", cleaned)
                    st.success(f"Deduplicated and saved {len(cleaned)} leads directly to '{Config.LEADS_CSV_PATH.name}'!")
                    # Force reload leads view
                    st.rerun()
                else:
                    st.warning("No leads remained after cleaning (e.g. missing or malformed email addresses).")

# ==========================================
# TAB 2: Email Campaigns
# ==========================================
with tab_campaign:
    st.header("Draft & Dispatch Campaigns")
    
    # Load current leads CSV file
    leads_list = []
    if Config.LEADS_CSV_PATH.exists():
        try:
            df_leads = pd.read_csv(Config.LEADS_CSV_PATH)
            # Replace NaN with empty string
            df_leads = df_leads.fillna("")
            leads_list = df_leads.to_dict('records')
        except Exception as e:
            st.error(f"Error reading {Config.LEADS_CSV_PATH.name}: {e}")
            
    st.metric("Total Available Leads in CSV File", len(leads_list))
    
    if not leads_list:
        st.warning("No leads found in leads.csv database. Please search/scrape leads in Tab 1 first or upload a custom leads.csv below.")
        
        uploaded_file = st.file_uploader("Upload custom leads CSV file", type=['csv'])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                df.to_csv(Config.LEADS_CSV_PATH, index=False)
                st.success("File uploaded successfully. Refreshing dashboard...")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to read uploaded CSV: {e}")
    else:
        # Show mini preview of leads
        with st.expander("👁 View Available Lead List"):
            st.dataframe(pd.DataFrame(leads_list), use_container_width=True)
            
        # Campaign Builder forms
        st.subheader("Campaign Builder")
        col_c1, col_c2 = st.columns([3, 2])
        
        with col_c1:
            subject_tmpl = st.text_input("Email Subject Template (supports {{ company }}):", value="Quick question about {{ company }}")
            sender_name = st.text_input("Sender Name (Your Name):", value="Alex Mercer")
            custom_msg = st.text_area("Custom Message (inserts as {{ custom_message }}):", value="I wanted to check if your team would be interested in automated solutions.")
            
            body_tmpl = st.text_area(
                "Jinja2 HTML Body Template:", 
                value="""<h2>Hi {{ first_name }},</h2>
<p>I noticed you work at <b>{{ company }}</b> as <b>{{ title }}</b>.</p>
<p>We build automated pipelines and wanted to reach out regarding a potential collaboration.</p>
<p>{{ custom_message }}</p>
<p>Best,<br>{{ sender_name }}</p>""",
                height=250
            )
            
        with col_c2:
            st.subheader("Jinja2 Live Preview")
            st.markdown("Displays rendering using the *first* lead from your list:")
            
            if leads_list:
                first_lead = leads_list[0]
                try:
                    # Mock token for preview
                    preview_body = render_email(first_lead, sender_name, body_tmpl, custom_msg)
                    preview_subject = subject_tmpl.replace("{{ company }}", first_lead.get('company', ''))
                    
                    st.markdown(f"**Subject:** {preview_subject}")
                    st.markdown("---")
                    st.components.v1.html(preview_body, height=300, scrolling=True)
                except Exception as template_err:
                    st.error(f"Template rendering error: {template_err}")
            else:
                st.info("Add leads to see template preview.")
                
        st.markdown("---")
        st.subheader("Campaign Dispatch Operations")
        col_opts1, col_opts2 = st.columns(2)
        with col_opts1:
            send_method = st.selectbox("Dispatch Engine Gateway:", ["SMTP", "Mailgun"], index=0)
        with col_opts2:
            st.markdown("<br>", unsafe_allow_html=True)
            # Validation safety check
            is_ready = True
            if send_method == "SMTP" and (not Config.SMTP_USER or not Config.SMTP_PASSWORD):
                st.error("SMTP credentials must be specified in the sidebar to start sending.")
                is_ready = False
            elif send_method == "Mailgun" and (not Config.MAILGUN_API_KEY or not Config.MAILGUN_DOMAIN):
                st.error("Mailgun API settings must be specified in the sidebar to start sending.")
                is_ready = False
                
            if st.button("🚀 Dispatch Bulk Campaign", type="primary", disabled=not is_ready):
                progress_bar = st.progress(0)
                status_box = st.empty()
                log_box = st.code("Initiating email send thread...\n")
                
                log_content = ""
                def bulk_progress_cb(current, total, email, status):
                    global log_content
                    progress_bar.progress(current / total)
                    status_box.text(f"Processed email {current}/{total}: {email}")
                    log_content += f"[{status.upper()}] Sent email to {email}\n"
                    log_box.code(log_content)
                    
                with st.spinner("Dispatching campaign..."):
                    bulk_send(
                        leads=leads_list,
                        subject_template=subject_tmpl,
                        body_template=body_tmpl,
                        sender_name=sender_name,
                        method=send_method.lower(),
                        custom_message=custom_msg,
                        progress_callback=bulk_progress_cb
                    )
                st.success("Campaign dispatch run completed! Check logs in Tab 3.")

# ==========================================
# TAB 3: Analytics & Logs
# ==========================================
with tab_analytics:
    st.header("Real-Time Analytics & Campaign Logs")
    
    # Query Database counts
    sent_count = 0
    opened_count = 0
    failed_count = 0
    unsub_count = 0
    logs_df = pd.DataFrame()
    
    try:
        conn = sqlite3.connect(Config.DB_PATH)
        
        # Calculate stats
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM sent_emails")
        sent_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM sent_emails WHERE status = 'opened'")
        opened_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM sent_emails WHERE status LIKE 'failed%'")
        failed_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM sent_emails WHERE status = 'unsubscribed'")
        unsub_count = c.fetchone()[0]
        
        # Retrieve raw logs
        logs_df = pd.read_sql_query("SELECT * FROM sent_emails ORDER BY sent_at DESC", conn)
        conn.close()
    except Exception as db_err:
        st.error(f"Failed to query database: {db_err}")
        
    # Metrics Row
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    with col_m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-number" style="color: #2a5298;">{sent_count}</div>
            <div class="metric-label">Total Outbox Sent</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_m2:
        open_rate_str = f"{(opened_count / sent_count * 100):.1f}%" if sent_count > 0 else "0.0%"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-number" style="color: #27ae60;">{opened_count} ({open_rate_str})</div>
            <div class="metric-label">Opened (Tracking Pixel)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-number" style="color: #c0392b;">{failed_count}</div>
            <div class="metric-label">Delivery Failures</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-number" style="color: #7f8c8d;">{unsub_count}</div>
            <div class="metric-label">Unsubscribed Users</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.subheader("Detailed Logs Database")
    
    if not logs_df.empty:
        # Add search filter
        search_query = st.text_input("Filter logs by Email / Subject / Status:")
        if search_query:
            filtered_logs = logs_df[
                logs_df['email'].str.contains(search_query, case=False) |
                logs_df['subject'].str.contains(search_query, case=False) |
                logs_df['status'].str.contains(search_query, case=False)
            ]
        else:
            filtered_logs = logs_df
            
        st.dataframe(filtered_logs, use_container_width=True)
        
        # Reset control
        if st.button("🗑️ Clear Sent Logs Database", type="secondary"):
            try:
                conn = sqlite3.connect(Config.DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM sent_emails")
                conn.commit()
                conn.close()
                st.success("Sent logs database cleared successfully!")
                st.rerun()
            except Exception as reset_err:
                st.error(f"Failed to clear database: {reset_err}")
    else:
        st.info("No campaign email transmission history is logged in the database yet.")
