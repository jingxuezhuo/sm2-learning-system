from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from auth import hash_password, check_password, generate_token, token_required
from db import (
    get_user_by_username, create_user, get_user_cards, 
    add_card, update_card, delete_card, get_card, cards_collection
)
from sm2_card import SM2Card

load_dotenv()

app = Flask(__name__)

CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)


UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== 用户认证 API ====================

@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return resp


@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    if len(password) < 6:
        return jsonify({'error': '密码至少 6 位'}), 400
    
    existing_user = get_user_by_username(username)
    if existing_user:
        return jsonify({'error': '用户名已存在'}), 400
    
    password_hash = hash_password(password)
    user_id = create_user(username, password_hash)
    token = generate_token(user_id, username)
    
    return jsonify({
        'message': '注册成功',
        'token': token,
        'username': username
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    user = get_user_by_username(username)
    if not user:
        return jsonify({'error': '用户名或密码错误'}), 401
    
    if not check_password(password, user['password']):
        return jsonify({'error': '用户名或密码错误'}), 401
    
    token = generate_token(str(user['_id']), username)
    
    return jsonify({
        'message': '登录成功',
        'token': token,
        'username': username
    })

# ==================== 卡片 API ====================

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
                next_review = datetime.strptime(next_review, '%Y-%m-%d')
            if next_review.date() <= today.date():
                due_today += 1
    
    return jsonify({'total_cards': total_cards, 'due_today': due_today})

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
            'ef': card.get('ef', 2.5),
            'n': card.get('n', 0),
            'interval': card.get('interval', 0),
            'next_review': card.get('next_review'),
            'review_count': card.get('review_count', 0),
            'tags': card.get('tags', []),
            'note': card.get('note', ''),
            'images': card.get('images', [])
        })
    
    return jsonify({'cards': cards_data})

@app.route('/api/cards/due', methods=['POST'])
@token_required
def get_due_cards():
    user_id = request.user_id
    data = request.json
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': '日期格式错误'}), 400
    
    cards = get_user_cards(user_id)
    due_cards = []
    
    for card_data in cards:
        next_review = card_data.get('next_review')
        if next_review:
            if isinstance(next_review, str):
                next_review_date = datetime.strptime(next_review, '%Y-%m-%d')
            else:
                next_review_date = next_review
            
            if next_review_date.date() <= target_date.date():
                due_cards.append({
                    'card_id': card_data['card_id'],
                    'name': card_data.get('name', ''),
                    'first_date': card_data['first_date'],
                    'review_count': card_data.get('review_count', 0),
                    'next_review': card_data.get('next_review'),
                    'tags': card_data.get('tags', []),
                    'note': card_data.get('note', ''),
                    'images': card_data.get('images', [])
                })
    
    return jsonify({'date': date_str, 'count': len(due_cards), 'cards': due_cards})

@app.route('/api/cards/add', methods=['POST'])
@token_required
def add_card_api():
    user_id = request.user_id
    data = request.json
    card_id = data.get('card_id')
    first_date = data.get('first_date')
    score = data.get('score')
    name = data.get('name', '')
    tags = data.get('tags', [])
    
    if not card_id or not first_date or score is None:
        return jsonify({'error': '缺少必要参数'}), 400
    
    if not (0 <= score <= 5):
        return jsonify({'error': '评分必须在 0-5 之间'}), 400
    
    existing = get_card(user_id, card_id)
    if existing:
        return jsonify({'error': '卡片已存在'}), 400
    
    try:
        review_date = datetime.strptime(first_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': '日期格式错误'}), 400
    
    card = SM2Card(card_id, first_date)
    card.name = name
    card.tags = tags
    card.review(score, review_date)
    
    card_data = {
        'card_id': card.card_id,
        'name': card.name,
        'first_date': card.first_date,
        'ef': card.ef,
        'n': card.n,
        'interval': card.interval,
        'next_review': card.next_review.strftime('%Y-%m-%d') if card.next_review else None,
        'review_count': card.review_count,
        'tags': card.tags,
        'note': '',
        'images': []
    }
    
    add_card(user_id, card_data)
    
    return jsonify({
        'message': '添加成功',
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
    data = request.json
    card_id = data.get('card_id')
    score = data.get('score')
    review_date_str = data.get('review_date', datetime.now().strftime('%Y-%m-%d'))
    
    if not card_id or score is None:
        return jsonify({'error': '缺少必要参数'}), 400
    
    if not (0 <= score <= 5):
        return jsonify({'error': '评分必须在 0-5 之间'}), 400
    
    try:
        review_date = datetime.strptime(review_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': '日期格式错误'}), 400
    
    card_data = get_card(user_id, card_id)
    if not card_data:
        return jsonify({'error': '卡片不存在'}), 404
    
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
        'review_count': card.review_count
    }
    
    update_card(user_id, card_id, updates)
    
    return jsonify({
        'message': '复习成功',
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
    data = request.json
    cards = data.get('cards', [])
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': '日期格式错误'}), 400
    
    added = []
    reviewed = []
    
    for item in cards:
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
                'review_count': card.review_count
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
                'ef': card.ef,
                'n': card.n,
                'interval': card.interval,
                'next_review': card.next_review.strftime('%Y-%m-%d'),
                'review_count': card.review_count,
                'tags': [],
                'note': '',
                'images': []
            }
            add_card(user_id, card_data)
            added.append({'card_id': card_id})
    
    return jsonify({'added': added, 'reviewed': reviewed, 'errors': []})

@app.route('/api/cards/update', methods=['POST'])
@token_required
def update_card_api():
    user_id = request.user_id
    data = request.json
    card_id = data.get('card_id')
    
    if not card_id:
        return jsonify({'error': '缺少卡片ID'}), 400
    
    card_data = get_card(user_id, card_id)
    if not card_data:
        return jsonify({'error': '卡片不存在'}), 404
    
    updates = {}
    if 'name' in data:
        updates['name'] = data['name']
    if 'tags' in data:
        updates['tags'] = data['tags']
    if 'note' in data:
        updates['note'] = data['note']
    
    update_card(user_id, card_id, updates)
    
    return jsonify({'message': '更新成功'})

@app.route('/api/tags', methods=['GET'])
@token_required
def get_all_tags():
    user_id = request.user_id
    cards = get_user_cards(user_id)
    all_tags = set()
    for card in cards:
        all_tags.update(card.get('tags', []))
    return jsonify({'tags': sorted(list(all_tags))})

@app.route('/api/upload', methods=['POST'])
@token_required
def upload_image():
    user_id = request.user_id
    
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    
    file = request.files['file']
    card_id = request.form.get('card_id')
    
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400
    
    card_data = get_card(user_id, card_id)
    if not card_data:
        return jsonify({'error': '卡片不存在'}), 404
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{user_id}_{card_id}_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        images = card_data.get('images', [])
        images.append(filename)
        update_card(user_id, card_id, {'images': images})
        
        return jsonify({'message': '上传成功', 'filename': filename})
    
    return jsonify({'error': '文件格式不支持'}), 400

@app.route('/api/images/<filename>')
def get_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/cards/<card_id>', methods=['DELETE'])
@token_required
def delete_card_api(card_id):
    user_id = request.user_id
    success = delete_card(user_id, card_id)
    
    if success:
        return jsonify({'message': '删除成功'})
    else:
        return jsonify({'error': '卡片不存在'}), 404

if __name__ == '__main__':
    print("=" * 50)
    print("SM-2 学习系统后端已启动（多用户版本）")
    print("访问地址: http://localhost:5001")
    print("=" * 50)
    app.run(debug=True, port=5001)