from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取连接字符串
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DATABASE_NAME', 'sm2_learning_system')

print("=" * 50)
print("正在连接 MongoDB...")
print("数据库名称:", DB_NAME)
print("连接字符串前50字符:", MONGO_URI[:50] if MONGO_URI else "未找到")
print("=" * 50)

# 连接 MongoDB
try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,  # 5秒超时
        connectTimeoutMS=5000
    )
    # 测试连接
    client.admin.command('ping')
    print("✅ MongoDB 连接成功！")
except Exception as e:
    print("❌ MongoDB 连接失败:", e)
    raise

db = client[DB_NAME]

# 集合（相当于表）
users_collection = db['users']
cards_collection = db['cards']

def get_user_by_username(username):
    """根据用户名查找用户"""
    return users_collection.find_one({'username': username})

def create_user(username, password_hash):
    """创建新用户"""
    user = {
        'username': username,
        'password': password_hash,
        'created_at': datetime.utcnow()
    }
    result = users_collection.insert_one(user)
    return str(result.inserted_id)

def get_user_cards(user_id):
    """获取用户的所有卡片"""
    return list(cards_collection.find({'user_id': user_id}))

def add_card(user_id, card_data):
    """添加卡片"""
    card_data['user_id'] = user_id
    card_data['created_at'] = datetime.utcnow()
    result = cards_collection.insert_one(card_data)
    return str(result.inserted_id)

def update_card(user_id, card_id, updates):
    """更新卡片"""
    cards_collection.update_one(
        {'card_id': card_id, 'user_id': user_id},
        {'$set': updates}
    )

def delete_card(user_id, card_id):
    """删除卡片"""
    result = cards_collection.delete_one({'card_id': card_id, 'user_id': user_id})
    return result.deleted_count > 0

def get_card(user_id, card_id):
    """获取单个卡片"""
    return cards_collection.find_one({'card_id': card_id, 'user_id': user_id})