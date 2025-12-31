import asyncio
from playwright.async_api import async_playwright
import database
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("EMAIL_USER")
SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD")
DISPLAY_NAME = "Job Hunter Bot 🤖"

# --- מילות מפתח לסיווג ---
CATEGORY_KEYWORDS = {
    "Engineering": ['engineer', 'developer', 'r&d', 'data', 'algorithm', 'architect', 'full stack', 'backend', 'frontend', 'mobile', 'devops'],
    "Product": ['product', 'design', 'ux', 'ui', 'creative', 'art director'],
    "Marketing": ['marketing', 'sales', 'account', 'business development', 'sdr', 'bdr', 'content', 'seo', 'ppc'],
    "Finance": ['finance', 'legal', 'accountant', 'bookkeeper', 'controller', 'payroll', 'attorney', 'counsel'],
    "HR": ['hr', 'human resources', 'recruiter', 'talent', 'people', 'admin', 'office manager', 'operations'],
    "Support": ['support', 'customer', 'success', 'service', 'helpdesk', 'qa', 'quality', 'tier']
}

def classify_job(title):
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return category
    return "Other"

async def send_email(to_email, user_interests, new_jobs):
    if not new_jobs:
        return

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("❌ CRITICAL: Missing EMAIL keys in .env")
        return

    # המרת מחרוזת האינטרסים לרשימה
    user_interest_list = user_interests.split(',') if user_interests else []
    
    # מיון המשרות לפי קטגוריות
    grouped_jobs = {cat: [] for cat in CATEGORY_KEYWORDS.keys()}
    grouped_jobs["Other"] = []

    jobs_count_for_user = 0

    for job in new_jobs:
        category = classify_job(job['title'])
        
        # לוגיקת סינון: מציגים אם המשתמש בחר את הקטגוריה, או אם לא בחר כלום (מראה הכל)
        is_relevant = False
        if not user_interest_list: 
            is_relevant = True
        elif category in user_interest_list:
            is_relevant = True
        elif category == "Other" and "Other" in user_interest_list: # אופציונלי
            is_relevant = True
            
        if is_relevant:
             grouped_jobs[category].append(job)
             jobs_count_for_user += 1

    if jobs_count_for_user == 0:
        return # אין משרות שרלוונטיות למשתמש הזה

    # --- בניית ה-HTML ---
    subject = f"🚀 {jobs_count_for_user} New Jobs Found For You!"
    
    jobs_html = ""
    for cat_name, jobs in grouped_jobs.items():
        if jobs:
            jobs_html += f"""
            <div style="margin-top: 25px; margin-bottom: 10px;">
                <h3 style="color: #2d3436; border-bottom: 2px solid #ff7e5f; display: inline-block; padding-bottom: 3px; margin: 0;">
                    {cat_name}
                </h3>
            </div>
            <ul style="list-style-type: none; padding: 0;">
            """
            for job in jobs:
                jobs_html += f"""
                <li style="margin-bottom: 10px; padding-left: 10px; border-left: 3px solid #dfe6e9; background: #fdfdfd; padding: 8px;">
                    <a href='{job['link']}' style='color: #0984e3; text-decoration: none; font-weight: bold; font-size: 16px; display: block;'>{job['title']}</a>
                    <div style="font-size: 13px; color: #636e72; margin-top: 3px;">at {job['company']}</div>
                </li>
                """
            jobs_html += "</ul>"

    body = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; border: 1px solid #eee; box-shadow: 0 5px 15px rgba(0,0,0,0.05);">
        <h2 style="color: #2d3436; text-align: center; margin-top: 0;">We found new opportunities!</h2>
        <p style="text-align: center; color: #636e72;">Based on your preferences: <strong>{user_interests if user_interests else 'All Categories'}</strong></p>
        
        {jobs_html}
        
        <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
        
        <p style="font-size: 14px; color: #555; line-height: 1.6; text-align: center; font-style: italic; background: #f1f2f6; padding: 15px; border-radius: 8px;">
            "Our bot never sleeps! 🤖 It keeps hunting for jobs 24/7 so you can go play 
            <strong>Matkot at the beach</strong> 🏖️ or do something fun."
        </p>
        
        <div style="margin-top: 30px; font-size: 12px; color: #999; text-align: center;">
            Created by <strong>Nave Toren</strong> | Job Hunter Bot
        </div>
    </div>
    """

    msg = MIMEMultipart()
    msg['From'] = f"{DISPLAY_NAME} <{SENDER_EMAIL}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"📧 Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

async def scrape_company(page, company_row):
    c_id = company_row['id']
    name = company_row['name']
    url = company_row['careers_url']
    
    print(f"\n🔎 Scanning {name}...")

    try:
        await page.goto(url, timeout=60000)
        try:
            await page.wait_for_load_state('networkidle', timeout=10000)
        except:
            pass 
        
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        jobs = []
        links = await page.query_selector_all('a')
        
        for link in links:
            txt = await link.inner_text()
            href = await link.get_attribute('href')
            
            if txt and href and len(txt) > 3:
                # רשימת מילות מפתח מורחבת לתפיסה רחבה של משרות
                keywords = ['engineer', 'developer', 'data', 'manager', 'specialist', 'student', 'support', 'qa', 'analyst', 'lead', 'head', 'product', 'designer', 'finance', 'accountant', 'hr', 'recruiter', 'sales', 'officer', 'coordinator']
                if any(k in txt.lower() for k in keywords):
                    full_link = href if href.startswith('http') else url.rstrip('/') + href
                    
                    jobs.append({
                        'company_id': c_id,
                        'company': name,
                        'title': txt.strip(),
                        'link': full_link
                    })

        print(f"   ✅ Found {len(jobs)} potential links at {name}.")
        return jobs

    except Exception as e:
        print(f"   ❌ Error scanning {name}: {e}")
        return []

async def run_scraper_engine():
    print("🚀 Starting Job Scraper...")
    
    # --- התיקון כאן: הוספנו "companies =" בהתחלה ---
    companies = database.get_all_companies_for_scan()
    users = database.get_users()

    if not companies:
        print("😴 No companies to scan.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        all_new_jobs_for_report = []

        for company in companies:
            found_jobs = await scrape_company(page, company)
            
            for job in found_jobs:
                if not database.job_exists(job['link']):
                    print(f"   ✨ NEW: {job['title']}")
                    database.add_job(job['company_id'], job['title'], job['link'])
                    all_new_jobs_for_report.append(job)
        
        await browser.close()

    # שליחת מיילים
    if all_new_jobs_for_report and users:
        print(f"\n📨 Processing emails for {len(users)} subscribers...")
        # כאן צריך לוודא ששולחים למשתמש רק את המשרות של החברות שלו
        # כרגע הקוד שולח את *כל* המשרות החדשות לכל המשתמשים.
        # לגרסת בטא זה בסדר, אבל בעתיד נרצה לסנן גם כאן.
        for user_row in users:
            email = user_row['email']
            interests = user_row['interests']
            await send_email(email, interests, all_new_jobs_for_report)
    else:
        print("\n😴 No new jobs found this cycle.")