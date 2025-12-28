from typing import List, Optional
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import database
from scraper import run_scraper_engine

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- אתחול הדאטה-בייס בהפעלה ---
@app.on_event("startup")
def startup_db():
    database.init_db()

# --- דף הבית ---
@app.get("/")
async def index(request: Request, subscribed: bool = False, unsubscribed: bool = False):
    # שליפת רשימת החברות להצגה
    companies = database.get_companies()
    
    # לוגיקה להודעות הצלחה (Feedback) למשתמש
    success_message = None
    if subscribed:
        success_message = "You're in! 🤘 Details saved. If we match any jobs to your vibe, you'll get an email. Good luck!"
    elif unsubscribed:
        success_message = "You have been unsubscribed. No more emails from us. 👋"

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "companies": companies,
        "success_message": success_message
    })

# --- הוספת חברה חדשה (עם בדיקות תקינות) ---
@app.post("/add")
async def add_company(request: Request, name: str = Form(...), url: str = Form(...)):
    # 1. שליפת הרשימה הקיימת
    current_companies = database.get_companies()
    
    # 2. בדיקת מגבלה (עד 5 חברות)
    if len(current_companies) >= 5:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": "✋ System is limited to 5 companies to maintain performance."
        })

    # 3. אימות URL - בדיקה שהלינק הוא לדף קריירה
    valid_keywords = ["career", "jobs", "job", "position", "work", "join", "team", "culture", "opportunities", "vacancy"]
    
    # בדיקה האם ה-URL מכיל לפחות אחת מהמילים (באותיות קטנות)
    if not any(keyword in url.lower() for keyword in valid_keywords):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": "⚠️ The link must be a Careers page! (Missing words like 'careers', 'jobs', 'positions' in the URL)."
        })

    # 4. ניסיון הוספה לדאטה-בייס
    try:
        database.add_company(name, url)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        print(f"Error adding company: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": f"❌ Oops, something went wrong: {str(e)}"
        })

# --- הרשמה לקבלת התראות ---
@app.post("/subscribe")
async def subscribe(email: str = Form(...), departments: List[str] = Form(default=[])):
    # שמירת המשתמש בדאטה-בייס
    database.add_user(email)
    
    # (בעתיד: כאן נשמור גם את ה-departments אם נרצה לסנן לפי תחום)
    print(f"New Subscriber: {email}, Interests: {departments}")
    
    # הפניה מחדש לדף הבית עם דגל הצלחה
    return RedirectResponse(url="/?subscribed=true", status_code=303)

# --- הסרה מרשימת התפוצה ---
@app.post("/unsubscribe")
async def unsubscribe(email: str = Form(...)):
    database.remove_user(email)
    return RedirectResponse(url="/?unsubscribed=true", status_code=303)

# --- מחיקת חברה מהרשימה ---
@app.post("/delete-company")
async def delete_company(company_id: int = Form(...)):
    database.delete_company(company_id)
    return RedirectResponse(url="/", status_code=303)

# --- נתיב להפעלת הסורק (עבור Cron Job) ---
# הערה: שמרתי גם על /scan וגם על /trigger-scan כדי שיתאים למה שהגדרת ב-Cron
@app.get("/scan")
@app.get("/trigger-scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    """
    נתיב זה מיועד להפעלה על ידי שירות חיצוני (Cron-job.org).
    הסריקה תרוץ ברקע (Background Task) כדי לא לתקוע את השרת.
    """
    print("⏳ Triggering scan via Cron...")
    background_tasks.add_task(run_scraper_engine)
    return {"status": "success", "message": "Job scan started in background"}