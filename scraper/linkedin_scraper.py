import re
import requests
import urllib.parse
import validators
from config import Config

# Try importing from linkedin_api, handle ImportError if package setup issues occur
try:
    from linkedin_api import Linkedin
except ImportError:
    Linkedin = None

def search_people(keyword, location=None, count=10, username=None, password=None):
    """
    Search people on LinkedIn using the linkedin-api package.
    If no credentials are provided or login fails, falls back to mock search data.
    """
    u = username or Config.LINKEDIN_USERNAME
    p = password or Config.LINKEDIN_PASSWORD
    
    # Check if credentials are present
    if not u or not p or not Linkedin:
        print("LinkedIn credentials not fully configured or package missing. Using mock generator fallback.")
        return generate_mock_linkedin_leads(keyword, location, count)
        
    try:
        api = Linkedin(u, p)
        # Call search_people from linkedin-api
        results = api.search_people(keywords=keyword, regions=[location] if location else None, limit=count)
        leads = []
        for r in results:
            public_id = r.get('public_id')
            if not public_id:
                continue
                
            try:
                profile = api.get_profile(public_id)
            except Exception:
                profile = {}
                
            first_name = profile.get('firstName', '')
            last_name = profile.get('lastName', '')
            headline = profile.get('headline', '')
            
            # Extract company details
            experience = profile.get('experience', [])
            company = ''
            if experience:
                company = experience[0].get('companyName', '')
                
            leads.append({
                'first_name': first_name,
                'last_name': last_name,
                'email': '',  # Hiding emails is default LinkedIn behavior
                'company': company,
                'title': headline,
                'phone': '',
                'source_url': f"https://www.linkedin.com/in/{public_id}",
                'source_type': 'LinkedIn'
            })
        return leads
    except Exception as e:
        print(f"LinkedIn API error: {e}. Falling back to mock generator.")
        return generate_mock_linkedin_leads(keyword, location, count)

def generate_mock_linkedin_leads(keyword, location, count):
    """
    Generates realistic, mock lead data matching the keyword and location criteria.
    Helps demonstrate and test the dashboard functionality safely.
    """
    location = location or "United States"
    mock_first_names = ["Sarah", "Michael", "David", "Emma", "John", "Jessica", "James", "Sophia", "Robert", "Olivia"]
    mock_last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"]
    mock_companies = ["TechCorp", "InnovateLLC", "ApexSystems", "GlobalSolutions", "DevStudio", "NextGen", "ZenithInc"]
    
    leads = []
    for i in range(count):
        fn = mock_first_names[i % len(mock_first_names)]
        ln = mock_last_names[(i + 3) % len(mock_last_names)]
        comp = mock_companies[(i + i) % len(mock_companies)]
        title = f"Senior {keyword}" if i % 2 == 0 else f"{keyword} Lead"
        
        # Formulate a mock public ID
        public_id = f"{fn.lower()}-{ln.lower()}-{i}"
        
        # Make a guess of their email address using their company domain name
        domain = comp.lower() + ".com"
        guessed_email = f"{fn.lower()}.{ln.lower()}@{domain}"
        
        leads.append({
            'first_name': fn,
            'last_name': ln,
            'email': guessed_email,
            'company': comp,
            'title': title,
            'phone': f"+1 (555) {100 + i}-{2000 + i}",
            'source_url': f"https://www.linkedin.com/in/{public_id}",
            'source_type': 'LinkedIn (Mock)'
        })
    return leads

def find_email_hunter(first, last, domain, api_key=None):
    """
    Uses the Hunter.io API (Email Finder endpoint) to locate verified business emails.
    """
    key = api_key or Config.HUNTER_API_KEY
    if not key:
        return None
        
    url = 'https://api.hunter.io/v2/email-finder'
    params = {
        'first_name': first,
        'last_name': last,
        'domain': domain,
        'api_key': key
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json().get('data', {})
            return data.get('email')
    except Exception as e:
        print(f"Hunter.io API query failed: {e}")
    return None

def guess_email(first, last, domain):
    """
    Generates common business email heuristics.
    """
    if not first or not last or not domain:
        return []
        
    first = first.lower().strip()
    last = last.lower().strip()
    domain = domain.lower().strip()
    
    # Common business formats
    formats = [
        f"{first}.{last}@{domain}",       # john.doe@company.com
        f"{first}{last}@{domain}",         # johndoe@company.com
        f"{first[0]}{last}@{domain}",      # jdoe@company.com
        f"{first}@{domain}",               # john@company.com
        f"{first}_{last}@{domain}"         # john_doe@company.com
    ]
    return formats

def verify_email(email):
    """
    Checks email validity.
    Returns True if format is syntactically valid.
    """
    if not email:
        return False
    return validators.email(email)
