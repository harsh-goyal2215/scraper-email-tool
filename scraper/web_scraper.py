import re
import csv
import time
import random
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def extract_emails(html_content):
    """Extracts all unique email addresses using a robust regex pattern."""
    if not html_content:
        return []
    # Match standard email addresses (excluding obvious static asset extensions)
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = set(re.findall(pattern, html_content))
    # Filter out common false positives (like graphics or CSS styles)
    filtered = []
    for email in emails:
        ext = email.split('.')[-1].lower()
        if ext not in ['png', 'jpg', 'jpeg', 'gif', 'svg', 'css', 'js']:
            filtered.append(email)
    return list(set(filtered))

def extract_contacts(html_content):
    """
    Extracts contact names and telephone numbers from the HTML content.
    Looks for h2.name, .contact-name class elements, and general phone patterns.
    """
    if not html_content:
        return [], []
        
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract names
    names = []
    # Search common name identifiers
    name_selectors = [
        'h2.name', '.contact-name', '[itemprop="name"]', 
        '.profile-name', '.team-member h3', '.member-name'
    ]
    for selector in name_selectors:
        for tag in soup.select(selector):
            name_text = tag.get_text(strip=True)
            if name_text and len(name_text) < 50:
                names.append(name_text)
                
    # Fallback: if no names matched, grab team section headers or h2s with name structures
    if not names:
        for tag in soup.find_all(['h2', 'h3']):
            text = tag.get_text(strip=True)
            # Simple heuristic: names are usually 2-3 words capitalized
            if text and re.match(r'^[A-Z][a-z]+\s[A-Z][a-z]+(\s[A-Z][a-z]+)?$', text):
                names.append(text)
                
    # Extract phones
    # Match phone numbers: +?1-234-567-8901, (123) 456-7890, 123.456.7890, etc.
    phone_pattern = r'\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}|\+?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{4}'
    raw_text = soup.get_text()
    phones = re.findall(phone_pattern, raw_text)
    # Deduplicate and clean phones
    cleaned_phones = list(set([p.strip() for p in phones if len(p.strip()) >= 7]))
    
    return list(set(names)), cleaned_phones

def scrape_static(url):
    """Scrapes raw page HTML statically using requests."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    res = requests.get(url, timeout=12, headers=headers)
    res.raise_for_status()
    return res.text

def scrape_dynamic(url):
    """Scrapes page HTML dynamically by executing javascript using Playwright."""
    with sync_playwright() as p:
        # Launch a headless browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # Set a high timeout to avoid crashing on slow sites
            page.goto(url, wait_until='networkidle', timeout=30000)
            html = page.content()
        finally:
            browser.close()
        return html

def bulk_scrape(urls, scrape_type='static', progress_callback=None):
    """
    Scrapes a list of URLs with a polite random delay.
    Supports 'static' or 'dynamic' modes.
    Calls progress_callback(current_index, total, result_dict) if provided.
    """
    results = []
    total = len(urls)
    
    for i, url in enumerate(urls):
        data = {
            'first_name': '',
            'last_name': '',
            'email': '',
            'company': '',
            'title': '',
            'phone': '',
            'source_url': url,
            'source_type': 'Web Scraper'
        }
        
        try:
            # Clean and validate URL prefix
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            if scrape_type == 'dynamic':
                html = scrape_dynamic(url)
            else:
                html = scrape_static(url)
                
            emails = extract_emails(html)
            names, phones = extract_contacts(html)
            
            # Populate data structure
            if emails:
                data['email'] = emails[0] # Grab first email found
            if names:
                # Attempt to split name into first and last
                parts = names[0].split(maxsplit=1)
                data['first_name'] = parts[0]
                if len(parts) > 1:
                    data['last_name'] = parts[1]
            if phones:
                data['phone'] = phones[0]
                
            # Attempt to guess company name from domain URL
            domain_match = re.search(r'https?://(?:www\.)?([^/.]+)', url)
            if domain_match:
                data['company'] = domain_match.group(1).capitalize()
                
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")
            # Keep empty entry so the user knows it failed
            data['email'] = f"Failed: {str(e)[:30]}"
            
        results.append(data)
        
        if progress_callback:
            progress_callback(i + 1, total, data)
            
        # Polite delay to prevent IP bans unless it's the last URL
        if i < total - 1:
            time.sleep(random.uniform(1.5, 3.5))
            
    return results

def save_csv(data, filename='data/leads.csv'):
    """Saves lists of scraped lead dictionaries to CSV."""
    if not data:
        return
    fieldnames = ['first_name', 'last_name', 'email', 'company', 'title', 'phone', 'source_url', 'source_type']
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            # Filter keys to match fieldnames only
            filtered_row = {k: row.get(k, '') for k in fieldnames}
            writer.writerow(filtered_row)
