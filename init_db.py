import project_monitor
import sqlite3

print("Initializing database...")
if project_monitor.init_database():
    print("Database initialized successfully.")
else:
    print("Database initialization failed.")
