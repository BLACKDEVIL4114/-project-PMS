import sqlite3

try:
    con = sqlite3.connect('employee.db')
    cur = con.cursor()
    
    # Update users table
    try:
        cur.execute("ALTER TABLE users ADD COLUMN security_question TEXT")
        cur.execute("ALTER TABLE users ADD COLUMN security_answer TEXT")
        print("Updated users table")
    except Exception as e:
        print(f"users table update skipped: {e}")

    # Update employee table
    try:
        cur.execute("ALTER TABLE employee ADD COLUMN security_question TEXT")
        cur.execute("ALTER TABLE employee ADD COLUMN security_answer TEXT")
        print("Updated employee table")
    except Exception as e:
        print(f"employee table update skipped: {e}")
        
    con.commit()
    con.close()
except Exception as e:
    print(e)
