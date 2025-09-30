from app.user_crud_console_util import UserManager

manager = UserManager()
manager.create_user('demo', 'demo@example.com', 'Demo User', 'password')
print("User 'demo' has been created successfully!")