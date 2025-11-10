// youtube_injection.js
(() => {
  // ====== Config ======
  const API_BASE = "https://gschool.gdistrict.org";
  const RULES_ENDPOINT = `${API_BASE}/api/youtube_rules`;

  // ====== State ======
  let rules = {
    block_keywords: [],
    block_channels: [],
    allow: [],
    allow_mode: false
  };

  let lastCheckedKey = "";
  let overlayEl = null;

  // ====== Utils ======
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const log = (...a) => console.log("[G-School/YT]", ...a);

  const normalize = (s) => (s || "").toLowerCase().trim();

  function getTitle() {
    return (document.title || "").trim();
  }

  function getChannelName() {
    const candidates = [
      '#channel-name a',
      'ytd-channel-name #text',
      'meta[itemprop="author"]',
      'link[itemprop="name"]',
      'ytd-watch-metadata a.yt-simple-endpoint.style-scope.yt-formatted-string',
      'yt-formatted-string.ytd-channel-name a',
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      if (!el) continue;
      if (el.tagName === 'META' || el.tagName === 'LINK') {
        const v = (el.getAttribute('content') || el.getAttribute('name') || "").trim();
        if (v) return v;
      } else {
        const txt = el.textContent.trim();
        if (txt) return txt;
      }
    }
    return "";
  }

  function buildDecisionKey() {
    return `${normalize(getTitle())}||${normalize(getChannelName())}`;
  }

  // ====== Video Player Overlay ======
  function findPlayerContainer() {
    const candidates = [
      '#player-container', '#movie_player',
      'ytd-player#ytd-player', '#player',
      'div.html5-video-player'
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      if (el) {
        if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
        return el;
      }
    }
    const v = document.querySelector('video.html5-main-video');
    if (v && v.parentElement) {
      const p = v.parentElement;
      if (getComputedStyle(p).position === 'static') p.style.position = 'relative';
      return p;
    }
    return null;
  }

  function ensureOverlay() {
    const holder = findPlayerContainer();
    if (!holder) return null;

    if (!overlayEl) {
      overlayEl = document.createElement('div');
      overlayEl.id = 'gschool-yt-overlay';
      Object.assign(overlayEl.style, {
        position: 'absolute',
        inset: '0',
        display: 'none',
        background: 'rgba(0,0,0,0.92)',
        color: '#fff',
        zIndex: '999999',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '24px'
      });

      const box = document.createElement('div');
      box.style.maxWidth = '720px';
      box.style.margin = '0 auto';
      box.style.lineHeight = '1.4';
      box.innerHTML = `
        <div style="font-size:22px;font-weight:700;margin-bottom:10px;">
          🚫 This video has been blocked by your teacher.
        </div>
        <div style="opacity:.9">Please choose another educational video.</div>
      `;
      overlayEl.appendChild(box);
      holder.appendChild(overlayEl);
    }
    return overlayEl;
  }

  function showOverlay() {
    const ov = ensureOverlay();
    if (!ov) return;

    const video = document.querySelector('video.html5-main-video');
    try { video && video.pause(); } catch {}
    try { video && (video.muted = true); } catch {}

    ov.style.display = 'flex';
  }

  function hideOverlay() {
    if (overlayEl) overlayEl.style.display = 'none';
  }

  // ====== Blocking Logic ======
  function shouldBlockNow(title, channel) {
    title = normalize(title);
    channel = normalize(channel);

    if (!title && !channel) return false;

    if (rules.allow_mode) {
      const allowed = rules.allow.some(a => {
        const n = normalize(a);
        return title.includes(n) || channel.includes(n);
      });
      return !allowed;
    }

    if (rules.block_keywords.some(k => title.includes(normalize(k)))) return true;
    if (rules.block_channels.some(c => channel.includes(normalize(c)))) return true;
    return false;
  }

  async function enforceIfNeeded(force = false) {
    const key = buildDecisionKey();
    if (!force && key === lastCheckedKey) return;
    lastCheckedKey = key;

    const block = shouldBlockNow(getTitle(), getChannelName());
    if (block) showOverlay();
    else hideOverlay();
  }

  // ====== Thumbnail Removal (NEW FEATURE) ======
  function removeBlockedThumbnails() {
    const videoItems = document.querySelectorAll('ytd-rich-item-renderer, ytd-video-renderer, ytd-grid-video-renderer');
    for (const item of videoItems) {
      if (item.dataset.gschoolChecked === "1") continue;
      item.dataset.gschoolChecked = "1";

      const titleEl = item.querySelector('#video-title');
      const channelEl = item.querySelector('#channel-name, #text.ytd-channel-name, a.yt-simple-endpoint.yt-formatted-string');
      const title = titleEl ? titleEl.textContent.trim() : "";
      const channel = channelEl ? channelEl.textContent.trim() : "";

      if (shouldBlockNow(title, channel)) {
        // Hide thumbnail and show blocked banner
        item.style.display = "none";
      }
    }
  }

  // Observe dynamic page loads on YouTube
  const thumbObserver = new MutationObserver(() => removeBlockedThumbnails());
  thumbObserver.observe(document.body, { childList: true, subtree: true });

  // ====== Fetch Rules ======
  async function fetchRulesInitial() {
    try {
      const res = await fetch(RULES_ENDPOINT, {credentials: "omit"});
      if (!res.ok) throw new Error("rules fetch HTTP " + res.status);
      const j = await res.json();
      rules = {
        block_keywords: Array.isArray(j.block_keywords) ? j.block_keywords : [],
        block_channels: Array.isArray(j.block_channels) ? j.block_channels : [],
        allow: Array.isArray(j.allow) ? j.allow : [],
        allow_mode: !!j.allow_mode
      };
      log("Loaded rules", rules);
      await enforceIfNeeded(true);
      removeBlockedThumbnails();
    } catch (e) {
      console.warn("[G-School/YT] failed to load rules", e);
    }
  }

  // ====== Boot ======
  (async () => {
    const h = location.hostname;
    if (!/(^|\.)youtube\.com$/.test(h)) return;

    await sleep(300);
    fetchRulesInitial();

    // Recheck thumbnails every 3s (safety for lazy loads)
    setInterval(removeBlockedThumbnails, 3000);

    // Recheck player block every 1.5s
    setInterval(() => enforceIfNeeded(false), 1500);
  })();
})();
