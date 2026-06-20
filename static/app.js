const API_BASE = '/api';

let allItems = [];
let allLocations = [];

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

function statusLabel(s) {
    return { open: '开放中', claimed: '已认领', closed: '已关闭' }[s] || s;
}

function typeEmoji(t) {
    return t === 'lost' ? '🔴' : '🟢';
}

function placeholderEmoji(t) {
    return t === 'lost' ? '😢' : '🎉';
}

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s || '';
    return div.innerHTML;
}

function renderItems() {
    const keyword = $('searchInput').value.trim().toLowerCase();
    const typeFilter = $('typeFilter').value;
    const locationFilter = $('locationFilter').value;
    const statusFilter = $('statusFilter').value;

    let items = allItems.filter(it => {
        if (keyword) {
            const hay = `${it.title} ${it.description} ${it.location}`.toLowerCase();
            if (!hay.includes(keyword)) return false;
        }
        if (typeFilter && it.item_type !== typeFilter) return false;
        if (locationFilter && it.location !== locationFilter) return false;
        if (statusFilter && it.status !== statusFilter) return false;
        return true;
    });

    const grid = $('itemGrid');
    const empty = $('emptyState');

    if (items.length === 0) {
        grid.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    grid.innerHTML = items.map(it => {
        const hasImg = it.image_url && it.image_url.trim();
        return `
        <div class="item-card" data-id="${it.id}">
            <div class="item-image">
                ${hasImg
                    ? `<img src="${escapeHtml(it.image_url)}" alt="${escapeHtml(it.title)}" onerror="this.outerHTML='${placeholderEmoji(it.item_type)}'">`
                    : placeholderEmoji(it.item_type)}
            </div>
            <div class="item-body">
                <div class="item-header">
                    <h3 class="item-title">${escapeHtml(it.title)}</h3>
                    <span class="type-badge ${it.item_type}">
                        ${typeEmoji(it.item_type)} ${it.item_type === 'lost' ? '失物' : '招领'}
                    </span>
                </div>
                <p class="item-description">${escapeHtml(it.description) || '暂无描述'}</p>
                <div class="item-meta">
                    <div class="meta-item">
                        <span class="meta-icon">📍</span>
                        <span>${escapeHtml(it.location)}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-icon">🕒</span>
                        <span>${escapeHtml(it.event_time)}</span>
                    </div>
                </div>
                <span class="status-tag ${it.status}">${statusLabel(it.status)}</span>
            </div>
        </div>`;
    }).join('');

    grid.querySelectorAll('.item-card').forEach(card => {
        card.addEventListener('click', () => {
            const id = card.dataset.id;
            window.location.href = `detail.html?id=${id}`;
        });
    });
}

function renderLocationOptions() {
    const sel = $('locationFilter');
    const current = sel.value;
    sel.innerHTML = '<option value="">全部地点</option>' +
        allLocations.map(l => `<option value="${escapeHtml(l)}">${escapeHtml(l)}</option>`).join('');
    sel.value = current;
}

async function loadItems() {
    try {
        const data = await api('/items');
        allItems = data.items || [];
        allLocations = data.locations || [];
        renderLocationOptions();
        renderItems();
    } catch (e) {
        showToast('加载数据失败：' + e.message, true);
    }
}

function openForm() {
    $('formModal').classList.add('show');
    $('itemForm').reset();
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    $('event_time').value = now.toISOString().slice(0, 16);
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

    try {
        await api('/items', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        showToast('发布成功！');
        closeForm();
        await loadItems();
    } catch (err) {
        showToast('发布失败：' + err.message, true);
    }
}

function bindEvents() {
    $('openFormBtn').addEventListener('click', openForm);
    $('closeFormBtn').addEventListener('click', closeForm);
    $('cancelFormBtn').addEventListener('click', closeForm);
    $('formModal').addEventListener('click', (e) => {
        if (e.target.id === 'formModal') closeForm();
    });

    $('itemForm').addEventListener('submit', submitForm);

    $('searchInput').addEventListener('input', renderItems);
    $('typeFilter').addEventListener('change', renderItems);
    $('locationFilter').addEventListener('change', renderItems);
    $('statusFilter').addEventListener('change', renderItems);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && $('formModal').classList.contains('show')) {
            closeForm();
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    loadItems();
});
