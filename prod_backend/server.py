from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from auth import hash_password, check_password, generate_token, token_required
from db import (
    get_user_by_username, create_user, get_user_cards,
    add_card, update_card, delete_card, get_card
)
from sm2_card import SM2Card

load_dotenv()

app = Flask(__name__)

# Environment configuration
ENV = os.getenv("ENV", "production")
PORT = int(os.getenv("PORT", 10000))
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# CORS configuration
frontend_origins = os.getenv("FRONTEND_ORIGIN", "").split(",")
if not frontend_origins or frontend_origins == ['']:
    frontend_origins = ["*"]

CORS(
    app,
    resources={r"/api/*": {"origins": frontend_origins}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== Health Check ====================

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'message': 'Spaced-Repetition Memory System API',
        'version': '2.0.0',
        'status': 'running'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

# ==================== Auth APIs ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    if get_user_by_username(username):
        return jsonify({'error': 'Username already exists'}), 400
    
    uid = create_user(username, hash_password(password))
    token = generate_token(uid, username)
    
    return jsonify({'token': token, 'username': username, 'message': 'Registration successful'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user = get_user_by_username(username)
    if not user or not check_password(password, user['password']):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    token = generate_token(str(user['_id']), username)
    return jsonify({'token': token, 'username': username, 'message': 'Login successful'})

# ==================== Stats API ====================

@app.route('/api/stats', methods=['GET'])
@token_required
def get_statistics():
    user_id = request.user_id
    cards = get_user_cards(user_id)
    total_cards = len(cards)
    
    today = datetime.now()
    due_today = 0
    for card_data in cards:
        next_review = card_data.get('next_review')
        if next_review:
            if isinstance(next_review, str):
                try:
                    next_review = datetime.strptime(next_review, '%Y-%m-%d')
                except:
                    continue
            if next_review.date() <= today.date():
                due_today += 1
    
    return jsonify({'total_cards': total_cards, 'due_today': due_today})

# ==================== Tags API ====================

@app.route('/api/tags', methods=['GET'])
@token_required
def get_all_tags():
    user_id = request.user_id
    cards = get_user_cards(user_id)
    all_tags = set()
    for card in cards:
        all_tags.update(card.get('tags', []))
    return jsonify({'tags': sorted(list(all_tags))})

# ==================== Cards APIs ====================

@app.route('/api/cards', methods=['GET'])
@token_required
def get_all_cards():
    user_id = request.user_id
    cards = get_user_cards(user_id)
    
    cards_data = []
    for card in cards:
        cards_data.append({
            'card_id': card['card_id'],
            'name': card.get('name', ''),
            'first_date': card['first_date'],
            'last_review_date': card.get('last_review_date', card['first_date']),
            'ef': card.get('ef', 2.5),
            'n': card.get('n', 0),
            'interval': card.get('interval', 0),
            'next_review': card.get('next_review'),
            'review_count': card.get('review_count', 0),
            'tags': card.get('tags', []),
            'note': card.get('note', ''),
            'images': card.get('images', []),
            'link': card.get('link', '')
        })
    
    return jsonify({'cards': cards_data})

@app.route('/api/cards/due', methods=['POST'])
@token_required
def get_due_cards():
    user_id = request.user_id
    data = request.json or {}
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    cards = get_user_cards(user_id)
    due_cards = []
    
    for card_data in cards:
        next_review = card_data.get('next_review')
        if next_review:
            if isinstance(next_review, str):
                try:
                    next_review_date = datetime.strptime(next_review, '%Y-%m-%d')
                except:
                    continue
            else:
                next_review_date = next_review
            
            if next_review_date.date() <= target_date.date():
                due_cards.append({
                    'card_id': card_data['card_id'],
                    'name': card_data.get('name', ''),
                    'first_date': card_data['first_date'],
                    'last_review_date': card_data.get('last_review_date', card_data['first_date']),
                    'review_count': card_data.get('review_count', 0),
                    'next_review': card_data.get('next_review'),
                    'tags': card_data.get('tags', []),
                    'note': card_data.get('note', ''),
                    'images': card_data.get('images', []),
                    'ef': card_data.get('ef', 2.5),
                    'interval': card_data.get('interval', 0),
                    'link': card_data.get('link', '')
                })
    
    return jsonify({'date': date_str, 'count': len(due_cards), 'cards': due_cards})

@app.route('/api/cards/add', methods=['POST'])
@token_required
def add_card_api():
    user_id = request.user_id
    data = request.json or {}
    
    card_id = data.get('card_id')
    first_date = data.get('first_date')
    score = data.get('score')
    name = data.get('name', '')
    tags = data.get('tags', [])
    link = data.get('link', '')
    
    if not card_id or not first_date or score is None:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if not (0 <= score <= 5):
        return jsonify({'error': 'Score must be between 0-5'}), 400
    
    if get_card(user_id, card_id):
        return jsonify({'error': 'Card already exists'}), 400
    
    try:
        review_date = datetime.strptime(first_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    card = SM2Card(card_id, first_date)
    card.name = name
    card.tags = tags
    card.review(score, review_date)
    
    card_data = {
        'card_id': card.card_id,
        'name': card.name,
        'first_date': card.first_date,
        'last_review_date': first_date,
        'ef': card.ef,
        'n': card.n,
        'interval': card.interval,
        'next_review': card.next_review.strftime('%Y-%m-%d') if card.next_review else None,
        'review_count': card.review_count,
        'tags': card.tags,
        'note': '',
        'images': [],
        'link': link
    }
    
    add_card(user_id, card_data)
    
    return jsonify({
        'message': 'Card added successfully',
        'card': {
            'card_id': card.card_id,
            'name': card.name,
            'next_review': card.next_review.strftime('%Y-%m-%d') if card.next_review else None
        }
    })

@app.route('/api/cards/review', methods=['POST'])
@token_required
def review_card_api():
    user_id = request.user_id
    data = request.json or {}
    card_id = data.get('card_id')
    score = data.get('score')
    review_date_str = data.get('review_date', datetime.now().strftime('%Y-%m-%d'))
    
    if not card_id or score is None:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if not (0 <= score <= 5):
        return jsonify({'error': 'Score must be between 0-5'}), 400
    
    try:
        review_date = datetime.strptime(review_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    card_data = get_card(user_id, card_id)
    if not card_data:
        return jsonify({'error': 'Card not found'}), 404
    
    card = SM2Card(card_data['card_id'], card_data['first_date'])
    card.ef = card_data.get('ef', 2.5)
    card.n = card_data.get('n', 0)
    card.interval = card_data.get('interval', 0)
    card.review_count = card_data.get('review_count', 0)
    
    card.review(score, review_date)
    
    updates = {
        'ef': card.ef,
        'n': card.n,
        'interval': card.interval,
        'next_review': card.next_review.strftime('%Y-%m-%d') if card.next_review else None,
        'review_count': card.review_count,
        'last_review_date': review_date_str
    }
    
    update_card(user_id, card_id, updates)
    
    return jsonify({
        'message': 'Review successful',
        'card': {
            'card_id': card.card_id,
            'next_review': card.next_review.strftime('%Y-%m-%d') if card.next_review else None,
            'review_count': card.review_count
        }
    })

@app.route('/api/cards/batch', methods=['POST'])
@token_required
def batch_add_cards():
    user_id = request.user_id
    data = request.json or {}
    cards_list = data.get('cards', [])
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    added = []
    reviewed = []
    
    for item in cards_list:
        card_id = item.get('card_id')
        score = item.get('score')
        
        if not card_id or score is None or not (0 <= score <= 5):
            continue
        
        existing = get_card(user_id, card_id)
        
        if existing:
            card = SM2Card(existing['card_id'], existing['first_date'])
            card.ef = existing.get('ef', 2.5)
            card.n = existing.get('n', 0)
            card.interval = existing.get('interval', 0)
            card.review_count = existing.get('review_count', 0)
            card.review(score, target_date)
            
            updates = {
                'ef': card.ef,
                'n': card.n,
                'interval': card.interval,
                'next_review': card.next_review.strftime('%Y-%m-%d'),
                'review_count': card.review_count,
                'last_review_date': date_str
            }
            update_card(user_id, card_id, updates)
            reviewed.append({'card_id': card_id})
        else:
            card = SM2Card(card_id, date_str)
            card.review(score, target_date)
            
            card_data = {
                'card_id': card.card_id,
                'name': '',
                'first_date': card.first_date,
                'last_review_date': date_str,
                'ef': card.ef,
                'n': card.n,
                'interval': card.interval,
                'next_review': card.next_review.strftime('%Y-%m-%d'),
                'review_count': card.review_count,
                'tags': [],
                'note': '',
                'images': [],
                'link': ''
            }
            add_card(user_id, card_data)
            added.append({'card_id': card_id})
    
    return jsonify({'added': added, 'reviewed': reviewed, 'errors': []})

@app.route('/api/cards/update', methods=['POST'])
@token_required
def update_card_api():
    user_id = request.user_id
    data = request.json or {}
    card_id = data.get('card_id')
    new_card_id = data.get('new_card_id')
    
    if not card_id:
        return jsonify({'error': 'Missing card ID'}), 400
    
    card_data = get_card(user_id, card_id)
    if not card_data:
        return jsonify({'error': 'Card not found'}), 404
    
    # Check if updating card_id and if new ID already exists
    if new_card_id and new_card_id != card_id:
        existing = get_card(user_id, new_card_id)
        if existing:
            return jsonify({'error': 'New card ID already exists'}), 400
    
    updates = {}
    if 'name' in data:
        updates['name'] = data['name']
    if 'tags' in data:
        updates['tags'] = data['tags']
    if 'note' in data:
        updates['note'] = data['note']
    if 'link' in data:
        updates['link'] = data['link']
    if new_card_id and new_card_id != card_id:
        updates['card_id'] = new_card_id
    
    update_card(user_id, card_id, updates)
    
    return jsonify({'message': 'Update successful'})

@app.route('/api/cards/<card_id>', methods=['DELETE'])
@token_required
def delete_card_api(card_id):
    user_id = request.user_id
    success = delete_card(user_id, card_id)
    
    if success:
        return jsonify({'message': 'Card deleted successfully'})
    else:
        return jsonify({'error': 'Card not found'}), 404

# ==================== File Upload APIs ====================

@app.route('/api/upload', methods=['POST'])
@token_required
def upload_image():
    user_id = request.user_id
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    card_id = request.form.get('card_id')
    
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    card_data = get_card(user_id, card_id)
    if not card_data:
        return jsonify({'error': 'Card not found'}), 404
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{user_id}_{card_id}_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        images = card_data.get('images', [])
        if not images:
            images = []
        images.append(filename)
        update_card(user_id, card_id, {'images': images})
        
        return jsonify({'message': 'Upload successful', 'filename': filename})
    
    return jsonify({'error': 'File format not supported'}), 400

@app.route('/api/images/<filename>')
def get_image(filename):
    try:
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception:
        return jsonify({'error': 'File not found'}), 404

# ==================== Entry Point ====================

if __name__ == '__main__':
    print("=" * 50)
    print("Spaced-Repetition Memory System Backend")
    print("Environment:", ENV)
    print("Port:", PORT)
    print("=" * 50)
    app.run(host="0.0.0.0", port=PORT, debug=(ENV != "production"))