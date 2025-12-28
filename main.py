import sqlite3
from typing import List, Optional
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import database
from scraper import run_scraper_engine

# --- פונקציית יצירת הטבלאות (גרסת הניקוי והאיפוס) ---
def init_db_tables():
    """
    פונקציה זו רצה בהתחלה.
    מוחקת גרסאות ישנות ויוצרת דאטה-בייס נקי ותקין!
    """
    print("🛠 Maintenance: Resetting database tables...")
    
    conn = sqlite3.connect('jobs.db') 
    c = conn.cursor()
    
    # --- מחיקת הטבלאות הישנות (ניקוי הזיכרון התקוע) ---
    c.execute("DROP TABLE IF EXISTS jobs_cache")
    c.execute("DROP TABLE IF EXISTS subscribers")
    # c.execute("DROP TABLE IF EXISTS companies") # השארנו בהערה כדי לא למחוק חברות אם לא חייבים

    # --- יצירה מחדש (נקייה ותקינה) ---
    # טבלת משרות
    c.execute('''
        CREATE TABLE jobs_cache (
            id TEXT PRIMARY KEY,
            company_id INTEGER,
            title TEXT,
            link TEXT,
            seen_date TEXT
        )
    ''')
    
    # טבלת מנויים
    c.execute('''
        CREATE TABLE subscribers (
            email TEXT PRIMARY KEY,
            interests TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database tables reset and created successfully.")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- אתחול הדאטה-בייס בהפעלה ---
@app.on_event("startup")
def startup_db():
    # 1. מריץ את האתחול הרגיל שלך
    try:
        database.init_db()
    except Exception as e:
        print(f"Warning in database.init_db: {e}")

    # 2. מריץ את הניקוי והבנייה מחדש
    init_db_tables()

# --- דף הבית ---
@app.get("/")
async def index(request: Request, subscribed: bool = False, unsubscribed: bool = False):
    companies = database.get_companies()
    
    success_message = None
    if subscribed:
        success_message = "You're in! 🤘 Scanning started immediately. Check your inbox in a minute!"
    elif unsubscribed:
        success_message = "You have been unsubscribed. No more emails from us. 👋"

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
            "error_message": "✋ System is limited to 5 companies to maintain performance."
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
        print(f"Error adding company: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": f"❌ Error: {str(e)}"
        })

# --- הרשמה + סריקה מיידית (התיקון החשוב) ---
@app.post("/subscribe")
async def subscribe(
    background_tasks: BackgroundTasks,
    email: str = Form(...), 
    departments: List[str] = Form(default=[])
):
    # 1. שמירת משתמש
    database.add_user(email)
    print(f"✅ New Subscriber: {email}")
    
    # 2. הפעלת סריקה מיידית ברקע!
    print("🚀 Triggering IMMEDIATE scan for new user...")
    background_tasks.add_task(run_scraper_engine)
    
    return RedirectResponse(url="/?subscribed=true", status_code=303)

# --- שאר הפונקציות ---
@app.post("/unsubscribe")
async def unsubscribe(email: str = Form(...)):
    database.remove_user(email)
    return RedirectResponse(url="/?unsubscribed=true", status_code=303)

@app.post("/delete-company")
async def delete_company(