import sqlite3, os
db = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'employee.db')
con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLES:", [r[0] for r in cur.fetchall()])
for tbl in ['tasks', 'employee', 'attendance', 'timesheets']:
    try:
        cur.execute(f"PRAGMA table_info({tbl})")
        cols = [(r[1], r[2]) for r in cur.fetchall()]
        print(f"\n{tbl.upper()} COLUMNS:", cols)
    except Exception as e:
        print(f"{tbl}: ERROR {e}")
con.close()
