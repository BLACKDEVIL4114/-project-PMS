import sqlite3
import os

def check_schema():
    db_path = 'employee.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found")
        return
    
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    
    print("Table: leave_requests")
    cur.execute("PRAGMA table_info(leave_requests)")
    cols = cur.fetchall()
    for col in cols:
        print(col)
    
    con.close()

if __name__ == "__main__":
    check_schema()
