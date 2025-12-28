from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import database
from scraper import run_scraper_engine # ייבוא מנוע הסריקה

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# אתחול הדאטה-בייס בהפעלה
@app.on_event("startup")
def startup_db():
    database.init_db()

@app.get("/")
async def index(request: Request):
    companies = database.get_companies()
    return templates.TemplateResponse("index.html", {"request": request, "companies": companies})

@app.post("/subscribe")
async def subscribe(email: str = Form(...), company_id: int = Form(...), department: str = Form(...)):
    user_id = database.add_user(email)
    database.add_subscription(user_id, company_id, department)
    return RedirectResponse(url="/", status_code=303)

# --- נתיב חדש להפעלת הסורק ---
@app.get("/trigger-scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    """
    נתיב זה מיועד להפעלה על ידי שירות חיצוני (Cron).
    הסריקה תרוץ ברקע כדי לא לתקוע את השרת.
    """
    background_tasks.add_task(run_scraper_engine)
    return {"status": "success", "message": "Job scan started in background"}

@app.post("/delete-company")
async def delete_company(company_id: int = Form(...)):
    database.delete_company(company_id)
    return RedirectResponse(url="/", status_code=303)

@app.post("/add")
async def add_company(request: Request, name: str = Form(...), url: str = Form(...)):
    # 1. Get current companies
    current_companies = database.get_companies()
    
    # 2. Check limit (Max 5)
    if len(current_companies) >= 5:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": "✋ System is limited to 5 companies to maintain performance."
        })

    # 3. Validate URL Keywords
    # List of words expected in a careers page URL
    valid_keywords = ["career", "jobs", "job", "position", "work", "join", "team", "culture", "opportunities", "vacancy"]
    
    # Check if URL contains at least one keyword (case insensitive)
    if not any(keyword in url.lower() for keyword in valid_keywords):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": "⚠️ The link must be a Careers page! (Missing words like 'careers', 'jobs', 'positions' in the URL)."
        })

    # 4. Try to add to DB
    try:
        database.add_company(name, url)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        # Log the error for you
        print(f"Error adding company: {e}")
        # Show error to user
        return templates.TemplateResponse("index.html", {
            "request": request,
            "companies": current_companies,
            "error_message": f"❌ Oops, something went wrong: {str(e)}"
        })