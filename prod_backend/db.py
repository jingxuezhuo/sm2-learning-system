from pymongo import MongoClient
from datetime import datetime
import os

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is required")

DB_NAME = os.getenv("DATABASE_NAME", "sm2_prod")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

users = db.users
cards = db.cards

def get_user_by_username(username):
    return users.find_one({"username": username})

def create_user(username, password_hash):
    r = users.insert_one({
        "username": username,
        "password": password_hash,
        "created_at": datetime.utcnow()
    })
    return str(r.inserted_id)

def get_user_cards(uid):
    return list(cards.find({"user_id": uid}, {"_id": 0}))

def get_card(uid, cid):
    return cards.find_one({"user_id": uid, "card_id": cid})

def add_card(uid, data):
    data["user_id"] = uid
    data["created_at"] = datetime.utcnow()
    cards.insert_one(data)

def update_card(uid, cid, updates):
    cards.update_one(
        {"user_id": uid, "card_id": cid},
        {"$set": updates}
    )

def delete_card(uid, cid):
    return cards.delete_one({"user_id": uid, "card_id": cid}).deleted_count > 0
