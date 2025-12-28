import sqlite3

def init_db():
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = sqlite3.Row  # מאפשר גישה לשדות לפי שם (comp.name)
    cursor = conn.cursor()
    # טבלת חברות
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            careers_url TEXT NOT NULL
        )
    ''')
    # טבלת משתמשים
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_companies():
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM companies')
    companies = cursor.fetchall()
    conn.close()
    return companies

def add_company(name, url):
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO companies (name, careers_url) VALUES (?, ?)', (name, url))
    conn.commit()
    conn.close()

def delete_company(company_id):
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM companies WHERE id = ?', (company_id,))
    conn.commit()
    conn.close()

def add_user(email):
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (email) VALUES (?)', (email,))
    conn.commit()
    conn.close()

def remove_user(email):
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE email = ?', (email,))
    conn.commit()
    conn.close()