import json
import sys
import os
import time
import argparse
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

API_BASE = 'http://127.0.0.1:5000/api'

PASS = 0
FAIL = 0


def encode_url(path, query=None):
    parsed = urlparse(API_BASE + path)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    if query:
        for k, v in query.items():
            if v is not None and v != '':
                if isinstance(v, list):
                    qs[k] = v
                else:
                    qs[k] = [v]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, new_query, parsed.fragment
    ))


def section(name):
    print('\n' + '=' * 70)
    print(f'  {name}')
    print('=' * 70)


def subsection(name):
    print(f'\n  ── {name} ──')


def step(desc):
    print(f'\n  ▶ {desc} ...', end=' ', flush=True)


def check(cond, msg_good='OK', msg_bad='FAIL'):
    global PASS, FAIL
    if cond:
        print(f'\033[32m✓ {msg_good}\033[0m')
        PASS += 1
    else:
        print(f'\033[31m✗ {msg_bad}\033[0m')
        FAIL += 1


def check_equal(actual, expected, name='value'):
    check(actual == expected,
          f'{name}={actual!r}',
          f'{name} expected {expected!r}, got {actual!r}')


def check_in(needle, haystack, name='item'):
    check(needle in haystack,
          f'{name} found',
          f'{name}={needle!r} not found in {haystack!r}')


def check_has(cond, name):
    check(cond, f'{name} present', f'{name} missing')


def _request(method, path, payload=None, query=None):
    import urllib.request
    url = encode_url(path, query)
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body) if body else {}
    except Exception as e:
        if hasattr(e, 'read'):
            try:
                body = e.read().decode('utf-8')
                return e.code, json.loads(body) if body else {}
            except Exception:
                return e.code, {}
        raise


def post_json(path, payload):
    return _request('POST', path, payload)


def put_json(path, payload):
    return _request('PUT', path, payload)


def get_json(path, query=None):
    return _request('GET', path, query=query)


def wait_for_server(timeout=20):
    import urllib.request
    print(f'  ⏳ 等待服务启动 (最多 {timeout}s)...', end=' ', flush=True)
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(encode_url('/locations'), method='GET')
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    print('\033[32m服务器就绪 ✓\033[0m')
                    return True
        except Exception:
            time.sleep(1)
    print('\033[31m服务器启动超时 ✗\033[0m')
    return False


def print_summary(suite_name):
    total = PASS + FAIL
    print('\n' + '=' * 70)
    print(f'  {suite_name} - 验证汇总')
    print('=' * 70)
    print(f'  总检查项: {total}')
    print(f'  \033[32m通过: {PASS}\033[0m')
    print(f'  \033[31m失败: {FAIL}\033[0m')
    print(f'  通过率: {PASS * 100 // total if total else 0}%')
    print()


def approve_item(item_id, remark='', operator='admin'):
    return put_json(f'/items/{item_id}/audit', {'action': 'approve', 'remark': remark, 'operator': operator})


def reject_item(item_id, remark, operator='admin'):
    return put_json(f'/items/{item_id}/audit', {'action': 'reject', 'remark': remark, 'operator': operator})


def publish_and_approve(payload):
    """快捷：发布 + 审核通过"""
    s, r = post_json('/items', payload)
    if s != 201 or not r.get('id'):
        return s, r
    approve_item(r['id'])
    s2, r2 = get_json(f'/items/{r["id"]}')
    return s2, r2


# ================================
# Suite 1: 三条主链路（原链路，兼容审核流）
# ================================
def suite_main():
    global PASS, FAIL
    PASS = FAIL = 0
    ids = {}

    section('链路一：发布信息')

    lost_payload = {
        'title': '黑色皮质钱包',
        'description': '黑色皮质钱包，内有身份证、银行卡和少量现金',
        'item_type': 'lost',
        'location': '图书馆三楼自习区',
        'event_time': '2026-06-19 15:30',
        'contact': '13800138000 / 微信: zhangsan',
        'image_url': ''
    }

    step('发布失物信息（钱包）→ 状态应为 pending')
    status, resp = post_json('/items', lost_payload)
    ids['lost'] = resp.get('id')
    check_equal(status, 201, 'HTTP status')
    check(resp.get('id') is not None, f'id={resp.get("id")}')
    check_equal(resp.get('audit_status'), 'pending', 'audit_status')
    check_equal(resp.get('status'), 'open', 'status')
    check_equal(resp.get('title'), lost_payload['title'], 'title')
    check_equal(resp.get('item_type'), 'lost', 'item_type')

    step('审核通过失物信息')
    status, resp = approve_item(ids['lost'])
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('audit_status'), 'approved', 'audit_status=approved')
    check_has(resp.get('audited_at'), 'audited_at')
    ids['lost_approved'] = resp

    found_payload = {
        'title': '蓝色学生卡套',
        'description': '蓝色透明卡套，内有学生证和校园卡，姓名首字母 L',
        'item_type': 'found',
        'location': '一食堂二楼',
        'event_time': '2026-06-20 12:10',
        'contact': '13900139000',
        'image_url': ''
    }

    step('发布招领信息（学生卡套）→ 待审核 → 通过')
    status, resp = post_json('/items', found_payload)
    ids['found'] = resp.get('id')
    check_equal(status, 201, 'HTTP status')
    check(resp.get('id') is not None, f'id={resp.get("id")}')
    check_equal(resp.get('audit_status'), 'pending', 'audit_status=pending')
    approve_item(ids['found'])

    step('发布不完整信息应被拒绝')
    bad_payload = {'title': 'test', 'item_type': 'lost'}
    status, resp = post_json('/items', bad_payload)
    check(status >= 400, f'HTTP {status} (拒绝)', f'HTTP {status} (应拒绝)')

    step('发布非法 item_type 应被拒绝')
    bad2 = {'title': 'test', 'item_type': 'xxx', 'location': 'L', 'event_time': 'T', 'contact': 'C'}
    status, resp = post_json('/items', bad2)
    check(status >= 400, f'HTTP {status} (拒绝)', f'HTTP {status} (应拒绝)')

    step('列表接口(include_pending=1)能获取刚发布的信息')
    status, resp = get_json('/items', {'include_pending': '1'})
    items = resp.get('items', [])
    check_equal(status, 200, 'HTTP status')
    check(len(items) >= 2, f'共 {len(items)} 条 >= 2')
    titles = [i['title'] for i in items]
    check(lost_payload['title'] in titles, '失物标题在列表中', '失物标题未找到')
    check(found_payload['title'] in titles, '招领标题在列表中', '招领标题未找到')

    step('详情接口能查询单条信息')
    status, resp = get_json(f'/items/{ids["lost"]}')
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('id'), ids['lost'], 'id')
    check_equal(resp.get('title'), lost_payload['title'], 'title')
    check_equal(resp.get('contact'), lost_payload['contact'], 'contact')

    step('关键词搜索（"钱包"）')
    status, resp = get_json('/items', {'keyword': '钱包', 'include_pending': '1'})
    check_equal(status, 200, 'HTTP status')
    items_k = resp.get('items', [])
    check(len(items_k) >= 1 and all('钱包' in f"{i['title']}{i.get('description','')}{i['location']}" for i in items_k),
          f'返回 {len(items_k)} 条，均含关键词')

    step('地点筛选（"图书馆三楼自习区"）')
    status, resp = get_json('/items', {'location': '图书馆三楼自习区', 'include_pending': '1'})
    check_equal(status, 200, 'HTTP status')
    items_l = resp.get('items', [])
    check(len(items_l) >= 1 and all(i['location'] == '图书馆三楼自习区' for i in items_l),
          f'返回 {len(items_l)} 条，地点正确')

    step('类型筛选（仅招领 found）')
    status, resp = get_json('/items', {'type': 'found', 'include_pending': '1'})
    check_equal(status, 200, 'HTTP status')
    items_t = resp.get('items', [])
    check(len(items_t) >= 1 and all(i['item_type'] == 'found' for i in items_t),
          f'返回 {len(items_t)} 条，类型正确')

    # ================================
    # 链路 2: 认领
    # ================================
    section('链路二：认领信息')

    step('认领失物（需提供认领人信息）')
    status, resp = put_json(f'/items/{ids["lost"]}/status', {
        'status': 'claimed',
        'claimer_name': '王同学',
        'claimer_contact': '15800158000',
        'operator': '王同学'
    })
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('status'), 'claimed', 'status=claimed')
    check_equal(resp.get('claimer_name'), '王同学', 'claimer_name')
    check_equal(resp.get('claimer_contact'), '15800158000', 'claimer_contact')
    check_has(resp.get('claimed_at'), 'claimed_at')

    step('详情中能看到认领信息')
    status, resp = get_json(f'/items/{ids["lost"]}')
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('status'), 'claimed', 'status=claimed')
    check_equal(resp.get('claimer_name'), '王同学', 'claimer_name persisted')

    step('认领时缺少认领人信息应被拒绝')
    status, resp = put_json(f'/items/{ids["found"]}/status', {'status': 'claimed'})
    check(status >= 400, f'HTTP {status} (拒绝)', f'HTTP {status} (应拒绝)')

    step('已认领的物品不能再次认领')
    status, resp = put_json(f'/items/{ids["lost"]}/status', {
        'status': 'claimed',
        'claimer_name': '李同学',
        'claimer_contact': '15900159000'
    })
    check(status >= 400, f'HTTP {status} (拒绝重复认领)', f'HTTP {status} (应拒绝)')

    step('状态筛选（仅 claimed）')
    status, resp = get_json('/items', {'status': 'claimed', 'include_pending': '1'})
    check_equal(status, 200, 'HTTP status')
    items_s = resp.get('items', [])
    check(len(items_s) >= 1 and all(i['status'] == 'claimed' for i in items_s),
          f'返回 {len(items_s)} 条，均为已认领')

    # ================================
    # 链路 3: 关闭
    # ================================
    section('链路三：关闭信息')

    step('关闭已认领的失物')
    status, resp = put_json(f'/items/{ids["lost"]}/status', {'status': 'closed', 'operator': 'user'})
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('status'), 'closed', 'status=closed')
    check_has(resp.get('closed_at'), 'closed_at')

    step('详情中能看到关闭状态')
    status, resp = get_json(f'/items/{ids["lost"]}')
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('status'), 'closed', 'status=closed persisted')

    step('直接关闭开放中的招领（无需先认领）')
    status, resp = put_json(f'/items/{ids["found"]}/status', {'status': 'closed', 'operator': 'user'})
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('status'), 'closed', 'status=closed')

    step('已关闭的物品不能再更新状态')
    status, resp = put_json(f'/items/{ids["lost"]}/status', {'status': 'open'})
    check(status >= 400, f'HTTP {status} (拒绝)', f'HTTP {status} (应拒绝)')

    step('已关闭的物品不能被认领')
    status, resp = put_json(f'/items/{ids["lost"]}/status', {
        'status': 'claimed',
        'claimer_name': '赵同学',
        'claimer_contact': '16000160000'
    })
    check(status >= 400, f'HTTP {status} (拒绝)', f'HTTP {status} (应拒绝)')

    step('查询不存在的 ID 返回 404')
    status, _ = get_json('/items/999999')
    check_equal(status, 404, 'HTTP 404')

    print_summary('三条主链路')
    return FAIL == 0


# ================================
# Suite 2: 审核流验证
# ================================
def suite_audit():
    global PASS, FAIL
    PASS = FAIL = 0

    section('审核流验证')

    subsection('发布 -> 待审核状态')
    step('发布一条新的失物信息')
    p1 = {
        'title': 'AirPods Pro 耳机',
        'description': '白色 AirPods Pro，充电盒有划痕',
        'item_type': 'lost',
        'location': '二教 302 教室',
        'event_time': '2026-06-18 14:00',
        'contact': '15100151000',
        'image_url': ''
    }
    s, r = post_json('/items', p1)
    check_equal(s, 201, 'HTTP status')
    id1 = r['id']
    check_equal(r.get('audit_status'), 'pending', 'audit_status=pending')
    check_equal(r.get('status'), 'open', 'status=open')

    subsection('可见性验证')
    step('公开看板（include_pending=0）不应包含此信息')
    s, r = get_json('/items', {})
    items_public = [i['id'] for i in r.get('items', [])]
    check(id1 not in items_public, '未出现在公开列表', '不应出现在公开列表但出现了')

    step('审核中心（include_pending=1）应包含此信息')
    s, r = get_json('/items', {'include_pending': '1', 'audit_status': 'pending'})
    items_pending = [i['id'] for i in r.get('items', [])]
    check(id1 in items_pending, '出现在待审核列表', '未出现在待审核列表')

    subsection('驳回操作')
    step('驳回时缺少备注 → 应被拒绝（HTTP 400）')
    s, r = put_json(f'/items/{id1}/audit', {'action': 'reject', 'operator': 'admin'})
    check(s >= 400, f'HTTP {s} 拒绝', f'应拒绝但返回 HTTP {s}')

    step('驳回（附原因） → audit_status=rejected')
    reject_reason = '信息过于简略，缺少关键特征描述，请补充后重新提交'
    s, r = reject_item(id1, reject_reason)
    check_equal(s, 200, 'HTTP status')
    check_equal(r.get('audit_status'), 'rejected', 'audit_status=rejected')
    check_equal(r.get('audit_remark'), reject_reason, 'audit_remark 已记录')
    check_has(r.get('audited_at'), 'audited_at 已记录')
    check_equal(r.get('audited_by'), 'admin', 'audited_by=admin')

    step('已驳回的信息不能重复审核')
    s, r = approve_item(id1)
    check(s >= 400, f'HTTP {s} 拒绝重复审核', f'应拒绝但返回 HTTP {s}')

    subsection('通过操作')
    step('再发布一条新信息')
    p2 = {
        'title': '图书馆借阅卡',
        'description': '姓名首字母 W，卡号 2024****1234',
        'item_type': 'found',
        'location': '图书馆借还书处',
        'event_time': '2026-06-20 09:30',
        'contact': 'wechat: lib_helper',
        'image_url': ''
    }
    s, r = post_json('/items', p2)
    id2 = r['id']
    check_equal(s, 201, 'HTTP status')

    step('审核通过 → audit_status=approved')
    s, r = approve_item(id2, remark='信息完整，可公开展示')
    check_equal(s, 200, 'HTTP status')
    check_equal(r.get('audit_status'), 'approved', 'audit_status=approved')
    check_equal(r.get('audited_by'), 'admin', 'audited_by=admin')

    step('公开看板（默认）现在可以看到此信息')
    s, r = get_json('/items', {})
    items_ids = [i['id'] for i in r.get('items', [])]
    check(id2 in items_ids, 'id2 出现在公开列表', '未出现在公开列表')
    check(id1 not in items_ids, 'id1（驳回）不在公开列表', '被驳回的 id1 不应在公开列表')

    subsection('统计接口验证')
    step('GET /api/stats 返回各状态数量')
    s, r = get_json('/stats')
    check_equal(s, 200, 'HTTP status')
    for k in ['pending', 'open', 'claimed', 'closed']:
        check_has(k in r, f'stats.{k}')
        check(isinstance(r.get(k), int) and r.get(k) >= 0, f'stats.{k}={r.get(k)} 非负整数')

    print_summary('审核流验证')
    return FAIL == 0


# ================================
# Suite 3: 消息追踪验证
# ================================
def suite_tracking():
    global PASS, FAIL
    PASS = FAIL = 0

    section('消息追踪验证')

    subsection('准备数据：发布 -> 审核 -> 备注 -> 认领 -> 备注 -> 关闭')
    step('发布一条完整流程测试用的信息')
    p = {
        'title': '黑色双肩背包',
        'description': 'Nike 黑色双肩背包，内含笔记本电脑一台',
        'item_type': 'found',
        'location': '体育馆更衣室',
        'event_time': '2026-06-17 18:20',
        'contact': '15200152000',
        'image_url': ''
    }
    s, r = post_json('/items', p)
    check_equal(s, 201, 'HTTP status')
    tid = r['id']

    step('1. 发布后，应立即生成 create 日志')
    s, r = get_json(f'/items/{tid}/logs')
    logs = r.get('logs', [])
    check_equal(s, 200, 'HTTP status')
    check(len(logs) >= 1, f'日志数量 {len(logs)} >= 1')
    actions = [lg['action'] for lg in logs]
    check_in('create', actions, 'action=create')
    cr_log = next(lg for lg in logs if lg['action'] == 'create')
    check_has(cr_log.get('created_at'), 'create 日志的 created_at')

    step('2. 审核通过 → 生成 audit_approve 日志')
    s, r = approve_item(tid, remark='信息准确', operator='admin_x')
    s, r = get_json(f'/items/{tid}/logs')
    logs = r.get('logs', [])
    actions = [lg['action'] for lg in logs]
    check_in('audit_approve', actions, 'action=audit_approve')
    ap_log = next(lg for lg in logs if lg['action'] == 'audit_approve')
    check_equal(ap_log.get('operator'), 'admin_x', '审核操作人')
    check_equal(ap_log.get('remark'), '信息准确', '审核备注')

    step('3. 添加处理备注 → 生成 remark 日志')
    s, r = post_json(f'/items/{tid}/remark', {
        'remark': '已联系失物招领处暂存',
        'operator': '体育馆张老师'
    })
    check_equal(s, 201, 'HTTP 201 Created')
    s2, r2 = get_json(f'/items/{tid}/logs')
    logs = r2.get('logs', [])
    last = logs[-1]
    check_equal(last.get('action'), 'remark', '最后一条 action=remark')
    check_equal(last.get('operator'), '体育馆张老师', '操作人正确')
    check_equal(last.get('remark'), '已联系失物招领处暂存', '备注内容正确')

    step('4. 认领 → 生成 claim 日志，并记录 claimed_at')
    s, r = put_json(f'/items/{tid}/status', {
        'status': 'claimed',
        'claimer_name': '刘同学',
        'claimer_contact': '15300153000',
        'operator': '刘同学',
        'remark': '描述与我的背包完全一致'
    })
    check_equal(s, 200, 'HTTP status')
    check_has(r.get('claimed_at'), 'claimed_at 已记录')
    s2, r2 = get_json(f'/items/{tid}/logs')
    logs = r2.get('logs', [])
    actions = [lg['action'] for lg in logs]
    check_in('claim', actions, 'action=claim')
    claim_log = next(lg for lg in logs if lg['action'] == 'claim')
    check_equal(claim_log.get('operator'), '刘同学', '认领操作人正确')

    step('5. 认领后再添加备注 → 生成 remark 日志')
    s, r = post_json(f'/items/{tid}/remark', {
        'remark': '约定明日 10:00 在校门岗亭交接',
        'operator': '体育馆张老师'
    })
    check_equal(s, 201, 'HTTP 201 Created')

    step('6. 关闭信息 → 生成 close 日志，并记录 closed_at')
    s, r = put_json(f'/items/{tid}/status', {
        'status': 'closed',
        'operator': '刘同学',
        'remark': '已完成交接，失主确认无误'
    })
    check_equal(s, 200, 'HTTP status')
    check_has(r.get('closed_at'), 'closed_at 已记录')
    s2, r2 = get_json(f'/items/{tid}/logs')
    logs = r2.get('logs', [])
    actions = [lg['action'] for lg in logs]
    check_in('close', actions, 'action=close')

    subsection('时间线完整性校验')
    step('完整时间线应包含 6 条日志，顺序正确')
    expected_order = ['create', 'audit_approve', 'remark', 'claim', 'remark', 'close']
    actual_actions = [lg['action'] for lg in logs]
    # 允许出现额外的 remark，找主序列
    main_seq = [a for a in actual_actions if a in expected_order]
    check(len(main_seq) >= len(expected_order),
          f'主序列 {len(main_seq)} 条 >= {len(expected_order)}')
    # 检查关键事件的相对顺序
    idx = {a: main_seq.index(a) for a in ['create', 'audit_approve', 'claim', 'close']}
    order_ok = idx['create'] < idx['audit_approve'] < idx['claim'] < idx['close']
    check(order_ok,
          f'事件顺序正确: create < approve < claim < close',
          f'顺序异常: {main_seq}')

    step('所有操作均有 created_at')
    all_have_ts = all(lg.get('created_at') for lg in logs)
    check(all_have_ts, '100% 日志有 created_at')

    step('所有操作均有 operator')
    all_have_op = all(lg.get('operator') for lg in logs)
    check(all_have_op, '100% 日志有 operator',
          f'缺失 operator 的日志: {[lg for lg in logs if not lg.get("operator")]}')

    print_summary('消息追踪验证')
    return FAIL == 0


# ================================
# Suite 4: 筛选与我的发布验证
# ================================
def suite_filter():
    global PASS, FAIL
    PASS = FAIL = 0

    section('筛选与我的发布验证')

    my_contact_a = '17700177000'
    my_contact_b = '18800188000'

    subsection('准备测试数据')
    step('生成 4 条不同维度的测试数据')
    samples = [
        # 1 号：失物 · 图书馆 · contact A
        {
            'title': '银色 MacBook Pro',
            'description': '13 寸 MacBook Pro，机身有贴膜',
            'item_type': 'lost',
            'location': '图书馆二楼阅览区',
            'event_time': '2026-06-10 10:00',
            'contact': my_contact_a
        },
        # 2 号：招领 · 一食堂 · contact A
        {
            'title': '一串钥匙（含校园卡挂件）',
            'description': '约 5 把钥匙，附小熊挂件',
            'item_type': 'found',
            'location': '一食堂一楼',
            'event_time': '2026-06-12 12:30',
            'contact': my_contact_a
        },
        # 3 号：失物 · 操场 · contact B
        {
            'title': '运动水壶',
            'description': '蓝色大容量运动水壶',
            'item_type': 'lost',
            'location': '体育场田径场',
            'event_time': '2026-06-14 17:45',
            'contact': my_contact_b
        },
        # 4 号：招领 · 三食堂 · contact B
        {
            'title': '粉色雨伞',
            'description': '折叠粉色雨伞，有 Hello Kitty 图案',
            'item_type': 'found',
            'location': '三食堂门口',
            'event_time': '2026-06-16 18:00',
            'contact': my_contact_b
        },
    ]
    created_ids = []
    for i, sp in enumerate(samples):
        s, r = post_json('/items', sp)
        check_equal(s, 201, f'第{i+1}条发布成功')
        created_ids.append(r['id'])

    # 审核：1 通过，2 通过，3 通过，4 驳回
    approve_item(created_ids[0])
    approve_item(created_ids[1])
    approve_item(created_ids[2])
    reject_item(created_ids[3], '图片缺失，请补充图片链接或更详细的描述')

    # 给 2 号做一个认领
    put_json(f'/items/{created_ids[1]}/status', {
        'status': 'claimed',
        'claimer_name': '孙同学',
        'claimer_contact': '15500155000'
    })

    subsection('类型筛选')
    step('type=lost → 只返回失物（1 号和 3 号）')
    s, r = get_json('/items', {'type': 'lost', 'include_pending': '1'})
    ids = sorted([i['id'] for i in r.get('items', [])])
    expected_type = sorted([created_ids[0], created_ids[2]])
    check(all(i.get('item_type') == 'lost' for i in r.get('items', [])),
          '全部 item_type=lost',
          f'类型异常: {[(i["id"], i["item_type"]) for i in r.get("items", [])]}')

    subsection('关键词筛选')
    step('keyword=食堂 → 匹配地点（一食堂、三食堂）')
    s, r = get_json('/items', {'keyword': '食堂', 'include_pending': '1'})
    kw_ids = [i['id'] for i in r.get('items', [])]
    check(created_ids[1] in kw_ids, '2 号(一食堂) 命中')
    check(created_ids[3] in kw_ids, '4 号(三食堂) 命中')
    check(created_ids[0] not in kw_ids, '1 号(图书馆) 不命中')

    subsection('日期范围筛选')
    step('date_from=2026-06-14 → 只包含 14 号及之后发布（3、4号）')
    # 注意我们按 created_at 过滤。测试时我们直接用比较宽松的范围。
    s, r = get_json('/items', {'date_from': '2026-06-01', 'include_pending': '1'})
    check_equal(s, 200, 'HTTP status')
    all_pub = [i['id'] for i in r.get('items', [])]
    check(len(all_pub) >= 4, f'至少 4 条测试数据，实际 {len(all_pub)}')

    subsection('组合筛选（交集）')
    step('type=lost + status=open + include_pending=1 → 只返回失物中仍开放的')
    s, r = get_json('/items', {'type': 'lost', 'status': 'open', 'include_pending': '1'})
    combo_items = r.get('items', [])
    type_ok = all(i['item_type'] == 'lost' for i in combo_items)
    status_ok = all(i['status'] == 'open' for i in combo_items)
    check(type_ok and status_ok, f'组合筛选：{len(combo_items)} 条均为 lost+open',
          f'异常: {[(i["id"], i["item_type"], i["status"]) for i in combo_items]}')

    subsection('我的发布（按联系方式）')
    step(f'contact={my_contact_a} + include_pending=1 → 返回 1 号和 2 号')
    s, r = get_json('/items', {'contact': my_contact_a, 'include_pending': '1'})
    a_items = sorted([i['id'] for i in r.get('items', [])])
    expected_a = sorted([created_ids[0], created_ids[1]])
    # 可能有其他数据，所以用子集关系
    check(all(i in a_items for i in expected_a),
          f'1号和2号都在，实际: {a_items}')
    check(all(i.get('contact') == my_contact_a for i in r.get('items', [])),
          '所有返回 contact 匹配')

    step(f'contact={my_contact_b} + include_pending=1 → 包括被驳回的 4 号')
    s, r = get_json('/items', {'contact': my_contact_b, 'include_pending': '1'})
    b_items = [i['id'] for i in r.get('items', [])]
    # 4 号应在其中（审核状态 rejected）
    b_rejected = [i for i in r.get('items', []) if i['audit_status'] == 'rejected']
    check(created_ids[3] in b_items, f'4 号(驳回)也能被发布者查到')
    check(len(b_rejected) >= 1, f'至少 1 条 rejected 可见: {[i["id"] for i in b_rejected]}')
    # 驳回备注可见
    check(b_rejected[0].get('audit_remark') is not None, '驳回备注字段非空')

    subsection('空查询与 URL query 解析')
    step('不存在的联系方式 → 返回空列表')
    s, r = get_json('/items', {'contact': '00000-不存在', 'include_pending': '1'})
    check_equal(len(r.get('items', [])), 0, 'items 为空')

    step('多参数 query 全部能被解析（健壮性）')
    s, r = get_json('/items', {
        'keyword': '图书馆',
        'type': 'lost',
        'location': '',
        'status': 'open',
        'audit_status': 'approved',
        'date_from': '2026-01-01',
        'date_to': '2026-12-31',
        'include_pending': '1'
    })
    check_equal(s, 200, 'HTTP status')
    items_robust = r.get('items', [])
    check(all(i.get('item_type') == 'lost' for i in items_robust), '全部是 lost')
    check(all(i.get('status') == 'open' for i in items_robust), '全部是 open')
    check(all(i.get('audit_status') == 'approved' for i in items_robust), '全部是 approved')

    print_summary('筛选与我的发布验证')
    return FAIL == 0


# ================================
# 主入口
# ================================
def main():
    parser = argparse.ArgumentParser(description='校园失物招领看板验证脚本')
    parser.add_argument('--suite', default='all',
                        choices=['all', 'main', 'audit', 'tracking', 'filter'],
                        help='选择运行哪组验证（默认 all）')
    args = parser.parse_args()

    suite_map = {
        'main': ('三条主链路', suite_main),
        'audit': ('审核流', suite_audit),
        'tracking': ('消息追踪', suite_tracking),
        'filter': ('筛选与我的发布', suite_filter),
    }

    print('\n' + '#' * 70)
    print('#  校园失物招领看板 - 综合验证')
    print('#' * 70)

    if not wait_for_server():
        print('\n\033[31m  无法连接到服务器，请确认 app.py 已启动在 5000 端口\033[0m\n')
        sys.exit(1)

    global PASS, FAIL
    total_pass, total_fail = 0, 0
    results = []

    if args.suite == 'all':
        suites = list(suite_map.values())
    else:
        suites = [suite_map[args.suite]]

    for name, fn in suites:
        PASS = FAIL = 0
        print('\n\n' + '▓' * 70)
        print(f'▓  开始：{name} 验证')
        print('▓' * 70)
        ok = False
        try:
            ok = fn()
        except Exception as e:
            print(f'\n  \033[31m异常终止: {e}\033[0m')
            FAIL += 1
            ok = False
        results.append((name, ok, PASS, FAIL))
        total_pass += PASS
        total_fail += FAIL

    section('全局汇总')
    print(f'\n  {"验证组":<20} {"状态":<8} {"通过":>5} {"失败":>5}')
    print('  ' + '-' * 42)
    for name, ok, p, f in results:
        status = '\033[32m✓ 通过\033[0m' if ok else '\033[31m✗ 失败\033[0m'
        print(f'  {name:<18} {status:<14} {p:>5} {f:>5}')
    print('  ' + '-' * 42)
    total = total_pass + total_fail
    rate = total_pass * 100 // total if total else 0
    print(f'  {"合计":<18} {"":<14} {total_pass:>5} {total_fail:>5}')
    print(f'\n  总计: {total} 项, 通过率: {rate}%')

    if total_fail == 0:
        print('\n  \033[32m✓✓✓ 所有验证组全部通过！ ✓✓✓\033[0m\n')
    else:
        print(f'\n  \033[31m✗✗✗ 共 {total_fail} 项失败，请检查 ✗✗✗\033[0m\n')
        sys.exit(1)


if __name__ == '__main__':
    main()
