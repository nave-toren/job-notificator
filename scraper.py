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

# מילים שמעלות את הציון של הלינק (סבירות גבוהה שזו משרה)
POSITIVE_KEYWORDS = [
    'engineer', 'developer', 'manager', 'specialist', 'lead', 'director',
    'analyst', 'designer', 'qa', 'r&d', 'full stack', 'backend', 'frontend',
    'devops', 'product', 'marketing', 'sales', 'customer', 'success', 'support',
    'account', 'executive', 'officer', 'vp', 'head of', 'controller', 'legal',
    'attorney', 'counsel', 'data', 'scientist', 'researcher', 'technician'
]

# מילים שבגללן נפסול את הלינק מיידית
NEGATIVE_KEYWORDS = [
    'privacy', 'policy', 'terms', 'cookie', 'login', 'sign in', 'sign up',
    'register', 'forgot', 'blog', 'news', 'press', 'about', 'contact',
    'facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 'investor',
    'share', 'print', 'skip to', 'accessibility', 'sitemap', 'home',
    'read more', 'learn more', 'faq', 'help', 'events'
]

# מילים ב-URL שמעלות סבירות שזו משרה
URL_INDICATORS = ['/job', '/career', '/position', '/opening', '/apply', '/vacancy', 'greenhouse.io', 'lever.co', 'comeet']

# סיווג לפי קטגוריות (לשליחת המייל)
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
    """
    מנוע ההחלטה: האם הלינק הזה הוא משרה?
    מחזיר True/False
    """
    text_lower = text.lower().strip()
    href_lower = href.lower()
    
    # 1. סינון זבל מהיר
    if len(text) < 3 or len(text) > 100: return False # קצר מדי או ארוך מדי (כנראה כותרת מאמר)
    if any(neg in text_lower for neg in NEGATIVE_KEYWORDS): return False
    if any(neg in href_lower for neg in NEGATIVE_KEYWORDS): return False
    if "javascript:" in href_lower or "mailto:" in href_lower: return False

    # 2. האם יש מילת מפתח חזקה בטקסט? (Engineer, Manager...)
    has_title_keyword = any(pos in text_lower for pos in POSITIVE_KEYWORDS)
    
    # 3. האם ה-URL נראה כמו משרה?
    has_url_indicator = any(ind in href_lower for ind in URL_INDICATORS)
    
    # לוגיקת ההחלטה:
    # אם יש מילת מפתח בטקסט - זה כמעט בטוח משרה.
    if has_title_keyword:
        return True
    
    # אם אין מילת מפתח בטקסט, אבל ה-URL ממש צועק "משרה" (למשל job/123)
    if has_url_indicator:
        # נוודא שהטקסט לא גנרי מדי (כמו "View")
        if len(text.split()) > 1: 
            return True
            
    return False

async def scrape_universal(page, company_row):
    """
    הסקראפר האוניברסלי.
    סורק את הדף הראשי + כל ה-IFrames בצורה רקורסיבית.
    """
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🤖 Universal Scan for {name}...")
    found_jobs = []

    try:
        # 1. ניווט חכם
        try:
            await page.goto(url, timeout=60000, wait_until='domcontentloaded') # domcontentloaded מהיר יותר מ-networkidle
            await asyncio.sleep(4) # נותן ל-JS (ול-Comeet/Greenhouse) זמן להיטען
        except Exception as e:
            print(f"      ⚠️ Timeout/Nav error: {e}")
            # ממשיכים, אולי חלק מהדף נטען

        # 2. גלילה להערת Lazy Loading
        for _ in range(3):
            await page.keyboard.press("PageDown")
            await asyncio.sleep(1)

        # 3. איסוף כל האלמנטים מכל ה-Frames
        all_elements = []
        
        # אוסף מה-Main Frame
        main_links = await page.query_selector_all('a')
        all_elements.extend(main_links)
        
        # אוסף מכל ה-Iframes (זה ה-Game Changer עבור Base44/Check Point)
        for frame in page.frames:
            if frame == page.main_frame: continue
            try:
                frame_links = await frame.query_selector_all('a')
                all_elements.extend(frame_links)
            except: continue

        seen_links = set()

        # 4. עיבוד וסינון
        for link in all_elements:
            try:
                # משיכת טקסט ולינק (טיפול בשגיאות אלמנטים שנעלמו)
                text = await link.inner_text()
                href = await link.get_attribute('href')
                
                if not text or not href: continue
                
                # נרמול הלינק
                full_link = urljoin(url, href)
                
                # בדיקת הלינק במנוע ההחלטה
                if is_valid_job_link(text, href, url):
                    
                    if full_link not in seen_links:
                        seen_links.add(full_link)
                        found_jobs.append({
                            "company_id": c_id,
                            "company": name,
                            "title": text.strip(),
                            "link": full_link
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
        color = "#3498db"
        if cat == 'Engineering': color = "#e74c3c"
        elif cat == 'Marketing': color = "#2ecc71"
        
        html_body += f"""
        <li style="margin-bottom: 10px; padding: 10px; border-left: 4px solid {color}; background: #f8f9fa;">
            <div style="font-size: 12px; color: #7f8c8d;">{cat} @ {job['company']}</div>
            <a href="{job['link']}" style="font-weight: bold; text-decoration: none; color: #2c3e50; font-size: 16px;">
                {job['title']}
            </a>
        </li>
        """
    
    html_body += "</ul></div>"

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
        # User Agent חיוני כדי לא להיחסם
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})

        for company in companies:
            c_id = company['id']
            # שימוש בפונקציה האחת והיחידה!
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
        
        user_companies = database.get_companies_by_user(email)
        user_company_ids = [c['id'] for c in user_companies]
        
        jobs_to_send = []
        for c_id in user_company_ids:
            current_jobs = jobs_by_company.get(c_id, [])
            for job in current_jobs:
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