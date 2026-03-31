// ============================================================
// State
// ============================================================

const state = {
  page: 1,
  perPage: 20,
  loading: false,
  hasMore: true,
  filters: {
    q: '',
    type: '',
    digested: '',
    since: '',
    until: '',
    tag: '',
    starred: '',
  },
  // Tag modal state
  currentTagTopicId: null,
  currentTagTopicTags: [],
  lightbox: {
    scale: 1,
    minScale: 0.5,
    maxScale: 4,
    offsetX: 0,
    offsetY: 0,
    dragging: false,
    startX: 0,
    startY: 0,
  },
};

// ============================================================
// Utilities
// ============================================================

/**
 * Format an ISO 8601 datetime string to "YYYY-MM-DD HH:MM".
 * e.g. "2026-03-17T11:02:57.040+0800" → "2026-03-17 11:02"
 */
function formatDate(iso) {
  if (!iso) return '';
  // Take first 16 chars after replacing the T separator
  return iso.slice(0, 16).replace('T', ' ');
}

/**
 * Escape HTML special characters in a plain-text string.
 * Used only for user-supplied strings that haven't gone through the backend.
 */
function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Debounce helper: returns a function that delays `fn` by `ms` ms. */
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// ============================================================
// API functions
// ============================================================

/** Wrapper around fetch that checks response status and returns parsed JSON. */
async function apiFetch(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchTopics() {
  const params = new URLSearchParams({ page: state.page, per_page: state.perPage });
  const f = state.filters;
  if (f.q)        params.set('q', f.q);
  if (f.type)     params.set('type', f.type);
  if (f.digested) params.set('digested', '1');
  if (f.since)    params.set('since', f.since);
  if (f.until)    params.set('until', f.until);
  if (f.tag)      params.set('tag', f.tag);
  if (f.starred)  params.set('starred', '1');

  return apiFetch(`/api/topics?${params}`);
}

async function toggleStar(topicId) {
  return apiFetch(`/api/topics/${topicId}/star`, { method: 'POST' });
}

async function updateTags(topicId, tags) {
  return apiFetch(`/api/topics/${topicId}/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags }),
  });
}

async function fetchAllTags() {
  return apiFetch('/api/tags');
}

async function fetchStats() {
  return apiFetch('/api/stats');
}

// ============================================================
// Rendering
// ============================================================

/** Render an array of tags as tag-chip spans. */
function renderTagChips(tags) {
  return tags.map(t => `<span class="tag-chip">${escapeHtml(t)}</span>`).join('');
}

/**
 * Render a single image thumbnail that opens the lightbox on click.
 * Images are served from /images/{filename}.
 */
function renderImages(images) {
  if (!images || images.length === 0) return '';
  const thumbs = images.map(img => {
    const src = escapeHtml(`/images/${img.filename}`);
    return `<img class="topic-thumb" src="${src}" alt="" loading="lazy" onclick="openLightbox('${src}')" />`;
  }).join('');
  return `<div class="topic-images">${thumbs}</div>`;
}

/**
 * Render a single comment row.
 */
function renderComment(comment) {
  const author = escapeHtml(comment.author?.name || '匿名');
  const date   = formatDate(comment.create_time);
  const text   = escapeHtml(comment.text || '');
  const repliee = comment.repliee ? `<span class="repliee">→ ${escapeHtml(comment.repliee)}</span> ` : '';
  return `
    <div class="comment">
      <span class="comment-author">${author}</span>
      <span class="comment-date">${date}</span>
      <div class="comment-text">${repliee}${text}</div>
    </div>`;
}

/**
 * Render a full topic card as an HTML string.
 */
function renderTopic(topic) {
  const topicId  = topic.topic_id;
  const author   = escapeHtml(topic.author?.name || '匿名');
  const date     = formatDate(topic.create_time);
  const typeLabel = topic.type === 'q&a' ? '问答' : '分享';
  const typeCls   = topic.type === 'q&a' ? 'badge-qa' : 'badge-talk';

  // Digested badge
  const digestedBadge = topic.digested
    ? '<span class="badge badge-digested">精华</span>'
    : '';

  // text_html already has newlines converted to <br> by the backend
  const textHtml = topic.text_html || '';

  // Images (topic level)
  const imagesHtml = renderImages(topic.images);

  // Metadata row
  const starClass = topic.is_starred ? 'star-btn starred' : 'star-btn';
  const starIcon  = topic.is_starred ? '⭐' : '☆';
  const metaHtml = `
    <div class="topic-meta">
      <span>❤ ${topic.likes_count || 0}</span>
      <span>💬 ${topic.comments_count || 0}</span>
      <span>👁 ${topic.reading_count || 0}</span>
      <button class="${starClass}" data-topic-id="${topicId}" onclick="handleStar('${topicId}')">${starIcon} 收藏</button>
      <button class="tag-btn" data-topic-id="${topicId}" onclick="openTagModal('${topicId}')">🏷 标签</button>
    </div>`;

  // User tags chips
  const userTagsHtml = `<div class="user-tags" id="tags-${topicId}">${
    topic.user_tags && topic.user_tags.length > 0 ? renderTagChips(topic.user_tags) : ''
  }</div>`;

  // Answer block (q&a)
  let answerHtml = '';
  if (topic.type === 'q&a' && topic.answer) {
    const answerAuthor = escapeHtml(topic.answer.author?.name || '');
    const answerText   = topic.answer.text_html || escapeHtml(topic.answer.text || '');
    const answerImages = renderImages(topic.answer.images);
    answerHtml = `
      <div class="answer-block">
        <div class="answer-header">
          <span class="answer-label">回答</span>
          ${answerAuthor ? `<span class="answer-author">${answerAuthor}</span>` : ''}
        </div>
        <div class="answer-text">${answerText}</div>
        ${answerImages}
      </div>`;
  }

  // Comments section
  let commentsHtml = '';
  if (topic.comments && topic.comments.length > 0) {
    commentsHtml = `
      <div class="comments-section">
        ${topic.comments.map(renderComment).join('')}
      </div>`;
  }

  return `
    <div class="topic-card" id="topic-${topicId}">
      <div class="topic-header">
        <span class="topic-author">${author}</span>
        <span class="topic-date">${date}</span>
        <span class="badge ${typeCls}">${typeLabel}</span>
        ${digestedBadge}
      </div>
      <div class="topic-text">${textHtml}</div>
      ${imagesHtml}
      ${metaHtml}
      ${userTagsHtml}
      ${answerHtml}
      ${commentsHtml}
    </div>`;
}

// ============================================================
// Loading & infinite scroll
// ============================================================

function showLoading() {
  document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
  document.getElementById('loading').style.display = 'none';
}

function showNoResults() {
  document.getElementById('no-results').style.display = 'block';
}

function hideNoResults() {
  document.getElementById('no-results').style.display = 'none';
}

/**
 * Append the next page of topics to the container.
 * Manages state.loading and state.hasMore.
 */
async function loadMore() {
  if (state.loading || !state.hasMore) return;

  state.loading = true;
  showLoading();
  hideNoResults();

  try {
    const json = await fetchTopics();
    if (!json.success) throw new Error(json.error || 'API error');

    const topics  = json.data;
    const meta    = json.meta;
    const container = document.getElementById('topics');

    if (topics.length === 0 && state.page === 1) {
      showNoResults();
    } else {
      container.insertAdjacentHTML('beforeend', topics.map(renderTopic).join(''));
    }

    state.hasMore = meta.page * meta.per_page < meta.total;
    state.page += 1;

    // Update stats badge to reflect filtered total
    const badge = document.getElementById('stats-badge');
    if (badge) badge.textContent = `${meta.total} 条`;
  } catch (err) {
    console.error('Failed to load topics:', err);
  } finally {
    state.loading = false;
    hideLoading();
  }
}

/** Reset pagination state and clear the topics container, then reload. */
function resetAndLoad() {
  state.page    = 1;
  state.hasMore = true;
  document.getElementById('topics').innerHTML = '';
  loadMore();
}

// ============================================================
// Infinite scroll — IntersectionObserver on #scroll-sentinel
// ============================================================

function initInfiniteScroll() {
  const sentinel = document.getElementById('scroll-sentinel');
  const observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting) loadMore();
    },
    { rootMargin: '200px' }
  );
  observer.observe(sentinel);
}

// ============================================================
// Search
// ============================================================

function initSearch() {
  const input = document.getElementById('search-input');
  const onSearch = debounce(() => {
    state.filters.q = input.value.trim();
    resetAndLoad();
  }, 300);
  input.addEventListener('input', onSearch);
}

// ============================================================
// Filters
// ============================================================

function initFilters() {
  const typeEl     = document.getElementById('filter-type');
  const digestedEl = document.getElementById('filter-digested');
  const sinceEl    = document.getElementById('filter-since');
  const untilEl    = document.getElementById('filter-until');
  const tagEl      = document.getElementById('filter-tag');
  const starredEl  = document.getElementById('filter-starred');

  typeEl.addEventListener('change', () => {
    state.filters.type = typeEl.value;
    resetAndLoad();
  });

  digestedEl.addEventListener('change', () => {
    state.filters.digested = digestedEl.checked ? '1' : '';
    resetAndLoad();
  });

  sinceEl.addEventListener('change', () => {
    state.filters.since = sinceEl.value;
    resetAndLoad();
  });

  untilEl.addEventListener('change', () => {
    state.filters.until = untilEl.value;
    resetAndLoad();
  });

  tagEl.addEventListener('change', () => {
    state.filters.tag = tagEl.value;
    resetAndLoad();
  });

  starredEl.addEventListener('change', () => {
    state.filters.starred = starredEl.checked ? '1' : '';
    resetAndLoad();
  });
}

/** Fetch all tags and populate the filter-tag <select>. */
async function populateTagFilter() {
  try {
    const json = await fetchAllTags();
    if (!json.success) return;

    const select = document.getElementById('filter-tag');
    // Remove all options except the first "全部标签"
    while (select.options.length > 1) select.remove(1);

    const items = Array.isArray(json.data) ? json.data : [];
    items.forEach(({ tag, count }) => {
      const opt = document.createElement('option');
      opt.value = tag;
      opt.textContent = `${tag} (${count})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error('Failed to load tags:', err);
  }
}

// ============================================================
// Stats badge
// ============================================================

async function loadStats() {
  try {
    const json = await fetchStats();
    if (!json.success) return;
    const badge = document.getElementById('stats-badge');
    if (badge) badge.textContent = `${json.data.total_topics} 条`;
  } catch (err) {
    console.error('Failed to load stats:', err);
  }
}

// ============================================================
// Lightbox
// ============================================================

function applyLightboxTransform() {
  const img = document.getElementById('lightbox-img');
  if (!img) return;

  const { scale, offsetX, offsetY, dragging } = state.lightbox;
  img.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
  img.style.cursor = dragging ? 'grabbing' : (scale > 1 ? 'grab' : 'default');
}

function resetLightboxView() {
  state.lightbox.scale = 1;
  state.lightbox.offsetX = 0;
  state.lightbox.offsetY = 0;
  state.lightbox.dragging = false;
  applyLightboxTransform();
}

function zoomLightbox(factor) {
  const next = Math.min(
    state.lightbox.maxScale,
    Math.max(state.lightbox.minScale, state.lightbox.scale * factor),
  );
  state.lightbox.scale = Number(next.toFixed(3));
  if (state.lightbox.scale <= 1) {
    state.lightbox.offsetX = 0;
    state.lightbox.offsetY = 0;
  }
  applyLightboxTransform();
}

function openLightbox(src) {
  const lb  = document.getElementById('lightbox');
  const img = document.getElementById('lightbox-img');
  resetLightboxView();
  img.src = src;
  lb.style.display = 'flex';
}

function closeLightbox() {
  const img = document.getElementById('lightbox-img');
  document.getElementById('lightbox').style.display = 'none';
  img.src = '';
  resetLightboxView();
}

function handleLightboxBackdropClick(event) {
  if (event.target === event.currentTarget) {
    closeLightbox();
  }
}

function initLightbox() {
  const stage = document.getElementById('lightbox-stage');
  const img = document.getElementById('lightbox-img');
  if (!stage || !img) return;

  img.addEventListener('load', () => {
    resetLightboxView();
  });

  stage.addEventListener('wheel', (event) => {
    event.preventDefault();
    zoomLightbox(event.deltaY < 0 ? 1.1 : 0.9);
  }, { passive: false });

  img.addEventListener('pointerdown', (event) => {
    if (state.lightbox.scale <= 1) return;
    event.preventDefault();
    state.lightbox.dragging = true;
    state.lightbox.startX = event.clientX - state.lightbox.offsetX;
    state.lightbox.startY = event.clientY - state.lightbox.offsetY;
    img.setPointerCapture(event.pointerId);
    applyLightboxTransform();
  });

  img.addEventListener('pointermove', (event) => {
    if (!state.lightbox.dragging) return;
    state.lightbox.offsetX = event.clientX - state.lightbox.startX;
    state.lightbox.offsetY = event.clientY - state.lightbox.startY;
    applyLightboxTransform();
  });

  const stopDragging = (event) => {
    if (!state.lightbox.dragging) return;
    state.lightbox.dragging = false;
    if (event.pointerId !== undefined && img.hasPointerCapture(event.pointerId)) {
      img.releasePointerCapture(event.pointerId);
    }
    applyLightboxTransform();
  };

  img.addEventListener('pointerup', stopDragging);
  img.addEventListener('pointercancel', stopDragging);

  img.addEventListener('dblclick', () => {
    if (state.lightbox.scale === 1) {
      state.lightbox.scale = 2;
    } else {
      resetLightboxView();
      return;
    }
    applyLightboxTransform();
  });
}

// ============================================================
// Star
// ============================================================

async function handleStar(topicId) {
  try {
    const json = await toggleStar(topicId);
    if (!json.success) return;

    const isStarred = json.data.starred;
    // Update button in-place without a full reload
    const btn = document.querySelector(`.star-btn[data-topic-id="${topicId}"]`);
    if (btn) {
      btn.textContent = isStarred ? '⭐ 收藏' : '☆ 收藏';
      btn.classList.toggle('starred', isStarred);
    }
  } catch (err) {
    console.error('Failed to toggle star:', err);
  }
}

// ============================================================
// Tag modal
// ============================================================

function openTagModal(topicId) {
  // Read current tags from the DOM so we reflect any in-session changes
  const tagsContainer = document.getElementById(`tags-${topicId}`);
  const chips = tagsContainer ? Array.from(tagsContainer.querySelectorAll('.tag-chip')) : [];
  state.currentTagTopicId   = topicId;
  state.currentTagTopicTags = chips.map(c => c.textContent.trim());

  renderCurrentTags();
  document.getElementById('tag-input').value = '';
  document.getElementById('tag-modal').style.display = 'flex';
  document.getElementById('tag-input').focus();
}

function closeTagModal() {
  document.getElementById('tag-modal').style.display = 'none';
  state.currentTagTopicId   = null;
  state.currentTagTopicTags = [];
}

/** Re-render the chips inside the tag modal. */
function renderCurrentTags() {
  const container = document.getElementById('current-tags');
  container.innerHTML = state.currentTagTopicTags
    .map((tag, idx) =>
      `<span class="tag-chip removable">
         ${escapeHtml(tag)}
         <button class="tag-remove" onclick="removeTag(${idx})" title="删除">×</button>
       </span>`)
    .join('');
}

function removeTag(idx) {
  const newTags = state.currentTagTopicTags.filter((_, i) => i !== idx);
  state.currentTagTopicTags = newTags;
  renderCurrentTags();
  persistTags();
}

async function addTag() {
  const input = document.getElementById('tag-input');
  const value = input.value.trim();
  if (!value) return;

  // Avoid duplicates
  if (!state.currentTagTopicTags.includes(value)) {
    state.currentTagTopicTags = [...state.currentTagTopicTags, value];
    renderCurrentTags();
    await persistTags();
  }
  input.value = '';
  input.focus();
}

/** POST the full tag list to the API and update the topic card in-place. */
async function persistTags() {
  const topicId = state.currentTagTopicId;
  if (!topicId) return;
  try {
    const json = await updateTags(topicId, state.currentTagTopicTags);
    if (!json.success) return;

    // Update tag chips on the topic card in-place
    const tagsContainer = document.getElementById(`tags-${topicId}`);
    if (tagsContainer) {
      tagsContainer.innerHTML = renderTagChips(json.data.tags);
    }

    // Refresh the filter-tag dropdown to include any new tags
    populateTagFilter();
  } catch (err) {
    console.error('Failed to save tags:', err);
  }
}

// ============================================================
// Keyboard shortcuts
// ============================================================

function initKeyboard() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeLightbox();
      closeTagModal();
    }
    if (document.getElementById('lightbox').style.display === 'flex') {
      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        zoomLightbox(1.1);
      }
      if (e.key === '-') {
        e.preventDefault();
        zoomLightbox(0.9);
      }
      if (e.key === '0') {
        e.preventDefault();
        resetLightboxView();
      }
    }
  });

  // Enter key in tag input submits
  document.getElementById('tag-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addTag();
    }
  });
}

// ============================================================
// Init
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  initSearch();
  initFilters();
  initKeyboard();
  initLightbox();
  initInfiniteScroll();
  populateTagFilter();
  // Initial load — stats badge is pre-rendered server-side via Jinja,
  // but we refresh it from the API to keep it accurate after filters.
  loadMore();
});
