import sqlite3
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, g, send_from_directory

app = Flask(__name__, static_folder='static', static_url_path='')

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lost_found.db')

STATUS_OPEN = 'open'
STATUS_CLAIMED = 'claimed'
STATUS_CLOSED = 'closed'

TYPE_LOST = 'lost'
TYPE_FOUND = 'found'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            item_type TEXT NOT NULL CHECK(item_type IN ('lost', 'found')),
            location TEXT NOT NULL,
            event_time TEXT NOT NULL,
            contact TEXT NOT NULL,
            image_url TEXT,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'claimed', 'closed')),
            claimer_name TEXT,
            claimer_contact TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def row_to_dict(row):
    return {
        'id': row['id'],
        'title': row['title'],
        'description': row['description'],
        'item_type': row['item_type'],
        'location': row['location'],
        'event_time': row['event_time'],
        'contact': row['contact'],
        'image_url': row['image_url'],
        'status': row['status'],
        'claimer_name': row['claimer_name'],
        'claimer_contact': row['claimer_contact'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at']
    }


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/detail.html')
def detail():
    return send_from_directory('static', 'detail.html')


@app.route('/api/items', methods=['GET'])
def get_items():
    db = get_db()
    cursor = db.cursor()

    query = 'SELECT * FROM items WHERE 1=1'
    params = []

    keyword = request.args.get('keyword', '').strip()
    if keyword:
        query += ' AND (title LIKE ? OR description LIKE ? OR location LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like])

    location = request.args.get('location', '').strip()
    if location:
        query += ' AND location = ?'
        params.append(location)

    item_type = request.args.get('type', '').strip()
    if item_type:
        query += ' AND item_type = ?'
        params.append(item_type)

    status = request.args.get('status', '').strip()
    if status:
        query += ' AND status = ?'
        params.append(status)

    query += ' ORDER BY created_at DESC'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    items = [row_to_dict(r) for r in rows]

    cursor.execute('SELECT DISTINCT location FROM items ORDER BY location')
    locations = [r['location'] for r in cursor.fetchall()]

    return jsonify({
        'items': items,
        'locations': locations
    })


@app.route('/api/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': 'Item not found'}), 404
    return jsonify(row_to_dict(row))


@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.get_json(force=True)

    required = ['title', 'item_type', 'location', 'event_time', 'contact']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    if data['item_type'] not in (TYPE_LOST, TYPE_FOUND):
        return jsonify({'error': 'Invalid item_type, must be lost or found'}), 400

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO items (title, description, item_type, location, event_time,
                          contact, image_url, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['title'],
        data.get('description', ''),
        data['item_type'],
        data['location'],
        data['event_time'],
        data['contact'],
        data.get('image_url', ''),
        STATUS_OPEN,
        now,
        now
    ))
    db.commit()
    item_id = cursor.lastrowid

    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    return jsonify(row_to_dict(row)), 201


@app.route('/api/items/<int:item_id>/status', methods=['PUT'])
def update_status(item_id):
    data = request.get_json(force=True)
    new_status = data.get('status')

    if new_status not in (STATUS_OPEN, STATUS_CLAIMED, STATUS_CLOSED):
        return jsonify({'error': 'Invalid status'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': 'Item not found'}), 404

    current_status = row['status']

    if current_status == STATUS_CLOSED:
        return jsonify({'error': 'Closed item cannot be updated'}), 400

    if new_status == STATUS_CLAIMED and current_status != STATUS_OPEN:
        return jsonify({'error': 'Only open items can be claimed'}), 400

    if new_status == STATUS_CLOSED and current_status not in (STATUS_OPEN, STATUS_CLAIMED):
        return jsonify({'error': 'Invalid status transition'}), 400

    claimer_name = data.get('claimer_name', row['claimer_name'])
    claimer_contact = data.get('claimer_contact', row['claimer_contact'])

    if new_status == STATUS_CLAIMED:
        claimer_name = data.get('claimer_name')
        claimer_contact = data.get('claimer_contact')
        if not claimer_name or not claimer_contact:
            return jsonify({'error': 'claimer_name and claimer_contact required for claiming'}), 400

    if new_status == STATUS_OPEN:
        claimer_name = None
        claimer_contact = None

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        UPDATE items SET status = ?, claimer_name = ?, claimer_contact = ?, updated_at = ?
        WHERE id = ?
    ''', (new_status, claimer_name, claimer_contact, now, item_id))
    db.commit()

    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    return jsonify(row_to_dict(row))


@app.route('/api/locations', methods=['GET'])
def get_locations():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT DISTINCT location FROM items ORDER BY location')
    rows = cursor.fetchall()
    return jsonify([r['location'] for r in rows])


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
