const API_BASE = '/api';

let currentItem = null;
let itemId = null;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
    const res = await fetch(API_BASE + path, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.error || `Request failed: ${res.status}`);
    }
    return data;
}

function showToast(msg, isError = false) {
    const toast = $('toast');
    toast.textContent = msg;
    toast.classList.toggle('error', isError);
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s || '';
    return div.innerHTML;
}

function statusLabel(s) {
    return { open: '开放中', claimed: '已认领', closed: '已关闭' }[s] || s;
}

function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
}

function placeholderEmoji(t) {
    return t === 'lost' ? '😢' : '🎉';
}

function renderDetail(item) {
    const hasImg = item.image_url && item.image_url.trim();
    const container = $('detailContent');

    let claimerHtml = '';
    if (item.status === 'claimed' || item.claimer_name) {
        claimerHtml = `
        <div class="detail-section">
            <div class="detail-section-title">🤝 认领信息</div>
            <div class="claimer-box">
                <div class="claimer-title">✅ 已有人认领</div>
                <div class="claimer-grid">
                    <div>
                        <div class="detail-info-label">认领人</div>
                        <div class="detail-info-value">${escapeHtml(item.claimer_name)}</div>
                    </div>
                    <div>
                        <div class="detail-info-label">联系方式</div>
                        <div class="detail-info-value">${escapeHtml(item.claimer_contact)}</div>
                    </div>
                </div>
            </div>
        </div>`;
    }

    container.innerHTML = `
        <div class="detail-image">
            ${hasImg
                ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.title)}" onerror="this.outerHTML='${placeholderEmoji(item.item_type)}'">`
                : placeholderEmoji(item.item_type)}
        </div>
        <div class="detail-body">
            <div class="detail-header-row">
                <div>
                    <h2 class="detail-title">${escapeHtml(item.title)}</h2>
                    <div class="detail-title-row">
                        <span class="type-badge ${item.item_type}">
                            ${item.item_type === 'lost' ? '🔴 失物' : '🟢 招领'}
                        </span>
                        <span class="status-tag ${item.status}">${statusLabel(item.status)}</span>
                    </div>
                </div>
            </div>

            <div class="detail-section">
                <div class="detail-section-title">📝 详细描述</div>
                <div class="detail-description">${escapeHtml(item.description) || '暂无详细描述'}</div>
            </div>

            <div class="detail-section">
                <div class="detail-section-title">📋 基本信息</div>
                <div class="detail-grid">
                    <div class="detail-info">
                        <div class="detail-info-label">📍 ${item.item_type === 'lost' ? '丢失地点' : '拾取地点'}</div>
                        <div class="detail-info-value">${escapeHtml(item.location)}</div>
                    </div>
                    <div class="detail-info">
                        <div class="detail-info-label">🕒 ${item.item_type === 'lost' ? '丢失时间' : '拾取时间'}</div>
                        <div class="detail-info-value">${escapeHtml(item.event_time)}</div>
                    </div>
                    <div class="detail-info">
                        <div class="detail-info-label">📞 发布人联系方式</div>
                        <div class="detail-info-value">${escapeHtml(item.contact)}</div>
                    </div>
                    <div class="detail-info">
                        <div class="detail-info-label">🆔 编号</div>
                        <div class="detail-info-value">#${item.id}</div>
                    </div>
                </div>
            </div>

            ${claimerHtml}

            <div class="timeline">
                <span>📅 发布于：${escapeHtml(item.created_at)}</span>
                <span>✏️ 更新于：${escapeHtml(item.updated_at)}</span>
            </div>
        </div>
    `;

    renderActionPanel(item);
}

function renderActionPanel(item) {
    const panel = $('actionPanel');
    panel.style.display = 'block';
    panel.innerHTML = '';

    if (item.status === 'open') {
        const claimBtn = document.createElement('button');
        claimBtn.className = 'btn btn-success';
        claimBtn.innerHTML = '🤝 我要认领';
        claimBtn.onclick = openClaimModal;
        panel.appendChild(claimBtn);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'btn btn-danger';
        closeBtn.innerHTML = '🔒 关闭此信息';
        closeBtn.onclick = () => confirmClose();
        panel.appendChild(closeBtn);
    } else if (item.status === 'claimed') {
        const info = document.createElement('div');
        info.style.cssText = 'flex:1; display:flex; align-items:center; color:#f08c00; font-weight:600;';
        info.innerHTML = 'ℹ️ 此信息已被认领，可联系发布者或认领人确认';
        panel.appendChild(info);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'btn btn-danger';
        closeBtn.innerHTML = '🔒 关闭此信息';
        closeBtn.onclick = () => confirmClose();
        panel.appendChild(closeBtn);
    } else if (item.status === 'closed') {
        const info = document.createElement('div');
        info.style.cssText = 'width:100%; text-align:center; color:#868e96; font-weight:600; padding:8px 0;';
        info.innerHTML = '📦 此信息已关闭';
        panel.appendChild(info);
    }
}

function confirmClose() {
    const panel = $('actionPanel');
    const existing = panel.querySelector('.confirm-dialog');
    if (existing) {
        existing.remove();
        return;
    }

    const dialog = document.createElement('div');
    dialog.className = 'confirm-dialog';
    dialog.innerHTML = `
        <p>⚠️ 确定要关闭此信息吗？关闭后将无法再修改状态。</p>
        <div class="btn-group">
            <button class="btn btn-secondary" id="cancelClose">取消</button>
            <button class="btn btn-primary" id="doClose">确认关闭</button>
        </div>
    `;
    panel.insertBefore(dialog, panel.firstChild);

    $('cancelClose').onclick = () => dialog.remove();
    $('doClose').onclick = async () => {
        try {
            const updated = await api(`/items/${itemId}/status`, {
                method: 'PUT',
                body: JSON.stringify({ status: 'closed' })
            });
            currentItem = updated;
            renderDetail(updated);
            showToast('已关闭');
        } catch (e) {
            showToast('关闭失败：' + e.message, true);
        }
    };
}

function openClaimModal() {
    $('claimModal').classList.add('show');
    $('claimForm').reset();
}

function closeClaimModal() {
    $('claimModal').classList.remove('show');
}

async function submitClaim(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
        const updated = await api(`/items/${itemId}/status`, {
            method: 'PUT',
            body: JSON.stringify({
                status: 'claimed',
                claimer_name: fd.get('claimer_name').trim(),
                claimer_contact: fd.get('claimer_contact').trim()
            })
        });
        currentItem = updated;
        closeClaimModal();
        renderDetail(updated);
        showToast('认领成功！');
    } catch (err) {
        showToast('认领失败：' + err.message, true);
    }
}

function bindEvents() {
    $('closeClaimBtn').addEventListener('click', closeClaimModal);
    $('cancelClaimBtn').addEventListener('click', closeClaimModal);
    $('claimModal').addEventListener('click', (e) => {
        if (e.target.id === 'claimModal') closeClaimModal();
    });
    $('claimForm').addEventListener('submit', submitClaim);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && $('claimModal').classList.contains('show')) {
            closeClaimModal();
        }
    });
}

async function loadDetail() {
    itemId = getQueryParam('id');
    if (!itemId) {
        $('detailContent').innerHTML = '<div class="loading" style="color:#c92a2a;">未指定信息 ID</div>';
        return;
    }

    try {
        const item = await api(`/items/${itemId}`);
        currentItem = item;
        renderDetail(item);
    } catch (e) {
        $('detailContent').innerHTML = `<div class="loading" style="color:#c92a2a;">加载失败：${escapeHtml(e.message)}</div>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    loadDetail();
});
