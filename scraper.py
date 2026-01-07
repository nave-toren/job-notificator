import asyncio
import os
import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import database

# ================== ENV ==================
load_dotenv()

# ================== CLASSIFICATION ==================

CATEGORY_KEYWORDS = {
    "Engineering": [
        'engineer', 'developer', 'r&d', 'data', 'algorithm', 'architect',
        'full stack', 'backend', 'frontend', 'mobile', 'devops', 'software', 'qa', 'cyber'
    ],
    "Product": ['product', 'design', 'ux', 'ui', 'creative'],
    "Marketing": ['marketing', 'sales', 'account', 'business', 'sdr', 'bdr', 'content', 'seo', 'ppc', 'growth'],
    "Finance": ['finance', 'accountant', 'controller', 'payroll', 'fp&a', 'legal', 'compliance', 'economist'],
    "HR": ['hr', 'recruiter', 'talent', 'people', 'office manager', 'admin', 'operations'],
    "Support": ['support', 'customer', 'success', 'service', 'helpdesk', 'tier', 'qa']
}

def classify_job(title):
    t = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in t for k in keywords):
            return category
    return "Other"

# ================== GENERIC SCRAPER ==================

JOB_TITLE_KEYWORDS = [
    'engineer','developer','manager','specialist','lead','director',
    'analyst','designer','qa','support','intern','product','marketing',
    'finance','accountant','recruiter','hr','operations'
]

JOB_URL_KEYWORDS = ['job','career','position','opening','apply','role','vacancy']

JUNK_KEYWORDS = [
    'privacy','policy','terms','cookie','login','signin','signup','forgot',
    'blog','news','press','about','contact','facebook','twitter','linkedin','instagram','investor'
]

async def scrape_generic(page, company_row):
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🟡 Using generic scraper for {name}")
    found_jobs = []

    try:
        await page.goto(url, timeout=60000, wait_until='domcontentloaded')
        await asyncio.sleep(3)

        links = await page.query_selector_all("a")
        seen = set()

        for link in links:
            try:
                txt = (await link.inner_text() or "").strip()
                href = await link.get_attribute("href")

                if not txt or not href:
                    continue

                t = txt.lower()
                h = href.lower()

                if not (
                    any(k in t for k in JOB_TITLE_KEYWORDS) or
                    any(k in h for k in JOB_URL_KEYWORDS)
                ):
                    continue

                if any(j in t for j in JUNK_KEYWORDS):
                    continue

                full = href if href.startswith("http") else url.rstrip("/") + href

                if full in seen:
                    continue

                seen.add(full)

                found_jobs.append({
                    "company_id": c_id,
                    "company": name,
                    "title": txt,
                    "link": full
                })

            except:
                continue

    except Exception as e:
        print(f"❌ Generic scrape error for {name}: {e}")

    print(f"   ✅ Generic found {len(found_jobs)} jobs at {name}")
    return found_jobs

# ================== GREENHOUSE SCRAPER ==================

async def scrape_greenhouse(page, company_row):
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🟢 Using Greenhouse scraper for {name}")
    found_jobs = []

    try:
        await page.goto(url, timeout=60000, wait_until='domcontentloaded')
        await asyncio.sleep(2)

        job_cards = await page.query_selector_all("div.opening a")

        for card in job_cards:
            title = (await card.inner_text()).strip()
            href = await card.get_attribute("href")

            if not title or not href:
                continue

            full = href if href.startswith("http") else "https://boards.greenhouse.io" + href

            found_jobs.append({
                "company_id": c_id,
                "company": name,
                "title": title,
                "link": full
            })

    except Exception as e:
        print(f"❌ Greenhouse scrape error for {name}: {e}")

    print(f"   ✅ Greenhouse found {len(found_jobs)} jobs at {name}")
    return found_jobs

# ================== LEVER SCRAPER ==================

async def scrape_lever(page, company_row):
    url = company_row['careers_url']
    name = company_row['name']
    c_id = company_row['id']

    print(f"   🟣 Using Lever scraper for {name}")
    found_jobs = []

    try:
        await page.goto(url, timeout=60000, wait_until='domcontentloaded')
        await asyncio.sleep(2)

        job_cards = await page.query_selector_all("a.posting-title")

        for card in job_cards:
            title = (await card.inner_text()).strip()
            href = await card.get_attribute("href")

            if not title or not href:
                continue

            full = href if href.startswith("http") else url.rstrip("/") + href

            found_jobs.append({
                "company_id": c_id,
                "company": name,
                "title": title,
                "link": full
            })

    except Exception as e:
        print(f"❌ Lever scrape error for {name}: {e}")

    print(f"   ✅ Lever found {len(found_jobs)} jobs at {name}")
    return found_jobs

# ================== DISPATCHER ==================

async def scrape_company(page, company_row):
    url = company_row['careers_url'].lower()

    if "greenhouse.io" in url:
        return await scrape_greenhouse(page, company_row)

    elif "lever.co" in url:
        return await scrape_lever(page, company_row)

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
        if not user_interest_list or cat in user_interest_list:
            relevant_jobs.append(job)

    if not relevant_jobs:
        print(f"   ℹ️ No relevant jobs for {to_email}")
        return False

    html_body = f"""
    <div style="font-family: Arial, sans-serif;">
        <h2>🚀 New jobs just for you</h2>

        <p style="font-style: italic; color: #636e72;">
        Now you can play matkot on the beach 🏖️ while I'm finding jobs for you 😎
        </p>

        <p>We found <b>{len(relevant_jobs)}</b> jobs matching your interests:</p>
        <ul style="padding: 0; list-style-type: none;">
    """

    for job in relevant_jobs:
        html_body += f"""
        <li style="margin-bottom:12px;padding:10px;border-left:4px solid #ff7e5f;background:#f9f9f9;">
            <a href="{job['link']}" style="font-weight:bold;color:#0984e3;text-decoration:none;">
                {job['title']}
            </a>
            <div style="font-size:13px;color:#555;">🏢 {job['company']}</div>
        </li>
        """

    html_body += """
        </ul>

        <p style="margin-top:20px; font-size:13px; color:#888;">
            — Career Agent 🤖 <br>
            by Nave Toren
        </p>
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
        "subject": f"🎯 Career Agent found {len(relevant_jobs)} new roles for you",
        "html": html_body
    }

    try:
        print("   📤 Sending email via Resend...")
        r = requests.post("https://api.resend.com/emails", json=payload, headers=headers)

        if r.status_code >= 400:
            print("❌ Resend error:", r.text)
            return False

        print(f"✅ Email sent to {to_email}")
        return True

    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

# ================== ENGINE ==================

async def run_scraper_engine():
    print("🚀 Starting Smart Scraper MVP...")

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
            args=['--no-sandbox','--disable-dev-shm-usage','--single-process']
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

    print(f"\n📨 Processing emails for {len(users)} users...")

    for user in users:
        email = user['email']
        interests = user['interests']

        user_companies = database.get_companies_by_user(email)
        user_company_ids = [c['id'] for c in user_companies]

        jobs_to_send = []

        for c_id in user_company_ids:
            for job in jobs_by_company.get(c_id, []):
                if job['link'] in globally_new_links:
                    jobs_to_send.append(job)

        if jobs_to_send:
            await send_email(email, interests, jobs_to_send)
        else:
            print(f"🤷‍♂️ No updates for {email}")

    print("🏁 Scraper finished.")
