import sqlite3
import smtplib
import time
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("EMAIL_USER")
SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD")
DISPLAY_NAME = "Job Seeker 🔍"

DEPARTMENTS = {
    'R&D': ['developer', 'engineer', 'fullstack', 'backend', 'frontend', 'software', 'qa', 'automation', 'devops', 'cyber', 'mobile', 'architect', 'embedded'],
    'Student': ['student', 'intern', 'internship', 'graduate', 'junior', 'university', 'entry level'],
    'Data': ['data scientist', 'data analyst', 'bi', 'machine learning', 'ml', 'ai', 'big data', 'sql', 'tableau', 'researcher'],
    'Product': ['product manager', 'product owner', 'ux', 'ui', 'designer', 'product designer', 'ux/ui'],
    'Marketing': ['marketing', 'ua', 'acquisition', 'growth', 'seo', 'content', 'brand', 'copywriter', 'pr'],
    'Sales & Biz': ['sales', 'account manager', 'sdr', 'bdr', 'business development', 'partnerships', 'customer success'],
    'HR & Ops': ['hr', 'recruiter', 'talent acquisition', 'operations', 'office manager', 'people', 'admin'],
    'Finance & Legal': ['finance', 'legal', 'lawyer', 'accounting', 'controller', 'analyst', 'bookkeeper', 'tax']
}

def send_notification_email(receiver_email, job_title, company_name, job_link, department):
    """ שליחת מייל מעוצב למשתמש """
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{DISPLAY_NAME} <{SENDER_EMAIL}>"
        msg['To'] = receiver_email
        msg['Subject'] = f"🚀 New {department} Position at {company_name}!"

        body = f"""
        Hello!
        
        Job Seeker found a new position matching your profile:
        
        🏢 Company: {company_name}
        💼 Position: {job_title}
        🏷️ Department: {department}
        🔗 Apply here: {job_link}
        
        Good luck with your application!
        ---------------------------------
        Created by Nave Toren
        """
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print(f"   ✅ Email sent to {receiver_email}")
    except Exception as e:
        print(f"   ❌ Email error: {e}")

def run_scraper_engine():
    """ המנוע הראשי שסורק את האתרים ושולח התראות """
    print(f"\n{'='*40}")
    print("🚀 Job Seeker Engine is starting...")
    print(f"{'='*40}\n")
    
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, careers_url FROM companies")
    companies = cursor.fetchall()
    
    if not companies:
        print("ℹ️ No companies to scan. Add some via the website first.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        for comp in companies:
            comp_id, comp_name, url = comp['id'], comp['name'], comp['careers_url']
            print(f"🔎 Scanning {comp_name}...")
            
            page = context.new_page()
            try:
    
                page.goto(url, wait_until="domcontentloaded", timeout=60000)

                time.sleep(5) 
                
                soup = BeautifulSoup(page.content(), 'html.parser')
                found_count = 0
                
                for a in soup.find_all('a'):
                    title = a.get_text().strip()
                    link = a.get('href', '')
                    
                    # סינון בסיסי של לינקים שנראים כמו משרות
                    if len(title) > 5 and any(x in link.lower() for x in ['job', 'position', 'careers', 'apply', 'gh_jid']):
                        full_link = link if link.startswith('http') else url.split('/jobs')[0].rstrip('/') + '/' + link.lstrip('/')
                        
                        # סיווג למחלקה
                        matched_dept = None
                        title_lower = title.lower()
                        for dept, keywords in DEPARTMENTS.items():
                            if any(word in title_lower for word in keywords):
                                matched_dept = dept
                                break
                        
                        if matched_dept:
                            # בדיקה אם המשרה כבר קיימת בזיכרון
                            cursor.execute("SELECT id FROM jobs_cache WHERE link = ?", (full_link,))
                            if cursor.fetchone() is None:
                                # שמירה בדאטה-בייס
                                cursor.execute("INSERT INTO jobs_cache (company_id, title, link) VALUES (?, ?, ?)", 
                                               (comp_id, title, full_link))
                                conn.commit()
                                print(f"   ✨ Found New Job: {title} ({matched_dept})")
                                found_count += 1
                                
                                # שליחת התראות למנויים רלוונטיים
                                cursor.execute("""
                                    SELECT u.email FROM users u 
                                    JOIN subscriptions s ON u.id = s.user_id 
                                    WHERE s.company_id = ? AND s.department = ?
                                """, (comp_id, matched_dept))
                                
                                for (email,) in cursor.fetchall():
                                    send_notification_email(email, title, comp_name, full_link, matched_dept)
                
                if found_count == 0:
                    print(f"   😴 No new jobs found at {comp_name}.")
                    
            except Exception as e:
                print(f"   ❌ Error scanning {comp_name}: {str(e)[:100]}...")
            finally:
                page.close()
                
        browser.close()
    conn.close()
    print(f"\n{'='*40}")
    print("🏁 Scan Complete.")
    print(f"{'='*40}")

if __name__ == "__main__":
    print("🚀 Server is starting on port 10000...")
    app.run(host="0.0.0.0", port=10000)