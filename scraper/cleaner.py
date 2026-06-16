import re

def clean_text(text):
    """Safely trims whitespace and returns an empty string if None."""
    if not text:
        return ''
    return str(text).strip()

def clean_email(email):
    """Lowercases and strips whitespace from email strings."""
    if not email:
        return ''
    return str(email).lower().strip()

def clean_phone(phone):
    """Cleans phone numbers by removing non-alphanumeric separators, leaving a standard representation."""
    if not phone:
        return ''
    cleaned = re.sub(r'[^\d+\s()-]', '', str(phone))
    return cleaned.strip()

def clean_name(name):
    """Capitalizes the first letter of each name part."""
    if not name:
        return ''
    parts = [part.capitalize() for part in str(name).split()]
    return ' '.join(parts)

def clean_leads(leads_list):
    """
    Cleans a list of lead dictionaries:
    - Trims spaces and formats fields
    - Validates email formats
    - Deduplicates by email (keeping the first occurrence)
    """
    cleaned_leads = []
    seen_emails = set()
    
    for lead in leads_list:
        email = clean_email(lead.get('email', ''))
        
        # Skip empty or failed scrapings
        if not email or email.startswith('failed'):
            continue
            
        # Deduplicate
        if email in seen_emails:
            continue
            
        # Clean fields
        cleaned_lead = {
            'first_name': clean_name(lead.get('first_name', '')),
            'last_name': clean_name(lead.get('last_name', '')),
            'email': email,
            'company': clean_text(lead.get('company', '')),
            'title': clean_text(lead.get('title', '')),
            'phone': clean_phone(lead.get('phone', '')),
            'source_url': clean_text(lead.get('source_url', '')),
            'source_type': clean_text(lead.get('source_type', ''))
        }
        
        seen_emails.add(email)
        cleaned_leads.append(cleaned_lead)
        
    return cleaned_leads
