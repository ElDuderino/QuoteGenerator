import configparser
import sqlite3
import logging
import getpass
from passlib.context import CryptContext


class UserManager:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        config = configparser.ConfigParser()
        config.read('config.cfg')

        self.db_file = config.get("SQLITE", "db_file")

        # Initialize SQLite Database
        self._create_users_table()

    def _create_users_table(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            email TEXT,
                            full_name TEXT,
                            disabled BOOLEAN DEFAULT 0,
                            hashed_password TEXT NOT NULL
                          )''')
        conn.commit()
        conn.close()

    def get_password_hash(self, password):
        # Bcrypt has a 72-byte password length limit
        return self.pwd_context.hash(password[:72])

    def create_user(self, username, email, full_name, password):
        hashed_password = self.get_password_hash(password)
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO users (username, email, full_name, hashed_password)
                              VALUES (?, ?, ?, ?)''',
                           (username, email, full_name, hashed_password))
            conn.commit()
            conn.close()
            print(f"User {username} created successfully.")
        except sqlite3.IntegrityError:
            print(f"Error: User {username} already exists.")

    def update_user(self, username, email=None, full_name=None, password=None):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        updates = []
        params = []

        if email:
            updates.append("email = ?")
            params.append(email)
        if full_name:
            updates.append("full_name = ?")
            params.append(full_name)
        if password:
            hashed_password = self.get_password_hash(password)
            updates.append("hashed_password = ?")
            params.append(hashed_password)

        if updates:
            params.append(username)
            update_query = f"UPDATE users SET {', '.join(updates)} WHERE username = ?"
            cursor.execute(update_query, params)
            conn.commit()
            print(f"User {username} updated successfully.")
        else:
            print("No updates provided.")

        conn.close()

    def delete_user(self, username):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        if cursor.rowcount > 0:
            print(f"User {username} deleted successfully.")
        else:
            print(f"User {username} not found.")
        conn.close()

    def list_users(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT username, email, full_name, disabled FROM users")
        users = cursor.fetchall()
        if users:
            print("\nList of users:")
            for user in users:
                print(f"Username: {user[0]}, Email: {user[1]}, Full Name: {user[2]}, Disabled: {user[3]}")
        else:
            print("No users found.")
        conn.close()


def main():

    manager = UserManager()

    while True:
        print("\nUser Management Console")
        print("1. Create User")
        print("2. Update User")
        print("3. Delete User")
        print("4. List Users")
        print("5. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            username = input("Username: ")
            email = input("Email: ")
            full_name = input("Full Name: ")
            password = getpass.getpass("Password: ")
            manager.create_user(username, email, full_name, password)
        elif choice == '2':
            username = input("Username: ")
            email = input("New Email (leave blank to keep current): ")
            full_name = input("New Full Name (leave blank to keep current): ")
            password = getpass.getpass("New Password (leave blank to keep current): ")
            manager.update_user(username, email, full_name, password)
        elif choice == '3':
            username = input("Username: ")
            manager.delete_user(username)
        elif choice == '4':
            manager.list_users()
        elif choice == '5':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()