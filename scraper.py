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

ISRAEL_LOCATIONS = [
    'israel', 'tel aviv', 'tlv', 'haifa', 'jerusalem', 'herzliya', 
    'raanana', 'petah tikva', 'rishon', 'rehovot', 'netanya', 
    'hod hasharon', 'ramat gan', 'givatayim', 'yokneam', 'beer sheva'
]

BLOCK_LOCATIONS = [
    'united states', 'usa', 'uk', 'united kingdom', 'london', 'paris', 'berlin', 
    'new york', 'san francisco', 'california', 'austin', 'texas', 'boston', 
    'germany', 'france', 'amsterdam', 'netherlands', 'canada', 'toronto', 
    'australia', 'sydney', 'singapore', 'tokyo', 'india'
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

# ================== LOGIC ==================

def is_valid_job_link(text, href, url_base):
    text_lower = text.lower().strip()
    href_lower = href.lower()
    
    if len(text.split()) == 1 and text_lower in ['products', 'solutions', 'customers', 'support', 'company', 'resources', 'platform', 'careers', 'jobs']:
        return False

    if re.search(r'\d+\s+(jobs|positions|roles|openings)', text_lower):
        return False
    
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
        except: pass

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
                
                clean_title = text.strip().replace("Find out more >", "").replace("Find out more", "").strip()

                if is_valid_job_link(clean_title, href, url):
                    if full_link not in seen_links:
                        seen_links.add(full_link)
                        
                        location_tag = "🌎 Global/Other"
                        txt_lower = clean_title.lower()
                        url_lower = full_link.lower()
                        
                        if any(loc in txt_lower or loc in url_lower for loc in ISRAEL_LOCATIONS):
                            location_tag = "🇮🇱 Israel"

                        found_jobs.append({
                            "company_id": c_id,
                            "company": name,
                            "title": clean_title,
                            "link": full_link,
                            "location": location_tag
                        })
            except: continue

    except Exception as e:
        print(f"❌ Error scanning {name}: {e}")

    print(f"   ✅ Found {len(found_jobs)} potential jobs at {name}")
    return found_jobs

# ================== EMAIL SYSTEM ==================

async def send_email(to_email, user_interests, jobs_list):
    if not jobs_list: return False
    
    user_interest_list = user_interests.split(',') if user_interests else []
    
    jobs_by_category = {}
    for job in jobs_list:
        cat = classify_job(job['title'])
        if user_interest_list and cat not in user_interest_list:
            continue
        if cat not in jobs_by_category:
            jobs_by_category[cat] = []
        jobs_by_category[cat].append(job)
            
    if not jobs_by_category: return False

    total_jobs = sum(len(v) for v in jobs_by_category.values())

    html_body = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
        <div style="background: linear-gradient(135deg, #6c5ce7, #a29bfe); padding: 20px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">🎯 Fresh Opportunities!</h1>
            <p style="color: #e2e2e2; margin-top: 5px; font-size: 13px; font-weight: 600;">Created by Nave Toren</p>
        </div>
        
        <div style="padding: 20px; background: #ffffff; border: 1px solid #e1e1e1; border-top: none;">
            
            <p style="color: #636e72; font-size: 14px; margin-bottom: 25px; text-align: center; line-height: 1.5; background: #f1f2f6; padding: 10px; border-radius: 8px;">
                I will continue scanning these companies for you.<br>
                You'll receive an email only when a new matching position pops up! 🕵️‍♂️
            </p>

    """
    
    sorted_categories = sorted(jobs_by_category.keys())

    for cat in sorted_categories:
        cat_color = "#6c5ce7"
        if cat == "Engineering": cat_color = "#e17055"
        elif cat == "Marketing": cat_color = "#00b894"
        elif cat == "Finance": cat_color = "#0984e3"

        html_body += f"""
        <div style="margin-top: 25px; margin-bottom: 10px; padding-bottom: 5px; border-bottom: 2px solid {cat_color};">
            <h3 style="margin: 0; color: {cat_color}; text-transform: uppercase; font-size: 16px; letter-spacing: 1px;">
                {cat} ({len(jobs_by_category[cat])})
            </h3>
        </div>
        <ul style="padding: 0; list-style: none;">
        """
        
        for job in jobs_by_category[cat]:
            html_body += f"""
            <li style="margin-bottom: 12px; padding: 12px; background: #f8f9fa; border-radius: 8px; border-left: 3px solid {cat_color};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <a href="{job['link']}" style="font-weight: bold; color: #2d3436; text-decoration: none; font-size: 15px; display: block; margin-bottom: 4px;">
                            {job['title']}
                        </a>
                        <div style="font-size: 12px; color: #636e72;">
                            {job['company']}
                        </div>
                    </div>
                </div>
            </li>
            """
        html_body += "</ul>"
    
    html_body += """
            <div style="margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px; text-align: center; color: #b2bec3; font-size: 12px;">
                <p>Now you can play matkot on the beach 🏖️ while I'm finding jobs for you 😎</p>
                <p style="font-weight: bold; margin-top: 5px;">— Career Agent 🤖</p>
            </div>
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
                "subject": f"🔥 {total_jobs} New Jobs Found!",
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
        region_pref = user.get('region_preference', 'Other') 
        
        user_companies = database.get_companies_by_user(email)
        user_company_ids = [c['id'] for c in user_companies]
        
        jobs_to_send = []
        for c_id in user_company_ids:
            current_jobs = jobs_by_company.get(c_id, [])
            for job in current_jobs:
                if region_pref == 'Israel':
                    title_lower = job['title'].lower()
                    link_lower = job['link'].lower()
                    is_blocked_location = any(b in title_lower or b in link_lower for b in BLOCK_LOCATIONS)
                    if is_blocked_location:
                        continue 
                
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
        return
    is_scraping = True
    try:
        await run_scraper_engine()
    finally:
        is_scraping = False