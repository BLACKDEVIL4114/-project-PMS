import sqlite3
import os
import sys

# Mock get_db_path if needed or just use current dir
db_path = "employee.db"
if os.path.exists(db_path):
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='queries'")
        print(f"Table 'queries' exists: {cur.fetchone()}")
        
        cur.execute("PRAGMA table_info(queries)")
        print(f"Columns: {[r[1] for r in cur.fetchall()]}")
        con.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"DB not found at {db_path}")
