// v13 Service Worker — Google Workspace Identity + Bootstrap + Safe Init

// =============== GLOBAL STATE ===============
let STATE = {
  studentId: "",
  studentName: "",
  backendBase: "https://gschool.gdistrict.org",
  paused: false,
  focusMode: false,
  examMode: false,
  examUrl: "",
  categories: {},
  allowlist: [],
  teacher_blocks: [],
  chat_enabled: true,
  classInfo: { id: "period1", name: "Period 1", active: true },
  lockApplied: false
};

const URLS = {
  tabClosed:   "https://blocked.gdistrict.org/tab_closed",
  locked:      "https://blocked.gdistrict.org/locked",
  zeroTrust:   "https://blocked.gdistrict.org/Zerotrust",
  teacherBlock:"https://blocked.gdistrict.org/G_schools_Teacher_block"
};

// =============== UTILITIES ===============
function persistState() {
  try { chrome.storage.local.set({ STATE }); }
  catch (err) { console.warn("[PersistState] failed", err); }
}

function nowMs() { return Date.now(); }

// =============== GOOGLE WORKSPACE BOOTSTRAP (fixed) ===============
async function resolveIdentityAndBootstrap() {
  try {
    console.log("[Identity] Starting Workspace bootstrap…");

    // Attempt to get Chrome identity
    const info = await new Promise((resolve) => {
      chrome.identity.getProfileUserInfo({ accountStatus: "ANY" }, (data) => {
        if (chrome.runtime.lastError) {
          console.warn("[Identity] Chrome identity error:", chrome.runtime.lastError.message);
          resolve(null);
        } else {
          resolve(data);
        }
      });
    });

    let email = info?.email || "";
    console.log("[Identity] Chrome identity result:", email || "none");

    // Fallback to interactive OAuth if needed
    if (!email) {
      const token = await new Promise((resolve) => {
        chrome.identity.getAuthToken({ interactive: true }, (tok) => resolve(tok || ""));
      });

      if (token) {
        const resp = await fetch("https://www.googleapis.com/oauth2/v2/userinfo", {
          headers: { Authorization: "Bearer " + token },
        });
        const user = await resp.json();
        email = user.email || "";
        console.log("[Identity] Fallback OAuth email:", email || "none");
      }
    }

    // If still no identity → safe mode as guest
    if (!email) {
      STATE.studentId = "guest-" + Math.random().toString(36).substring(2, 8) + "@local";
      STATE.studentName = "Guest User";
      persistState();
      await enterSafeMode("[Identity] Guest detected (no email)");
      return;
    }

    // Populate identity
    STATE.studentId = email;
    STATE.studentName = email.split("@")[0].replace(/[._]+/g, " ");
    persistState();

    // Domain restriction
    if (!STATE.studentId.endsWith("@gdistrict.org")) {
      await enterSafeMode("[Identity] Non-Gdistrict account blocked: " + STATE.studentId);
      return;
    }

    console.log("[Identity] Logged in as", STATE.studentId);

    // Enable normal icon
    chrome.action.setIcon({
      path: { "16": "icons/16.png", "48": "icons/48.png", "128": "icons/128.png" }
    });

    // Connect to backend
    STATE.backendBase = "https://gschool.gdistrict.org";
    try {
      const res = await fetch(`${STATE.backendBase}/api/heartbeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student: STATE.studentId,
          student_name: STATE.studentName,
          ts: Date.now(),
        }),
      });
      console.log("[Backend] Heartbeat:", res.status);
    } catch (err) {
      console.warn("[Backend] Unreachable:", err);
    }

  } catch (err) {
    console.error("[Identity] Bootstrap error:", err);
    await enterSafeMode("[Identity] Fatal bootstrap error");
  }
}

async function enterSafeMode(reason) {
  console.warn(reason);
  try {
    chrome.action.setPopup({ popup: "" });
    chrome.action.setIcon({
      path: {
        "16": "icons/disabled_16.png",
        "48": "icons/disabled_48.png",
        "128": "icons/disabled_128.png"
      }
    });
    STATE.backendBase = "";
    persistState();
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/disabled_48.png",
      title: "Extension Disabled",
      message: "This extension only works with subscribed users' accounts.",
    });
  } catch (e) {
    console.warn("[SafeMode] enterSafeMode failed:", e);
  }
}

// =============== STARTUP INITIALIZATION ===============
async function initializeServiceWorker() {
  console.log("[Init] Starting G-Schools Service Worker…");

  // Restore last state
  try {
    const res = await chrome.storage.local.get(["STATE"]);
    if (res && res.STATE) Object.assign(STATE, res.STATE);
  } catch (err) {
    console.warn("[Init] Could not load STATE:", err);
  }

  persistState();
  await resolveIdentityAndBootstrap();

  // Optional: call loops after identity resolves
  if (typeof startLoops === "function") startLoops();
}

initializeServiceWorker();

// =============== HANDLE SIGN-IN CHANGES ===============
try {
  chrome.identity.onSignInChanged.addListener((_account, signedIn) => {
    if (signedIn) {
      console.log("[Identity] Sign-in changed — refreshing identity");
      resolveIdentityAndBootstrap();
    }
  });
} catch (err) {
  console.warn("[Identity] onSignInChanged not supported", err);
}

// Expose globally (useful for debugging)
self.resolveIdentityAndBootstrap = resolveIdentityAndBootstrap;

// =============== NOTIFICATIONS ===============
async function showNotification(title, message, require = true) {
  try {
    const id = "gschool-" + String(Date.now());
    await chrome.notifications.create(id, {
      type: "basic",
      iconUrl: "icons/128.png",
      title: title || "G School",
      message: message || "",
      requireInteraction: !!require,
      priority: 2
    });
    return id;
  } catch (e) { /* ignore */ }
  return null;
}

// =============== MAIN LOOPS ===============
function startLoops() {
  (async function loop() {
    try { await syncPolicy(); } catch (e) {}
    try { await pullCommands(); } catch (e) {}
    setTimeout(loop, 5000);
  })();

  (async function loop2() {
    try { await heartbeat(); } catch (e) {}
    setTimeout(loop2, 8000);
  })();
}

// =============== RUNTIME MESSAGES ===============
chrome.runtime.onMessage.addListener((msg, _s, send) => {
  if (!msg) return;
  if (msg.type === "SET_BASE") { STATE.backendBase = msg.base || STATE.backendBase; persistState(); send && send({ ok: true }); }
  if (msg.type === "SET_STUDENT_ID") { STATE.studentId = msg.studentId || STATE.studentId; persistState(); send && send({ ok: true }); }
  if (msg.type === "CHAT_ENABLED") { STATE.chat_enabled = !!msg.enabled; persistState(); }
  if (msg.type === "ANNOUNCE_DISMISSED" && msg.message) {
    chrome.storage.local.get("dismissedAnnouncements", res => {
      const dismissed = res.dismissedAnnouncements || {}; dismissed[msg.message] = true;
      chrome.storage.local.set({ dismissedAnnouncements: dismissed });
    });
  }
  if (msg.type === "POLL_ANSWER") {
    (async () => {
      try {
        await fetch(`${STATE.backendBase}/api/poll_response`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ poll_id: msg.id, answer: msg.answer, student: STATE.studentId || "" })
        });
      } catch (e) { }
    })();
    send && send({ ok: true });
  }
});

// =============== POLICY SYNC / ENFORCEMENT ===============
async function syncPolicy() {
  const r = await fetch(`${STATE.backendBase}/api/policy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student: STATE.studentId || "" })
  });
  if (!r.ok) return;
  const j = await r.json();

  Object.assign(STATE, {
    paused: !!j.paused,
    focusMode: !!j.focus_mode,
    categories: j.categories || {},
    blocked_redirect: j.blocked_redirect || STATE.blocked_redirect,
    allowlist: j.allowlist || [],
    teacher_blocks: j.teacher_blocks || [],
    chat_enabled: !!j.chat_enabled,
    classInfo: j["class"] || STATE.classInfo
  });
  persistState();

  try {
    const prev = (await chrome.storage.local.get("gschool_lastActive")).gschool_lastActive;
    const cur = !!(STATE.classInfo && STATE.classInfo.active);
    if (cur && !prev) {
      await showNotification("Class session is active", "Please open your class tab now. Stay until dismissed.", true);
    }
    await chrome.storage.local.set({ gschool_lastActive: cur });
  } catch (e) {}

  await applyRules();

  if (j.announcement) { handleAnnouncementOnce(j.announcement); }

  // Lock/unlock
  if (STATE.paused) {
    if (!STATE.lockApplied) {
      STATE.lockApplied = true; persistState();
      chrome.tabs.query({ url: ["http://*/*", "https://*/*"] }, (tabs) => {
        const filtered = tabs.filter(t => !t.url.startsWith("chrome://") && !includesBlockedHost(t.url));
        const savedTabs = filtered.map(t => ({ url: t.url, pinned: !!t.pinned, active: !!t.active }));
        chrome.storage.local.set({ gschool_savedTabs: savedTabs, gschool_pauseStartedAt: nowMs() });
        try { chrome.tabs.remove(filtered.map(t => t.id)); } catch (e) {}
        chrome.tabs.create({ url: URLS.locked, active: true });
      });
    } else {
      chrome.tabs.query({ url: ["http://*/*", "https://*/*"] }, (tabs) => {
        for (const t of tabs) { if (!includesBlockedHost(t.url)) { try { chrome.tabs.remove(t.id); } catch (e) {} } }
      });
      chrome.tabs.query({ url: [URLS.locked] }, (existing) => {
        if (!(existing && existing.length)) { chrome.tabs.create({ url: URLS.locked, active: true }); }
      });
    }
  } else if (STATE.lockApplied) {
    STATE.lockApplied = false; persistState();
    chrome.tabs.query({ url: [URLS.locked] }, (lockeds) => {
      if (lockeds && lockeds.length) { try { chrome.tabs.remove(lockeds.map(t => t.id)); } catch (e) {} }
    });
    chrome.storage.local.get(["gschool_savedTabs", "gschool_pauseStartedAt"], (res) => {
      const savedTabs = res.gschool_savedTabs || []; const pausedAt = res.gschool_pauseStartedAt || 0;
      const withinHour = (nowMs() - pausedAt) <= 60 * 60 * 1000;
      if (savedTabs.length && withinHour) {
        for (const t of savedTabs) { try { chrome.tabs.create({ url: t.url, pinned: !!t.pinned, active: !!t.active }); } catch (e) {} }
      }
      chrome.storage.local.remove(["gschool_savedTabs", "gschool_pauseStartedAt"]);
    });
  }
}

async function tabsSendAll(message) {
  const tabs = await chrome.tabs.query({ url: ["http://*/*", "https://*/*"] });
  for (const t of tabs) {
    try { chrome.tabs.sendMessage(t.id, message); } catch (e) {}
  }
}

async function pullCommands() {
  if (!STATE.studentId) return;
  const r = await fetch(`${STATE.backendBase}/api/commands/${encodeURIComponent(STATE.studentId)}`);
  if (!r.ok) return;
  const j = await r.json();

  for (const cmd of (j.commands || [])) {
    if (cmd.type === "notify" && (cmd.title || cmd.message)) {
      await showNotification(cmd.title || "G School", String(cmd.message || ""), true);
      continue;
    }

    if (cmd.type === "poll") {
      chrome.tabs.query({ url: ["http://*/*", "https://*/*"] }, (tabs) => {
        for (const t of tabs) {
          try { chrome.tabs.sendMessage(t.id, { type: "POLL", id: cmd.id, question: cmd.question, options: cmd.options }); }
          catch (e) {}
        }
      });
      continue;
    }

    if (cmd.type === "policy_refresh") {
      try { await syncPolicy(); } catch (e) {}
      continue;
    }

    if (cmd.type === "attention_check") {
      await tabsSendAll({ type: "ATTENTION_CHECK", title: cmd.title || "Are you here?", timeout: cmd.timeout || 30 });
      continue;
    }

    if (cmd.type === "focus_tab" && cmd.url) {
      chrome.tabs.create({ url: String(cmd.url), active: true }, (tab) => {
        if (!tab) return;
        setTimeout(() => {
          try {
            chrome.scripting.executeScript({
              target: { tabId: tab.id },
              func: () => {
                document.addEventListener("visibilitychange", () => {}, { passive: true });
                if (!document.getElementById("gschool-focus-banner")) {
                  const b = document.createElement('div'); b.id = "gschool-focus-banner";
                  Object.assign(b.style, { position: "fixed", bottom: "0", left: 0, right: 0, padding: "6px", background: "#0b57d0", color: "#fff", textAlign: "center", zIndex: 2147483647 });
                  b.textContent = "Focus Mode — stay on this page";
                  document.body.appendChild(b);
                }
              }
            });
          } catch (e) {}
        }, 300);
      });
      continue;
    }

    if (cmd.type === "wb_draw" && Array.isArray(cmd.strokes)) {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs.length) return;
        try {
          chrome.scripting.executeScript({
            target: { tabId: tabs[0].id },
            func: (strokes) => {
              let c = document.getElementById("gschool-wb");
              if (!c) {
                c = document.createElement("canvas"); c.id = "gschool-wb";
                Object.assign(c.style, { position: "fixed", left: 0, top: 0, width: "100vw", height: "100vh", pointerEvents: "none", zIndex: 2147483646 });
                document.body.appendChild(c);
              }
              const ctx = c.getContext("2d");
              const rect = c.getBoundingClientRect();
              const sx = rect.width, sy = rect.height;
              ctx.lineWidth = 3; ctx.strokeStyle = "#ff3465";
              strokes.forEach(s => { ctx.beginPath(); ctx.moveTo(s.x1 * sx, s.y1 * sy); ctx.lineTo(s.x2 * sx, s.y2 * sy); ctx.stroke(); });
            },
            args: [cmd.strokes]
          });
        } catch (e) {}
      });
      continue;
    }

    // === Exam Logic ===
    if (cmd.type === "exam_start" && cmd.url) {
      const examTabId = await startExam(cmd.url);   // now returns tabId
      if (examTabId) {
        try { chrome.tabs.sendMessage(examTabId, { type: "exam_overlay_on" }); } catch (e) {}
      }
      continue;
    }

    if (cmd.type === "exam_end") {
      const stored = await chrome.storage.local.get(["examTabId"]);
      const examTabId = stored.examTabId || null;
      await endExam();
      if (examTabId) {
        try { chrome.tabs.sendMessage(examTabId, { type: "exam_overlay_off" }); } catch (e) {}
      }
      continue;
    }

    if (cmd.type === "close_tabs" && cmd.pattern) {
      chrome.tabs.query({}, (tabs) => {
        for (const t of tabs) {
          if (matchPatternSafe(t.url, cmd.pattern)) {
            chrome.tabs.update(t.id, { url: URLS.tabClosed });
          }
        }
      });
      continue;
    }

    if (cmd.type === "screencap" && cmd.tabId) {
      try {
        chrome.tabs.update(cmd.tabId, { active: true }, () => {
          setTimeout(async () => {
            try {
              const dataUrl = await chrome.tabs.captureVisibleTab(undefined, { format: "png" });
              const pl = { student: STATE.studentId || "", tabshots: {} };
              pl.tabshots[cmd.tabId] = dataUrl;
              await fetch(`${STATE.backendBase}/api/heartbeat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(pl)
              });
            } catch (e) {}
          }, 500);
        });
      } catch (e) {}
      continue;
    }

    if (cmd.type === "open_tabs" && Array.isArray(cmd.urls) && cmd.urls.length) {
      for (const u of cmd.urls) {
        try { chrome.tabs.create({ url: String(u), active: false }); } catch (e) {}
      }
      continue;
    }
  }
}

async function applyRules() {
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  if (existing.length) { await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: existing.map(r => r.id) }); }
  let id = 1; const rules = [];
  const add = (pattern, url) => rules.push({
    id: id++,
    priority: 1,
    action: { type: "redirect", redirect: { url } },
    condition: { urlFilter: pattern, resourceTypes: ["main_frame"] }
  });

  const ALWAYS_ALLOW = "blocked.gdistrict.org";

  if (STATE.examMode && STATE.examUrl) {
    let examHosts = [];
    try {
      const u = new URL(STATE.examUrl);
      const host = u.hostname || "";
      if (host) {
        const parts = host.split(".");
        const variants = new Set([host]);
        if (parts.length >= 2) { variants.add(parts.slice(-2).join(".")); }
        examHosts = Array.from(variants);
      }
    } catch (e) {}
    const excluded = [...examHosts];
    if (!excluded.includes(ALWAYS_ALLOW)) excluded.push(ALWAYS_ALLOW);
    rules.push({
      id: id++,
      priority: 1,
      action: { type: "redirect", redirect: { url: URLS.zeroTrust } },
      condition: { urlFilter: "|http*", resourceTypes: ["main_frame"], excludedRequestDomains: excluded }
    });
  } else if (STATE.paused) {
    rules.push({
      id: id++,
      priority: 1,
      action: { type: "redirect", redirect: { url: URLS.locked } },
      condition: { urlFilter: "|http*", resourceTypes: ["main_frame"] }
    });
  } else if (STATE.focusMode) {
    const allowed = [];
    for (const patt of (STATE.allowlist || [])) {
      const m = patt.match(/\*\:\/\/\*\.([^\/\*]+)\/\*/);
      if (m && m[1]) allowed.push(m[1]);
    }
    if (!allowed.includes(ALWAYS_ALLOW)) allowed.push(ALWAYS_ALLOW);
    rules.push({
      id: id++,
      priority: 1,
      action: { type: "redirect", redirect: { url: URLS.zeroTrust } },
      condition: { urlFilter: "|http*", resourceTypes: ["main_frame"], excludedRequestDomains: allowed }
    });
    for (const p of (STATE.teacher_blocks || [])) { if (p.includes(ALWAYS_ALLOW)) continue; add(p, URLS.teacherBlock); }
  } else {
    for (const p of (STATE.teacher_blocks || [])) { if (p.includes(ALWAYS_ALLOW)) continue; add(p, URLS.teacherBlock); }
    for (const [_nm, cat] of Object.entries(STATE.categories || {})) {
      for (const p of (cat.urls || [])) { if (p.includes(ALWAYS_ALLOW)) continue; add(p, STATE.blocked_redirect); }
    }
  }

  if (rules.length) { await chrome.declarativeNetRequest.updateDynamicRules({ addRules: rules }); }
}

function includesBlockedHost(url) {
  try { return (url || "").includes("blocked.gdistrict.org"); }
  catch (e) { return false; }
}
function matchPatternSafe(url, pattern) {
  if (!pattern) return false;
  try {
    const esc = String(pattern).replace(/[-/\\^$+?.()|[\]{}]/g, "\\$&").replace(/\*/g, ".*");
    return new RegExp("^" + esc + "$", "i").test(url || "");
  } catch (e) { return false; }
}

// ===== DROP-IN: Focus Mode Open/Close Tabs (v3) =====
let lastFocusOpen = 0;

async function enforceFocusTabs() {
  if (!STATE.focusMode) return;

  const allowlist = STATE.allowlist || [];
  if (!allowlist.length) return;

  const alwaysAllow = "blocked.gdistrict.org";
  const allowedHosts = new Set();
  const allowedExact = [];

  for (const pattern of allowlist) {
    try {
      const m = pattern.match(/\*\:\/\/\*\.([^\/\*]+)\/\*/);
      if (m && m[1]) allowedHosts.add(m[1].toLowerCase());
      else if (/^https?:/.test(pattern)) allowedExact.push(pattern.replace(/\*/g, ""));
    } catch (e) {}
  }

  const tabs = await chrome.tabs.query({ url: ["http://*/*", "https://*/*"] });

  // Close all non-allowed tabs
  for (const t of tabs) {
    try {
      const url = new URL(t.url);
      const host = url.hostname.toLowerCase();
      const allowed =
        host.includes(alwaysAllow) ||
        allowedHosts.has(host) ||
        [...allowedHosts].some(h => host.endsWith(h)) ||
        allowedExact.some(p => t.url.startsWith(p));
      if (!allowed) await chrome.tabs.remove(t.id);
    } catch (e) {}
  }

  // Open allowed list once per activation
  const now = Date.now();
  if (now - lastFocusOpen > 10000) { // only once per 10s window
    lastFocusOpen = now;

    const updatedTabs = await chrome.tabs.query({ url: ["http://*/*", "https://*/*"] });
    for (const pattern of allowlist) {
      let openUrl = pattern
        .replace("*://*.", "https://")
        .replace("*://", "https://")
        .replace("/*", "/");
      if (!/^https?:/.test(openUrl)) openUrl = "https://" + openUrl;

      const alreadyOpen = updatedTabs.some(t => t.url.startsWith(openUrl));
      if (!alreadyOpen) {
        console.log("[Focus] Opening:", openUrl);
        try { await chrome.tabs.create({ url: openUrl, active: true }); } catch (e) {}
      }
    }
  }

  // Add focus banner
  const remainTabs = await chrome.tabs.query({ url: ["http://*/*", "https://*/*"] });
  for (const t of remainTabs) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: t.id },
        func: () => {
          if (!document.getElementById("focusBanner")) {
            const b = document.createElement("div");
            b.id = "focusBanner";
            b.textContent = "Focus Mode — Only approved tabs are allowed";
            Object.assign(b.style, {
              position: "fixed",
              bottom: "0",
              left: "0",
              right: "0",
              background: "#0b57d0",
              color: "#fff",
              padding: "8px",
              textAlign: "center",
              fontWeight: "600",
              zIndex: "2147483647"
            });
            document.body.appendChild(b);
          }
        }
      });
    } catch (e) {}
  }
}

// Run immediately when Focus Mode is active
chrome.storage.local.get(["STATE"], async (res) => {
  if (res.STATE && res.STATE.focusMode) await enforceFocusTabs();
});

// Keep enforcing every 15s in case tabs change
setInterval(async () => {
  try { if (STATE.focusMode) await enforceFocusTabs(); }
  catch (e) { console.warn("Focus enforce error", e); }
}, 15000);
// ===== END DROP-IN =====

// =============== HEARTBEAT & BACKEND TOGGLE ===============
async function heartbeat() {
  try {
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    let dataUrl = "";
    try { dataUrl = await chrome.tabs.captureVisibleTab(undefined, { format: "png" }); } catch (e) {}

    const allTabs = await chrome.tabs.query({});
    const pl = {
      student: STATE.studentId || "",
      student_name: STATE.studentName || "",
      tab: activeTab ? { title: activeTab.title, url: activeTab.url, favIconUrl: activeTab.favIconUrl } : {},
      tabs: allTabs.map(t => ({
        id: t.id, title: t.title, url: t.url, active: t.active, favIconUrl: t.favIconUrl
      })),
      screenshot: dataUrl || ""
    };

    const res = await fetch(`${STATE.backendBase}/api/heartbeat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pl)
    });

    if (!res.ok) throw new Error("Backend heartbeat failed");
    const j = await res.json();

    // ===== DISABLE EXTENSION (backend off / subscription ended) =====
    async function disableExtensionGlobally() {
      STATE.disabledByBackend = true;
      persistState();

      try {
        console.log("[Extension] Disabled by backend");

        chrome.action.setIcon({
          path: { "16": "icons/disabled_16.png", "48": "icons/disabled_48.png", "128": "icons/disabled_128.png" }
        });

        // Show disabled popup (custom HTML file)
        chrome.action.setPopup({ popup: "disabled_popup.html" });

        // Notify once
        const notified = (await chrome.storage.local.get("gschool_disabledNotified")).gschool_disabledNotified;
        if (!notified) {
          await chrome.notifications.create({
            type: "basic",
            iconUrl: "icons/disabled_48.png",
            title: "Extension Disabled",
            message: "This extension has been disabled. It may be due to a system malfunction or your device not being compatible with G-School features. Monitoring is still active.",
            priority: 2
          });
          await chrome.storage.local.set({ gschool_disabledNotified: true });
        }

        // Clear rules
        try {
          const existing = await chrome.declarativeNetRequest.getDynamicRules();
          if (existing.length) {
            await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: existing.map(r => r.id) });
            console.log("[Extension] All blocking rules cleared");
          }
        } catch (e) { console.warn("[Extension] Failed to clear rules:", e); }

        // Disable internal flags
        STATE.paused = false;
        STATE.focusMode = false;
        STATE.examMode = false;
        STATE.allowlist = [];
        STATE.teacher_blocks = [];
        persistState();

        console.log("[Extension] Fully disabled");
      } catch (e) {
        console.warn("[DisableExtension] Failed:", e);
      }
    }

    // ===== ENABLE EXTENSION (back to normal) =====
    async function enableExtensionGlobally() {
      STATE.disabledByBackend = false;
      persistState();

      try {
        console.log("[Extension] Re-enabled by backend");

        chrome.action.setIcon({
          path: { "16": "icons/16.png", "48": "icons/48.png", "128": "icons/128.png" }
        });

        // Restore normal popup
        chrome.action.setPopup({ popup: "popup.html" });

        // Clear disabled flag
        await chrome.storage.local.remove("gschool_disabledNotified");

        // Restart loops and rules
        if (typeof startLoops === "function") startLoops();
        await syncPolicy();

        // Welcome notification
        await chrome.notifications.create({
          type: "basic",
          iconUrl: "icons/48.png",
          title: "Welcome to G-School!",
          message: "Hi! Welcome to G-School — your classroom management & online safety system.",
          priority: 2
        });

        console.log("[Extension] Fully restored");
      } catch (e) {
        console.warn("[EnableExtension] Failed:", e);
      }
    }

    // Backend toggle → enable/disable
    if (j && typeof j.extension_enabled !== "undefined") {
      if (!j.extension_enabled) {
        console.warn("[Extension] Disabled by backend toggle.");
        await disableExtensionGlobally();
        return;
      } else if (STATE.disabledByBackend) {
        console.log("[Extension] Re-enabled by backend toggle.");
        STATE.disabledByBackend = false;
        await enableExtensionGlobally();
      }
    }

    // Offtask check (fire-and-forget)
    (async () => {
      try {
        if (pl && pl.tab && pl.tab.url) {
          await fetch(`${STATE.backendBase}/api/offtask/check`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ student: STATE.studentId || "", url: pl.tab.url })
          });
        }
      } catch (e) {}
    })();

  } catch (e) {
    console.warn("[Heartbeat] Error:", e);
  }
}

// =============== ANNOUNCEMENTS ===============
function handleAnnouncementOnce(message) {
  if (!message) return;
  chrome.storage.local.get(["dismissedAnnouncements", "shownAnnouncements"], (res) => {
    const dismissed = res.dismissedAnnouncements || {};
    const shown = res.shownAnnouncements || {};
    if (dismissed[message]) return; if (shown[message]) return;
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || !tabs.length) return; const tabId = tabs[0].id;
      chrome.scripting.executeScript({
        target: { tabId },
        func: (msg) => {
          if (document.getElementById("gschool-announcement")) return;
          const banner = document.createElement("div"); banner.id = "gschool-announcement"; banner.textContent = msg;
          Object.assign(banner.style, { position: "fixed", top: "0", left: "0", width: "100%", padding: "10px", background: "#ffec99", color: "#111", fontSize: "18px", textAlign: "center", zIndex: "2147483647", boxShadow: "0 2px 10px rgba(0,0,0,.15)" });
          const closeBtn = document.createElement("span"); closeBtn.textContent = " ✕"; closeBtn.style.marginLeft = "12px"; closeBtn.style.cursor = "pointer";
          closeBtn.onclick = () => { banner.remove(); chrome.runtime.sendMessage({ type: "ANNOUNCE_DISMISSED", message: msg }); };
          banner.appendChild(closeBtn); document.documentElement.appendChild(banner);
        },
        args: [message]
      });
      shown[message] = Date.now(); chrome.storage.local.set({ shownAnnouncements: shown });
    });
  });
}

// Optional lightweight AI hook: classify and maybe block
async function gscFetchJSON(url, opts) {
  try {
    const res = await fetch(url, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
    return await res.json();
  } catch (e) { return { ok: false, error: String(e) }; }
}
async function classifyAndMaybeBlock(tabId, url) {
  try {
    const base = (STATE && STATE.backendBase) ? STATE.backendBase : "https://gschool.gdistrict.org";
    const resp = await gscFetchJSON(base + "/api/ai/classify", { method: "POST", body: JSON.stringify({ url }) });
    if (resp && resp.ok && resp.blocked && resp.block_url) { chrome.tabs.update(tabId, { url: resp.block_url }); }
  } catch (e) {}
}
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "loading" && tab && tab.url && /^https?:/.test(tab.url)) { classifyAndMaybeBlock(tabId, tab.url); }
});

// ===== BEGIN DROP-IN: Exam Helpers =====
async function setExamState(active, url, tabId) {
  await chrome.storage.local.set({
    examActive: active,
    examUrl: url || "",
    examTabId: tabId || null
  });
}

// Return a Promise that resolves to the created tabId
async function startExam(url) {
  STATE.examMode = true;
  STATE.examUrl = url;
  persistState();

  await new Promise((resolve) => {
    chrome.tabs.query({ url: ["http://*/*", "https://*/*"] }, (tabs) => {
      const filtered = tabs.filter(t => !t.url.startsWith("chrome://") && !includesBlockedHost(t.url));
      const savedTabs = filtered.map(t => ({ url: t.url, pinned: !!t.pinned, active: !!t.active }));
      chrome.storage.local.set({ gschool_examSavedTabs: savedTabs, gschool_examStartedAt: nowMs() });
      try { chrome.tabs.remove(filtered.map(t => t.id)); } catch (e) {}
      resolve();
    });
  });

  const tabId = await new Promise((resolve) => {
    chrome.tabs.create({ url: url, active: true }, async (tab) => {
      await setExamState(true, url, tab?.id || null);
      resolve(tab?.id || null);
    });
  });

  await applyRules();
  return tabId;
}

async function endExam() {
  STATE.examMode = false;
  STATE.examUrl = "";
  persistState();

  await setExamState(false, "", null);

  chrome.tabs.query({}, (tabs) => {
    for (const t of tabs) {
      chrome.scripting.executeScript({
        target: { tabId: t.id },
        func: () => {
          if (document.fullscreenElement) { try { document.exitFullscreen(); } catch (e) {} }
          const b = document.getElementById("gschool-exam-banner"); if (b) b.remove();
          const o = document.getElementById("gschool-exam-overlay"); if (o) o.remove();
        }
      });
    }
  });

  chrome.storage.local.get(["gschool_examSavedTabs", "gschool_examStartedAt"], (res) => {
    const savedTabs = res.gschool_examSavedTabs || [];
    const startedAt = res.gschool_examStartedAt || 0;
    const within2h = (nowMs() - startedAt) <= 2 * 60 * 60 * 1000;
    if (savedTabs.length && within2h) {
      for (const t of savedTabs) {
        try { chrome.tabs.create({ url: t.url, pinned: !!t.pinned, active: !!t.active }); } catch (e) {}
      }
    }
    chrome.storage.local.remove(["gschool_examSavedTabs", "gschool_examStartedAt"]);
  });

  await applyRules();
}

let monitorInterval = null;
function startExamMonitoring() {
  if (monitorInterval) clearInterval(monitorInterval);
  monitorInterval = setInterval(async () => {
    try {
      const stored = await chrome.storage.local.get(["examActive", "examUrl", "examTabId"]);
      if (!stored.examActive) return;
      const tabs = await chrome.tabs.query({});
      const examTab = tabs.find(t => t.id === stored.examTabId);
      if (!examTab) { reportViolation("exam_tab_closed"); return; }
      if (!examTab.url.startsWith(stored.examUrl)) { reportViolation("url_violation", examTab.url); }
      const win = await chrome.windows.get(examTab.windowId);
      if (win.state !== "fullscreen") { reportViolation("fullscreen_exit", examTab.url); chrome.windows.update(win.id, { state: "fullscreen" }); }
    } catch (e) { console.error("Exam monitor error", e); }
  }, 5000);
}
function stopExamMonitoring() { if (monitorInterval) clearInterval(monitorInterval); monitorInterval = null; }

async function reportViolation(reason, url = "") {
  try {
    await fetch(`${STATE.backendBase}/api/exam_violation`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student: STATE.studentId || "", reason, url })
    });
  } catch (e) { console.error("Violation report failed", e); }
}
// ===== END DROP-IN =====


// === AUTO_OPEN_PRESENTATION ===
const AUTO_ROOM_URL = "https://gschool.gdistrict.org/present/admin";
let autoOpenEnabled = true;
let lastAutoOpenTs = 0;

async function checkPresentationAndOpen(){
  if (!autoOpenEnabled) return;
  const now = Date.now();
  if (now - lastAutoOpenTs < 10 * 60 * 1000) return;
  try {
    const res = await fetch("https://gschool.gdistrict.org/api/present/admin/status", { cache: "no-store" });
    if (!res.ok) return;
    const j = await res.json();
    if (j && j.active){
      chrome.tabs.create({ url: AUTO_ROOM_URL });
      lastAutoOpenTs = now;
    }
  } catch (e) {}
}
setInterval(checkPresentationAndOpen, 5000);
