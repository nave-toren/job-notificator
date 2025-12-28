import sqlite3

def init_db():
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    print("🛠️ Updating database schema...")

    # 1. Companies
    cursor.execute('''CREATE TABLE IF NOT EXISTS companies 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, careers_url TEXT)''')

    # 2. Users
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE)''')

    # 3. Subscriptions (The missing table!)
    cursor.execute('''CREATE TABLE IF NOT EXISTS subscriptions 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, company_id INTEGER, 
         department TEXT, is_active BOOLEAN DEFAULT 1)''')

    # 4. Jobs Cache
    cursor.execute('''CREATE TABLE IF NOT EXISTS jobs_cache 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, title TEXT, link TEXT UNIQUE)''')

    conn.commit()
    conn.close()
    print("✅ Database is 100% ready.")

if __name__ == "__main__":
    init_db()