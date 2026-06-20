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

AUDIT_PENDING = 'pending'
AUDIT_APPROVED = 'approved'
AUDIT_REJECTED = 'rejected'

LOG_ACTION_CREATE = 'create'
LOG_ACTION_AUDIT_APPROVE = 'audit_approve'
LOG_ACTION_AUDIT_REJECT = 'audit_reject'
LOG_ACTION_CLAIM = 'claim'
LOG_ACTION_CLOSE = 'close'
LOG_ACTION_REOPEN = 'reopen'
LOG_ACTION_REMARK = 'remark'


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


def migrate_db():
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

    existing_cols = [row[1] for row in cursor.execute('PRAGMA table_info(items)').fetchall()]

    new_cols = {
        'audit_status': "TEXT NOT NULL DEFAULT 'approved' CHECK(audit_status IN ('pending', 'approved', 'rejected'))",
        'audit_remark': 'TEXT',
        'audited_at': 'TEXT',
        'audited_by': 'TEXT',
        'claimed_at': 'TEXT',
        'closed_at': 'TEXT'
    }

    for col, definition in new_cols.items():
        if col not in existing_cols:
            cursor.execute(f'ALTER TABLE items ADD COLUMN {col} {definition}')

    cursor.execute('''
        UPDATE items SET audit_status = 'approved' WHERE audit_status IS NULL
    ''')
    cursor.execute('''
        UPDATE items SET audited_at = created_at WHERE audited_at IS NULL AND audit_status = 'approved'
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            operator TEXT DEFAULT 'system',
            remark TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()

    cursor.execute('SELECT id, created_at, status FROM items')
    rows = cursor.fetchall()
    for row in rows:
        item_id, created_at, status = row
        cursor.execute('SELECT COUNT(*) FROM audit_logs WHERE item_id = ?', (item_id,))
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute('''
                INSERT INTO audit_logs (item_id, action, operator, remark, created_at)
                VALUES (?, ?, 'system', '数据迁移时补录', ?)
            ''', (item_id, LOG_ACTION_CREATE, created_at))

            if status == STATUS_CLAIMED:
                cursor.execute('''
                    INSERT INTO audit_logs (item_id, action, operator, remark, created_at)
                    VALUES (?, ?, 'system', '数据迁移时补录', ?)
                ''', (item_id, LOG_ACTION_CLAIM, created_at))
            elif status == STATUS_CLOSED:
                cursor.execute('''
                    INSERT INTO audit_logs (item_id, action, operator, remark, created_at)
                    VALUES (?, ?, 'system', '数据迁移时补录', ?)
                ''', (item_id, LOG_ACTION_CLOSE, created_at))

    conn.commit()
    conn.close()


def init_db():
    migrate_db()


def add_log(cursor, item_id, action, operator='system', remark=None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO audit_logs (item_id, action, operator, remark, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (item_id, action, operator, remark, now))
    return now


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
        'audit_status': row['audit_status'],
        'audit_remark': row['audit_remark'],
        'audited_at': row['audited_at'],
        'audited_by': row['audited_by'],
        'claimed_at': row['claimed_at'],
        'closed_at': row['closed_at'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at']
    }


def log_row_to_dict(row):
    return {
        'id': row['id'],
        'item_id': row['item_id'],
        'action': row['action'],
        'operator': row['operator'],
        'remark': row['remark'],
        'created_at': row['created_at']
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

    include_pending = request.args.get('include_pending', '').strip().lower() in ('1', 'true', 'yes')

    query = 'SELECT * FROM items WHERE 1=1'
    params = []

    if not include_pending:
        query += " AND audit_status = 'approved'"

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

    audit_status = request.args.get('audit_status', '').strip()
    if audit_status:
        query += ' AND audit_status = ?'
        params.append(audit_status)

    contact = request.args.get('contact', '').strip()
    if contact:
        query += ' AND contact = ?'
        params.append(contact)

    date_from = request.args.get('date_from', '').strip()
    if date_from:
        query += ' AND date(created_at) >= date(?)'
        params.append(date_from)

    date_to = request.args.get('date_to', '').strip()
    if date_to:
        query += ' AND date(created_at) <= date(?)'
        params.append(date_to)

    query += ' ORDER BY created_at DESC'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    items = [row_to_dict(r) for r in rows]

    cursor.execute('SELECT DISTINCT location FROM items ORDER BY location')
    locations = [r['location'] for r in cursor.fetchall()]

    cursor.execute('SELECT DISTINCT audit_status FROM items ORDER BY audit_status')
    audit_statuses = [r['audit_status'] for r in cursor.fetchall()]

    return jsonify({
        'items': items,
        'locations': locations,
        'audit_statuses': audit_statuses
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
                          contact, image_url, status, audit_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['title'],
        data.get('description', ''),
        data['item_type'],
        data['location'],
        data['event_time'],
        data['contact'],
        data.get('image_url', ''),
        STATUS_OPEN,
        AUDIT_PENDING,
        now,
        now
    ))
    db.commit()
    item_id = cursor.lastrowid

    add_log(cursor, item_id, LOG_ACTION_CREATE, operator='user',
            remark=f"发布{TYPE_LOST == data['item_type'] and '失物' or '招领'}信息")
    db.commit()

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
    operator = data.get('operator', 'user')
    remark = data.get('remark')

    claimed_at = row['claimed_at']
    closed_at = row['closed_at']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if new_status == STATUS_CLAIMED:
        claimer_name = data.get('claimer_name')
        claimer_contact = data.get('claimer_contact')
        if not claimer_name or not claimer_contact:
            return jsonify({'error': 'claimer_name and claimer_contact required for claiming'}), 400
        claimed_at = now
        add_log(cursor, item_id, LOG_ACTION_CLAIM, operator=operator,
                remark=remark or f"认领人：{claimer_name}")

    if new_status == STATUS_CLOSED:
        closed_at = now
        add_log(cursor, item_id, LOG_ACTION_CLOSE, operator=operator,
                remark=remark or '关闭信息')

    if new_status == STATUS_OPEN:
        claimer_name = None
        claimer_contact = None
        claimed_at = None
        add_log(cursor, item_id, LOG_ACTION_REOPEN, operator=operator, remark=remark or '重新开放')

    cursor.execute('''
        UPDATE items SET status = ?, claimer_name = ?, claimer_contact = ?,
                       claimed_at = ?, closed_at = ?, updated_at = ?
        WHERE id = ?
    ''', (new_status, claimer_name, claimer_contact, claimed_at, closed_at, now, item_id))
    db.commit()

    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    return jsonify(row_to_dict(row))


@app.route('/api/items/<int:item_id>/audit', methods=['PUT'])
def audit_item(item_id):
    data = request.get_json(force=True)
    action = data.get('action')
    operator = data.get('operator', 'admin') or 'admin'
    remark = data.get('remark', '')

    if action not in ('approve', 'reject'):
        return jsonify({'error': 'Invalid audit action, must be approve or reject'}), 400

    if action == 'reject' and not remark:
        return jsonify({'error': 'Remark required for rejection'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': 'Item not found'}), 404

    if row['audit_status'] != AUDIT_PENDING:
        return jsonify({'error': 'Only pending items can be audited'}), 400

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_audit_status = AUDIT_APPROVED if action == 'approve' else AUDIT_REJECTED

    cursor.execute('''
        UPDATE items SET audit_status = ?, audit_remark = ?, audited_at = ?, audited_by = ?, updated_at = ?
        WHERE id = ?
    ''', (new_audit_status, remark, now, operator, now, item_id))

    log_action = LOG_ACTION_AUDIT_APPROVE if action == 'approve' else LOG_ACTION_AUDIT_REJECT
    add_log(cursor, item_id, log_action, operator=operator,
            remark=remark or (action == 'approve' and '审核通过' or remark))
    db.commit()

    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    return jsonify(row_to_dict(row))


@app.route('/api/items/<int:item_id>/logs', methods=['GET'])
def get_item_logs(item_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute('SELECT id FROM items WHERE id = ?', (item_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Item not found'}), 404

    cursor.execute('''
        SELECT * FROM audit_logs WHERE item_id = ? ORDER BY created_at ASC, id ASC
    ''', (item_id,))
    rows = cursor.fetchall()
    logs = [log_row_to_dict(r) for r in rows]
    return jsonify({'logs': logs})


@app.route('/api/items/<int:item_id>/remark', methods=['POST'])
def add_remark(item_id):
    data = request.get_json(force=True)
    remark = (data.get('remark') or '').strip()
    operator = data.get('operator', 'user') or 'user'

    if not remark:
        return jsonify({'error': 'Remark cannot be empty'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id FROM items WHERE id = ?', (item_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Item not found'}), 404

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    add_log(cursor, item_id, LOG_ACTION_REMARK, operator=operator, remark=remark)
    db.commit()

    cursor.execute('''
        SELECT * FROM audit_logs WHERE item_id = ? ORDER BY created_at DESC, id DESC LIMIT 1
    ''', (item_id,))
    row = cursor.fetchone()
    return jsonify(log_row_to_dict(row)), 201


@app.route('/api/locations', methods=['GET'])
def get_locations():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT DISTINCT location FROM items ORDER BY location')
    rows = cursor.fetchall()
    return jsonify([r['location'] for r in rows])


@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM items WHERE audit_status = 'pending'")
    pending_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE audit_status = 'approved' AND status = 'open'")
    open_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'claimed'")
    claimed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'closed'")
    closed_count = cursor.fetchone()[0]

    return jsonify({
        'pending': pending_count,
        'open': open_count,
        'claimed': claimed_count,
        'closed': closed_count
    })


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
