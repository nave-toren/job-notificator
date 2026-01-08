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

# ================== CLASSIFICATION ==================

CATEGORY_KEYWORDS = {
    "Engineering": [
        'engineer', 'developer', 'r&d', 'data', 'algorithm', 'architect',
        'full stack', 'backend', 'frontend', 'mobile', 'devops', 'software', 'qa', 'cyber', 'security', 'it '
    ],
    "Product": ['product', 'design', 'ux', 'ui', 'creative', 'graphic', 'art director'],
    "Marketing": ['marketing', 'sales', 'account', 'business', 'sdr', 'bdr', 'content', 'seo', 'ppc', 'growth', 'social', 'brand'],
    "Finance": ['finance', 'accountant', 'controller', 'payroll', 'fp&a', 'legal', 'compliance', 'economist', 'bookkeeper'],
    "HR": ['hr', 'recruiter', 'talent', 'people', 'office', 'admin', 'operations', 'welfare'],
    "Support": ['support', 'customer', 'success', 'service', 'helpdesk', 'tier']
}

def classify_job(title):
    t = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        # בדיקה מדויקת יותר כדי למנוע False Positives
        if any(f" {k} " in f" {t} " or t.startswith(k) or t.endswith(k) for k in keywords):
            return category
    return "Other"

# ================== GENERIC SCRAPER IMPROVED ==================

# מילות מפתח חזקות - חייבות להופיע בכותרת או בלינק
JOB_STRONG_KEYWORDS = [
    'engineer', 'developer', 'manager', 'specialist', 'lead', 'director',
    'analyst', 'designer', 'qa', 'support', 'intern', 'product', 'marketing',
    'finance', 'accountant', 'recruiter', 'hr', 'operations', 'admin', 'counsel',
    'architect', 'consultant', 'coordinator', 'head of', 'vp', 'officer'
]

# מילות מפתח שמופיעות ב-URL של משרות
JOB_URL_INDICATORS = ['/job', '/career', '/position', '/opening', '/apply', '/role', '/vacancy', 'greenhouse', 'lever', 'comeet']

# מילים שאנחנו ממש לא רוצים (סינון רעשים)
JUNK_KEYWORDS = [
    'privacy', 'policy', 'terms', 'cookie', 'login', 'sign in', 'sign up', 'register', 'forgot',
    'blog', 'news', 'press', 'about', 'contact', 'facebook', 'twitter', 'linkedin', 'instagram', 
    'investor', 'read more', 'learn more', 'home', 'accessibility', 'sitemap', 'share', 'print'
]

async def scrape_generic(page, company_row):
    """
    סקראפר חכם יותר:
    1. מתעלם מ-Nav/Footer
    2. משתמש ב-urljoin לתיקון לינקים
    3. בודק הקשר (Context)
    """
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🟡 Using SMART generic scraper for {name}")
    found_jobs = []

    try:
        # שינוי ל-networkidle: מחכה שהרשת תירגע (טוב לאתרים כבדים כמו Base44)
        try:
            await page.goto(url, timeout=60000, wait_until='networkidle')
        except:
            # Fallback אם networkidle נתקע
            await asyncio.sleep(5)
        
        await asyncio.sleep(3) # אקסטרה זמן לרינדור JS

        # אסטרטגיה 1: לחפש לינקים רק בתוך אזור ה-Main אם קיים, כדי להימנע מ-Header/Footer
        # ננסה למצוא אלמנטים שמכילים את המשרות
        job_links = await page.evaluate('''() => {
            const anchors = Array.from(document.querySelectorAll('a'));
            return anchors.map(a => {
                // בדיקה אם האלמנט נמצא בתוך Header או Footer
                const closestNav = a.closest('nav, header, footer, .footer, .header, .cookie-banner');
                if (closestNav) return null;

                return {
                    text: a.innerText.trim(),
                    href: a.getAttribute('href'),
                    isVisible: (a.offsetWidth > 0 && a.offsetHeight > 0) // סינון אלמנטים מוסתרים
                };
            }).filter(item => item !== null && item.href !== null && item.text.length > 3);
        }''')

        seen = set()

        for link_obj in job_links:
            txt = link_obj['text']
            raw_href = link_obj['href']
            
            # --- שלב 1: ניקוי ותיקון URL (פותר את הבעיה של Artlist) ---
            full_link = urljoin(url, raw_href)
            
            # בדיקה שהלינק הוא לא סתם עוגן (#) או mailto
            if "javascript:" in full_link or "mailto:" in full_link or full_link == url:
                continue

            txt_lower = txt.lower()
            
            # --- שלב 2: סינון רעשים אגרסיבי (פותר את הבעיה של Earnix) ---
            if any(junk in txt_lower for junk in JUNK_KEYWORDS):
                continue
            
            # כותרות ארוכות מדי הן בדרך כלל שמות של מאמרים בבלוג
            if len(txt) > 100: 
                continue

            # --- שלב 3: בדיקת רלוונטיות ---
            # האם הטקסט מכיל תפקיד, או שהלינק נראה כמו משרה?
            is_title_match = any(k in txt_lower for k in JOB_STRONG_KEYWORDS)
            is_url_match = any(k in full_link.lower() for k in JOB_URL_INDICATORS)
            
            # אם אין התאמה לא בטקסט ולא ב-URL - דלג
            if not (is_title_match or is_url_match):
                continue

            if full_link in seen:
                continue

            seen.add(full_link)

            found_jobs.append({
                "company_id": c_id,
                "company": name,
                "title": txt,
                "link": full_link
            })

    except Exception as e:
        print(f"❌ Generic scrape error for {name}: {e}")

    print(f"   ✅ Generic found {len(found_jobs)} jobs at {name}")
    return found_jobs

# ================== SPECIALIZED SCRAPERS (Improved) ==================

async def scrape_greenhouse(page, company_row):
    """ תומך כעת גם ב-Iframes """
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🟢 Using Greenhouse scraper for {name}")
    found_jobs = []

    try:
        await page.goto(url, timeout=60000, wait_until='networkidle')
        await asyncio.sleep(2)

        # נסיון 1: חיפוש רגיל בעמוד
        job_cards = await page.query_selector_all("div.opening a, td.cell a")
        
        # נסיון 2: אם לא מצאנו, אולי זה בתוך Iframe? (נפוץ מאוד)
        if not job_cards:
            print("      ...Looking inside iframes")
            for frame in page.frames:
                try:
                    iframe_cards = await frame.query_selector_all("div.opening a, td.cell a")
                    if iframe_cards:
                        job_cards = iframe_cards
                        break
                except: continue

        for card in job_cards:
            title = (await card.inner_text()).strip()
            href = await card.get_attribute("href")
            if not title or not href: continue
            
            full = urljoin("https://boards.greenhouse.io", href)
            found_jobs.append({"company_id": c_id, "company": name, "title": title, "link": full})

    except Exception as e:
        print(f"❌ Greenhouse error: {e}")

    print(f"   ✅ Greenhouse found {len(found_jobs)} jobs")
    return found_jobs

async def scrape_lever(page, company_row):
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🟣 Using Lever scraper for {name}")
    found_jobs = []

    try:
        await page.goto(url, timeout=60000, wait_until='networkidle')
        await asyncio.sleep(2)

        job_cards = await page.query_selector_all("a.posting-title")
        
        for card in job_cards:
            title_elem = await card.query_selector("h5") # Lever structure often has h5 inside anchor
            title = (await title_elem.inner_text()).strip() if title_elem else (await card.inner_text()).strip()
            href = await card.get_attribute("href")

            if title and href:
                found_jobs.append({"company_id": c_id, "company": name, "title": title, "link": href})

    except Exception as e:
        print(f"❌ Lever error: {e}")

    print(f"   ✅ Lever found {len(found_jobs)} jobs")
    return found_jobs

async def scrape_comeet(page, company_row):
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🔵 Using Comeet scraper for {name}")
    found_jobs = []

    try:
        await page.goto(url, timeout=60000, wait_until='networkidle') # חשוב ל-Comeet
        await asyncio.sleep(4) # Comeet איטי בטעינה

        # Comeet לפעמים משתמש ב-Script שמזריק תוכן
        job_cards = await page.query_selector_all("a[data-position-id], .comeet-position-link a, a.comeet-position")

        if not job_cards:
             # נסיון בתוך Iframe
            for frame in page.frames:
                try:
                    iframe_cards = await frame.query_selector_all("a[data-position-id]")
                    if iframe_cards:
                        job_cards = iframe_cards
                        break
                except: continue

        for card in job_cards:
            title = (await card.inner_text()).strip()
            href = await card.get_attribute("href")
            
            if title and href:
                # Comeet links can be relative or full
                full = urljoin(url, href)
                found_jobs.append({"company_id": c_id, "company": name, "title": title, "link": full})

    except Exception as e:
        print(f"❌ Comeet error: {e}")

    print(f"   ✅ Comeet found {len(found_jobs)} jobs")
    return found_jobs

# ================== DISPATCHER ==================

async def scrape_company(page, company_row):
    url = company_row['careers_url'].lower()
    
    # זיהוי חכם יותר של פלטפורמות גם אם ה-URL הוא דומיין פרטי
    # (לפעמים החברה מפנה ל-jobs.company.com אבל זה בעצם Greenhouse)
    
    if "greenhouse.io" in url:
        return await scrape_greenhouse(page, company_row)
    elif "lever.co" in url:
        return await scrape_lever(page, company_row)
    elif "comeet" in url:
        return await scrape_comeet(page, company_row)
    
    # אם לא זוהה ב-URL, ננסה לראות אם יש הפניה (Redirect)
    # אבל כרגע נשאיר את זה פשוט ונשלח לגנרי החכם
    else:
        return await scrape_generic(page, company_row)

# ================== EMAIL (RESEND) ==================

async def send_email(to_email, user_interests, jobs_list):
    if not jobs_list:
        return False

    user_interest_list = user_interests.split(',') if user_interests else []
    relevant_jobs = []

    for job in jobs_list:
        cat = classify_job(job['title'])
        # סינון חכם: אם המשתמש לא בחר כלום - שלח הכל. אחרת, רק מה שהתאים.
        if not user_interest_list or cat in user_interest_list:
            relevant_jobs.append(job)

    if not relevant_jobs:
        return False

    # עיצוב המייל נשאר זהה אך עם כותרת משופרת
    html_body = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
        <div style="background: linear-gradient(135deg, #6c5ce7, #a29bfe); padding: 20px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">🎯 Fresh Opportunities Found!</h1>
            <p style="color: #dfe6e9; margin-top: 5px;">Career Agent Update</p>
        </div>
        
        <div style="padding: 20px; background: #ffffff; border: 1px solid #e1e1e1; border-top: none;">
            <p>Hey there! We found <b>{len(relevant_jobs)}</b> new positions matching your criteria: <b>{user_interests if user_interests else 'All Categories'}</b></p>
            
            <ul style="padding: 0; list-style-type: none;">
    """

    for job in relevant_jobs:
        # צבעים לפי קטגוריות
        border_color = "#0984e3" # default blue
        cat = classify_job(job['title'])
        if cat == 'Engineering': border_color = "#e17055" # red/orange
        elif cat == 'Product': border_color = "#6c5ce7" # purple
        elif cat == 'Marketing': border_color = "#00b894" # green

        html_body += f"""
        <li style="margin-bottom:15px; padding:12px; border-left:4px solid {border_color}; background:#f8f9fa; border-radius: 0 8px 8px 0;">
            <div style="font-size: 12px; color: #636e72; text-transform: uppercase; margin-bottom: 4px;">{cat} @ {job['company']}</div>
            <a href="{job['link']}" style="font-weight:bold; color:#2d3436; text-decoration:none; font-size: 16px; display: block;">
                {job['title']} <span style="float: right;">👉</span>
            </a>
        </li>
        """

    html_body += """
            </ul>
            <div style="text-align: center; margin-top: 30px; font-size: 12px; color: #b2bec3;">
                Generated by Career Agent Bot 🤖 <br>
                <a href="#" style="color: #b2bec3;">Unsubscribe</a>
            </div>
        </div>
    </div>
    """

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("❌ RESEND_API_KEY missing.")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "from": "Career Agent <onboarding@resend.dev>",
        "to": [to_email],
        "subject": f"🔥 {len(relevant_jobs)} New Jobs: {relevant_jobs[0]['company']} and more...",
        "html": html_body
    }

    try:
        r = requests.post("https://api.resend.com/emails", json=payload, headers=headers)
        if r.status_code >= 400:
            print(f"❌ Resend error: {r.text}")
            return False
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

# ================== ENGINE ==================

async def run_scraper_engine():
    print("🚀 Starting Smart Scraper (v2.0 Refined)...")

    companies = database.get_all_companies_for_scan()
    users = database.get_users()

    if not companies:
        print("😴 No companies to scan.")
        return

    jobs_by_company = {}
    globally_new_links = set()

    async with async_playwright() as p:
        print("   🔨 Launching Browser...")
        # הרצה עם דגלים לאופטימיזציה ב-Render/Server
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote', 
                '--single-process', 
                '--disable-gpu'
            ]
        )

        page = await browser.new_page()
        # User Agent אמיתי כדי למנוע חסימות בוטים פשוטות
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})

        for company in companies:
            c_id = company['id']
            try:
                jobs = await scrape_company(page, company)
            except Exception as e:
                print(f"⚠️ Critical error scanning {company['name']}: {e}")
                jobs = []
            
            jobs_by_company[c_id] = jobs

            for job in jobs:
                if not database.job_exists(job['link']):
                    database.add_job(c_id, job['title'], job['link'])
                    globally_new_links.add(job['link'])

        await browser.close()

    print(f"\n📨 Processing emails for {len(users)} users...")

    for user in users:
        email = user['email']
        interests = user['interests'] # e.g "Engineering,Product"
        is_new_user = user.get('is_new_user', False)

        user_companies = database.get_companies_by_user(email)
        user_company_ids = [c['id'] for c in user_companies]

        jobs_to_send = []

        for c_id in user_company_ids:
            current_jobs = jobs_by_company.get(c_id, [])
            for job in current_jobs:
                # אם המשתמש חדש - שלח הכל. אם ותיק - רק משרות שלא היו ב-DB לפני הריצה הזו
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

# ================== LOCK WRAPPER ==================

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