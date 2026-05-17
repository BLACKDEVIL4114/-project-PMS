import sqlite3

def dump():
    con = sqlite3.connect("employee.db")
    cur = con.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    for name, sql in cur.fetchall():
        print(f"Table: {name}")
        print(sql)
        print("-" * 50)
    con.close()

if __name__ == '__main__':
    dump()
