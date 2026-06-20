const API_BASE = '/api';

let currentView = 'public';
let allItems = [];
let allLocations = [];
let currentFilters = {
    keyword: '',
    type: '',
    location: '',
    status: '',
    audit_status: '',
    date_from: '',
    date_to: '',
    contact: ''
};
let myContact = '';
let pendingAuditItem = null;
let stats = { pending: 0, open: 0, claimed: 0, closed: 0 };

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
    const res = await fetch(API_BASE + path, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.error || `请求失败: ${res.status}`);
    }
    return data;
}

function showToast(msg, type = 'success') {
    const toast = $('toast');
    toast.className = `toast ${type} show`;
    const icons = { success: '✓', error: '✗', warning: '⚠' };
    toast.innerHTML = `<span>${icons[type] || '✓'}</span><span>${escapeHtml(msg)}</span>`;
    setTimeout(() => toast.classList.remove('show'), 3500);
}

function statusLabel(s) {
    return { open: '开放中', claimed: '已认领', closed: '已关闭' }[s] || s;
}

function auditLabel(s) {
    return { pending: '待审核', approved: '已通过', rejected: '已驳回' }[s] || s;
}

function actionLabel(a) {
    const map = {
        create: '发布',
        audit_approve: '审核通过',
        audit_reject: '审核驳回',
        claim: '认领',
        close: '关闭',
        reopen: '重新开放',
        remark: '添加备注'
    };
    return map[a] || a;
}

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s || '';
    return div.innerHTML;
}

function placeholderEmoji(t) {
    return t === 'lost' ? '😢' : '🎉';
}

/* ==================== URL Query 管理 ==================== */
function filtersToQuery() {
    const params = new URLSearchParams();
    if (currentView && currentView !== 'public') params.set('view', currentView);
    Object.entries(currentFilters).forEach(([k, v]) => {
        if (v && v.trim()) params.set(k, v.trim());
    });
    if (myContact) params.set('my_contact', myContact);
    const q = params.toString();
    return q ? `?${q}` : location.pathname;
}

function queryToFilters() {
    const params = new URLSearchParams(window.location.search);
    const view = params.get('view');
    if (['public', 'mine', 'audit'].includes(view)) currentView = view;

    Object.keys(currentFilters).forEach(k => {
        currentFilters[k] = params.get(k) || '';
    });
    myContact = params.get('my_contact') || '';
}

function updateUrl() {
    const newUrl = filtersToQuery();
    history.replaceState(null, '', newUrl);
}

/* ==================== 统计栏 ==================== */
function renderStats() {
    const bar = $('statsBar');
    bar.innerHTML = `
        <span class="stat-chip pending"><span class="stat-dot"></span>待审核 ${stats.pending}</span>
        <span class="stat-chip open"><span class="stat-dot"></span>开放中 ${stats.open}</span>
        <span class="stat-chip claimed"><span class="stat-dot"></span>已认领 ${stats.claimed}</span>
        <span class="stat-chip closed"><span class="stat-dot"></span>已关闭 ${stats.closed}</span>
    `;
    const auditTab = $('auditTab');
    if (auditTab) auditTab.setAttribute('data-count', stats.pending || '0');
}

async function loadStats() {
    try {
        stats = await api('/stats');
        renderStats();
    } catch (e) { /* ignore */ }
}

/* ==================== 筛选器 ==================== */
function renderFilters() {
    const container = $('filters');
    const mineOrAudit = currentView === 'mine' || currentView === 'audit';

    const auditFilterHtml = currentView === 'audit' ? `
        <div class="filter-field">
            <label>审核状态</label>
            <select data-filter="audit_status">
                <option value="">全部</option>
                <option value="pending" ${currentFilters.audit_status === 'pending' ? 'selected' : ''}>待审核</option>
                <option value="approved" ${currentFilters.audit_status === 'approved' ? 'selected' : ''}>已通过</option>
                <option value="rejected" ${currentFilters.audit_status === 'rejected' ? 'selected' : ''}>已驳回</option>
            </select>
        </div>
    ` : '';

    const fields = [
        {
            key: 'keyword',
            label: '关键词',
            html: `<input type="text" data-filter="keyword" placeholder="搜索物品名、描述、地点..." value="${escapeHtml(currentFilters.keyword)}">`
        },
        {
            key: 'type',
            label: '类型',
            html: `<select data-filter="type">
                <option value="">全部</option>
                <option value="lost" ${currentFilters.type === 'lost' ? 'selected' : ''}>失物</option>
                <option value="found" ${currentFilters.type === 'found' ? 'selected' : ''}>招领</option>
            </select>`
        },
        {
            key: 'location',
            label: '地点',
            html: `<select data-filter="location">
                <option value="">全部</option>
                ${allLocations.map(l => `<option value="${escapeHtml(l)}" ${currentFilters.location === l ? 'selected' : ''}>${escapeHtml(l)}</option>`).join('')}
            </select>`
        },
        {
            key: 'status',
            label: '状态',
            html: `<select data-filter="status">
                <option value="">全部</option>
                <option value="open" ${currentFilters.status === 'open' ? 'selected' : ''}>开放中</option>
                <option value="claimed" ${currentFilters.status === 'claimed' ? 'selected' : ''}>已认领</option>
                <option value="closed" ${currentFilters.status === 'closed' ? 'selected' : ''}>已关闭</option>
            </select>`
        },
        {
            key: 'date_from',
            label: '起始日期',
            html: `<input type="date" data-filter="date_from" value="${currentFilters.date_from}">`
        },
        {
            key: 'date_to',
            label: '截止日期',
            html: `<input type="date" data-filter="date_to" value="${currentFilters.date_to}">`
        }
    ];

    if (mineOrAudit) {
        fields.splice(3, 0, {
            key: 'audit_status_inject',
            label: '',
            html: auditFilterHtml
        });
    }

    container.innerHTML = fields.map(f => f.html).join('');

    container.querySelectorAll('[data-filter]').forEach(el => {
        const evt = el.tagName === 'INPUT' && el.type !== 'date' ? 'input' : 'change';
        el.addEventListener(evt, () => {
            const key = el.getAttribute('data-filter');
            if (key in currentFilters) {
                currentFilters[key] = el.value;
                updateUrl();
                loadItems(true);
            }
        });
    });
}

/* ==================== 卡片渲染 ==================== */
function renderItemCard(it) {
    const hasImg = it.image_url && it.image_url.trim();
    const typeText = it.item_type === 'lost' ? '失物' : '招领';
    const statusText = statusLabel(it.status);
    const auditText = auditLabel(it.audit_status);

    const metaItems = [
        { label: '📍 地点', value: it.location },
        { label: '🕒 时间', value: it.event_time },
        { label: '📞 联系方式', value: it.contact, break: true }
    ];

    const quickBtns = currentView === 'audit' && it.audit_status === 'pending' ? `
        <button class="btn btn-sm btn-success" onclick="event.stopPropagation();window.openAudit(${it.id})">审核</button>
    ` : '';

    const auditBadgeHtml = currentView !== 'public' ? `<span class="badge audit-${it.audit_status}">${auditText}</span>` : '';

    return `
        <div class="item-card" data-id="${it.id}">
            <div class="card-image-col">
                <div class="card-type-stripe ${it.item_type}"></div>
                ${hasImg
                    ? `<img src="${escapeHtml(it.image_url)}" alt="${escapeHtml(it.title)}" onerror="this.outerHTML='${placeholderEmoji(it.item_type)}'">`
                    : placeholderEmoji(it.item_type)}
            </div>
            <div class="card-content-col">
                <div class="card-header-row">
                    <div class="card-title" title="${escapeHtml(it.title)}">${escapeHtml(it.title)}</div>
                    <div class="card-badges">
                        <span class="badge ${it.item_type}">${typeText}</span>
                        <span class="badge status-${it.status}">${statusText}</span>
                        ${auditBadgeHtml}
                    </div>
                </div>
                ${it.description ? `<div class="card-desc">${escapeHtml(it.description)}</div>` : ''}
                <div class="card-meta-grid">
                    ${metaItems.map(m => `
                        <div class="meta-item">
                            <span class="meta-label">${m.label}</span>
                            <span class="meta-value ${m.break ? 'break' : ''}" title="${escapeHtml(m.value)}">${escapeHtml(m.value)}</span>
                        </div>
                    `).join('')}
                    ${it.audit_remark && (currentView === 'mine' || currentView === 'audit') ? `
                        <div class="meta-item" style="grid-column:1/-1;margin-top:4px;">
                            <span class="meta-label">📝 审核备注:</span>
                            <span class="meta-value break" style="color:${it.audit_status === 'rejected' ? 'var(--color-danger)' : 'var(--color-success)'};">${escapeHtml(it.audit_remark)}</span>
                        </div>
                    ` : ''}
                </div>
            </div>
            <div class="card-action-col">
                <div class="card-id">#${it.id}</div>
                ${quickBtns || ''}
                <div class="card-arrow">→</div>
            </div>
        </div>
    `;
}

function renderItems(silent = false) {
    const board = $('itemBoard');
    const empty = $('emptyState');
    const loading = $('loadingState');
    const resultCount = $('resultCount');

    if (!silent) {
        loading.style.display = 'block';
        board.innerHTML = '';
        empty.style.display = 'none';
    }
    loading.style.display = 'none';

    const items = allItems;

    if (items.length === 0) {
        board.innerHTML = '';
        empty.style.display = 'block';
        const titles = {
            public: { icon: '📭', t: '暂无公开信息', d: '所有新发布的信息都需要审核通过才会展示在这里。' },
            mine: { icon: '🔍', t: myContact ? '未找到您的发布记录' : '请先输入联系方式', d: myContact ? '当前联系方式没有对应的发布记录。' : '请在上方输入您发布时使用的联系方式进行查询。' },
            audit: { icon: '✅', t: '审核队列为空', d: '所有待审核的信息都已处理完毕。' }
        };
        const t = titles[currentView] || titles.public;
        $('emptyIcon').textContent = t.icon;
        $('emptyTitle').textContent = t.t;
        $('emptyDesc').textContent = t.d;
        resultCount.innerHTML = '共 <strong>0</strong> 条信息';
        return;
    }

    empty.style.display = 'none';
    board.innerHTML = items.map(renderItemCard).join('');
    resultCount.innerHTML = `共 <strong>${items.length}</strong> 条信息`;

    board.querySelectorAll('.item-card').forEach(card => {
        card.addEventListener('click', () => {
            const id = card.dataset.id;
            const carry = new URLSearchParams();
            carry.set('from', currentView);
            if (myContact) carry.set('my_contact', myContact);
            const qs = carry.toString();
            window.location.href = `detail.html?id=${id}${qs ? '&' + qs : ''}`;
        });
    });
}

/* ==================== 加载数据 ==================== */
async function loadItems(silent = false) {
    if (!silent) {
        $('loadingState').style.display = 'block';
        $('itemBoard').innerHTML = '';
        $('emptyState').style.display = 'none';
    }

    const params = new URLSearchParams();
    Object.entries(currentFilters).forEach(([k, v]) => {
        if (v && v.trim()) params.set(k, v.trim());
    });

    if (currentView === 'public') {
        /* 公开看板只看 approved，由后端默认 include_pending=false */
    } else if (currentView === 'mine') {
        params.set('contact', myContact);
        params.set('include_pending', '1');
    } else if (currentView === 'audit') {
        params.set('include_pending', '1');
    }

    try {
        const qs = params.toString();
        const data = await api(`/items${qs ? '?' + qs : ''}`);
        allItems = data.items || [];
        allLocations = data.locations || [];
        renderFilters();
        renderItems(true);
    } catch (e) {
        $('loadingState').style.display = 'none';
        showToast('加载数据失败：' + e.message, 'error');
    }
}

/* ==================== 视图切换 ==================== */
function updateViewHeader() {
    const titles = {
        public: { h2: '公开信息看板', p: '已审核通过的失物与招领信息' },
        mine: { h2: '我的发布记录', p: '使用您的联系方式查看所有发布信息和状态' },
        audit: { h2: '审核中心', p: '管理员审核所有待发布的信息' }
    };
    const t = titles[currentView];
    $('viewTitle').querySelector('h2').textContent = t.h2;
    $('viewTitle').querySelector('p').textContent = t.p;

    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.view === currentView);
    });

    $('myForm').style.display = currentView === 'mine' ? 'block' : 'none';
    $('openFormBtn').style.display = currentView === 'audit' ? 'none' : '';
}

function switchView(view, fromNav = false) {
    if (!['public', 'mine', 'audit'].includes(view)) view = 'public';
    currentView = view;

    currentFilters = {
        keyword: '',
        type: '',
        location: '',
        status: '',
        audit_status: '',
        date_from: '',
        date_to: '',
        contact: ''
    };

    if (fromNav && currentView === 'audit' && currentFilters.audit_status === '') {
        currentFilters.audit_status = 'pending';
    }

    updateViewHeader();
    updateUrl();
    loadItems();
}

/* ==================== 发布表单 ==================== */
function openForm() {
    $('formModal').classList.add('show');
    $('itemForm').reset();
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    $('event_time').value = now.toISOString().slice(0, 16);
    if (myContact) $('contact').value = myContact;
}

function closeForm() {
    $('formModal').classList.remove('show');
}

async function submitForm(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
        item_type: fd.get('item_type'),
        title: fd.get('title').trim(),
        description: fd.get('description').trim(),
        location: fd.get('location').trim(),
        event_time: fd.get('event_time'),
        contact: fd.get('contact').trim(),
        image_url: fd.get('image_url').trim()
    };

    const submitBtn = $('submitFormBtn');
    submitBtn.disabled = true;
    const orig = submitBtn.textContent;
    submitBtn.textContent = '提交中...';

    try {
        const created = await api('/items', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        closeForm();
        showToast('发布成功！已进入待审核队列，审核通过后将展示在公开看板。', 'success');
        myContact = payload.contact;
        updateUrl();
        if (currentView === 'mine' || currentView === 'audit') {
            await loadItems();
        }
        await loadStats();
    } catch (err) {
        showToast('发布失败：' + err.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = orig;
    }
}

/* ==================== 审核弹窗 ==================== */
window.openAudit = async function (itemId) {
    try {
        const item = await api(`/items/${itemId}`);
        pendingAuditItem = item;
        $('auditModalTitle').textContent = `审核信息 #${item.id} · ${escapeHtml(item.title)}`;
        $('auditPreview').innerHTML = `
            <div style="margin-bottom:12px;">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
                    <span class="badge ${item.item_type}">${item.item_type === 'lost' ? '失物' : '招领'}</span>
                    <span class="badge status-${item.status}">${statusLabel(item.status)}</span>
                    <span class="badge audit-pending">待审核</span>
                </div>
                <h3 style="font-size:1.05rem;color:var(--color-gray-900);">${escapeHtml(item.title)}</h3>
            </div>
            ${item.description ? `<p style="font-size:0.88rem;color:var(--color-gray-600);margin-bottom:12px;line-height:1.6;">${escapeHtml(item.description)}</p>` : ''}
            <div class="detail-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                <div style="background:white;padding:10px;border-radius:8px;border:1px solid var(--color-gray-200);">
                    <div style="font-size:0.72rem;color:var(--color-gray-400);font-weight:600;">📍 地点</div>
                    <div style="font-size:0.88rem;color:var(--color-gray-800);margin-top:2px;">${escapeHtml(item.location)}</div>
                </div>
                <div style="background:white;padding:10px;border-radius:8px;border:1px solid var(--color-gray-200);">
                    <div style="font-size:0.72rem;color:var(--color-gray-400);font-weight:600;">🕒 时间</div>
                    <div style="font-size:0.88rem;color:var(--color-gray-800);margin-top:2px;">${escapeHtml(item.event_time)}</div>
                </div>
                <div style="background:white;padding:10px;border-radius:8px;border:1px solid var(--color-gray-200);grid-column:1/-1;">
                    <div style="font-size:0.72rem;color:var(--color-gray-400);font-weight:600;">📞 联系方式</div>
                    <div style="font-size:0.88rem;color:var(--color-gray-800);margin-top:2px;">${escapeHtml(item.contact)}</div>
                </div>
            </div>
        `;
        $('auditRemark').value = '';
        $('auditRemarkRequired').style.display = 'none';
        $('auditModal').classList.add('show');
    } catch (e) {
        showToast('加载信息失败：' + e.message, 'error');
    }
};

function closeAudit() {
    $('auditModal').classList.remove('show');
    pendingAuditItem = null;
}

async function doAudit(action) {
    if (!pendingAuditItem) return;
    const remark = $('auditRemark').value.trim();

    if (action === 'reject' && !remark) {
        $('auditRemarkRequired').style.display = 'inline';
        $('auditRemark').focus();
        showToast('驳回时必须填写驳回原因', 'warning');
        return;
    }

    try {
        await api(`/items/${pendingAuditItem.id}/audit`, {
            method: 'PUT',
            body: JSON.stringify({ action, remark, operator: 'admin' })
        });
        closeAudit();
        showToast(action === 'approve' ? '审核通过！' : '已驳回。', 'success');
        await loadItems();
        await loadStats();
    } catch (e) {
        showToast('审核失败：' + e.message, 'error');
    }
}

/* ==================== 我的发布 ==================== */
function queryMyItems() {
    const contact = $('myContact').value.trim();
    if (!contact) {
        showToast('请先输入您的联系方式', 'warning');
        $('myContact').focus();
        return;
    }
    myContact = contact;
    updateUrl();
    loadItems();
}

/* ==================== 事件绑定 ==================== */
function bindEvents() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchView(tab.dataset.view, true));
    });

    $('openFormBtn').addEventListener('click', openForm);
    $('closeFormBtn').addEventListener('click', closeForm);
    $('cancelFormBtn').addEventListener('click', closeForm);
    $('formModal').addEventListener('click', (e) => {
        if (e.target.id === 'formModal') closeForm();
    });
    $('itemForm').addEventListener('submit', submitForm);

    $('closeAuditBtn').addEventListener('click', closeAudit);
    $('cancelAuditBtn').addEventListener('click', closeAudit);
    $('auditModal').addEventListener('click', (e) => {
        if (e.target.id === 'auditModal') closeAudit();
    });
    $('auditApproveBtn').addEventListener('click', () => doAudit('approve'));
    $('auditRejectBtn').addEventListener('click', () => doAudit('reject'));

    $('queryMyBtn').addEventListener('click', queryMyItems);
    $('myContact').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') queryMyItems();
    });

    $('resetFilterBtn').addEventListener('click', () => {
        currentFilters = {
            keyword: '', type: '', location: '', status: '',
            audit_status: currentView === 'audit' ? 'pending' : '',
            date_from: '', date_to: '', contact: ''
        };
        updateUrl();
        loadItems();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if ($('formModal').classList.contains('show')) closeForm();
            if ($('auditModal').classList.contains('show')) closeAudit();
        }
    });
}

/* ==================== 初始化 ==================== */
document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();
    queryToFilters();

    const from = currentView;
    currentView = 'public';
    updateViewHeader();
    if (from !== 'public') {
        setTimeout(() => switchView(from, from === 'audit'), 0);
    }
    if (currentView === 'mine' && myContact) {
        $('myContact').value = myContact;
    }
    if (currentView === 'audit' && currentFilters.audit_status === '') {
        currentFilters.audit_status = 'pending';
    }

    await loadStats();
    await loadItems();
});
