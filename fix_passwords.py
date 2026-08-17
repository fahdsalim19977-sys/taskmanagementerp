import sqlite3
conn = sqlite3.connect('/app/data/tasks.db')
cursor = conn.cursor()
cursor.execute("SELECT username, password FROM users WHERE username = 'Adminerp'")
user = cursor.fetchone()
print(f"Username: {user[0]}")
print(f"Password hash: {user[1]}")
print(f"Starts with $2b$: {user[1].startswith('$2b$')}")
conn.close()