from typing import List, Optional
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import database
from scraper import run_scraper_engine
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def startup_db():
    database.init_db()

@app.get("/")
async def index(request: Request, subscribed: bool = False, unsubscribed: bool = False, error_message: str = None, view_email: str = None):
    my_companies = []
    
    # הצגת חברות של משתמש ספציפי
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
    # 1. בדיקת עומס (מגבלה של 5 חברות למשתמש)
    user_companies = database.get_companies_by_user(user_email)
    if len(user_companies) >= 5: 
        return RedirectResponse(
            url=f"/?view_email={user_email}&error_message=✋ Limit Reached. You have 5 companies. Delete one to add new.", 
            status_code=303
        )

    # 2. בדיקת תקינות URL (מונע הכנסת סתם אתרים)
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
    # שומר את האינטרסים של המשתמש כמחרוזת בנאון
    interests_str = ",".join(departments)
    database.add_user(email, interests_str)
    
    # מפעיל סריקה ברקע
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