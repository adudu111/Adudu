/* adudu · global search launcher frontend.
   Connects to the shared Bridge via QWebChannel. Search reuses the existing FTS5
   searchTerms slot; results are grouped client-side (matching categories first). Terms
   expand lazily via getTerm. Copy uses the bridge copyText slot. Never executes commands. */

"use strict";

var bridge = null;
var state = { query: "", groups: [], recent: [], pinned: [], pinnedIds: new Set(), expanded: {} };

// Suppress Chromium's default browser context menu (Back/Forward/Reload/Save page/...).
document.addEventListener("contextmenu", function (e) { e.preventDefault(); });

function termId(t) { return (t.id != null) ? t.id : t.term_id; }
function termName(t) { return t.name || t.term || ""; }
function isPinned(id) { return state.pinnedIds.has(id); }
function termById(id) {
    var all = [];
    state.groups.forEach(function (g) { all = all.concat(g.terms); });
    state.recent.forEach(function (t) { all.push(t); });
    state.pinned.forEach(function (t) { all.push(t); });
    for (var i = 0; i < all.length; i++) {
        if (termId(all[i]) === id) return all[i];
    }
    return null;
}

var HUES = [
    { c: "#4A7FFF", fill: "rgba(74,127,255,.16)",  txt: "#7FA8FF" },
    { c: "#8B7CF6", fill: "rgba(139,124,246,.16)", txt: "#A99EFF" },
    { c: "#38BDF8", fill: "rgba(56,189,248,.16)",  txt: "#67D2FB" },
    { c: "#2FBF71", fill: "rgba(47,191,113,.16)",  txt: "#5EDC9A" },
    { c: "#F5A524", fill: "rgba(245,165,36,.16)",  txt: "#FFC45C" },
    { c: "#EC6A9B", fill: "rgba(236,106,155,.16)", txt: "#F28FB4" }
];
function hueOf(name) {
    var h = 2166136261;
    name = (name || "").toLowerCase();
    for (var i = 0; i < name.length; i++) { h ^= name.charCodeAt(i); h = Math.imul(h, 16777619); }
    return HUES[(h >>> 0) % HUES.length];
}

var $ = function (id) { return document.getElementById(id); };
var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
};

var iconPaths = {
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/>',
    chevRight: '<path d="m9 6 6 6-6 6"/>',
    chevDown: '<path d="m6 9 6 6 6-6"/>',
    copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    command: '<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>',
    minimize: '<path d="M5 12h14"/>',
    restore: '<rect x="9" y="9" width="12" height="12" rx="1.5"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    pin: '<path d="M12 17v5"/><path d="M9 3h6l-1 7 3 3H7l3-3z"/>',
    folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
};
function svg(name, size) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="' + (size || 16) + '" height="' + (size || 16) + '">' + (iconPaths[name] || "") + '</svg>';
}
function mountIcons(root) {
    (root || document).querySelectorAll("[data-icon]").forEach(function (el) {
        el.innerHTML = svg(el.getAttribute("data-icon"));
        el.removeAttribute("data-icon");
    });
}

function callP(method) {
    var args = Array.prototype.slice.call(arguments, 1);
    return new Promise(function (resolve) {
        bridge[method].apply(bridge, args.concat(function (data) {
            if (data == null || data === "null") { resolve(null); return; }
            try { resolve(JSON.parse(data)); } catch (e) { resolve(data); }
        }));
    });
}
function callVoid(method) {
    var args = Array.prototype.slice.call(arguments, 1);
    bridge[method].apply(bridge, args);
}

function catChip(cat) {
    if (!cat) return "";
    var h = hueOf(cat);
    return '<span class="cat-chip" style="background:' + h.fill + '; color:' + h.txt + '">' + esc(cat) + '</span>';
}

function isPinned(id) { return state.pinnedIds.has(id); }

function sectionCard(s) {
    return '<div class="l-sec">' +
        '<div class="l-sec-head"><span class="chev">' + svg("chevRight", 14) + '</span><span class="s-title">' + esc(s.title) + '</span>' +
        '<button class="icon-btn" data-copy="' + esc(s.content) + '" title="Copy"><span>' + svg("copy", 14) + '</span></button></div>' +
        '<div class="l-sec-body">' + (esc(s.content) || '<span class="l-empty-sec">(empty)</span>') + '</div></div>';
}

function termDetailHtml(t) {
    var aliases = (t.aliases || []).map(function (a) { return '<span class="l-alias">' + esc(a) + '</span>'; }).join("");
    var secs = (t.sections || []).map(sectionCard).join("");
    if (!secs) secs = '<div class="l-empty-sec">No sections.</div>';
    return '<div class="l-td-meta"><span class="l-td-full">' + esc(t.full_name || "") + '</span></div>' +
        (aliases ? '<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">' + aliases + '</div>' : "") +
        secs;
}

function termRow(t, pinned) {
    return '<div class="l-term" data-id="' + termId(t) + '">' +
        '<div class="l-term-row" data-toggle>' +
        '<span class="chev">' + svg("chevRight", 14) + '</span>' +
        '<span class="t-name">' + esc(termName(t)) + '</span>' +
        catChip(t.category) +
        '<span class="t-desc">' + esc(t.full_name || "") + '</span>' +
        '<span class="t-actions">' +
        '<button class="icon-btn t-pin' + (pinned ? " on" : "") + '" data-pin="' + termId(t) + '" title="Pin"><span>' + svg("pin", 14) + '</span></button>' +
        '<button class="icon-btn" data-copy="' + esc(termName(t)) + '" title="Copy"><span>' + svg("copy", 14) + '</span></button>' +
        '</span></div>' +
        '<div class="l-term-body" data-body></div></div>';
}

function groupHtml(key, terms, label) {
    var rows = terms.map(function (t) { return termRow(t, isPinned(termId(t))); }).join("");
    return '<div class="l-group" data-group>' +
        '<div class="l-group-head" data-gtoggle><span class="chev">' + svg("chevRight", 14) + '</span>' +
        '<span class="g-tag">' + (label || "Category") + '</span>' +
        '<span class="g-name">' + esc(key || "Uncategorized") + '</span>' +
        '<span class="g-count">' + terms.length + '</span></div>' +
        '<div class="l-group-body">' + rows + '</div></div>';
}

function render() {
    var body = $("lBody");
    var results = $("lResults");
    if (!state.query) {
        results.innerHTML = "";
        var parts = [];
        if (state.pinned.length) parts.push(groupHtml("Pinned", state.pinned, "Pinned"));
        results.innerHTML = parts.join("");
        results.querySelectorAll(".l-group").forEach(function (g) { g.classList.add("open"); });
        results.querySelectorAll(".l-group-head .chev").forEach(function (c) { c.innerHTML = svg("chevDown", 14); });
    } else {
        results.innerHTML = state.groups.map(function (g) { return groupHtml(g.category, g.terms, "Category"); }).join("");
    }
    bindBody();
}

function search(q) {
    state.query = (q || "").trim();
    if (!state.query) { state.groups = []; render(); updateBar(); return; }
    callP("launcherSearch", state.query).then(function (d) {
        state.groups = (d && d.groups) || [];
        render();
        updateBar();
    }).catch(function () {
        state.groups = [];
        render();
    });
}

function updateBar() {
    var meta = "";
    if (state.query) {
        var count = 0;
        state.groups.forEach(function (g) { count += g.terms.length; });
        var top = state.groups.length ? state.groups[0].category : "";
        meta = count + " result" + (count === 1 ? "" : "s") + (top ? " · " + top : "");
        $("barText").textContent = state.query;
    } else {
        $("barText").textContent = "Search";
        meta = state.pinned.length ? state.pinned.length + " pinned" : "";
    }
    $("barMeta").textContent = meta;
}

/* ---- event binding (delegated) ---- */
function bindBody() {
    document.querySelectorAll(".l-group-head[data-gtoggle]").forEach(function (h) {
        h.onclick = function () {
            var g = h.closest(".l-group");
            var open = g.classList.toggle("open");
            h.querySelector(".chev").innerHTML = svg(open ? "chevDown" : "chevRight", 14);
        };
    });
    document.querySelectorAll(".l-term-row[data-toggle]").forEach(function (row) {
        row.onclick = function (e) {
            if (e.target.closest(".t-actions")) return;
            var termEl = row.closest(".l-term");
            var id = +termEl.dataset.id;
            var open = termEl.classList.toggle("open");
            row.querySelector(".chev").innerHTML = svg(open ? "chevDown" : "chevRight", 14);
            var body = termEl.querySelector("[data-body]");
            if (open && !body.dataset.loaded) {
                body.dataset.loaded = "1";
                callP("getTerm", id).then(function (t) {
                    if (t) { body.innerHTML = termDetailHtml(t); bindBody(); }
                });
                callVoid("launcherAddRecent", id);
            }
        };
    });
    document.querySelectorAll(".l-sec-head").forEach(function (h) {
        h.onclick = function (e) {
            if (e.target.closest("button")) return;
            var s = h.closest(".l-sec");
            var open = s.classList.toggle("open");
            h.querySelector(".chev").innerHTML = svg(open ? "chevDown" : "chevRight", 14);
        };
    });
    document.querySelectorAll("[data-pin]").forEach(function (b) {
        b.onclick = function (e) {
            e.stopPropagation();
            var id = +b.dataset.pin;
            callVoid("launcherTogglePin", id);
            var on = b.classList.toggle("on");
            if (on) {
                state.pinnedIds.add(id);
                var t = termById(id);
                if (t && !state.pinned.some(function (x) { return termId(x) === id; })) {
                    state.pinned.unshift({ id: id, name: termName(t), full_name: t.full_name, category: t.category });
                }
            } else {
                state.pinnedIds.delete(id);
                state.pinned = state.pinned.filter(function (x) { return termId(x) !== id; });
            }
        };
    });
    document.querySelectorAll("[data-copy]").forEach(function (b) {
        b.onclick = function (e) {
            try {
                e.stopPropagation();
                callVoid("copyText", b.dataset.copy);
                flashCopied(b);
            } catch (err) {
                console.error("JS_COPY_ERROR:", err);
            }
        };
    });
}

function flashCopied(btn) {
    try {
        var old = btn.innerHTML;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#2FBF71" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
        setTimeout(function () { btn.innerHTML = old; }, 700);
    } catch (err) {
        console.error("JS_COPY_FLASH_ERROR:", err);
    }
}

/* ---- minimize / restore / close ---- */
function setMinimized(min) {
    $("launcher").classList.toggle("hidden", min);
    $("bar").classList.toggle("hidden", !min);
    if (min) updateBar();
}

/* ---- bridge ---- */
function connectBridge() {
    if (typeof qt === "undefined" || !qt.webChannelTransport || typeof QWebChannel === "undefined") return;
    new QWebChannel(qt.webChannelTransport, function (channel) {
        bridge = channel.objects.bridge;
        window.__bridge = bridge;
        if (!bridge) return;
        callP("launcherInit").then(function (d) {
            if (d) {
                state.recent = d.recent || [];
                state.pinned = d.pinned || [];
                state.pinnedIds = new Set(state.pinned.map(function (t) { return termId(t); }));
                render();
            }
        });
    });
}

function init() {
    mountIcons();

    var timer = null;
    $("q").addEventListener("input", function () {
        if (timer) clearTimeout(timer);
        timer = setTimeout(function () { search($("q").value); }, 150);
    });

    $("btnClose").onclick = function () { callVoid("launcherClose"); };
    $("btnClose2").onclick = function () { callVoid("launcherClose"); };
    $("btnMin").onclick = function () { setMinimized(true); callVoid("launcherMinimize"); };
    $("btnRestore").onclick = function () { setMinimized(false); callVoid("launcherRestore"); $("q").focus(); };

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { callVoid("launcherClose"); }
    });

    $("launcherDrag").addEventListener("pointerdown", function (e) {
        if (e.button !== 0) return;
        if (e.target.closest && e.target.closest("button")) return;
        callVoid("launcherMove");
        e.preventDefault();
    });
    $("bar").addEventListener("pointerdown", function (e) {
        if (e.button !== 0) return;
        if (e.target.closest && e.target.closest("button")) return;
        callVoid("launcherMove");
        e.preventDefault();
    });

    document.querySelectorAll(".rz").forEach(function (h) {
        h.addEventListener("pointerdown", function (e) {
            if (e.button !== 0) return;
            callVoid("launcherResize", h.dataset.edge);
            e.preventDefault();
        });
    });

    render();
    connectBridge();
}
document.addEventListener("DOMContentLoaded", init);
