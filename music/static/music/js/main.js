/* ─────────────────────────────────────────────────────────────────
   Cithara — main.js
   Shared across app page (landing) and library page.
   Page context is read from window.CITHARA.page ('app' | 'library').
   ───────────────────────────────────────────────────────────────── */

'use strict';

/* ── CSRF helper ─────────────────────────────────────────────── */
function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

/* ── Fetch wrapper ───────────────────────────────────────────── */
async function api(method, url, data) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
    credentials: 'same-origin',
  };
  if (data !== undefined) opts.body = JSON.stringify(data);
  const res = await fetch(url, opts);
  let json = null;
  try { json = await res.json(); } catch (_) { /* empty */ }
  return { ok: res.ok, status: res.status, data: json };
}

/* ── Application state ───────────────────────────────────────── */
const state = {
  songs: [],
  currentSongId: null,
  isGenerating: false,
  pollTimer: null,
  audio: new Audio(),
  isPlaying: false,
  sidebarOpen: false,
};

const PAGE = (window.CITHARA || {}).page || 'app';

/* ── Toast system ────────────────────────────────────────────── */
function toast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; }, 3200);
  setTimeout(() => el.remove(), 3600);
}

/* ── Sidebar ─────────────────────────────────────────────────── */
function openSidebar() {
  const sb = document.getElementById('sidebar');
  sb.classList.add('open');
  state.sidebarOpen = true;
}
function closeSidebar() {
  const sb = document.getElementById('sidebar');
  sb.classList.remove('open');
  state.sidebarOpen = false;
}

/* ── Format helpers ──────────────────────────────────────────── */
function fmtTime(secs) {
  if (!isFinite(secs)) return '0:00';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}
function moodClass(mood) {
  const valid = ['happy','sad','calm','energetic','romantic','angry','melancholic'];
  return valid.includes(mood) ? `mood-${mood}` : '';
}

/* ────────────────────────────────────────────────────────────────
   LIBRARY — load + render (library page only)
   ─────────────────────────────────────────────────────────────── */
async function loadLibrary() {
  if (PAGE !== 'library') return;
  const r = await api('GET', '/library/api/');
  if (!r.ok) { toast('Could not load library.', 'error'); return; }

  const { songs, song_count, is_full } = r.data;
  state.songs = songs || [];

  // Update counts
  const countEl = document.getElementById('libraryCount');
  if (countEl) countEl.textContent = `${song_count}/20`;
  window.CITHARA.isLibraryFull = is_full;
  const fullAlert = document.getElementById('libraryFullAlert');
  if (fullAlert) fullAlert.style.display = is_full ? 'block' : 'none';
  const genBtn = document.getElementById('generateBtn');
  if (genBtn) genBtn.disabled = is_full && !state.isGenerating;

  renderLibrary();
}

function renderLibrary() {
  if (PAGE !== 'library') return;

  const empty    = document.getElementById('libEmpty');
  const area     = document.getElementById('libSongsArea');
  const detail   = document.getElementById('songDetail');

  // If a song is currently in detail view, keep detail visible
  if (state.currentSongId) return;

  if (!state.songs.length) {
    if (empty)  empty.style.display  = 'flex';
    if (area)   area.style.display   = 'none';
    if (detail) detail.style.display = 'none';
    return;
  }

  if (empty)  empty.style.display  = 'none';
  if (area)   area.style.display   = 'block';
  if (detail) detail.style.display = 'none';

  const grid = document.getElementById('libSongGrid');
  if (!grid) return;
  grid.innerHTML = '';
  state.songs.forEach(song => grid.appendChild(buildLibCard(song)));
}

function buildLibCard(song) {
  const card = document.createElement('div');
  card.className = 'lib-song-card' + (song.id === state.currentSongId ? ' active' : '');
  card.dataset.songId = song.id;
  const mood = song.mood || '';

  card.innerHTML = `
    <div class="lib-song-card-artwork ${moodClass(mood)}">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" style="opacity:0.3">
        <circle cx="12" cy="12" r="3" fill="currentColor"/>
        <path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="lib-song-card-title">${escHtml(song.title || '—')}</div>
    <div class="lib-song-card-meta">${capitalize(mood)} · ${capitalize(song.voice_style || '')}</div>
    <button class="lib-song-card-delete" data-song-id="${song.id}" title="Delete">Delete</button>
  `;

  card.addEventListener('click', (e) => {
    if (e.target.classList.contains('lib-song-card-delete')) return;
    viewSong(song.id);
  });
  card.querySelector('.lib-song-card-delete').addEventListener('click', (e) => {
    e.stopPropagation();
    confirmDeleteSong(song.id, song.title);
  });

  return card;
}


/* ────────────────────────────────────────────────────────────────
   SONG DETAIL VIEW
   ─────────────────────────────────────────────────────────────── */
async function viewSong(songId) {
  const r = await api('GET', `/songs/${songId}/`);
  if (!r.ok) { toast('Could not load song.', 'error'); return; }

  const song = r.data;
  state.currentSongId = songId;

  if (PAGE === 'library') {
    // Update active card state
    document.querySelectorAll('.lib-song-card').forEach(c => {
      c.classList.toggle('active', parseInt(c.dataset.songId) === songId);
    });

    document.getElementById('libEmpty').style.display   = 'none';
    document.getElementById('libSongsArea').style.display = 'none';
    document.getElementById('songDetail').style.display  = 'flex';

    // Wire the "Back to Library" button
    const backBtn = document.getElementById('libBackBtn');
    if (backBtn) backBtn.onclick = () => { state.currentSongId = null; renderLibrary(); };

    // Wire the detail Delete button
    const delBtn = document.getElementById('detailDeleteBtn');
    if (delBtn) delBtn.onclick = () => confirmDeleteSong(songId, song.title || song.metadata?.title);
  }

  // Populate artwork gradient
  const artworkEl = document.getElementById('detailArtwork');
  if (artworkEl) artworkEl.className = `detail-artwork ${moodClass(song.mood || song.metadata?.mood || '')}`;

  // Title + tags
  const titleEl = document.getElementById('detailTitle');
  if (titleEl) titleEl.textContent = song.title || song.metadata?.title || '—';

  const tagsEl = document.getElementById('detailTags');
  if (tagsEl) {
    tagsEl.innerHTML = '';
    const mood = song.mood || song.metadata?.mood;
    const voice = song.voice_style;
    const occasion = song.occasion || song.metadata?.occasion;
    if (mood)    tagsEl.innerHTML += `<span class="tag tag-yellow">${capitalize(mood)}</span>`;
    if (voice)   tagsEl.innerHTML += `<span class="tag">${capitalize(voice)}</span>`;
    if (occasion) tagsEl.innerHTML += `<span class="tag">${capitalize(occasion)}</span>`;
    if (song.status) tagsEl.innerHTML += `<span class="tag">${capitalize(song.status.toLowerCase())}</span>`;
  }

  // Meta grid
  const metaEl = document.getElementById('detailMeta');
  if (metaEl) {
    const meta = song.metadata || {};
    const rows = [
      ['Theme', meta.theme || song.theme],
      ['Duration', meta.duration ? `${meta.duration}s` : null],
      ['Lyrics mode', capitalize((song.lyrics?.mode || song.lyrics_mode || '').replace(/_/g, ' '))],
      ['Created', song.created_at ? new Date(song.created_at).toLocaleDateString() : null],
    ].filter(([, v]) => v);
    metaEl.innerHTML = rows.map(([k, v]) => `
      <div class="meta-item">
        <span class="meta-key">${k}</span>
        <span class="meta-val">${escHtml(String(v))}</span>
      </div>
    `).join('');
  }

  // Lyrics
  const lyricsSection = document.getElementById('detailLyricsSection');
  const lyricsEl = document.getElementById('detailLyrics');
  const lyricsMode = song.lyrics?.mode || song.lyrics_mode;
  const lyricsContent = song.lyrics?.content || song.lyrics_content;
  if (lyricsSection && lyricsEl) {
    if (lyricsMode !== 'instrumental' && lyricsContent) {
      lyricsEl.textContent = lyricsContent;
      lyricsSection.style.display = 'block';
    } else {
      lyricsSection.style.display = 'none';
    }
  }

  // Audio player
  if (song.audio_url) loadPlayer(song);

  // Show / hide inline player section
  const detailPlayerSection = document.getElementById('detailPlayerSection');
  if (detailPlayerSection) detailPlayerSection.style.display = song.audio_url ? 'block' : 'none';
}


/* ────────────────────────────────────────────────────────────────
   AUDIO PLAYER
   ─────────────────────────────────────────────────────────────── */
function loadPlayer(song) {
  const bar = document.getElementById('playerBar');
  if (!bar) return;
  bar.style.display = 'flex';

  const mood  = song.mood || song.metadata?.mood || '';
  const voice = song.voice_style || '';

  document.getElementById('playerTitle').textContent = song.title || song.metadata?.title || '—';
  document.getElementById('playerMeta').textContent =
    [capitalize(mood), capitalize(voice)].filter(Boolean).join(' · ');

  const pa = document.getElementById('playerArtwork');
  if (pa) pa.className = `player-artwork ${moodClass(mood)}`;

  if (state.audio.src !== song.audio_url) {
    state.audio.src = song.audio_url;
    state.audio.load();
  }
  syncPlayPauseIcons();
}

function syncPlayPauseIcons() {
  // Bottom player bar
  const play  = document.querySelector('#playerPlayBtn .icon-play');
  const pause = document.querySelector('#playerPlayBtn .icon-pause');
  if (play && pause) {
    if (state.isPlaying) { play.style.display = 'none'; pause.style.display = 'inline'; }
    else                 { play.style.display = 'inline'; pause.style.display = 'none'; }
  }
  // Inline detail player
  const iplay  = document.querySelector('#detailInlinePlayBtn .icon-play');
  const ipause = document.querySelector('#detailInlinePlayBtn .icon-pause');
  if (iplay && ipause) {
    if (state.isPlaying) { iplay.style.display = 'none'; ipause.style.display = 'inline'; }
    else                 { iplay.style.display = 'inline'; ipause.style.display = 'none'; }
  }
}

function setupPlayerEvents() {
  const playBtn  = document.getElementById('playerPlayBtn');
  const progress = document.getElementById('progressSlider');
  const timeEl   = document.getElementById('playerTime');
  const durEl    = document.getElementById('playerDuration');
  const vol      = document.getElementById('volumeSlider');
  if (!playBtn) return;

  const audio = state.audio;
  audio.volume = 0.8;

  audio.addEventListener('timeupdate', () => {
    if (!isFinite(audio.duration)) return;
    const pct = (audio.currentTime / audio.duration) * 100;
    progress.value = pct;
    timeEl.textContent = fmtTime(audio.currentTime);
    // Keep inline player in sync
    const inlineSlider = document.getElementById('detailInlineSlider');
    const inlineTime   = document.getElementById('detailInlineTime');
    if (inlineSlider) inlineSlider.value = pct;
    if (inlineTime)   inlineTime.textContent = fmtTime(audio.currentTime);
  });
  audio.addEventListener('loadedmetadata', () => {
    durEl.textContent = fmtTime(audio.duration);
    const inlineDur = document.getElementById('detailInlineDur');
    if (inlineDur) inlineDur.textContent = fmtTime(audio.duration);
  });
  audio.addEventListener('ended', () => { state.isPlaying = false; syncPlayPauseIcons(); });

  playBtn.addEventListener('click', () => {
    if (state.isPlaying) { audio.pause(); state.isPlaying = false; }
    else                 { audio.play().catch(() => toast('Cannot play audio.', 'error')); state.isPlaying = true; }
    syncPlayPauseIcons();
  });

  progress.addEventListener('input', () => {
    if (!isFinite(audio.duration)) return;
    audio.currentTime = (progress.value / 100) * audio.duration;
  });
  vol.addEventListener('input', () => { audio.volume = vol.value / 100; });

  // Inline slider also seeks the same audio
  const inlineSlider = document.getElementById('detailInlineSlider');
  if (inlineSlider) {
    inlineSlider.addEventListener('input', () => {
      if (!isFinite(audio.duration)) return;
      audio.currentTime = (inlineSlider.value / 100) * audio.duration;
      progress.value = inlineSlider.value;
    });
  }
}


/* ────────────────────────────────────────────────────────────────
   GENERATE SONG
   ─────────────────────────────────────────────────────────────── */
function getChipValue(groupId) {
  // If the user typed a custom value, that wins over any chip selection
  const CUSTOM_MAP = { moodChips: 'moodCustom', occasionChips: 'occasionCustom' };
  if (CUSTOM_MAP[groupId]) {
    const customEl = document.getElementById(CUSTOM_MAP[groupId]);
    if (customEl && customEl.value.trim()) return customEl.value.trim();
  }
  const active = document.querySelector(`#${groupId} .chip-active`);
  return active ? active.dataset.value : '';
}
function getToggleValue(groupId) {
  const active = document.querySelector(`#${groupId} .toggle-btn-active`);
  return active ? active.dataset.value : '';
}

async function handleGenerate(e) {
  e.preventDefault();
  if (state.isGenerating) return;

  const statusEl  = document.getElementById('genStatus');
  const btn       = document.getElementById('generateBtn');
  const btnText   = btn.querySelector('.generate-btn-text');
  const btnSpinner= btn.querySelector('.generate-btn-spinner');

  const lyricsMode    = getToggleValue('lyricsModeToggle');
  const lyricsContent = document.getElementById('genLyrics')?.value.trim() || '';

  const payload = {
    title:         document.getElementById('genTitle').value.trim(),
    mood:          getChipValue('moodChips'),
    occasion:      getChipValue('occasionChips'),
    theme:         document.getElementById('genTheme')?.value.trim() || null,
    voice_style:   getChipValue('voiceChips'),
    lyrics_mode:   lyricsMode,
    lyrics_content: lyricsMode === 'custom' ? lyricsContent : '',
    duration:      null,
  };

  if (!payload.title) { toast('Please enter a song title.', 'error'); return; }

  state.isGenerating = true;
  btn.disabled = true;
  btnText.style.display = 'none';
  btnSpinner.style.display = 'inline-flex';
  statusEl.textContent = 'Sending request…';
  statusEl.className = 'gen-status active';

  const r = await api('POST', '/songs/generate/', payload);

  if (!r.ok) {
    const msg = r.data?.error || 'Generation failed.';
    toast(msg, 'error');
    statusEl.textContent = msg;
    statusEl.className = 'gen-status error';
    resetGenerateBtn();
    return;
  }

  const songId = r.data.song_id;
  statusEl.textContent = 'Generating your track…';

  // Start polling; on completion redirect to /library/ (or refresh library page)
  pollGeneration(songId, statusEl, payload.title);
}

function resetGenerateBtn() {
  state.isGenerating = false;
  const btn = document.getElementById('generateBtn');
  if (!btn) return;
  btn.disabled = window.CITHARA.isLibraryFull;
  btn.querySelector('.generate-btn-text').style.display = 'inline-flex';
  btn.querySelector('.generate-btn-spinner').style.display = 'none';
}

function pollGeneration(songId, statusEl, songTitle) {
  clearInterval(state.pollTimer);

  state.pollTimer = setInterval(async () => {
    const r = await api('GET', `/songs/${songId}/generation-status/`);
    if (!r.ok) return;

    const { status, audio_url, error_message } = r.data;

    if (status === 'SUCCESS' || status === 'COMPLETED') {
      clearInterval(state.pollTimer);
      statusEl.textContent = 'Done!';
      statusEl.className = 'gen-status';
      toast(`"${songTitle}" is ready!`, 'success');
      resetGenerateBtn();

      if (PAGE === 'app') {
        // Landing page → redirect to library after short delay
        statusEl.textContent = 'Done! Redirecting to library…';
        setTimeout(() => { window.location.href = '/library/'; }, 900);
      } else {
        // Library page → reload library and show song
        await loadLibrary();
        viewSong(songId);
      }

    } else if (status === 'FAILED') {
      clearInterval(state.pollTimer);
      const msg = error_message || 'Generation failed.';
      statusEl.textContent = msg;
      statusEl.className = 'gen-status error';
      toast(msg, 'error');
      resetGenerateBtn();
      if (PAGE === 'library') await loadLibrary();

    } else if (status === 'TIMEOUT') {
      clearInterval(state.pollTimer);
      statusEl.textContent = 'Generation timed out (>10 min). Please try again.';
      statusEl.className = 'gen-status error';
      toast('Generation timed out.', 'error');
      resetGenerateBtn();
      if (PAGE === 'library') await loadLibrary();
    }
  }, 3000);
}


/* ────────────────────────────────────────────────────────────────
   DELETE SONG
   ─────────────────────────────────────────────────────────────── */
function confirmDeleteSong(songId, title) {
  if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;
  deleteSong(songId);
}

async function deleteSong(songId) {
  const r = await api('DELETE', `/songs/${songId}/delete/`);
  if (!r.ok) { toast(r.data?.error || 'Delete failed.', 'error'); return; }

  toast('Song deleted.', 'success');
  state.currentSongId = null;

  const bar = document.getElementById('playerBar');
  if (bar) bar.style.display = 'none';
  const detailPlayerSection = document.getElementById('detailPlayerSection');
  if (detailPlayerSection) detailPlayerSection.style.display = 'none';
  state.audio.pause();
  state.isPlaying = false;

  if (PAGE === 'library') {
    await loadLibrary();
  }
}


/* ────────────────────────────────────────────────────────────────
   SHARE
   ─────────────────────────────────────────────────────────────── */
async function shareCurrentSong() {
  if (!state.currentSongId) return;
  const r = await api('POST', `/songs/${state.currentSongId}/share/`);
  if (!r.ok) { toast(r.data?.error || 'Share failed.', 'error'); return; }

  const shareUrl = `${window.location.origin}/share/${r.data.token}/`;
  document.getElementById('shareUrlInput').value = shareUrl;
  document.getElementById('shareModal').style.display = 'flex';
}


/* ────────────────────────────────────────────────────────────────
   DOWNLOAD
   ─────────────────────────────────────────────────────────────── */
async function downloadCurrentSong() {
  if (!state.currentSongId) return;

  // The download endpoint now streams the audio directly (handles both local
  // files and remote Suno CDN URLs server-side). Open it as a plain link so
  // the browser receives the Content-Disposition: attachment header and saves
  // the file instead of navigating to it.
  const a = document.createElement('a');
  a.href = `/songs/${state.currentSongId}/download/`;
  a.download = '';          // hint to browser; actual filename comes from C-D header
  document.body.appendChild(a);
  a.click();
  a.remove();
}


/* ────────────────────────────────────────────────────────────────
   LOGOUT
   ─────────────────────────────────────────────────────────────── */
async function handleLogout() {
  const r = await api('POST', '/auth/logout/');
  if (r.ok || r.status === 302) {
    window.location.href = '/auth/login/';
  } else {
    toast('Logout failed.', 'error');
  }
}


/* ────────────────────────────────────────────────────────────────
   CHIP / TOGGLE SETUP
   ─────────────────────────────────────────────────────────────── */
function setupChipGroup(groupId) {
  const group = document.getElementById(groupId);
  if (!group) return;

  const CUSTOM_MAP = { moodChips: 'moodCustom', occasionChips: 'occasionCustom' };
  const customEl = CUSTOM_MAP[groupId] ? document.getElementById(CUSTOM_MAP[groupId]) : null;

  group.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      group.querySelectorAll('.chip').forEach(c => c.classList.remove('chip-active'));
      chip.classList.add('chip-active');
      // Clear the custom input so the chip selection takes effect
      if (customEl) customEl.value = '';
    });
  });

  // When user types a custom value, deselect all chips
  if (customEl) {
    customEl.addEventListener('input', () => {
      if (customEl.value.trim()) {
        group.querySelectorAll('.chip').forEach(c => c.classList.remove('chip-active'));
      }
    });
  }
}

function setupToggleGroup(groupId) {
  const group = document.getElementById(groupId);
  if (!group) return;
  group.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      group.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('toggle-btn-active'));
      btn.classList.add('toggle-btn-active');
      if (groupId === 'lyricsModeToggle') {
        const custom = document.getElementById('lyricsContentField');
        if (custom) custom.style.display = btn.dataset.value === 'custom' ? 'flex' : 'none';
      }
    });
  });
}


/* ── XSS-safe helper ─────────────────────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}


/* ────────────────────────────────────────────────────────────────
   INIT
   ─────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {

  // Chip / toggle groups (present on both pages)
  setupChipGroup('moodChips');
  setupChipGroup('occasionChips');
  setupChipGroup('voiceChips');
  setupToggleGroup('lyricsModeToggle');

  // Generate form (present on both pages)
  const form = document.getElementById('generateForm');
  if (form) form.addEventListener('submit', handleGenerate);

  // Sidebar (app page only — legacy collapse/expand, kept for completeness)
  const stripEl = document.getElementById('sidebarToggleStrip');
  const closeEl = document.getElementById('sidebarClose');
  if (stripEl) stripEl.addEventListener('click', openSidebar);
  if (closeEl) closeEl.addEventListener('click', closeSidebar);

  // Player (library page)
  setupPlayerEvents();

  // Detail action buttons (library page)
  const shareBtn    = document.getElementById('detailShareBtn');
  const downloadBtn = document.getElementById('detailDownloadBtn');
  if (shareBtn)    shareBtn.addEventListener('click', shareCurrentSong);
  if (downloadBtn) downloadBtn.addEventListener('click', downloadCurrentSong);

  // Inline play button (library page)
  const inlinePlayBtn = document.getElementById('detailInlinePlayBtn');
  if (inlinePlayBtn) inlinePlayBtn.addEventListener('click', () => {
    if (state.isPlaying) { state.audio.pause(); state.isPlaying = false; }
    else { state.audio.play().catch(() => toast('Cannot play audio.', 'error')); state.isPlaying = true; }
    syncPlayPauseIcons();
  });

  // Share modal
  const shareModal = document.getElementById('shareModal');
  const shareClose = document.getElementById('shareModalClose');
  const copyBtn    = document.getElementById('copyShareBtn');
  if (shareClose) shareClose.addEventListener('click', () => shareModal.style.display = 'none');
  if (shareModal) shareModal.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.currentTarget.style.display = 'none';
  });
  if (copyBtn) copyBtn.addEventListener('click', () => {
    const inp = document.getElementById('shareUrlInput');
    navigator.clipboard?.writeText(inp.value)
      .then(() => toast('Link copied!', 'success'))
      .catch(() => { inp.select(); document.execCommand('copy'); toast('Link copied!', 'success'); });
  });

  // Logout
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);

  // Library page: load songs on entry
  if (PAGE === 'library') {
    loadLibrary();
  }
});

