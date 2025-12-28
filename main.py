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