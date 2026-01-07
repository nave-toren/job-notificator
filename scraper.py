import asyncio
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import database

# טעינת משתני סביבה
load_dotenv()

# --- הגדרות וקבועים ---

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
    """ מסווג משרה לקטגוריה לפי הכותרת """
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return category
    return "Other"

# --- פונקציית המייל (החלק שתוקן) ---
async def send_email(to_email, user_interests, jobs_list, is_first_email=False):
    """ שולח מייל בשיטה המותאמת לשרתים (Port 587 STARTTLS) """
    
    # 1. בדיקה שיש תוכן לשלוח
    if not jobs_list:
        return False

    # 2. סינון משרות
    user_interest_list = user_interests.split(',') if user_interests else []
    relevant_jobs = []

    if is_first_email:
        relevant_jobs = jobs_list
    else:
        for job in jobs_list:
            cat = classify_job(job['title']) 
            if not user_interest_list or user_interest_list == [''] or cat in user_interest_list:
                relevant_jobs.append(job)
            
    if not relevant_jobs:
        print(f"   ℹ️ No relevant jobs for {to_email} after filtering.")
        return False

    # 3. התחברות לשרת המייל
    sender_email = os.getenv("EMAIL_ADDRESS") or os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")
    
    if not sender_email or not password:
        print("❌ Error: Email credentials missing in environment variables.")
        return False

    # 4. בניית ההודעה
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    
    title_text = "👋 Welcome! Here are ALL open positions for you" if is_first_email else "🚀 New Jobs Found!"
    msg['Subject'] = f"{title_text} ({len(relevant_jobs)})"

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

    # 5. שליחה (התיקון: מעבר ל-TLS בפורט 587)
    try:
        print(f"   🔌 Connecting to Gmail (Port 587 TLS)...")
        
        # שינוי: שימוש ב-SMTP רגיל (לא SSL) בפורט 587
        server = smtplib.SMTP('smtp.gmail.com', 587)
        
        # שינוי: פקודה קריטית שמשדרגת את השיחה למוצפנת
        server.starttls()
        
        server.login(sender_email, password)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email sent successfully to {to_email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {e}")
        return False

# --- פונקציית הסריקה ---
async def scrape_company(page, company_row):
    """ סורק חברה ומחזיר את כל המשרות שנמצאו בה כרגע """
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']
    
    print(f"🔎 Scanning {name}...")
    found_jobs = []

    try:
        print(f"   ⏳ Navigating to {url}...")
        # שימוש ב-domcontentloaded למניעת תקיעות
        await page.goto(url, timeout=60000, wait_until='domcontentloaded')
        
        # גלילה להעיר את האתר
        for _ in range(3): 
            await page.keyboard.press("PageDown")
            await asyncio.sleep(1) 
            
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
                    if any(junk in txt_lower for junk in JUNK_KEYWORDS): continue
                    
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

# --- המנוע הראשי ---
async def run_scraper_engine():
    print("🚀 Starting Smart Scraper MVP...")
    
    companies = database.get_all_companies_for_scan()
    users = database.get_users()
    
    if not companies:
        print("😴 No companies to scan.")
        return

    jobs_by_company = {}
    globally_new_links = set()

    # שלב 1: סריקה
    async with async_playwright() as p:
        print("   🔨 Launching Browser (Low Memory)...")
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
        
        for company in companies:
            c_id = company['id']
            jobs = await scrape_company(page, company)
            jobs_by_company[c_id] = jobs
            
            for job in jobs:
                if not database.job_exists(job['link']):
                    database.add_job(c_id, job['title'], job['link'])
                    globally_new_links.add(job['link'])
        
        await browser.close()

    # שלב 2: שליחת מיילים
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
            success = await send_email(email, interests, jobs_to_send, is_first_email=is_new_user)
            
            if success and is_new_user:
                database.mark_user_as_not_new(email)
                print(f"✅ User {email} marked as regular.")
        else:
            print(f"🤷‍♂️ No relevant updates for {email}")

    print("🏁 Scraper finished successfully.")