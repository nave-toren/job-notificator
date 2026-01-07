import asyncio
import ssl
from playwright.async_api import async_playwright
import database
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

# הגדרות SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("EMAIL_USER")
SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD")
DISPLAY_NAME = "Job Hunter Bot 🤖"

# מילות מפתח לסינון קטגוריות
CATEGORY_KEYWORDS = {
    "Engineering": ['engineer', 'developer', 'r&d', 'data', 'algorithm', 'architect', 'full stack', 'backend', 'frontend', 'mobile', 'devops', 'software', 'qa', 'cyber'],
    "Product": ['product', 'design', 'ux', 'ui', 'creative', 'head of product'],
    "Marketing": ['marketing', 'sales', 'account', 'business', 'sdr', 'bdr', 'content', 'seo', 'ppc', 'growth'],
    "Finance": ['finance', 'legal', 'accountant', 'bookkeeper', 'controller', 'payroll', 'attorney', 'counsel', 'economist'],
    "HR": ['hr', 'human resources', 'recruiter', 'talent', 'people', 'admin', 'office', 'operations'],
    "Support": ['support', 'customer', 'success', 'service', 'helpdesk', 'tier']
}

JUNK_KEYWORDS = [
    'privacy', 'policy', 'terms', 'cookie', 'login', 'signin', 'signup', 'forgot', 'blog', 'news', 
    'press', 'about us', 'contact', 'facebook', 'twitter', 'linkedin', 'instagram', 'investor'
]

def classify_job(title):
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return category
    return "Other"

async def send_email(to_email, user_interests, jobs_list, is_first_email=False):
    """ שולח מייל עם רשימת המשרות שנמצאו עבור המשתמש """
    if not jobs_list:
        return

    # סינון לפי קטגוריות שהמשתמש בחר
    user_interest_list = user_interests.split(',') if user_interests else []
    relevant_jobs = []

    for job in jobs_list:
        cat = classify_job(job['title'])
        # אם המשתמש לא בחר כלום, או שהקטגוריה ברשימה שלו
        if not user_interest_list or user_interest_list == [''] or cat in user_interest_list:
            relevant_jobs.append(job)
            
    if not relevant_jobs:
        return

    # כותרת המייל
    title_text = "👋 Welcome! Here are ALL open positions for you" if is_first_email else "🚀 New Jobs Found!"
    
    # בניית גוף המייל
    jobs_html = "<ul style='padding: 0; list-style-type: none;'>"
    for job in relevant_jobs:
        jobs_html += f"""
        <li style="margin-bottom: 12px; padding: 10px; border-left: 4px solid #ff7e5f; background: #f9f9f9; border-radius: 4px;">
            <a href='{job['link']}' style='font-weight: bold; text-decoration: none; color: #0984e3; font-size: 16px;'>{job['title']}</a>
            <div style="font-size: 13px; color: #555; margin-top: 4px;">🏢 <strong>{job['company']}</strong></div>
        </li>
        """
    jobs_html += "</ul>"

    body = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; max-width: 600px; margin: auto; border: 1px solid #eee; border-radius: 8px;">
        <h2 style="color: #2d3436; text-align: center;">{title_text}</h2>
        <p style="text-align: center; color: #666;">Showing {len(relevant_jobs)} jobs matching your interests.</p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        {jobs_html}
        <p style="font-size: 12px; color: #999; margin-top: 30px; text-align: center;">Job Hunter Bot 🤖 | Built by Nave Toren</p>
    </div>
    """

    msg = MIMEMultipart()
    msg['From'] = f"{DISPLAY_NAME} <{SENDER_EMAIL}>"
    msg['To'] = to_email
    msg['Subject'] = f"🎯 {len(relevant_jobs)} Opportunities found for you!"
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"📧 Sent email to {to_email}")
    except Exception as e:
        print(f"❌ Email failed to {to_email}: {e}")




async def send_email(to_email, user_interests, jobs_list, is_first_email=False):
    """ שולח מייל עם רשימת המשרות - גרסה משולבת (עיצוב + תיקון SSL) """
    
    # 1. סינון לפי קטגוריות (שמרנו מהקוד המקורי שלך)
    if not jobs_list:
        return False

    user_interest_list = user_interests.split(',') if user_interests else []
    relevant_jobs = []

    # אם זה המייל הראשון - שולחים הכל. אם לא - מסננים לפי תחומי עניין.
    if is_first_email:
        relevant_jobs = jobs_list
    else:
        for job in jobs_list:
            # נניח ש-classify_job מוגדרת אצלך בקובץ
            cat = classify_job(job['title']) 
            if not user_interest_list or user_interest_list == [''] or cat in user_interest_list:
                relevant_jobs.append(job)
            
    if not relevant_jobs:
        print(f"   ℹ️ No relevant jobs for {to_email} after filtering.")
        return False

    # 2. בניית המייל והעיצוב (שמרנו את העיצוב היפה שלך)
    sender_email = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    
    if not sender_email or not password:
        print("❌ Email credentials missing!")
        return False

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    
    title_text = "👋 Welcome! Here are ALL open positions for you" if is_first_email else "🚀 New Jobs Found!"
    msg['Subject'] = f"{title_text} ({len(relevant_jobs)})"

    # גוף המייל המעוצב
    html_body = f"""
    <div style="font-family: Arial, sans-serif; direction: ltr;">
        <h2>{title_text}</h2>
        <p>We found {len(relevant_jobs)} jobs matching your interests: <b>{user_interests}</b></p>
        <ul style='padding: 0; list-style-type: none;'>
    """
    
    for job in relevant_jobs:
        html_body += f"""
        <li style="margin-bottom: 12px; padding: 10px; border-left: 4px solid #ff7e5f; background: #f9f9f9; border-radius: 4px;">
            <a href='{job['link']}' style='font-weight: bold; text-decoration: none; color: #0984e3; font-size: 16px;'>{job['title']}</a>
            <div style="font-size: 13px; color: #555; margin-top: 4px;">🏢 <strong>{job['company']}</strong></div>
        </li>
        """
    html_body += "</ul><p>Good luck! <br> Job Hunter Bot 🤖</p></div>"
    
    msg.attach(MIMEText(html_body, 'html'))

    # 3. החלק החדש והקריטי - שליחה דרך SSL (פותר את ה-Network Unreachable)
    try:
        context = ssl.create_default_context()
        # שימוש בפורט 465 המאובטח
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, to_email, msg.as_string())
        
        print(f"✅ Email sent successfully to {to_email}")
        return True

    except Exception as e:
        print(f"❌ Email failed to {to_email}: {e}")
        return False

async def scrape_company(page, company_row):
    """ סורק חברה ומחזיר את כל המשרות שנמצאו בה כרגע - גרסה עמידה לקריסות """
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']
    
    print(f"🔎 Scanning {name}...")
    found_jobs = []

    try:
        print(f"   ⏳ Navigating to {url}...")
        
        # 1. לא מחכים ל-load מלא, אלא רק לטקסט ראשוני
        await page.goto(url, timeout=60000, wait_until='domcontentloaded')
        
        # 2. גלילה הדרגתית כדי להעיר את האתר
        for _ in range(3): 
            await page.keyboard.press("PageDown")
            await asyncio.sleep(1) 
            
        # 3. המתנה קצרה אחרונה
        print("   💤 Waiting for content to render...")
        await asyncio.sleep(3)

        links = await page.query_selector_all('a')
        seen_links = set()

        for link in links:
            try:
                txt = await link.inner_text()
                href = await link.get_attribute('href')
                
                if txt and href and len(txt) > 3:
                    txt_lower = txt.lower()
                    # (הנחתי שיש לך משתנה גלובלי JUNK_KEYWORDS מוגדר למעלה)
                    # אם לא, תמחק את השורה הבאה או תוסיף: JUNK_KEYWORDS = ['login', 'privacy', 'terms']
                    if 'JUNK_KEYWORDS' in globals() and any(junk in txt_lower for junk in JUNK_KEYWORDS): continue
                    
                    full_link = href if href.startswith('http') else url.rstrip('/') + href
                    
                    if full_link not in seen_links:
                        seen_links.add(full_link)
                        found_jobs.append({
                            'company_id': c_id,
                            'company': name,
                            'title': txt.strip(),
                            'link': full_link
                        })
            except:
                continue 
                
    except Exception as e:
        print(f"❌ Error scanning {name}: {e}")
        
    print(f"   ✅ Found {len(found_jobs)} jobs at {name}")
    return found_jobs

async def run_scraper_engine():
    print("🚀 Starting Smart Scraper...")
    
    companies = database.get_all_companies_for_scan()
    users = database.get_users()
    
    if not companies:
        print("😴 No companies to scan.")
        return

    # מילון לאחסון כל המשרות החיות שנמצאו בסריקה הזו
    jobs_by_company = {}
    
    # סט לשמירת לינקים שהם חדשים גלובלית
    globally_new_links = set()

    # --- שלב 1: איסוף כל המשרות מהשטח ---
    async with async_playwright() as p:
        # === כאן השינוי הגדול: מצב חיסכון בזיכרון ===
        print("   🔨 Launching Browser in low-memory mode...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage', # מציל את הזיכרון!
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu'
            ]
        )
        print("   ✅ Browser launched successfully!")
        
        page = await browser.new_page()
        
        for company in companies:
            c_id = company['id']
            jobs = await scrape_company(page, company)
            jobs_by_company[c_id] = jobs
            
            # בדיקה האם המשרות חדשות ב-DB
            for job in jobs:
                if not database.job_exists(job['link']):
                    database.add_job(c_id, job['title'], job['link'])
                    globally_new_links.add(job['link'])
        
        await browser.close()

    # --- שלב 2: הפצת מיילים מותאמת אישית ---
    print(f"\n📨 Processing emails for {len(users)} users...")
    
    for user in users:
        email = user['email']
        is_new_user = user.get('is_new_user', False)
        interests = user['interests']
        
        user_companies = database.get_companies_by_user(email)
        user_company_ids = [c['id'] for c in user_companies]
        
        jobs_to_send = []
        
        for c_id in user_company_ids:
            company_jobs = jobs_by_company.get(c_id, [])
            
            for job in company_jobs:
                if is_new_user:
                    jobs_to_send.append(job)
                else:
                    if job['link'] in globally_new_links:
                        jobs_to_send.append(job)
        
        if jobs_to_send:
            await send_email(email, interests, jobs_to_send, is_first_email=is_new_user)
            
            if is_new_user:
                database.mark_user_as_not_new(email)
                print(f"✅ User {email} welcomed and marked as regular.")
        else:
            print(f"🤷‍♂️ No relevant updates for {email}")

    print("🏁 Scraper finished successfully.")