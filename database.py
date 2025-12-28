import sqlite3

def init_db():
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    print("🛠️ Updating database schema...")

    # 1. Companies - הוספנו את careers_url כפי שביקשת
    cursor.execute('''CREATE TABLE IF NOT EXISTS companies 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, careers_url TEXT)''')

    # 2. Users
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE)''')

    # 3. Subscriptions
    cursor.execute('''CREATE TABLE IF NOT EXISTS subscriptions 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, company_id INTEGER, 
         department TEXT, is_active BOOLEAN DEFAULT 1)''')

    # 4. Jobs Cache
    cursor.execute('''CREATE TABLE IF NOT EXISTS jobs_cache 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, title TEXT, link TEXT UNIQUE)''')

    conn.commit()
    conn.close()
    print("✅ Database is 100% ready.")

def get_companies():
    """הפונקציה שהייתה חסרה וגרמה לשגיאה ב-Render"""
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    # וודא שהטבלה קיימת לפני שמושכים נתונים
    cursor.execute('SELECT name, careers_url FROM companies')
    rows = cursor.fetchall()
    conn.close()
    # אנחנו מחזירים רשימה של מילונים (Dictionaries) ש-main.py מצפה לקבל
    return [{"name": row[0], "url": row[1]} for row in rows]

if __name__ == "__main__":
    init_db()