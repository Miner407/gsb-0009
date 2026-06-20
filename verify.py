import json
import sys
import os
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

API_BASE = 'http://127.0.0.1:5000/api'


def encode_url(path):
    parsed = urlparse(API_BASE + path)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    new_qs = {}
    for k, v in qs.items():
        new_qs[k] = v
    new_query = urlencode(new_qs, doseq=True)
    return urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, new_query, parsed.fragment
    ))

PASS = 0
FAIL = 0


def section(name):
    print('\n' + '=' * 70)
    print(f'  {name}')
    print('=' * 70)


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


def post_json(path, payload):
    import urllib.request
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        encode_url(path),
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        return e.code, json.loads(body) if body else {}


def put_json(path, payload):
    import urllib.request
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        encode_url(path),
        data=data,
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        return e.code, json.loads(body) if body else {}


def get_json(path):
    import urllib.request
    req = urllib.request.Request(encode_url(path), method='GET')
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        return e.code, json.loads(body) if body else {}


def wait_for_server(timeout=15):
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


def run_tests():
    global PASS, FAIL
    PASS = FAIL = 0

    print('\n' + '#' * 70)
    print('#  校园失物招领看板 - 三条主链路验证')
    print('#  发布链路 / 认领链路 / 关闭链路')
    print('#' * 70)

    if not wait_for_server():
        print('\n\033[31m  无法连接到服务器，请确认 app.py 已启动在 5000 端口\033[0m\n')
        sys.exit(1)

    ids = {}

    # ================================
    # 链路 1: 发布
    # ================================
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

    step('发布失物信息（钱包）')
    status, resp = post_json('/items', lost_payload)
    ids['lost'] = resp.get('id')
    check_equal(status, 201, 'HTTP status')
    check(resp.get('id') is not None, f'id={resp.get("id")}')
    check_equal(resp.get('status'), 'open', 'status')
    check_equal(resp.get('title'), lost_payload['title'], 'title')
    check_equal(resp.get('item_type'), 'lost', 'item_type')
    check_equal(resp.get('location'), lost_payload['location'], 'location')

    found_payload = {
        'title': '蓝色学生卡套',
        'description': '蓝色透明卡套，内有学生证和校园卡，姓名首字母 L',
        'item_type': 'found',
        'location': '一食堂二楼',
        'event_time': '2026-06-20 12:10',
        'contact': '13900139000',
        'image_url': ''
    }

    step('发布招领信息（学生卡套）')
    status, resp = post_json('/items', found_payload)
    ids['found'] = resp.get('id')
    check_equal(status, 201, 'HTTP status')
    check(resp.get('id') is not None, f'id={resp.get("id")}')
    check_equal(resp.get('status'), 'open', 'status')
    check_equal(resp.get('item_type'), 'found', 'item_type')

    step('发布不完整信息应被拒绝')
    bad_payload = {'title': 'test', 'item_type': 'lost'}
    status, resp = post_json('/items', bad_payload)
    check(status >= 400, f'HTTP {status} (拒绝)', f'HTTP {status} (应拒绝)')

    step('发布非法 item_type 应被拒绝')
    bad2 = {'title': 'test', 'item_type': 'xxx', 'location': 'L', 'event_time': 'T', 'contact': 'C'}
    status, resp = post_json('/items', bad2)
    check(status >= 400, f'HTTP {status} (拒绝)', f'HTTP {status} (应拒绝)')

    step('列表接口能获取刚发布的信息')
    status, resp = get_json('/items')
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
    status, resp = get_json('/items?keyword=钱包')
    check_equal(status, 200, 'HTTP status')
    items_k = resp.get('items', [])
    check(len(items_k) >= 1 and all('钱包' in f"{i['title']}{i.get('description','')}{i['location']}" for i in items_k),
          f'返回 {len(items_k)} 条，均含关键词')

    step('地点筛选（"图书馆三楼自习区"）')
    status, resp = get_json('/items?location=图书馆三楼自习区')
    check_equal(status, 200, 'HTTP status')
    items_l = resp.get('items', [])
    check(len(items_l) >= 1 and all(i['location'] == '图书馆三楼自习区' for i in items_l),
          f'返回 {len(items_l)} 条，地点正确')

    step('类型筛选（仅招领 found）')
    status, resp = get_json('/items?type=found')
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
        'claimer_contact': '15800158000'
    })
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('status'), 'claimed', 'status=claimed')
    check_equal(resp.get('claimer_name'), '王同学', 'claimer_name')
    check_equal(resp.get('claimer_contact'), '15800158000', 'claimer_contact')

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
    status, resp = get_json('/items?status=claimed')
    check_equal(status, 200, 'HTTP status')
    items_s = resp.get('items', [])
    check(len(items_s) >= 1 and all(i['status'] == 'claimed' for i in items_s),
          f'返回 {len(items_s)} 条，均为已认领')

    # ================================
    # 链路 3: 关闭
    # ================================
    section('链路三：关闭信息')

    step('关闭已认领的失物')
    status, resp = put_json(f'/items/{ids["lost"]}/status', {'status': 'closed'})
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('status'), 'closed', 'status=closed')

    step('详情中能看到关闭状态')
    status, resp = get_json(f'/items/{ids["lost"]}')
    check_equal(status, 200, 'HTTP status')
    check_equal(resp.get('status'), 'closed', 'status=closed persisted')

    step('直接关闭开放中的招领（无需先认领）')
    status, resp = put_json(f'/items/{ids["found"]}/status', {'status': 'closed'})
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

    # ================================
    # 汇总
    # ================================
    section('验证结果汇总')
    total = PASS + FAIL
    print(f'\n  总检查项: {total}')
    print(f'  \033[32m通过: {PASS}\033[0m')
    print(f'  \033[31m失败: {FAIL}\033[0m')
    print(f'  通过率: {PASS * 100 // total if total else 0}%')
    print()

    if FAIL == 0:
        print('  \033[32m✓✓✓ 三条主链路全部验证通过！ ✓✓✓\033[0m\n')
    else:
        print('  \033[31m✗✗✗ 存在失败项，请检查 ✗✗✗\033[0m\n')
        sys.exit(1)


if __name__ == '__main__':
    run_tests()
