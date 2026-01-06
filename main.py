import uvicorn
from typing import List, Optional
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import database
# וודא שקובץ scraper.py נמצא באותה תיקייה
from scraper import run_scraper_engine
from dotenv import load_dotenv

# טעינת משתני סביבה
load_dotenv()

app = FastAPI()

# 1. הגדרת תיקיית טמפלייטים (HTML)
templates = Jinja2Templates(directory="templates")

# 2. אופציונלי: אם יש לך קבצי CSS/Images, צריך את השורה הזו:
# app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup_db():
    """ יצירת הטבלאות בעת עליית השרת """
    database.init_db()

@app.get("/")
async def index(request: Request, subscribed: bool = False, unsubscribed: bool = False, error_message: str = None, view_email: str = None):
    my_companies = []
    
    # אם יש מייל ב-URL, נציג את החברות של אותו משתמש
    if view_email:
        my_companies = database.get_companies_by_user(view_email)

    success_message = None
    if subscribed:
        success_message = "Success! Scanning started. Check your inbox."
    elif unsubscribed:
        success_message = "Unsubscribed successfully."

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "companies": my_companies,
        "view_email": view_email, 
        "success_message": success_message,
        "error_message": error_message
    })

@app.post("/add")
async def add_company(request: Request, name: str = Form(...), url: str = Form(...), user_email: str = Form(...)):
    # בדיקת כמות חברות (מגבלה של 5)
    user_companies = database.get_companies_by_user(user_email)
    if len(user_companies) >= 5: 
        return RedirectResponse(
            url=f"/?view_email={user_email}&error_message=✋ Limit Reached. Max 5 companies allowed.", 
            status_code=303
        )

    # בדיקת תקינות URL בסיסית
    valid_keywords = ["career", "jobs", "job", "position", "work", "join", "team", "opportunities", "vacancy", "location", "about"]
    if not any(keyword in url.lower() for keyword in valid_keywords):
        return RedirectResponse(
            url=f"/?view_email={user_email}&error_message=⚠️ Invalid URL. Link must be a Career page.", 
            status_code=303
        )

    database.add_company(name, url, user_email)
    return RedirectResponse(url=f"/?view_email={user_email}", status_code=303)

@app.post("/subscribe")
async def subscribe(
    background_tasks: BackgroundTasks, 
    email: str = Form(...),
    departments: List[str] = Form(default=[]) 
):
    """
    הרשמה:
    1. שומרים/מעדכנים את המשתמש והמחלקות שלו.
    2. מפעילים סריקה ברקע (שתשלח לו מייל 'ברוכים הבאים' אם הוא חדש).
    """
    # המרת רשימת המחלקות למחרוזת אחת (למשל: "Engineering,Marketing")
    interests_str = ",".join(departments)
    
    # הוספה לדאטה בייס (אם המשתמש לא קיים - הוא יסומן כחדש)
    database.add_user(email, interests_str)
    
    print(f"👤 User {email} subscribed with interests: {interests_str}")
    
    # הפעלת הסריקה באופן מיידי ברקע כדי שהמשתמש יקבל מייל ראשוני
    background_tasks.add_task(run_scraper_engine)
    
    return RedirectResponse(url=f"/?subscribed=true&view_email={email}", status_code=303)

@app.post("/unsubscribe")
async def unsubscribe(email: str = Form(...)):
    database.remove_user(email)
    return RedirectResponse(url="/?unsubscribed=true", status_code=303)

@app.post("/delete-company")
async def delete_company(company_id: int = Form(...), user_email: str = Form(...)):
    database.delete_company(company_id, user_email)
    return RedirectResponse(url=f"/?view_email={user_email}", status_code=303)

@app.get("/trigger-scan")
async def manual_trigger_scan(background_tasks: BackgroundTasks):
    """
    נקודת קצה להפעלה על ידי Cron Job או ידנית.
    """
    print("🔔 Manual/Cron Trigger Received! Starting Scraper...")
    background_tasks.add_task(run_scraper_engine)
    return {"status": "success", "message": "Scraper started in background 🚀"}

# --- זה החלק שהיה חסר לך! ---
if __name__ == "__main__":
    # מאפשר להריץ את הקובץ ישירות (python main.py) לבדיקות מקומיות
    uvicorn.run(app, host="0.0.0.0", port=10000)