import asyncio
import sqlite3
from datetime import datetime
from playwright.async_api import async_playwright
import database
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- CONFIGURATION (כמו שביקשת) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("EMAIL_USER")
SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD")
DISPLAY_NAME = "Job Seeker 🔍"

async def send_email(to_email, new_jobs):
    if not new_jobs:
        return

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("❌ CRITICAL: Missing EMAIL_USER or EMAIL_PASSWORD in environment variables.")
        return

    subject = f"🚀 {len(new_jobs)} New Jobs Found!"
    
    body = "<h3>New positions found matching your interests:</h3><ul>"
    for job in new_jobs:
        body += f"<li><a href='{job['link']}'><strong>{job['title']}</strong></a> at {job['company']}</li>"
    body += "</ul><p>Good luck! 🤘</p>"

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
        print(f"📧 Email sent successfully to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

async def scrape_company(page, company):
    # company tuple: (id, name, url)
    url = company[2]
    name = company[1]
    print(f"\n🔎 Scanning {name} ({url})...")

    try:
        await page.goto(url, timeout=60000)
        try:
            await page.wait_for_load_state('networkidle', timeout=10000)
        except:
            pass 
        
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        jobs = []

        # --- Earnix / Comeet ---
        comeet_jobs = await page.query_selector_all('a[href*="comeet.com"], .positionItem a')
        if comeet_jobs:
            print(f"   Detected Comeet structure for {name}")
            for job in comeet_jobs:
                title = await job.inner_text()
                link = await job.get_attribute('href')
                if title and link:
                    jobs.append({'title': title.strip(), 'link': link, 'company': name})

        # --- Greenhouse ---
        elif await page.query_selector('.opening'):
            print(f"   Detected Greenhouse structure for {name}")
            greenhouse_jobs = await page.query_selector_all('.opening a')
            for job in greenhouse_jobs:
                title = await job.inner_text()
                link = await job.get_attribute('href')
                if title and link:
                    if not link.startswith('http'):
                        link = f"https://boards.greenhouse.io{link}"
                    jobs.append({'title': title.strip(), 'link': link, 'company': name})

        # --- Generic Scanner ---
        else:
            print(f"   Using generic scanner for {name}")
            links = await page.query_selector_all('a')
            for link in links:
                txt = await link.inner_text()
                href = await link.get_attribute('href')
                
                if txt and href and len(txt) > 3:
                    keywords = ['engineer', 'developer', 'manager', 'specialist', 'student', 'support', 'designer']
                    if any(k in txt.lower() for k in keywords):
                        full_link = href if href.startswith('http') else url.rstrip('/') + href
                        jobs.append({'title': txt.strip(), 'link': full_link, 'company': name})

        print(f"   ✅ Found {len(jobs)} potential jobs at {name}.")
        return jobs

    except Exception as e:
        print(f"   ❌ Error scanning {name}: {e}")
        return []

async def run_scraper_engine():
    print("\n========================================")
    print("🚀 Job Seeker Engine is starting...")
    print("========================================")

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("❌ ERROR: Could not load credentials via os.getenv")
        # לא עוצרים כאן כדי לפחות לראות אם הסריקה עובדת, אבל המייל ייכשל
    
    companies = database.get_companies()
    users = database.get_users()

    if not companies:
        print("😴 No companies to scan.")
        return
    if not users:
        print("😴 No subscribers found.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # User Agent
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"})

        all_new_jobs = []

        for company in companies:
            found_jobs = await scrape_company(page, company)
            for job in found_jobs:
                if not database.job_exists(job['link']):
                    print(f"   ✨ New Job: {job['title']}")
                    database.add_job(job['company_id'] if 'company_id' in job else 0, job['title'], job['link'])
                    all_new_jobs.append(job)
        
        await browser.close()

    if all_new_jobs:
        print(f"\n📨 Sending updates to {len(users)} subscribers...")
        for user in users:
            # user[0] הוא המייל
            await send_email(user[0], all_new_jobs)
    else:
        print("\n😴 No new jobs found this cycle.")

    print("\n========================================")
    print("🏁 Scan Complete.")
    print("========================================")