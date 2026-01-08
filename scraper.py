import asyncio
import os
import requests
import re
from urllib.parse import urljoin
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import database

# 🔐 GLOBAL LOCK
is_scraping = False

# ================== ENV ==================
load_dotenv()

# ================== CONFIGURATION & KEYWORDS ==================

POSITIVE_KEYWORDS = [
    'engineer', 'developer', 'manager', 'specialist', 'lead', 'director',
    'analyst', 'designer', 'qa', 'r&d', 'full stack', 'backend', 'frontend',
    'devops', 'product', 'marketing', 'sales', 'customer', 'success', 'support',
    'account', 'executive', 'officer', 'vp', 'head of', 'controller', 'legal',
    'attorney', 'counsel', 'data', 'scientist', 'researcher', 'technician'
]

NEGATIVE_KEYWORDS = [
    'privacy', 'policy', 'terms', 'cookie', 'login', 'sign in', 'sign up',
    'register', 'forgot', 'blog', 'news', 'press', 'about', 'contact',
    'facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 'investor',
    'share', 'print', 'skip to', 'accessibility', 'sitemap', 'home',
    'read more', 'learn more', 'faq', 'help', 'events'
]

URL_INDICATORS = ['/job', '/career', '/position', '/opening', '/apply', '/vacancy', 'greenhouse.io', 'lever.co', 'comeet']

# --- מיקומים ---

# ערים בישראל (לזיהוי חיובי - לשימוש בתצוגה)
ISRAEL_LOCATIONS = [
    'israel', 'tel aviv', 'tlv', 'haifa', 'jerusalem', 'herzliya', 
    'raanana', 'petah tikva', 'rishon', 'rehovot', 'netanya', 
    'hod hasharon', 'ramat gan', 'givatayim', 'yokneam', 'beer sheva'
]

# ערים בחו"ל (לזיהוי שלילי - לחסימה רק אם המשתמש ביקש ישראל)
# הרעיון: חוסמים רק מה שבטוח לא רלוונטי
BLOCK_LOCATIONS = [
    'united states', 'usa', 'uk', 'united kingdom', 'london', 'paris', 'berlin', 
    'new york', 'san francisco', 'california', 'austin', 'texas', 'boston', 
    'germany', 'france', 'amsterdam', 'netherlands', 'canada', 'toronto', 
    'australia', 'sydney', 'remote - us', 'remote - eu', 'emea remote', 
    'singapore', 'tokyo', 'india', 'bangalore', 'poland', 'warsaw'
]

CATEGORY_MAPPING = {
    "Engineering": ['engineer', 'developer', 'r&d', 'data', 'algorithm', 'architect', 'full stack', 'backend', 'frontend', 'mobile', 'devops', 'software', 'qa', 'cyber', 'security', 'it'],
    "Product": ['product', 'design', 'ux', 'ui', 'creative', 'graphic'],
    "Marketing": ['marketing', 'sales', 'account', 'business', 'sdr', 'bdr', 'content', 'seo', 'ppc', 'growth', 'social'],
    "Finance": ['finance', 'accountant', 'controller', 'payroll', 'fp&a', 'legal', 'economist', 'bookkeeper'],
    "HR": ['hr', 'recruiter', 'talent', 'people', 'admin', 'operations', 'office'],
    "Support": ['support', 'customer', 'success', 'service', 'helpdesk']
}

def classify_job(title):
    t = title.lower()
    for category, keywords in CATEGORY_MAPPING.items():
        if any(k in t for k in keywords):
            return category
    return "Other"

# ================== THE UNIVERSAL SCRAPER LOGIC ==================

def is_valid_job_link(text, href, url_base):
    text_lower = text.lower().strip()
    href_lower = href.lower()
    
    if len(text) < 3 or len(text) > 100: return False
    if any(neg in text_lower for neg in NEGATIVE_KEYWORDS): return False
    if any(neg in href_lower for neg in NEGATIVE_KEYWORDS): return False
    if "javascript:" in href_lower or "mailto:" in href_lower: return False

    has_title_keyword = any(pos in text_lower for pos in POSITIVE_KEYWORDS)
    has_url_indicator = any(ind in href_lower for ind in URL_INDICATORS)
    
    if has_title_keyword: return True
    if has_url_indicator:
        if len(text.split()) > 1: return True
            
    return False

async def scrape_universal(page, company_row):
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🤖 Universal Scan for {name}...")
    found_jobs = []

    try:
        try:
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')
            await asyncio.sleep(4)
        except Exception as e:
            print(f"      ⚠️ Timeout/Nav error: {e}")

        for _ in range(3):
            await page.keyboard.press("PageDown")
            await asyncio.sleep(1)

        all_elements = []
        main_links = await page.query_selector_all('a')
        all_elements.extend(main_links)
        
        for frame in page.frames:
            if frame == page.main_frame: continue
            try:
                frame_links = await frame.query_selector_all('a')
                all_elements.extend(frame_links)
            except: continue

        seen_links = set()

        for link in all_elements:
            try:
                text = await link.inner_text()
                href = await link.get_attribute('href')
                
                if not text or not href: continue
                full_link = urljoin(url, href)
                
                if is_valid_job_link(text, href, url):
                    if full_link not in seen_links:
                        seen_links.add(full_link)
                        
                        # זיהוי מיקום להצגה (לא לסינון - הסינון קורה לפני השליחה)
                        location_tag = "🌎 Global/Other"
                        txt_lower = text.lower()
                        url_lower = full_link.lower()
                        
                        if any(loc in txt_lower or loc in url_lower for loc in ISRAEL_LOCATIONS):
                            location_tag = "🇮🇱 Israel"

                        found_jobs.append({
                            "company_id": c_id,
                            "company": name,
                            "title": text.strip(),
                            "link": full_link,
                            "location": location_tag
                        })
            except:
                continue

    except Exception as e:
        print(f"❌ Error scanning {name}: {e}")

    print(f"   ✅ Found {len(found_jobs)} potential jobs at {name}")
    return found_jobs


# ================== EMAIL SYSTEM ==================

async def send_email(to_email, user_interests, jobs_list):
    if not jobs_list: return False
    
    user_interest_list = user_interests.split(',') if user_interests else []
    relevant_jobs = []
    
    for job in jobs_list:
        cat = classify_job(job['title'])
        if not user_interest_list or cat in user_interest_list:
            relevant_jobs.append(job)
            
    if not relevant_jobs: return False

    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #4a4a4a;">🚀 New Jobs Found!</h2>
        <p>Found <b>{len(relevant_jobs)}</b> matches for: <b>{user_interests if user_interests else 'All'}</b></p>
        <ul style="padding: 0; list-style: none;">
    """
    
    for job in relevant_jobs:
        cat = classify_job(job['title'])
        loc_display = job.get('location', '🌎')
        color = "#3498db"
        if cat == 'Engineering': color = "#e74c3c"
        elif cat == 'Marketing': color = "#2ecc71"
        
        html_body += f"""
        <li style="margin-bottom: 10px; padding: 10px; border-left: 4px solid {color}; background: #f8f9fa;">
            <div style="font-size: 12px; color: #7f8c8d;">
                {cat} @ {job['company']} &nbsp; | &nbsp; <b>{loc_display}</b>
            </div>
            <a href="{job['link']}" style="font-weight: bold; text-decoration: none; color: #2c3e50; font-size: 16px;">
                {job['title']}
            </a>
        </li>
        """
    
    # --- הפוטר החדש שלך ---
    html_body += """
        </ul>
        <div style="margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px; text-align: center; color: #555; font-size: 14px;">
            <p>Now you can play matkot on the beach 🏖️ while I'm finding jobs for you 😎</p>
            <p style="font-weight: bold; margin-top: 10px;">— Career Agent 🤖<br>by Nave Toren</p>
        </div>
    </div>
    """

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key: return False
        
    try:
        requests.post(
            "https://api.resend.com/emails",
            json={
                "from": "Career Agent <onboarding@resend.dev>",
                "to": [to_email],
                "subject": f"🔥 {len(relevant_jobs)} New Jobs Found!",
                "html": html_body
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

# ================== MAIN ENGINE ==================

async def run_scraper_engine():
    print("🚀 Starting Universal Scraper Engine...")
    companies = database.get_all_companies_for_scan()
    users = database.get_users()
    
    if not companies:
        print("😴 No companies to scan.")
        return

    jobs_by_company = {}
    globally_new_links = set()

    async with async_playwright() as p:
        print("   🔨 Launching Browser...")
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--single-process']
        )
        page = await browser.new_page()
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})

        for company in companies:
            c_id = company['id']
            jobs = await scrape_universal(page, company)
            jobs_by_company[c_id] = jobs

            for job in jobs:
                if not database.job_exists(job['link']):
                    database.add_job(c_id, job['title'], job['link'])
                    globally_new_links.add(job['link'])
        
        await browser.close()

    print(f"\n📨 Processing emails for {len(users)} users...")
    
    for user in users:
        email = user['email']
        interests = user['interests']
        is_new_user = user.get('is_new_user', False)
        
        # שליפת העדפת האזור (ברירת מחדל 'Other' אם לא קיים)
        region_pref = user.get('region_preference', 'Other') 
        
        user_companies = database.get_companies_by_user(email)
        user_company_ids = [c['id'] for c in user_companies]
        
        jobs_to_send = []
        for c_id in user_company_ids:
            current_jobs = jobs_by_company.get(c_id, [])
            for job in current_jobs:
                
                # --- לוגיקת סינון משופרת ---
                
                # 1. אם המשתמש בחר "Israel", בדוק אם צריך לחסום
                if region_pref == 'Israel':
                    title_lower = job['title'].lower()
                    link_lower = job['link'].lower()
                    
                    # בדיקה: האם זה בבירור מחוץ לישראל?
                    is_blocked_location = any(b in title_lower or b in link_lower for b in BLOCK_LOCATIONS)
                    
                    # אם זה מזוהה כחו"ל (למשל "London"), אנחנו מדלגים.
                    # אבל אם לא זיהינו כלום (או שזיהינו ישראל) - אנחנו משאירים!
                    if is_blocked_location:
                        continue 
                
                # 2. בדיקת חדש/ישן
                if is_new_user:
                    jobs_to_send.append(job)
                else:
                    if job['link'] in globally_new_links:
                        jobs_to_send.append(job)
                        
        if jobs_to_send:
            await send_email(email, interests, jobs_to_send)
            if is_new_user:
                database.mark_user_as_not_new(email)
        else:
            print(f"🤷‍♂️ No relevant updates for {email}")

    print("🏁 Scraper finished.")

async def run_scraper_with_lock():
    global is_scraping
    if is_scraping:
        print("⏳ Scraper running. Skipping.")
        return
    is_scraping = True
    try:
        await run_scraper_engine()
    finally:
        is_scraping = False