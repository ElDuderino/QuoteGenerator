import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()
cursor.execute("SELECT username, email, full_name, disabled FROM users WHERE username='demo'")
user = cursor.fetchone()
conn.close()

if user:
    print(f"✓ User found:")
    print(f"  Username: {user[0]}")
    print(f"  Email: {user[1]}")
    print(f"  Full Name: {user[2]}")
    print(f"  Disabled: {user[3]}")
else:
    print("✗ User not found")