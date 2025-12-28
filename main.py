from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import List
import sqlite3
import uvicorn

app = FastAPI(title="Job Seeker 🔍")
templates = Jinja2Templates(directory="templates")

def get_db():
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = get_db()
    companies = conn.execute("SELECT * FROM companies ORDER BY name ASC").fetchall()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "companies": companies})

@app.post("/add-company")
async def add_company(name: str = Form(...), url: str = Form(...)):
    conn = get_db()
    conn.execute("INSERT INTO companies (name, careers_url) VALUES (?, ?)", (name, url))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete-company/{company_id}")
async def delete_company(company_id: int):
    conn = get_db()
    try:
        # Delete from both tables to be clean
        conn.execute("DELETE FROM subscriptions WHERE company_id = ?", (company_id,))
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        conn.close()

@app.post("/subscribe")
async def subscribe(email: str = Form(...), departments: List[str] = Form(...)):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (email) VALUES (?)", (email,))
        user_id = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()['id']
        companies = cursor.execute("SELECT id FROM companies").fetchall()
        
        for comp in companies:
            c_id = comp['id']
            cursor.execute("DELETE FROM subscriptions WHERE user_id = ? AND company_id = ?", (user_id, c_id))
            for dept in departments:
                cursor.execute("INSERT INTO subscriptions (user_id, company_id, department) VALUES (?, ?, ?)", 
                               (user_id, c_id, dept))
        conn.commit()
        return {"status": "success", "message": "Profile updated!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)