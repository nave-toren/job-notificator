import sqlite3
from typing import List, Optional
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import database
from scraper import run_scraper_engine

# --- פונקציית יצירת הטבלאות (גרסת התיקון הסופי) ---
def init_db_tables():
    print("🛠 Maintenance: Resetting database tables to match Scraper...")
    
    conn = sqlite3.connect('jobs.db') 
    c = conn.cursor()
    
    # מחיקת כל הגרסאות הישנות למניעת התנגשויות
    c.execute("DROP TABLE IF EXISTS jobs_cache")
    c.execute("DROP TABLE IF EXISTS subscribers")   # השם הישן
    c.execute("DROP TABLE IF EXISTS subscriptions") # השם החדש (ליתר ביטחון)
    
    # יצירה מחדש - טבלת משרות
    c.execute('''
        CREATE TABLE jobs_cache (
            id TEXT PRIMARY KEY,
            company_id INTEGER,
            title TEXT,
            link TEXT,
            seen_date TEXT
        )
    ''')
    
    # יצירה מחדש - טבלת מנויים (בשם subscriptions שהסורק דורש!)
    c.execute('''
        CREATE TABLE subscriptions (
            email TEXT PRIMARY KEY,
            interests TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database tables (jobs_cache, subscriptions) created successfully.")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- אתחול הדאטה-בייס בהפעלה ---
@app.on_event("startup")
def startup_db():
    # קודם כל מוחקים ויוצרים מחדש את הטבלאות הנכונות
    init_db_tables()
    
    # מריצים את האתחול הרגיל (ליתר ביטחון, למקרה שיש שם לוגיקה נוספת)
    try:
        database.init_db()
    except Exception as e:
        print(f"Note: database.init_db skipped or failed (expected if tables exist): {e}")

# --- דף הבית ---
@app.get("/")
async def index(request: Request, subscribed: bool = False, unsubscribed: bool = False):
    companies = database.get_companies()
    
    success_message = None
    if subscribed:
        success_message = "You're in! 🤘 Scanning started immediately. Check your inbox in a minute!"
    elif unsubscribed:
        success_message = "You have been unsubscribed. 👋"

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "companies": companies,
        "success_message": success_message
    })

# --- הוספת חברה ---
@app.post("/add")
async def add_company(request: Request, name: str = Form(...), url: str = Form(...)):
    current_companies = database.get_companies()
    
    if len(current_companies) >= 5:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": "✋ Limit: 5 companies."
        })

    valid_keywords = ["career", "jobs", "job", "position", "work", "join", "team", "culture", "opportunities", "vacancy"]
    if not any(keyword in url.lower() for keyword in valid_keywords):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": "⚠️ The link must be a Careers page!"
        })

    try:
        database.add_company(name, url)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": f"❌ Error: {str(e)}"
        })

# --- הרשמה + סריקה מיידית ---
@app.post("/subscribe")
async def subscribe(
    background_tasks: BackgroundTasks,
    email: str = Form(...), 
    departments: List[str] = Form(default=[])
):
    # שומרים את המשתמש (וודא ששינית ל-subscriptions ב-database.py!)
    try:
        database.add_user(email)
        print(f"✅ New Subscriber added: {email}")
    except Exception as e:
        print(f"❌ Error adding user to DB (Check table name in database.py): {e}")
    
    # מפעילים סריקה מיידית
    print("🚀 Triggering IMMEDIATE scan for new user...")
    background_tasks.add_task(run_scraper_engine)
    
    return RedirectResponse(url="/?subscribed=true", status_code=303)

# --- הסרה ---
@app.post("/unsubscribe")
async def unsubscribe(email: str = Form(...)):
    database.remove_user(email)
    return RedirectResponse(url="/?unsubscribed=true", status_code=303)

# --- מחיקת חברה ---
@app.post("/delete-company")
async def delete_company(company_id: int = Form(...)):
    database.delete_company(company_id)
    return RedirectResponse(url="/", status_code=303)

# --- טריגר לסריקה ---
@app.get("/scan")
@app.get("/trigger-scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    print("⏳ Triggering scan via Cron...")
    background_tasks.add_task(run_scraper_engine)
    return {"status": "success", "message": "Job scan started in background"}