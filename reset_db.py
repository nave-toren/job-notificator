import database

def reset_all_data():
    print("⚠️  WARNING: Deleting ALL data from Neon DB...")
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # מחיקת התוכן של הטבלאות (אבל השארת המבנה שלהן)
        # סדר המחיקה חשוב בגלל קשרי גומלין (Foreign Keys)
        cursor.execute("TRUNCATE TABLE jobs_cache, companies, users RESTART IDENTITY CASCADE;")
        
        conn.commit()
        print("✅ Database successfully wiped clean! (Tables are empty and ready)")
    except Exception as e:
        print(f"❌ Error resetting DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_all_data()