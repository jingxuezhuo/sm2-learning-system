from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os

from auth import hash_password, check_password, generate_token, token_required
from db import (
    get_user_by_username, create_user, get_user_cards,
    add_card, update_card, delete_card, get_card
)
from sm2_card import SM2Card

# =====================
# App init
# =====================

app = Flask(__name__)

ENV = os.getenv("ENV", "production")
PORT = int(os.getenv("PORT", 5001))
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/var/app/uploads")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# CORS（生产：只允许前端域名）
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": os.getenv("FRONTEND_ORIGIN", "").split(",")
        }
    }
)

# =====================
# Auth APIs
# =====================

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    if get_user_by_username(username):
        return jsonify({"error": "user already exists"}), 400

    uid = create_user(username, hash_password(password))
    token = generate_token(uid, username)

    return jsonify({"token": token, "username": username})


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    user = get_user_by_username(username)
    if not user or not check_password(password, user["password"]):
        return jsonify({"error": "invalid credentials"}), 401

    token = generate_token(str(user["_id"]), username)
    return jsonify({"token": token, "username": username})


# =====================
# Card APIs
# =====================

@app.route("/api/cards", methods=["GET"])
@token_required
def get_cards():
    cards = get_user_cards(request.user_id)
    return jsonify({"cards": cards})


@app.route("/api/cards/add", methods=["POST"])
@token_required
def add_card_api():
    data = request.json or {}

    card_id = data.get("card_id")
    score = data.get("score")
    first_date = data.get("first_date")

    if not card_id or score is None or not first_date:
        return jsonify({"error": "missing fields"}), 400

    if get_card(request.user_id, card_id):
        return jsonify({"error": "card exists"}), 400

    review_date = datetime.strptime(first_date, "%Y-%m-%d")

    card = SM2Card(card_id, first_date)
    card.review(score, review_date)

    add_card(request.user_id, {
        "card_id": card.card_id,
        "first_date": card.first_date,
        "ef": card.ef,
        "n": card.n,
        "interval": card.interval,
        "next_review": card.next_review.strftime("%Y-%m-%d"),
        "review_count": card.review_count,
        "tags": [],
        "note": "",
        "images": []
    })

    return jsonify({"message": "added"})


@app.route("/api/cards/review", methods=["POST"])
@token_required
def review_card():
    data = request.json or {}
    card_id = data.get("card_id")
    score = data.get("score")

    card_data = get_card(request.user_id, card_id)
    if not card_data:
        return jsonify({"error": "not found"}), 404

    card = SM2Card(card_data["card_id"], card_data["first_date"])
    card.ef = card_data["ef"]
    card.n = card_data["n"]
    card.interval = card_data["interval"]
    card.review_count = card_data["review_count"]

    card.review(score, datetime.utcnow())

    update_card(request.user_id, card_id, {
        "ef": card.ef,
        "n": card.n,
        "interval": card.interval,
        "next_review": card.next_review.strftime("%Y-%m-%d"),
        "review_count": card.review_count
    })

    return jsonify({"message": "reviewed"})


@app.route("/api/cards/<card_id>", methods=["DELETE"])
@token_required
def delete_card_api(card_id):
    if delete_card(request.user_id, card_id):
        return jsonify({"message": "deleted"})
    return jsonify({"error": "not found"}), 404


# =====================
# Entry
# =====================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
