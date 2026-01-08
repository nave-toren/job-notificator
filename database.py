import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    # הוספנו את sslmode='require' כדי להכריח חיבור מאובטח
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')
    return conn

def init_db():
    print("⏳ Connecting to Neon DB...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS companies (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    careers_url TEXT NOT NULL,
                    user_email TEXT NOT NULL
                );
            ''')
            
            # השינוי כאן: הוספת is_new_user
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    interests TEXT,
                    is_new_user BOOLEAN DEFAULT TRUE
                );
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs_cache (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER,
                    title TEXT,
                    link TEXT,
                    seen_date TEXT,
                    UNIQUE(link, company_id)
                );
            ''')
            
            conn.commit()
            conn.close()
            print("✅ Connected to Neon PostgreSQL DB & Tables Ready.")
            return 
            
        except Exception as e:
            print(f"⚠️ Attempt {attempt+1}/{max_retries} failed. Error: {e}")
            time.sleep(2)

    raise RuntimeError("DB initialization failed — stopping app")


# --- Companies ---
def get_companies_by_user(user_email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM companies WHERE user_email = %s', (user_email,))
    companies = cursor.fetchall()
    conn.close()
    return companies

def get_all_companies_for_scan():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM companies')
    companies = cursor.fetchall()
    conn.close()
    return companies

def add_company(name, url, user_email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO companies (name, careers_url, user_email) VALUES (%s, %s, %s)', 
            (name, url, user_email)
        )
        conn.commit()
    except Exception as e:
        print(f"Error adding company: {e}")
    finally:
        conn.close()

def delete_company(company_id, user_email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM companies WHERE id = %s AND user_email = %s', (company_id, user_email))
    conn.commit()
    conn.close()

# --- Users ---
def add_user(email, interests_str=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT 1 FROM users WHERE email = %s', (email,))
        if cursor.fetchone():
            cursor.execute('UPDATE users SET interests = %s WHERE email = %s', (interests_str, email))
        else:
            # ברירת מחדל: משתמש חדש
            cursor.execute('INSERT INTO users (email, interests, is_new_user) VALUES (%s, %s, TRUE)', (email, interests_str))
        conn.commit()
    except Exception as e:
        print(f"Error adding/updating user: {e}")
    finally:
        conn.close()

def mark_user_as_not_new(email):
    """ מסמן שהמשתמש קיבל את המייל הראשון שלו """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET is_new_user = FALSE WHERE email = %s', (email,))
        conn.commit()
    except Exception as e:
        print(f"Error updating user status: {e}")
    finally:
        conn.close()

def remove_user(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE email = %s', (email,))
    conn.commit()
    conn.close()

def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

# --- Jobs Cache ---
def job_exists(link):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM jobs_cache WHERE link = %s', (link,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_job(company_id, title, link):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute('''
            INSERT INTO jobs_cache (company_id, title, link, seen_date) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (link, company_id) DO NOTHING
        ''', (company_id, title, link, date_now))
        conn.commit()
    except Exception as e:
        print(f"Error caching job: {e}")
    finally:
        conn.close()