import os
import asyncio
import uvicorn
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

import database
from scraper import run_scraper_with_lock

# Load env vars
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 LIFESPAN STARTUP: initializing database")
    database.init_db()
    yield
    print("🛑 LIFESPAN SHUTDOWN")

app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")


# ✅ Wrapper so BackgroundTasks can run the async scraper safely
def start_scraper_task():
    """
    Runs the async scraper from a sync context (BackgroundTasks).
    """
    try:
        asyncio.run(run_scraper_with_lock())
    except RuntimeError:
        # If there's already a running event loop (rare in this context),
        # fallback to creating a task on that loop.
        loop = asyncio.get_event_loop()
        loop.create_task(run_scraper_with_lock())


@app.get("/")
async def index(
    request: Request, 
    subscribed: bool = False, 
    unsubscribed: bool = False, 
    error_message: str | None = None, 
    view_email: str | None = None
):
    my_companies = []
    
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
async def add_company(
    request: Request, 
    name: str = Form(...), 
    url: str = Form(...), 
    user_email: str = Form(...)
):
    user_companies = database.get_companies_by_user(user_email)
    if len(user_companies) >= 5: 
        return RedirectResponse(
            url=f"/?view_email={user_email}&error_message=✋ Limit Reached. Max 5 companies allowed.", 
            status_code=303
        )

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
    departments: List[str] = Form(default=[]),
    region: str = Form(default="Other") # <--- 1. קליטת האזור מהטופס
):
    interests_str = ",".join(departments)
    
    # <--- 2. העברת האזור לדאטה בייס
    database.add_user(email, interests_str, region)
    
    print(f"👤 User {email} subscribed. Region: {region}, Interests: {interests_str}")
    
    # ✅ Trigger scraper in background
    background_tasks.add_task(start_scraper_task)
    
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
    print("🔔 Manual/Cron Trigger Received! Starting Scraper...")
    background_tasks.add_task(start_scraper_task)
    return {"status": "success", "message": "Scraper started in background 🚀"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)