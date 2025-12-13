from dotenv import load_dotenv
import os

load_dotenv()
print("连接字符串:", os.getenv('MONGO_URI')[:50], "...")

try:
    from db import users_collection
    print("✅ 数据库连接成功！")
except Exception as e:
    print("❌ 数据库连接失败:", e)
    