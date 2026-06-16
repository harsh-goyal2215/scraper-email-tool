import sys
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from config import Config
from scraper.web_scraper import bulk_scrape, save_csv
from scraper.linkedin_scraper import search_people
from scraper.cleaner import clean_leads
from emailer.sender import bulk_send

def run_pipeline():
    print("==================================================")
    print("   Starting Python Data Extractor & Email Sender   ")
    print("==================================================")

    # Initialize data folders
    Config.initialize_dirs()

    # Step 1: Scrape leads from website URLs
    # Using public domains for demonstration. They might not contain emails, which is normal.
    urls = [
        'https://example.com/contact',
        'https://example.com/team'
    ]
    print(f"\n[Step 1/4] Scraping Web leads statically from: {urls}...")
    web_leads = bulk_scrape(urls, scrape_type='static')
    print(f"-> Extracted {len(web_leads)} raw web leads.")

    # Step 2: Search LinkedIn leads
    # Will use Mock data generator if credentials are not configured in .env
    keyword = "Marketing Manager"
    location = "Paris"
    print(f"\n[Step 2/4] Querying LinkedIn for '{keyword}' in '{location}'...")
    li_leads = search_people(keyword, location, count=5)
    print(f"-> Found {len(li_leads)} LinkedIn leads.")

    # Step 3: Merge, Clean & Save leads
    print("\n[Step 3/4] Merging, cleaning and deduplicating leads...")
    all_raw_leads = web_leads + li_leads
    cleaned_leads = clean_leads(all_raw_leads)
    
    # Save the output CSV file
    save_path = Config.LEADS_CSV_PATH
    save_csv(cleaned_leads, save_path)
    print(f"-> Saved {len(cleaned_leads)} cleaned leads to '{save_path}'")

    if not cleaned_leads:
        print("\nNo cleaned leads found with valid emails. Exiting pipeline.")
        return

    # Step 4: Dispatch Email Campaign
    print("\n[Step 4/4] Preparing Email Campaign...")
    
    # Template strings
    subject_template = "Quick question about {{ company }}"
    body_template = """
    <h2>Hi {{ first_name }},</h2>
    <p>I noticed you work at <b>{{ company }}</b> as <b>{{ title }}</b>.</p>
    <p>We build automated pipelines and wanted to reach out regarding a potential collaboration.</p>
    <p>{{ custom_message }}</p>
    <p>Best,<br>{{ sender_name }}</p>
    """
    
    sender_name = "Alex Mercer"
    custom_msg = "Let me know if you are free for a brief 10-minute call next week."

    # Verify if SMTP is configured. If not, inform the user we are running in Dry Run mode.
    if not Config.SMTP_USER or not Config.SMTP_PASSWORD:
        print("\n[!] SMTP credentials not detected in environment/.env file.")
        print("[!] Running in DRY-RUN mode: printing rendered emails instead of sending.")
        
        for i, lead in enumerate(cleaned_leads[:2]):
            print(f"\n--- Rendered Draft #{i+1} for {lead['email']} ---")
            print(f"Subject: {subject_template.replace('{{ company }}', lead['company'])}")
            print(f"To: {lead['email']}")
            print("Body:")
            # Render just to print
            from emailer.sender import render_email, add_tracking_and_unsubscribe
            body = render_email(lead, sender_name, body_template, custom_msg)
            tracked_body = add_tracking_and_unsubscribe(body, lead['email'], f"mock-token-{i}")
            print(tracked_body)
            print("-" * 40)
    else:
        print(f"\nSMTP credentials detected. Initiating bulk email send via '{Config.SMTP_HOST}'...")
        # Run bulk send
        bulk_send(
            leads=cleaned_leads,
            subject_template=subject_template,
            body_template=body_template,
            sender_name=sender_name,
            method='smtp',
            custom_message=custom_msg
        )
        print("\nBulk campaign finished! Logs saved to SQLite database.")

if __name__ == '__main__':
    run_pipeline()
