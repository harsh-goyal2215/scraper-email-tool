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
        print("LinkedIn credentials not fully configured. Executing public search scraping alternative...")
        public_results = scrape_public_linkedin_profiles(keyword, location, count)
        if public_results:
            return public_results
        print("Public scraping returned 0 results. Falling back to mock generator.")
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
        print(f"LinkedIn API error: {e}. Executing public search scraping alternative...")
        public_results = scrape_public_linkedin_profiles(keyword, location, count)
        if public_results:
            return public_results
        print("Public scraping returned 0 results. Falling back to mock generator.")
        return generate_mock_linkedin_leads(keyword, location, count)

def scrape_public_linkedin_profiles(keyword, location, count):
    """
    Scrapes Google Search using search operators to find indexable public LinkedIn profile URLs
    matching the keyword and location parameters. Falls back to SerpAPI if configured.
    """
    from bs4 import BeautifulSoup
    import time
    import random
    
    query = f'site:linkedin.com/in/ "{keyword}"'
    if location:
        query += f' "{location}"'
        
    leads = []
    
    # Fallback to SerpAPI if API key is provided
    if Config.SERPAPI_API_KEY:
        print("Using SerpAPI for Google Search query...")
        serp_url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": Config.SERPAPI_API_KEY,
            "engine": "google",
            "num": count
        }
        try:
            res = requests.get(serp_url, params=params, timeout=12)
            if res.status_code == 200:
                results = res.json().get('organic_results', [])
                for item in results:
                    href = item.get('link', '')
                    if 'linkedin.com/in/' not in href:
                        continue
                    
                    title_text = item.get('title', '')
                    first_name = ''
                    last_name = ''
                    title = keyword
                    company = ''
                    
                    clean_title = title_text.replace(' - LinkedIn', '').replace(' | LinkedIn', '')
                    parts = [p.strip() for p in clean_title.split('-')]
                    if parts:
                        name_part = parts[0]
                        name_words = name_part.split()
                        if len(name_words) >= 1:
                            first_name = name_words[0]
                        if len(name_words) >= 2:
                            last_name = ' '.join(name_words[1:])
                        if len(parts) > 1:
                            title = parts[1]
                        if len(parts) > 2:
                            company = parts[2]
                            
                    guessed_email = ""
                    if first_name and last_name and company:
                        clean_comp = re.sub(r'[^\w]', '', company).lower()
                        guessed_email = f"{first_name.lower()}.{last_name.lower()}@{clean_comp}.com"
                    else:
                        guessed_email = f"{first_name.lower() or 'contact'}@company.com"
                        
                    leads.append({
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': guessed_email,
                        'company': company or 'Undetected Company',
                        'title': title or keyword,
                        'phone': '',
                        'source_url': href,
                        'source_type': 'LinkedIn (SerpAPI)'
                    })
                if leads:
                    return leads
        except Exception as serp_ex:
            print(f"SerpAPI query failed: {serp_ex}. Proceeding with HTML scraping...")

    # HTML Scraping Fallback
    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}&num={count + 5}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Google search results are in anchors under div.g or inside h3 tags
        for element in soup.select('div.g'):
            link_tag = element.find('a')
            if not link_tag:
                continue
            href = link_tag.get('href', '')
            if 'linkedin.com/in/' not in href:
                continue
                
            # Clean Google redirect links if present
            if '/url?q=' in href:
                href = href.split('/url?q=')[1].split('&')[0]
                href = urllib.parse.unquote(href)
                
            title_tag = element.find('h3')
            title_text = title_tag.get_text() if title_tag else ''
            
            # Google titles usually format as: "First Last - Job Title - Company | LinkedIn"
            # Parse names out of title text
            first_name = ''
            last_name = ''
            title = keyword
            company = ''
            
            clean_title = title_text.replace(' - LinkedIn', '').replace(' | LinkedIn', '')
            parts = [p.strip() for p in clean_title.split('-')]
            
            if parts:
                name_part = parts[0]
                name_words = name_part.split()
                if len(name_words) >= 1:
                    first_name = name_words[0]
                if len(name_words) >= 2:
                    last_name = ' '.join(name_words[1:])
                    
                if len(parts) > 1:
                    title = parts[1]
                if len(parts) > 2:
                    company = parts[2]
            
            # Guess email from company name if available
            guessed_email = ""
            if first_name and last_name and company:
                clean_comp = re.sub(r'[^\w]', '', company).lower()
                guessed_email = f"{first_name.lower()}.{last_name.lower()}@{clean_comp}.com"
            else:
                # General default guess fallback
                guessed_email = f"{first_name.lower() or 'contact'}@company.com"
                
            leads.append({
                'first_name': first_name,
                'last_name': last_name,
                'email': guessed_email,
                'company': company or 'Undetected Company',
                'title': title or keyword,
                'phone': '',
                'source_url': href,
                'source_type': 'LinkedIn (Public Search)'
            })
            
            if len(leads) >= count:
                break
                
            time.sleep(random.uniform(0.5, 1.5))
            
        return leads
    except Exception as ex:
        print(f"Failed to scrape public profiles: {ex}")
        return []

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
