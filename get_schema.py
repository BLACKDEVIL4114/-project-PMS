import sqlite3
con = sqlite3.connect('employee.db')
cur = con.cursor()
cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='leave_requests'")
res = cur.fetchone()
if res:
    print(res[0])
else:
    print("Table not found")
