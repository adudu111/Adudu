/* adudu · standalone lookup popup frontend.
   Renders a single lookup result pushed from Python through the bridge, with
   Esc/close, Edit, and Open Full Page hand-off to the main window. */

"use strict";

var bridge = null;
var lookupTerm = null;
var lookupQuery = null;

// Suppress Chromium's default browser context menu (Back/Forward/Reload/Save page/...).
document.addEventListener("contextmenu", function (e) { e.preventDefault(); });

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
    chevDown: '<path d="m6 9 6 6 6-6"/>',
    command: '<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>'
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

function catChip(cat) {
    if (!cat) return "";
    var h = hueOf(cat);
    return '<span class="cat-chip" style="background:' + h.fill + '; color:' + h.txt + '">' + esc(cat) + '</span>';
}

function callVoid(method) {
    var args = Array.prototype.slice.call(arguments, 1);
    bridge[method].apply(bridge, args);
}

function secCard(s, index) {
    return '<div class="sec-card compact' + (index === 0 ? " open" : "") + '">' +
        '<div class="sec-head" data-toggle><span class="chev">' + svg("chevDown", 16) + '</span><span class="sec-title">' + esc(s.title) + '</span></div>' +
        '<div class="sec-body"><div class="sec-body-inner"><div class="sec-body-content">' + esc(s.content) + '</div></div></div></div>';
}

function bindSectionToggles() {
    document.querySelectorAll(".sec-card").forEach(function (card) {
        var t = card.querySelector("[data-toggle]");
        if (t) t.onclick = function () { card.classList.toggle("open"); };
    });
}

function renderTerm(t) {
    lookupTerm = t;
    lookupTerm._id = (t.id != null) ? t.id : t.term_id;
    var name = t.name || t.term || "";
    $("btnLookupCreate").style.display = "none";
    $("btnLookupEdit").style.display = "";
    $("btnLookupFull").style.display = "";
    $("lookupBody").innerHTML = '<div class="lookup-term">' +
        '<div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap">' +
        '<h3 style="margin:0">' + esc(name) + '</h3>' +
        catChip(t.category) +
        '</div>' +
        '<div class="lt-full">' + esc(t.full_name || "") + '</div>' +
        '<div style="margin-top:14px">' +
        (t.sections || []).map(function (s, i) { return secCard(s, i); }).join("") +
        '</div>' +
        '</div>';
    bindSectionToggles();
}

function renderNotFound(query) {
    lookupTerm = null;
    lookupQuery = query || "";
    $("btnLookupCreate").style.display = "";
    $("btnLookupEdit").style.display = "none";
    $("btnLookupFull").style.display = "none";
    $("lookupBody").innerHTML = '<div class="lookup-term">' +
        '<h3>' + esc(query || "") + '</h3>' +
        '<p style="color:var(--text-muted)">Term not found in current profile.</p></div>';
}

function onLookupResult(payload) {
    var r = payload;
    if (!r || !r.found) { renderNotFound(r && r.query); return; }
    renderTerm(r);
}

function connectBridge() {
    if (typeof qt === "undefined" || !qt.webChannelTransport || typeof QWebChannel === "undefined") {
        $("lookupBody").innerHTML = '<p style="color:var(--text-muted); padding:16px">Unable to connect.</p>';
        return;
    }
    new QWebChannel(qt.webChannelTransport, function (channel) {
        bridge = channel.objects.bridge;
        window.__bridge = bridge;
        if (!bridge) return;
        bridge.lookupResult.connect(function (payload) {
            try { onLookupResult(JSON.parse(payload)); } catch (e) { }
        });
        bridge.frontendReady();
        $("lookup").focus();
    });
}

function init() {
    mountIcons();

    $("btnLookupClose").onclick = function () { callVoid("closePopup"); };
    $("btnLookupCreate").onclick = function () {
        if (lookupQuery) { callVoid("requestCreateTerm", lookupQuery); }
    };
    $("btnLookupEdit").onclick = function () {
        if (lookupTerm && lookupTerm._id != null) { callVoid("openTerm", lookupTerm._id, true); }
    };
    $("btnLookupFull").onclick = function () {
        if (lookupTerm && lookupTerm._id != null) { callVoid("openTerm", lookupTerm._id, false); }
    };

    $("lookup").addEventListener("keydown", function (e) {
        if (e.key === "Escape") { callVoid("closePopup"); }
    });

    // Drag by the header; skip clicks on the close button.
    $("lookupDrag").addEventListener("pointerdown", function (e) {
        if (e.button !== 0) return;
        if (e.target.closest && e.target.closest("button")) return;
        callVoid("startMove");
        e.preventDefault();
    });

    // Resize from every edge/corner handle.
    document.querySelectorAll(".rz").forEach(function (h) {
        h.addEventListener("pointerdown", function (e) {
            if (e.button !== 0) return;
            callVoid("startResize", h.dataset.edge);
            e.preventDefault();
        });
    });

    connectBridge();
}
document.addEventListener("DOMContentLoaded", init);
