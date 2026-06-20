const API_BASE = '/api';

let currentItem = null;
let itemLogs = [];
let itemId = null;
let fromView = 'public';
let myContact = '';

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

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s || '';
    return div.innerHTML;
}

function statusLabel(s) {
    return { open: '开放中', claimed: '已认领', closed: '已关闭' }[s] || s;
}

function auditLabel(s) {
    return { pending: '待审核', approved: '已通过', rejected: '已驳回' }[s] || s;
}

function actionLabel(a) {
    const map = {
        create: '发布信息',
        audit_approve: '审核通过',
        audit_reject: '审核驳回',
        claim: '物品认领',
        close: '关闭信息',
        reopen: '重新开放',
        remark: '添加备注'
    };
    return map[a] || a;
}

function placeholderEmoji(t) {
    return t === 'lost' ? '😢' : '🎉';
}

function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
}

/* ==================== 详情渲染 ==================== */
function renderDetail(item) {
    $('loadingState').style.display = 'none';
    $('errorState').style.display = 'none';
    $('detailContent').style.display = 'block';

    const hasImg = item.image_url && item.image_url.trim();
    const container = $('detailContent');

    let claimerSection = '';
    if ((item.status === 'claimed' || item.claimer_name) && item.claimer_name) {
        claimerSection = `
            <div class="detail-section">
                <div class="detail-section-title"><span class="icon">🤝</span> 认领信息</div>
                <div class="claimer-card">
                    <div class="claimer-header">✅ 已有人认领此物品</div>
                    <div class="claimer-grid">
                        <div class="info-block" style="background:white;">
                            <div class="info-label">认领人</div>
                            <div class="info-value">${escapeHtml(item.claimer_name)}</div>
                        </div>
                        <div class="info-block" style="background:white;">
                            <div class="info-label">联系方式</div>
                            <div class="info-value">${escapeHtml(item.claimer_contact)}</div>
                        </div>
                        ${item.claimed_at ? `
                        <div class="info-block" style="background:white;grid-column:1/-1;">
                            <div class="info-label">认领时间</div>
                            <div class="info-value">${escapeHtml(item.claimed_at)}</div>
                        </div>` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    let auditSection = `
        <div class="detail-section">
            <div class="detail-section-title"><span class="icon">🛡️</span> 审核状态</div>
            <div class="audit-card ${item.audit_status}">
                <div class="audit-header">
                    <div class="audit-status-label">
                        ${item.audit_status === 'pending' ? '⏳ ' : item.audit_status === 'approved' ? '✅ ' : '🚫 '}
                        ${auditLabel(item.audit_status)}
                    </div>
                    ${item.audited_at ? `<div class="audit-meta">${item.audited_by || 'system'} · ${escapeHtml(item.audited_at)}</div>` : '<div class="audit-meta">等待管理员审核</div>'}
                </div>
                ${item.audit_remark ? `<div class="audit-remark">📝 ${escapeHtml(item.audit_remark)}</div>` : ''}
            </div>
        </div>
    `;

    container.innerHTML = `
        <div class="detail-main-card">
            <div class="detail-image-wrap ${item.item_type}">
                ${hasImg
                    ? `<img class="detail-image" src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.title)}" onerror="this.outerHTML='<div class=\\'detail-emoji\\'>${placeholderEmoji(item.item_type)}</div>'">`
                    : `<div class="detail-emoji">${placeholderEmoji(item.item_type)}</div>`}
            </div>
            <div class="detail-body">
                <div class="detail-title-row">
                    <h2 class="detail-title">${escapeHtml(item.title)}</h2>
                    <div class="detail-badges">
                        <span class="badge ${item.item_type}">${item.item_type === 'lost' ? '失物' : '招领'}</span>
                        <span class="badge status-${item.status}">${statusLabel(item.status)}</span>
                        <span class="badge audit-${item.audit_status}">${auditLabel(item.audit_status)}</span>
                    </div>
                </div>

                <div class="detail-section">
                    <div class="detail-section-title"><span class="icon">📝</span> 详细描述</div>
                    <div class="desc-block ${item.description ? '' : 'empty'}">${escapeHtml(item.description) || '暂无详细描述'}</div>
                </div>

                <div class="detail-section">
                    <div class="detail-section-title"><span class="icon">📋</span> 基本信息</div>
                    <div class="info-grid">
                        <div class="info-block">
                            <div class="info-label">📍 ${item.item_type === 'lost' ? '丢失地点' : '拾取地点'}</div>
                            <div class="info-value">${escapeHtml(item.location)}</div>
                        </div>
                        <div class="info-block">
                            <div class="info-label">🕒 ${item.item_type === 'lost' ? '丢失时间' : '拾取时间'}</div>
                            <div class="info-value">${escapeHtml(item.event_time)}</div>
                        </div>
                        <div class="info-block">
                            <div class="info-label">📞 发布者联系方式</div>
                            <div class="info-value">${escapeHtml(item.contact)}</div>
                        </div>
                        <div class="info-block">
                            <div class="info-label">🆔 信息编号</div>
                            <div class="info-value">#${item.id}</div>
                        </div>
                        <div class="info-block">
                            <div class="info-label">📅 发布时间</div>
                            <div class="info-value">${escapeHtml(item.created_at)}</div>
                        </div>
                        ${item.closed_at ? `
                        <div class="info-block">
                            <div class="info-label">🔒 关闭时间</div>
                            <div class="info-value">${escapeHtml(item.closed_at)}</div>
                        </div>` : ''}
                    </div>
                </div>

                ${claimerSection}
                ${auditSection}
            </div>
        </div>

        <div class="timeline-card">
            <div class="timeline-header">
                <div class="timeline-title">📜 状态追踪时间线</div>
                <button class="btn btn-sm btn-ghost" id="addRemarkBtn">📝 添加备注</button>
            </div>
            <div class="timeline" id="timeline"></div>
        </div>
    `;

    $('addRemarkBtn').addEventListener('click', openRemarkModal);
}

/* ==================== 时间线渲染 ==================== */
function renderTimeline() {
    const container = $('timeline');
    if (!container) return;

    if (!itemLogs || itemLogs.length === 0) {
        container.innerHTML = `
            <div style="padding:16px;text-align:center;color:var(--color-gray-400);font-size:0.88rem;">
                暂无追踪记录
            </div>
        `;
        return;
    }

    container.innerHTML = itemLogs.map(log => `
        <div class="timeline-item">
            <div class="timeline-dot ${log.action}"></div>
            <div class="timeline-action">
                <span class="timeline-action-label">${actionLabel(log.action)}</span>
                <span class="timeline-action-time">${escapeHtml(log.created_at)}</span>
            </div>
            <div class="timeline-operator">操作人：<strong>${escapeHtml(log.operator || 'system')}</strong></div>
            ${log.remark ? `<div class="timeline-remark-text">${escapeHtml(log.remark)}</div>` : ''}
        </div>
    `).join('');
}

/* ==================== 操作面板 ==================== */
function renderActionPanel(item) {
    const panel = $('actionPanel');
    panel.style.display = 'flex';
    panel.innerHTML = '';

    if (item.status === 'open') {
        const info = document.createElement('div');
        info.className = 'action-info info-open';
        info.innerHTML = '<span>💡</span><span>此信息正开放中，欢迎认领或联系发布者</span>';
        panel.appendChild(info);

        const remarkBtn = document.createElement('button');
        remarkBtn.className = 'btn btn-secondary';
        remarkBtn.innerHTML = '📝 添加备注';
        remarkBtn.onclick = openRemarkModal;
        panel.appendChild(remarkBtn);

        const claimBtn = document.createElement('button');
        claimBtn.className = 'btn btn-success';
        claimBtn.innerHTML = '🤝 我要认领';
        claimBtn.onclick = openClaimModal;
        panel.appendChild(claimBtn);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'btn btn-danger';
        closeBtn.innerHTML = '🔒 关闭此信息';
        closeBtn.onclick = () => showCloseConfirm(item);
        panel.appendChild(closeBtn);

    } else if (item.status === 'claimed') {
        const info = document.createElement('div');
        info.className = 'action-info info-claimed';
        info.innerHTML = '<span>ℹ️</span><span>此信息已被认领，可联系发布者或认领人确认交接</span>';
        panel.appendChild(info);

        const remarkBtn = document.createElement('button');
        remarkBtn.className = 'btn btn-secondary';
        remarkBtn.innerHTML = '📝 添加备注';
        remarkBtn.onclick = openRemarkModal;
        panel.appendChild(remarkBtn);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'btn btn-danger';
        closeBtn.innerHTML = '🔒 关闭此信息';
        closeBtn.onclick = () => showCloseConfirm(item);
        panel.appendChild(closeBtn);

    } else if (item.status === 'closed') {
        const info = document.createElement('div');
        info.className = 'action-info info-closed';
        info.innerHTML = '<span>📦</span><span>此信息已关闭，状态不再可变更</span>';
        panel.appendChild(info);

        const remarkBtn = document.createElement('button');
        remarkBtn.className = 'btn btn-secondary';
        remarkBtn.innerHTML = '📝 补充备注';
        remarkBtn.onclick = openRemarkModal;
        panel.appendChild(remarkBtn);
    }

    if (item.audit_status === 'pending') {
        const auditBlock = document.createElement('div');
        auditBlock.className = 'audit-actions-block';
        auditBlock.style.order = '-1';
        auditBlock.style.flex = '1 1 100%';
        auditBlock.innerHTML = `
            <div class="audit-actions-info">
                <span class="warn-icon">⏳</span>
                <div>
                    <h4>此信息待审核</h4>
                    <p>请管理员进行审核操作，审核通过后将出现在公开看板</p>
                </div>
            </div>
            <div class="audit-actions-buttons">
                <button class="btn btn-sm btn-success" id="quickApproveBtn">✅ 通过审核</button>
                <button class="btn btn-sm btn-danger" id="quickRejectBtn">🚫 驳回</button>
            </div>
        `;
        panel.insertBefore(auditBlock, panel.firstChild);
        $('quickApproveBtn').onclick = () => doQuickAudit('approve');
        $('quickRejectBtn').onclick = () => doQuickAudit('reject');
    }
}

function showCloseConfirm(item) {
    const dialog = $('closeConfirmDialog');
    dialog.style.display = 'flex';
    dialog.innerHTML = `
        <p>⚠️ 确定要关闭此信息吗？关闭后将无法再修改状态（仍可添加备注）。</p>
        <div class="btn-group">
            <button class="btn btn-secondary" id="cancelCloseBtn">取消</button>
            <button class="btn btn-danger" id="doCloseBtn">🔒 确认关闭</button>
        </div>
    `;
    $('cancelCloseBtn').onclick = () => dialog.style.display = 'none';
    $('doCloseBtn').onclick = async () => {
        try {
            const updated = await api(`/items/${itemId}/status`, {
                method: 'PUT',
                body: JSON.stringify({ status: 'closed', operator: 'user', remark: '用户手动关闭' })
            });
            currentItem = updated;
            dialog.style.display = 'none';
            renderDetail(updated);
            renderActionPanel(updated);
            await loadLogs();
            showToast('已关闭此信息');
        } catch (e) {
            showToast('关闭失败：' + e.message, 'error');
        }
    };
}

/* ==================== 认领 ==================== */
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
    const submitBtn = $('submitClaimBtn');
    submitBtn.disabled = true;
    const orig = submitBtn.textContent;
    submitBtn.textContent = '提交中...';

    try {
        const updated = await api(`/items/${itemId}/status`, {
            method: 'PUT',
            body: JSON.stringify({
                status: 'claimed',
                claimer_name: fd.get('claimer_name').trim(),
                claimer_contact: fd.get('claimer_contact').trim(),
                operator: fd.get('claimer_name').trim() || 'user',
                remark: (fd.get('claim_remark') || '').trim() || undefined
            })
        });
        currentItem = updated;
        closeClaimModal();
        renderDetail(updated);
        renderActionPanel(updated);
        await loadLogs();
        showToast('认领成功！请尽快与发布者联系完成交接。');
    } catch (err) {
        showToast('认领失败：' + err.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = orig;
    }
}

/* ==================== 备注 ==================== */
function openRemarkModal() {
    $('remarkModal').classList.add('show');
    $('remarkForm').reset();
    if (myContact) $('remark_operator').value = myContact;
}

function closeRemarkModal() {
    $('remarkModal').classList.remove('show');
}

async function submitRemark(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const submitBtn = $('submitRemarkBtn');
    submitBtn.disabled = true;
    const orig = submitBtn.textContent;
    submitBtn.textContent = '提交中...';

    try {
        await api(`/items/${itemId}/remark`, {
            method: 'POST',
            body: JSON.stringify({
                remark: fd.get('remark_text').trim(),
                operator: (fd.get('remark_operator') || '').trim() || 'user'
            })
        });
        closeRemarkModal();
        await loadLogs();
        showToast('备注已添加');
    } catch (err) {
        showToast('添加备注失败：' + err.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = orig;
    }
}

/* ==================== 快速审核 ==================== */
async function doQuickAudit(action) {
    if (action === 'reject') {
        const reason = prompt('请填写驳回原因（必填）：');
        if (!reason || !reason.trim()) {
            showToast('驳回时必须填写原因', 'warning');
            return;
        }
        try {
            const updated = await api(`/items/${itemId}/audit`, {
                method: 'PUT',
                body: JSON.stringify({ action, operator: 'admin', remark: reason.trim() })
            });
            currentItem = updated;
            renderDetail(updated);
            renderActionPanel(updated);
            await loadLogs();
            showToast('已驳回此信息');
        } catch (e) {
            showToast('审核失败：' + e.message, 'error');
        }
    } else {
        try {
            const updated = await api(`/items/${itemId}/audit`, {
                method: 'PUT',
                body: JSON.stringify({ action, operator: 'admin', remark: '' })
            });
            currentItem = updated;
            renderDetail(updated);
            renderActionPanel(updated);
            await loadLogs();
            showToast('审核通过，已展示在公开看板');
        } catch (e) {
            showToast('审核失败：' + e.message, 'error');
        }
    }
}

/* ==================== 加载数据 ==================== */
async function loadLogs() {
    try {
        const data = await api(`/items/${itemId}/logs`);
        itemLogs = data.logs || [];
        renderTimeline();
    } catch (e) { /* ignore */ }
}

async function loadDetail() {
    itemId = getQueryParam('id');
    fromView = getQueryParam('from') || 'public';
    myContact = getQueryParam('my_contact') || '';

    const backParams = new URLSearchParams();
    if (fromView !== 'public') backParams.set('view', fromView);
    if (myContact && fromView === 'mine') backParams.set('my_contact', myContact);
    const backQs = backParams.toString();
    $('backLink').href = `/${backQs ? '?' + backQs : ''}`;

    if (!itemId) {
        $('loadingState').style.display = 'none';
        $('errorState').style.display = 'block';
        $('errorTitle').textContent = '参数错误';
        $('errorDesc').textContent = '未指定信息 ID';
        return;
    }

    try {
        const item = await api(`/items/${itemId}`);
        currentItem = item;
        renderDetail(item);
        renderActionPanel(item);
        await loadLogs();
    } catch (e) {
        $('loadingState').style.display = 'none';
        $('errorState').style.display = 'block';
        $('errorTitle').textContent = '加载失败';
        $('errorDesc').textContent = e.message || '无法加载该信息详情';
    }
}

/* ==================== 事件绑定 ==================== */
function bindEvents() {
    $('backBrand').addEventListener('click', () => {
        const params = new URLSearchParams();
        if (fromView !== 'public') params.set('view', fromView);
        if (myContact && fromView === 'mine') params.set('my_contact', myContact);
        const qs = params.toString();
        window.location.href = `/${qs ? '?' + qs : ''}`;
    });

    $('closeClaimBtn').addEventListener('click', closeClaimModal);
    $('cancelClaimBtn').addEventListener('click', closeClaimModal);
    $('claimModal').addEventListener('click', (e) => {
        if (e.target.id === 'claimModal') closeClaimModal();
    });
    $('claimForm').addEventListener('submit', submitClaim);

    $('closeRemarkBtn').addEventListener('click', closeRemarkModal);
    $('cancelRemarkBtn').addEventListener('click', closeRemarkModal);
    $('remarkModal').addEventListener('click', (e) => {
        if (e.target.id === 'remarkModal') closeRemarkModal();
    });
    $('remarkForm').addEventListener('submit', submitRemark);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if ($('claimModal').classList.contains('show')) closeClaimModal();
            if ($('remarkModal').classList.contains('show')) closeRemarkModal();
            if ($('closeConfirmDialog').style.display === 'flex') {
                $('closeConfirmDialog').style.display = 'none';
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    loadDetail();
});
