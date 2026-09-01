/* adudu · standalone "New Term" window frontend.
   Creates a term (with one or more sections) through the existing Bridge:
   createTerm -> addSection. Never touches SQLite directly. */

"use strict";

var bridge = null;

// Suppress Chromium's default browser context menu (Back/Forward/Reload/Save page/...).
document.addEventListener("contextmenu", function (e) { e.preventDefault(); });

var $ = function (id) { return document.getElementById(id); };
var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
};

var iconPaths = {
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
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

function addSectionRow(title, content) {
    var row = document.createElement("div");
    row.className = "sec-row";
    row.innerHTML =
        '<div class="sr-top">' +
        '<input class="input" data-sctitle placeholder="Section title" value="' + esc(title || "") + '" autocomplete="off"/>' +
        '<button class="sr-del" title="Remove section"><span>' + svg("trash", 14) + '</span></button>' +
        '</div>' +
        '<textarea class="input textarea" data-sccontent placeholder="Section content">' + esc(content || "") + '</textarea>';
    row.querySelector(".sr-del").onclick = function () {
        if ($("secRows").children.length > 1) { row.remove(); }
    };
    $("secRows").appendChild(row);
}

function setError(msg) { $("ctErr").textContent = msg || ""; }

function createTerm() {
    var name = $("fName").value.trim();
    var full = $("fFull").value.trim();
    var cat = $("fCat").value || "";
    if (!name) { setError("Enter a term name"); $("fName").focus(); return; }
    setError("");

    var sections = [];
    $("secRows").querySelectorAll(".sec-row").forEach(function (row) {
        var title = row.querySelector("[data-sctitle]").value.trim();
        var content = row.querySelector("[data-sccontent]").value;
        if (title || content.trim()) sections.push({ title: title, content: content });
    });

    callP("createTerm", name, full, cat).then(function (term) {
        if (!term || !term.id) { setError("Could not create the term."); return; }
        var chain = Promise.resolve();
        sections.forEach(function (s) {
            chain = chain.then(function () {
                return callP("addSection", term.id, s.title, s.content);
            });
        });
        return chain.then(function () {
            callVoid("createTermClose");
        });
    }).catch(function (e) {
        console.error("JS_CREATE_TERM_ERROR:", e);
        setError("Create failed");
    });
}

function connectBridge() {
    if (typeof qt === "undefined" || !qt.webChannelTransport || typeof QWebChannel === "undefined") return;
    new QWebChannel(qt.webChannelTransport, function (channel) {
        bridge = channel.objects.bridge;
        window.__bridge = bridge;
        if (!bridge) return;
        callP("getCreateTermInit").then(function (d) {
            if (d) {
                $("fName").value = d.name || "";
                var sel = $("fCat");
                var opts = '<option value="">(None)</option>';
                (d.categories || []).forEach(function (c) { opts += '<option value="' + esc(c) + '">' + esc(c) + '</option>'; });
                sel.innerHTML = opts;
            }
            addSectionRow("", "");
        });
    });
}

function init() {
    mountIcons();
    $("addSecIco").innerHTML = svg("plus", 14);

    $("btnAddSec").onclick = function () { addSectionRow("", ""); };
    $("btnCancel").onclick = function () { callVoid("createTermClose"); };
    $("btnClose").onclick = function () { callVoid("createTermClose"); };
    $("btnCreate").onclick = createTerm;

    $("fName").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); createTerm(); } });
    $("fFull").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); createTerm(); } });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { callVoid("createTermClose"); }
    });

    $("ctDrag").addEventListener("pointerdown", function (e) {
        if (e.button !== 0) return;
        if (e.target.closest && e.target.closest("button")) return;
        callVoid("createTermMove");
        e.preventDefault();
    });
    document.querySelectorAll(".rz").forEach(function (h) {
        h.addEventListener("pointerdown", function (e) {
            if (e.button !== 0) return;
            callVoid("createTermResize", h.dataset.edge);
            e.preventDefault();
        });
    });

    connectBridge();
}
document.addEventListener("DOMContentLoaded", init);
