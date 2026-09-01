/* adudu · production frontend for the QWebEngine shell.
   The DOM/CSS come from adudu-ui-preview.html; this script wires the QWebChannel
   bridge to the real backend. No SQLite, services, or business logic live here —
   every mutation is a bridge call that reuses the existing backend. */

"use strict";

window.onerror = function (msg) { window.__jserr = String(msg); };

// Suppress Chromium's default browser context menu on unhandled areas; the app's
// own custom context menus (term/category contextmenu handlers) still appear.
document.addEventListener("contextmenu", function (e) { e.preventDefault(); });

var state = {
    view: "terms",
    selectedId: null,
    multi: new Set(),
    catFilter: null,
    editMode: false,
    lastClickedIdx: -1,
    terms: [],
    cats: [],
    profiles: [],
    activeProfileId: null,
    hotkey: "",
    sortMode: "default"
};
var bridge = null;

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

/* ---- bridge helpers ---- */
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
function termById(id) {
    for (var i = 0; i < state.terms.length; i++) if (state.terms[i].id === id) return state.terms[i];
    return null;
}
function catByName(name) {
    for (var i = 0; i < state.cats.length; i++) if (state.cats[i].name === name) return state.cats[i];
    return null;
}

/* ---- real term CRUD helpers (source of truth = SQLite) ---- */
function updateTermCache(term) {
    for (var i = 0; i < state.terms.length; i++) {
        if (state.terms[i].id === term.id) { state.terms[i] = term; return; }
    }
    state.terms.push(term);
}
function selectTerm(id) {
    state.multi.clear();
    state.selectedId = id;
    state.editMode = false;
    showBulk();
    return callP("getTerm", id).then(function (t) {
        if (!t) { state.selectedId = null; renderDetail(); return null; }
        updateTermCache(t);
        renderDetail();
        return t;
    });
}
function deleteTermById(id) {
    return callP("deleteTerm", id).then(function () {
        if (state.selectedId === id) state.selectedId = null;
        return reloadAll();
    });
}
function duplicateTermById(id) {
    return callP("duplicateTerm", id).then(function (t2) {
        if (t2 && t2.id) { return selectTerm(t2.id); }
        return reloadAll();
    });
}

/* ---- icon svg (port of the preview icon set) ---- */
var iconPaths = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    chevDown: '<path d="m6 9 6 6 6-6"/>',
    chevRight: '<path d="m9 6 6 6-6 6"/>',
    book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6M14 11v6"/>',
    moreH: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    filter: '<path d="M22 3H2l8 9.46V19l4 2v-8.54z"/>',
    sort: '<path d="M7 15l5 5 5-5"/><path d="M7 9l5-5 5 5"/>',
    sidebar: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    moon: '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    chevronsUpDown: '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
    copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    command: '<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 8 5 5 5-5"/><path d="M12 13V3"/>',
    fileText: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8M16 17H8M10 9H8"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-2.64-6.36L21 8"/><path d="M21 3v5h-5"/>',
    power: '<path d="M12 2v10"/><path d="M18.36 6.64a9 9 0 1 1-12.72 0"/>',
    archive: '<rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
    alert: '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/>'
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

function catChip(cat, cls) {
    if (!cat) return "";
    var h = hueOf(cat);
    return '<span class="cat-chip ' + (cls || "") + '" style="--chip-c:' + h.c + '; background:' + h.fill + '; color:' + h.txt + '">' + esc(cat) + '</span>';
}

/* ---- render: term list ---- */
function sortTerms(list) {
    if (state.sortMode === "az") return list.slice().sort(function (a, b) { return (a.name || "").toLowerCase().localeCompare((b.name || "").toLowerCase()); });
    if (state.sortMode === "za") return list.slice().sort(function (a, b) { return (b.name || "").toLowerCase().localeCompare((a.name || "").toLowerCase()); });
    if (state.sortMode === "category") return list.slice().sort(function (a, b) { return ((a.category || "") + (a.name || "")).toLowerCase().localeCompare(((b.category || "") + (b.name || "")).toLowerCase()); });
    return list;
}
function currentTerms() {
    var q = ($("filterInput").value || "").trim().toLowerCase();
    var terms = state.terms.filter(function (t) { return !state.catFilter || t.category === state.catFilter; });
    if (q) {
        terms = terms.filter(function (t) {
            return (t.name || "").toLowerCase().indexOf(q) >= 0 ||
                (t.full_name || "").toLowerCase().indexOf(q) >= 0 ||
                (t.aliases || []).some(function (a) { return a.toLowerCase().indexOf(q) >= 0; });
        });
    }
    return sortTerms(terms);
}
function renderList() {
    var terms = currentTerms();
    $("listCount").textContent = "(" + terms.length + ")";
    if (!terms.length) {
        var q = ($("filterInput").value || "").trim();
        $("listBox").innerHTML = '<div class="empty"><div class="tile muted">' + svg("search", 18) + '</div><h4>' + (q ? 'No terms match "' + esc(q) + '"' : "No terms yet") + '</h4><p>' + (q ? "Try a different filter, or add a new term." : "Use New term below to add your first term.") + '</p><button class="btn btn-ghost btn-sm" id="btnClearFilter">Clear filter</button></div>';
        var b = $("btnClearFilter"); if (b) b.onclick = function () { $("filterInput").value = ""; renderList(); };
        return;
    }
    $("listBox").innerHTML = terms.map(function (t) {
        var sel = state.selectedId === t.id, m = state.multi.has(t.id), h = hueOf(t.category);
        var tile = m ? '<span class="tile chk">' + svg("check", 14) + '</span>'
            : '<span class="tile' + (t.category ? "" : " muted") + '" style="' + (t.category ? "background:" + h.fill + ";color:" + h.txt : "") + '">' + esc((t.name || "?")[0]) + '</span>';
        return '<div class="term-row' + (sel ? " selected" : "") + '" data-term="' + t.id + '" title="' + esc(t.name) + ' — ' + esc(t.full_name) + '">' + tile +
            '<div class="term-meta"><div class="term-name">' + esc(t.name) + catChip(t.category) + '</div><div class="term-full">' + esc(t.full_name) + '</div></div></div>';
    }).join("");
}
function showBulk() {
    var on = state.multi.size > 0;
    $("listHead").classList.toggle("hidden", on);
    $("bulkBar").classList.toggle("hidden", !on);
    $("bulkCount").textContent = state.multi.size + " terms selected";
    renderList(); renderDetail();
}

/* ---- render: term detail ---- */
var editingSection = false;
var dragAnchorIdx = -1, dragStartX = 0, dragStartY = 0, dragMoved = false;

function secCard(s, index, compact, editable) {
    var body;
    if (editable) {
        body = '<div class="sec-body"><div class="sec-body-inner"><div class="sec-body-content" style="padding:0">' +
            '<textarea class="input textarea" data-sec="' + s.id + '" data-sec-edit rows="4" style="width:100%; min-height:88px">' + esc(s.content) + '</textarea>' +
            '</div></div></div>';
    } else {
        body = '<div class="sec-body"><div class="sec-body-inner"><div class="sec-body-content sec-content" data-sec-content="' + s.id + '" title="Double-click to edit content" style="cursor:text">' + esc(s.content) + '</div></div></div>';
    }
    return '<div class="sec-card' + (compact ? " compact" : "") + (index === 0 ? " open" : "") + '" data-sec="' + index + '">' +
        '<div class="sec-head" data-toggle><span class="chev">' + svg("chevDown", 16) + '</span><span class="sec-title" data-sec-title="' + s.id + '" title="Double-click to rename" style="cursor:text">' + esc(s.title) + '</span></div>' + body + '</div>';
}

function inlineEditTitle(span, secId) {
    var old = span.textContent;
    var input = document.createElement("input");
    input.className = "input";
    input.value = old;
    input.style.height = "26px";
    input.style.padding = "0 6px";
    span.replaceWith(input);
    editingSection = true;
    input.focus();
    input.select();
    var done = false;
    function finish(save) {
        if (done) return;
        done = true;
        editingSection = false;
        var val = input.value.trim();
        if (save && val && val !== old) { callVoid("renameSection", secId, val); return; }
        renderDetail();
    }
    input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); finish(true); }
        else if (e.key === "Escape") { finish(false); }
    });
    input.addEventListener("blur", function () { finish(true); });
}

function inlineEditContent(div, secId) {
    var old = div.textContent;
    var ta = document.createElement("textarea");
    ta.className = "input textarea";
    ta.value = old;
    ta.style.width = "100%";
    ta.style.minHeight = "88px";
    div.replaceWith(ta);
    editingSection = true;
    ta.focus();
    var done = false;
    function finish(save) {
        if (done) return;
        done = true;
        editingSection = false;
        if (save && ta.value !== old) { callVoid("updateSection", secId, ta.value); return; }
        renderDetail();
    }
    ta.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { finish(false); }
        else if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); finish(true); }
    });
    ta.addEventListener("blur", function () { finish(true); });
}

function bindSecEvents() {
    document.querySelectorAll(".sec-card").forEach(function (card) {
        var togg = card.querySelector("[data-toggle]");
        if (togg) togg.onclick = function () {
            if (editingSection) return;
            card.classList.toggle("open");
        };
    });
    document.querySelectorAll("[data-sec-title]").forEach(function (el) {
        el.addEventListener("dblclick", function (e) {
            e.stopPropagation();
            inlineEditTitle(el, +el.dataset.secTitle);
        });
    });
    document.querySelectorAll("[data-sec-content]").forEach(function (el) {
        el.addEventListener("dblclick", function (e) {
            e.stopPropagation();
            inlineEditContent(el, +el.dataset.secContent);
        });
    });
}
function bindSectionEditors(term) {
    document.querySelectorAll("[data-sec-edit]").forEach(function (ta) {
        var secId = +ta.dataset.sec;
        var timer = null;
        ta.addEventListener("input", function () {
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () {
                callVoid("updateSection", secId, ta.value);
                var sec = term.sections.find(function (s) { return s.id === secId; });
                if (sec) sec.content = ta.value;
            }, 400);
        });
    });
}
function renderEdit(t) {
    var secs = t.sections.map(function (s, i) { return secCard(s, i, false, true); }).join("");
    var categories = state.cats.map(function (c) { return c.name; });
    var currentCat = t.category || "";
    var opts = '<option value=""' + (currentCat ? "" : " selected") + '>(None)</option>' +
        categories.map(function (c) {
            return '<option value="' + esc(c) + '"' + (c === currentCat ? " selected" : "") + '>' + esc(c) + '</option>';
        }).join("");
    $("detailBox").innerHTML =
        '<div class="header-card">' +
        '<h2 style="font-size:16px; margin-bottom:16px">Editing · ' + esc(t.name) + '</h2>' +
        '<div class="field"><label>Term</label><input class="input" id="eName" value="' + esc(t.name) + '" autocomplete="off"/></div>' +
        '<div class="field"><label>Full name</label><input class="input" id="eFull" value="' + esc(t.full_name) + '" autocomplete="off"/></div>' +
        '<div class="field-row"><div class="field" style="flex:1"><label>Category</label>' +
        '<div class="select-wrap" style="height:32px">' + svg("folder", 16) +
        '<select class="input" id="eCat" style="padding-left:30px">' + opts + '</select></div></div>' +
        '<div class="field" style="flex:2"><label>Aliases <span style="color:var(--text-muted);font-weight:400">(Enter to add)</span></label><input class="input" id="eAlias" value="' + esc((t.aliases || []).join(", ")) + '" placeholder="alias1, alias2" autocomplete="off"/></div></div>' +
        '<div style="margin-top:16px"><div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">Sections</div>' + secs +
        '<button class="add-section" id="btnAddSection2">' + svg("plus", 15) + 'Add section</button></div>' +
        '<div style="display:flex; justify-content:flex-end; gap:8px; margin-top:20px">' +
        '<button class="btn btn-ghost" id="btnCancelEdit">Cancel</button>' +
        '<button class="btn btn-primary" id="btnSaveEdit">Save</button></div>' +
        '</div>';
    mountIcons();
    bindSecEvents();
    bindSectionEditors(t);
    $("btnAddSection2").onclick = function () {
        openNameDialog("section", function (val, content) { callVoid("addSection", t.id, val, content || ""); }, "", true);
    };
    $("btnCancelEdit").onclick = function () { state.editMode = false; renderDetail(); };
    $("btnSaveEdit").onclick = function () {
        var name = $("eName").value.trim() || t.name;
        var full = $("eFull").value.trim();
        var cat = $("eCat").value || "";
        var aliases = $("eAlias").value.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        callP("updateTerm", t.id, name, full, cat).then(function (updated) {
        (t.aliases || []).forEach(function (a) { if (aliases.indexOf(a) < 0) { callVoid("removeAlias", t.id, a); } });
        aliases.forEach(function (a) { if ((t.aliases || []).indexOf(a) < 0) { callVoid("addAlias", t.id, a); } });
        if (updated) updateTermCache(updated);
        state.editMode = false;
        renderList();
        renderDetail();
        toast("Saved");
        }).catch(function (e) {
            console.error("JS_UPDATE_TERM_ERROR:", e);
            toast("Save failed");
        });
    };
}
function renderDetail() {
    var box = $("detailBox");
    if (!box) return;
    if (state.multi.size > 0) {
        box.innerHTML = '<div class="header-card" style="text-align:center; padding:40px"><h2 style="font-size:16px">' + state.multi.size + ' terms selected</h2><p style="color:var(--text-muted); margin:6px 0 0">Select a single term to view its details.</p></div>';
        return;
    }
    if (!state.selectedId) {
        box.innerHTML = '<div class="detail-empty"><div class="tile muted" style="width:40px;height:40px;display:grid;place-items:center;opacity:.6">' + svg("book", 20) + '</div><h3>Select a term to view it</h3><p>Use the list, or press Ctrl K to search.</p></div>';
        return;
    }
    var t = termById(state.selectedId);
    if (!t) return;
    if (state.editMode) { renderEdit(t); return; }
    var secs = t.sections.map(function (s, i) { return secCard(s, i, false, false); }).join("");
    box.innerHTML =
        '<div class="header-card">' +
        '<div class="hrow">' +
        '<div style="display:flex; align-items:center; gap:10px; min-width:0">' +
        '<h2 style="margin:0">' + esc(t.name) + '</h2>' +
        catChip(t.category) +
        '</div>' +
        '<div style="display:flex; gap:8px; flex:0 0 auto">' +
        '<button class="icon-btn" id="btnOverflow">' + svg("moreH") + '</button>' +
        '<button class="btn btn-primary" id="btnEdit">' + svg("pencil", 14) + 'Edit</button></div></div>' +
        '<div class="hmeta"><span style="color:var(--text-secondary); font-size:13px">' + esc(t.full_name) + '</span></div>' +
        ((t.aliases && t.aliases.length) ? '<div style="margin-top:12px"><div class="aliases-label">Aliases</div><div class="aliases">' + t.aliases.map(function (a) { return '<span class="chip">' + esc(a) + '</span>'; }).join("") + '</div></div>' : '') +
        '</div>' +
        secs +
        '<button class="add-section" id="btnAddSection">' + svg("plus", 15) + 'Add section</button>' +
        '<div class="detail-foot"><span>' + t.sections.length + ' sections · dynamic titles</span><span>' + esc(t.category || "no category") + '</span></div>';
    mountIcons();
    bindSecEvents();
    $("btnEdit").onclick = function () { state.editMode = true; renderDetail(); };
    $("btnOverflow").onclick = function (e) {
        e.stopPropagation();
        ctxShow(e.clientX, e.clientY,
            '<button class="ctx-item" data-oa="duplicate">' + svg("copy") + 'Duplicate</button>' +
            '<button class="ctx-item" data-oa="export">' + svg("upload") + 'Export</button>' +
            '<button class="ctx-item danger" data-oa="delete">' + svg("trash") + 'Delete</button>', "overflow");
    };
    $("btnAddSection").onclick = function () {
        openNameDialog("section", function (val, content) { callVoid("addSection", t.id, val, content || ""); }, "", true);
    };
}

/* ---- render: categories ---- */
function renderCategories() {
    if (!$("catRows")) return;
    var counts = {};
    state.terms.forEach(function (t) { if (t.category) counts[t.category] = (counts[t.category] || 0) + 1; });
    $("catCount").textContent = "(" + Object.keys(counts).length + ")";
    $("catRows").innerHTML = state.cats.map(function (c) {
        return '<div class="cat-row' + (state.catFilter === c.name ? " selected" : "") + '" data-cat="' + esc(c.name) + '">' + svg("folder", 16) +
            '<span class="cat-name">' + esc(c.name) + '</span><span class="cat-count">' + (counts[c.name] || 0) + '</span></div>';
    }).concat('<div class="cat-row' + (state.catFilter === null ? " selected" : "") + '" data-cat="">' + svg("book", 16) + '<span class="cat-name">All terms</span><span class="cat-count">' + state.terms.length + '</span></div>').join("");
    renderCatTerms();
}
function renderCatTerms() {
    if (!$("catTermsBox")) return;
    var q = ($("catFilter").value || "").trim().toLowerCase();
    var terms = sortTerms((state.catFilter ? state.terms.filter(function (t) { return t.category === state.catFilter; }) : state.terms)
        .filter(function (t) { return !q || (t.name || "").toLowerCase().indexOf(q) >= 0 || (t.full_name || "").toLowerCase().indexOf(q) >= 0; }));
    $("catTermsTitle").textContent = state.catFilter || "All terms";
    $("catTermsCount").textContent = state.catFilter ? ("(" + terms.length + " of " + state.terms.length + ")") : ("(" + terms.length + ")");
    if (!terms.length) {
        $("catTermsBox").innerHTML = '<div class="empty"><div class="tile muted">' + svg("folder", 18) + '</div><h4>' + esc(state.catFilter || "This view") + ' is empty</h4><p>No terms ' + (state.catFilter ? "in this category" : "yet") + '.</p></div>';
        return;
    }
    $("catTermsBox").innerHTML = terms.map(function (t) {
        var h = hueOf(t.category);
        return '<div class="term-row catterm" data-term="' + t.id + '" title="' + esc(t.name) + ' — ' + esc(t.full_name) + '">' +
            '<span class="tile' + (t.category ? "" : " muted") + '" style="' + (t.category ? "background:" + h.fill + ";color:" + h.txt : "") + '">' + esc((t.name || "?")[0]) + '</span>' +
            '<div class="term-meta"><div class="term-name">' + esc(t.name) + '</div><div class="term-full">' + esc(t.full_name) + '</div></div></div>';
    }).join("");
}

/* ---- add-terms-to-category dialog ---- */
function openAddTermsDialog() {
    if (!state.catFilter) return;
    var already = {};
    state.terms.forEach(function (t) { if (t.category === state.catFilter) already[t.id] = true; });
    var rows = state.terms.map(function (t) {
        if (already[t.id]) return null;
        return '<label style="display:flex; align-items:center; gap:10px; height:30px; padding:0 8px; border-radius:var(--r-md); cursor:pointer; color:var(--text-primary)">' +
            '<input type="checkbox" data-addterm="' + t.id + '"/>' +
            '<span style="flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">' + esc(t.name) + '</span>' +
            '<span style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted)">' + esc(t.category || "—") + '</span></label>';
    }).filter(Boolean);
    $("dlgAddTermsTitle").textContent = 'Add terms to "' + state.catFilter + '"';
    $("addTermsBox").innerHTML = rows.length ? rows.join("") : '<p style="color:var(--text-muted)">All terms are already in this category.</p>';
    openDialog("dlgAddTerms");
}

/* ---- context menu ---- */
var ctxKind = null, ctxTarget = null;
function ctxShow(x, y, html, kind) {
    ctxKind = kind;
    var m = $("ctx");
    m.innerHTML = html; mountIcons();
    m.classList.remove("hidden");
    m.style.left = Math.min(x, window.innerWidth - 210) + "px";
    m.style.top = Math.min(y, window.innerHeight - 200) + "px";
    ctxBind();
}
function ctxBind() {
    document.querySelectorAll("#ctx .ctx-item").forEach(function (b) {
        b.onclick = function (e) {
            e.stopPropagation();
            var act = b.dataset.oa;
            if (ctxKind === "category") {
                var c = ctxTarget;
                if (act === "rename") openNameDialog("category", function (val) { callVoid("renameCategory", c.id, val); }, c.name);
                if (act === "moveup" || act === "movedown") {
                    var ids = state.cats.map(function (x) { return x.id; });
                    var idx = ids.indexOf(c.id);
                    var nidx = act === "moveup" ? idx - 1 : idx + 1;
                    if (idx >= 0 && nidx >= 0 && nidx < ids.length) {
                        var tmp = ids[idx]; ids[idx] = ids[nidx]; ids[nidx] = tmp;
                        callVoid("reorderCategories", JSON.stringify(ids));
                    }
                }
                if (act === "delete") openConfirm('Delete category "' + c.name + '"', "Its terms will be kept — only the category assignment is cleared.", function () { callVoid("deleteCategory", c.id); });
            } else if (ctxKind === "term") {
                var t = termById(ctxTarget);
                if (act === "open") { state.selectedId = t.id; state.editMode = false; state.multi.clear(); setView("terms"); renderList(); renderDetail(); }
                if (act === "edit") { state.selectedId = t.id; state.editMode = true; state.multi.clear(); setView("terms"); renderList(); renderDetail(); }
                if (act === "uncat") { callVoid("clearCategory", t.id); }
                if (act === "delete") openConfirm('Delete "' + t.name + '"', "This term will be permanently removed.", function () { callVoid("deleteTerm", t.id); });
            } else if (ctxKind === "term-list") {
                var tl = termById(ctxTarget);
                if (act === "open") { selectTerm(tl.id); }
                if (act === "edit") { state.selectedId = tl.id; state.editMode = true; state.multi.clear(); showBulk(); }
                if (act === "duplicate") duplicateTermById(tl.id);
                if (act === "delete") openConfirm('Delete "' + tl.name + '"', "This term will be permanently removed.", function () { deleteTermById(tl.id); });
            } else if (ctxKind === "profile") {
                var p = ctxTarget;
                if (act === "rename") openNameDialog("profile", function (val) { callVoid("renameProfile", p.id, val); }, p.name);
                if (act === "delete") openConfirm('Delete profile "' + p.name + '"?', "The profile and all of its terms will be permanently removed.", function () { callVoid("deleteProfile", p.id); });
            } else if (ctxKind === "overflow") {
                var tt = termById(state.selectedId);
                if (act === "duplicate") duplicateTermById(tt.id);
                if (act === "export") callVoid("fileAction", "export-json");
                if (act === "delete") openConfirm('Delete "' + tt.name + '"', "This term will be permanently removed.", function () { deleteTermById(tt.id); });
            }
            hideCtx();
        };
    });
}
function hideCtx() { $("ctx").classList.add("hidden"); ctxKind = null; ctxTarget = null; }

/* ---- profile selector ---- */
function refreshProfileSelect() {
    var sel = $("profileSelect");
    if (!sel) return;
    var current = state.activeProfileId;
    sel.innerHTML = state.profiles.map(function (p) {
        return '<option value="' + p.id + '">' + esc(p.name) + '</option>';
    }).join("");
    if (current != null) {
        for (var i = 0; i < sel.options.length; i++) {
            if (+sel.options[i].value === current) { sel.selectedIndex = i; break; }
        }
    }
}
function currentProfile() {
    for (var i = 0; i < state.profiles.length; i++) if (state.profiles[i].id === state.activeProfileId) return state.profiles[i];
    return null;
}

/* ---- search popover + lookup ---- */
function highlight(name, q) {
    if (!q) return esc(name);
    var i = (name || "").toLowerCase().indexOf(q.toLowerCase());
    return i < 0 ? esc(name) : esc(name.slice(0, i)) + "<mark>" + esc(name.slice(i, i + q.length)) + "</mark>" + esc(name.slice(i + q.length));
}
function resultRows(terms, q) {
    if (!terms.length) return '<div class="empty" style="padding:24px 12px"><div class="tile muted">' + svg("search", 18) + '</div><h4>No results for "' + esc(q) + '"</h4><p>Check the spelling, or search a full name or alias.</p></div>';
    return terms.slice(0, 8).map(function (r) {
        return '<div class="lookup-row" data-term="' + r.term_id + '">' + catChip(r.category, "") +
            '<span class="lr-name">' + highlight(r.term, q) + '</span><span class="lr-full">' + esc(r.full_name) + '</span></div>';
    }).join("") + (terms.length > 8 ? '<div class="lookup-row" data-seeall style="color:var(--accent-text); justify-content:center; font-weight:600">See all results →</div>' : "");
}
function renderSearchPop() {
    var q = $("globalSearch").value.trim();
    var pop = $("searchPop");
    $("searchClear").classList.toggle("hidden", !q);
    $("searchKbd").classList.toggle("hidden", !!q);
    if (!q) { pop.classList.add("hidden"); return; }
    callP("searchTerms", q).then(function (terms) {
        terms = terms || [];
        $("searchPopBody").innerHTML = resultRows(terms, q);
        pop.classList.remove("hidden");
    });
}
function openLookupTerm(t) {
    $("lookup").classList.remove("hidden");
    $("lookupHints").classList.add("hidden");
    var name = t.name || t.term || "";
    $("lookupBody").innerHTML = '<div class="lookup-term">' +
        '<h3>' + esc(name) + '</h3><div class="lt-full">' + esc(t.full_name || "") + '</div>' +
        '<div class="lt-meta" style="margin-top:8px">' + catChip(t.category) + '</div>' +
        (t.sections || []).map(function (s, i) { return secCard(s, i, true, false); }).join("") +
        '</div>';
    mountIcons(); bindSecEvents();
    state._lookupTerm = t;
    $("lookup").focus();
}
function openLookupResults() {
    $("lookup").classList.remove("hidden");
    $("lookupHints").classList.remove("hidden");
    $("lookupBody").innerHTML = resultRows(state.terms.slice(0, 8).map(function (t) {
        return { term_id: t.id, term: t.name, full_name: t.full_name, category: t.category };
    }), "");
    mountIcons();
    state._lookupTerm = null;
    $("lookup").focus();
}
function closeLookup() {
    $("lookup").classList.add("hidden");
    state._lookupTerm = null;
    $("globalSearch").blur();
}

/* ---- dialogs ---- */
var dlgCb = null;
function openDialog(id) { $("scrim").classList.remove("hidden"); $(id).classList.remove("hidden"); var f = $(id).querySelector("input"); if (f) setTimeout(function () { f.focus(); }, 40); }
function closeDialogs() { $("scrim").classList.add("hidden"); document.querySelectorAll(".dialog").forEach(function (d) { d.classList.add("hidden"); }); dlgCb = null; }
function openConfirm(title, msg, cb) { $("cfTitle").textContent = title; $("cfMsg").textContent = msg; dlgCb = cb; openDialog("dlgConfirm"); }
function openNameDialog(kind, cb, prefill, showContent) {
    prefill = prefill || "";
    $("dlgNameTitle").textContent = (kind === "section" ? "New Section" : (kind === "category" ? "New Category" : "Rename"));
    $("dlgNameLabel").textContent = (kind === "section" ? "Section title" : (kind === "category" ? "Category name" : "Profile name"));
    $("fName").value = prefill;
    $("fNameContentWrap").classList.toggle("hidden", !showContent);
    $("fNameContent").value = "";
    dlgCb = cb; openDialog("dlgName");
}
function fillCatSelect() {
    var s = $("fTermCat");
    s.innerHTML = '<option value="">(None)</option>' + state.cats.map(function (c) { return "<option>" + esc(c.name) + "</option>"; }).join("");
}

/* ---- misc ---- */
function toast(msg) {
    var t = $("toast");
    $("toastMsg").textContent = msg;
    t.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.add("hidden"); }, 1800);
}
function setView(v) {
    state.view = v;
    document.querySelectorAll(".view").forEach(function (el) { el.classList.toggle("hidden", el.id !== "view-" + v); });
    document.querySelectorAll(".nav-item[data-view]").forEach(function (b) { b.classList.toggle("active", b.dataset.view === v); });
    $("bcCur").textContent = v === "terms" ? "All Terms" : "Categories";
    if (v === "terms") { renderList(); renderDetail(); }
    else { renderCategories(); }
}
function applyTheme() {
    var dark = !(document.body.classList.contains("light"));
    var sw = $("btnTheme");
    if (sw) {
        sw.classList.toggle("is-dark", dark);
        var icon = sw.querySelector(".ts-icon");
        if (icon) icon.innerHTML = svg(dark ? "moon" : "sun", 12);
    }
}

/* ---- data load ---- */
function reloadAll() {
    return callP("getTerms").then(function (terms) {
        state.terms = terms || [];
    }).then(function () {
        return callP("getCategories").then(function (cats) { state.cats = cats || []; });
    }).then(function () {
        return callP("getProfiles").then(function (d) {
            if (d) {
                state.profiles = d.profiles || [];
                state.activeProfileId = d.active_profile_id;
            }
        });
    }).then(function () {
        refreshProfileSelect();
        if (state.selectedId && !termById(state.selectedId)) state.selectedId = null;
        if (state.view === "terms") { renderList(); renderDetail(); }
        else { renderCategories(); }
    });
}
function loadTerms() {
    // Terms come from SQLite through the bridge, never a hard-coded array.
    var box = $("listBox");
    if (box && !state.terms.length) {
        box.innerHTML = '<div class="empty">Loading terms\u2026</div>';
    }
    return callP("getTerms").then(function (terms) {
        state.terms = terms || [];
        if (state.terms.length && !state.selectedId) state.selectedId = state.terms[0].id;
        if (state.view === "terms") { renderList(); renderDetail(); }
        return state.terms;
    }).catch(function (e) {
        console.error("JS_GET_TERMS_ERROR:", e);
        toast("Failed to load terms");
        return [];
    });
}
function load() {
    return callP("getInitData").then(function (d) {
        if (!d) return;
        state.profiles = d.profiles || [];
        state.activeProfileId = d.active_profile_id;
        state.cats = d.categories || [];
        state.hotkey = d.hotkey || "";
        if ($("settingsHotkey") && state.hotkey) $("settingsHotkey").textContent = state.hotkey;
        if (d.settings) {
            document.body.classList.toggle("light", d.settings.theme === "light");
        }
        applyTheme();
        refreshProfileSelect();
        setView(state.view);
        return loadTerms();
    }).then(function () {
        window.__loaded = true;
    });
}

/* ---- init + wiring ---- */
function connectBridge() {
    if (typeof qt === "undefined" || !qt.webChannelTransport || typeof QWebChannel === "undefined") {
        window.__jserr = window.__jserr || "qt.webChannelTransport / QWebChannel unavailable";
        return;
    }
    new QWebChannel(qt.webChannelTransport, function (channel) {
        bridge = channel.objects.bridge;
        window.__bridge = bridge;
        window.__state = state;
        if (!bridge) {
            window.__jserr = window.__jserr || "bridge object not registered";
            return;
        }
        bridge.dataChanged.connect(function () { reloadAll(); });
        bridge.openTermInWindow.connect(function (termId, editMode) {
            setView("terms");
            state.selectedId = termId;
            state.editMode = !!editMode;
            state.multi.clear();
            callP("getTerm", termId).then(function (t) {
                if (!t) { state.selectedId = null; renderDetail(); return; }
                updateTermCache(t);
                renderList();
                renderDetail();
            });
        });
        bridge.openCreateTerm.connect(function (name) {
            setView("terms");
            fillCatSelect();
            $("fTermName").value = name || "";
            $("fTermFull").value = "";
            openDialog("dlgTerm");
        });
        bridge.themeChanged.connect(function (mode) {
            document.body.classList.toggle("light", mode === "light");
            applyTheme();
        });
        bridge.hotkeyChanged.connect(function (text) {
            state.hotkey = text;
            if ($("settingsHotkey")) $("settingsHotkey").textContent = text;
        });
        bridge.toast.connect(function (msg) { toast(msg); });
        bridge.openSettings.connect(function () {
            if ($("settingsHotkey")) {
                callP("getHotkeyText").then(function (text) {
                    if (text) $("settingsHotkey").textContent = text;
                });
            }
            if ($("settingsLauncherHotkey")) {
                callP("getLauncherHotkeyText").then(function (text) {
                    if (text) $("settingsLauncherHotkey").textContent = text;
                });
            }
            openDialog("dlgSettings");
        });
        load().catch(function (e) {
            window.__loadErr = String((e && e.stack) || e);
        });
    });
}

function bindSkin() {
    var th = $("btnTheme");
    if (th) th.onclick = function () {
        var dark = document.body.classList.contains("light");
        document.body.classList.toggle("light", !dark);
        applyTheme();
        if (bridge) callVoid("setTheme", dark);
    };
}

function init() {
    try {
        initImpl();
    } catch (e) {
        window.__jserr = String((e && e.stack) || e);
    }
    try {
        connectBridge();
    } catch (e2) {
        window.__jserr = window.__jserr || String((e2 && e2.stack) || e2);
    }
    // Watchdog: if the bridge never connected, make the failure visible.
    setTimeout(function () {
        if (!window.__bridge) {
            window.__jserr = window.__jserr || "QWebChannel bridge did not connect";
            var banner = document.createElement("div");
            banner.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:9999;background:#B83A3A;color:#fff;padding:6px 12px;font-size:12px";
            banner.textContent = "Backend not connected: " + (window.__jserr || "unknown error");
            document.body.appendChild(banner);
        }
    }, 4000);
}

function initImpl() {
    mountIcons();
    bindSkin();

    /* term list selection: click / ctrl / shift / ctrl+A */
    $("listBox").addEventListener("click", function (e) {
        if (dragMoved) { dragMoved = false; return; }
        var row = e.target.closest(".term-row"); if (!row) return;
        var vis = currentTerms();
        var idx = vis.findIndex(function (t) { return t.id === +row.dataset.term; });
        if (e.shiftKey && state.lastClickedIdx >= 0) {
            var a = Math.min(state.lastClickedIdx, idx), b = Math.max(state.lastClickedIdx, idx);
            state.multi.clear();
            for (var i = a; i <= b; i++) state.multi.add(vis[i].id);
            showBulk(); return;
        }
        if (e.ctrlKey || e.metaKey) {
            state.multi.has(+row.dataset.term) ? state.multi.delete(+row.dataset.term) : state.multi.add(+row.dataset.term);
            state.lastClickedIdx = idx; showBulk(); return;
        }
        if (state.multi.size > 0) {
            // Already in a multi-selection: clicking a row toggles only that row,
            // so you can un-check a single term without clearing the whole group.
            state.multi.has(+row.dataset.term) ? state.multi.delete(+row.dataset.term) : state.multi.add(+row.dataset.term);
            state.lastClickedIdx = idx;
            showBulk();
            return;
        }
        state.multi.clear();
        state.lastClickedIdx = idx;
        selectTerm(+row.dataset.term);
        if (state.view === "categories") setView("terms");
    });
    // Click-and-drag across rows to select a contiguous group for bulk actions.
    $("listBox").addEventListener("pointerdown", function (e) {
        if (e.button !== 0) return;
        var row = e.target.closest(".term-row"); if (!row) return;
        var vis = currentTerms();
        dragAnchorIdx = vis.findIndex(function (t) { return t.id === +row.dataset.term; });
        dragStartX = e.clientX; dragStartY = e.clientY; dragMoved = false;
    });
    $("listBox").addEventListener("pointermove", function (e) {
        if (dragAnchorIdx < 0) return;
        if (!dragMoved) {
            if (Math.abs(e.clientX - dragStartX) < 4 && Math.abs(e.clientY - dragStartY) < 4) return;
            dragMoved = true;
        }
        var rows = $("listBox").querySelectorAll(".term-row");
        var cur = -1;
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i].getBoundingClientRect();
            if (e.clientY >= r.top && e.clientY <= r.bottom) { cur = i; break; }
        }
        if (cur < 0) return;
        var vis = currentTerms();
        var a = Math.min(dragAnchorIdx, cur), b = Math.max(dragAnchorIdx, cur);
        state.multi.clear();
        state.selectedId = null;
        for (var j = a; j <= b; j++) state.multi.add(vis[j].id);
        showBulk();
    });
    $("listBox").addEventListener("pointerup", function () { dragAnchorIdx = -1; });
    $("listBox").addEventListener("dblclick", function (e) {
        var row = e.target.closest(".term-row");
        if (row) { state.selectedId = +row.dataset.term; state.editMode = true; state.multi.clear(); showBulk(); }
    });
    $("listBox").addEventListener("contextmenu", function (e) {
        var row = e.target.closest(".term-row"); if (!row) return;
        e.preventDefault();
        ctxTarget = +row.dataset.term;
        ctxShow(e.clientX, e.clientY,
            '<button class="ctx-item" data-oa="open">' + svg("book") + 'Open</button>' +
            '<button class="ctx-item" data-oa="edit">' + svg("pencil") + 'Edit</button>' +
            '<button class="ctx-item" data-oa="duplicate">' + svg("copy") + 'Duplicate</button>' +
            '<div class="ctx-sep"></div>' +
            '<button class="ctx-item danger" data-oa="delete">' + svg("trash") + 'Delete</button>', "term-list");
    });

    $("filterInput").addEventListener("input", renderList);
    $("filterInput").addEventListener("keydown", function (e) { if (e.key === "Escape") { e.target.value = ""; e.target.blur(); renderList(); } });
    $("catFilter").addEventListener("input", renderCatTerms);
    $("catRows").addEventListener("click", function (e) {
        var r = e.target.closest(".cat-row");
        if (r) { state.catFilter = r.dataset.cat || null; renderCategories(); }
    });
    $("catRows").addEventListener("contextmenu", function (e) {
        var r = e.target.closest(".cat-row");
        if (!r || !r.dataset.cat) return;
        e.preventDefault();
        var c = catByName(r.dataset.cat);
        ctxTarget = c;
        ctxShow(e.clientX, e.clientY,
            '<button class="ctx-item" data-oa="rename">' + svg("pencil") + 'Rename</button>' +
            '<button class="ctx-item" data-oa="moveup">' + svg("chevronsUpDown") + 'Move up</button>' +
            '<button class="ctx-item" data-oa="movedown">' + svg("chevronsUpDown") + 'Move down</button>' +
            '<div class="ctx-sep"></div>' +
            '<button class="ctx-item danger" data-oa="delete">' + svg("trash") + 'Delete</button>', "category");
    });
    $("catTermsBox").addEventListener("click", function (e) {
        var r = e.target.closest(".term-row");
        if (r) { state.selectedId = +r.dataset.term; state.editMode = false; state.multi.clear(); setView("terms"); renderList(); renderDetail(); }
    });
    $("catTermsBox").addEventListener("contextmenu", function (e) {
        var r = e.target.closest(".term-row"); if (!r) return;
        e.preventDefault();
        ctxTarget = +r.dataset.term;
        ctxShow(e.clientX, e.clientY,
            '<button class="ctx-item" data-oa="open">' + svg("book") + 'Open</button>' +
            '<button class="ctx-item" data-oa="edit">' + svg("pencil") + 'Edit</button>' +
            '<button class="ctx-item" data-oa="uncat">' + svg("x") + 'Remove from Category</button>' +
            '<div class="ctx-sep"></div>' +
            '<button class="ctx-item danger" data-oa="delete">' + svg("trash") + 'Delete</button>', "term");
    });

    document.querySelectorAll(".nav-item[data-view]").forEach(function (b) {
        b.onclick = function () { state.catFilter = null; setView(b.dataset.view); };
    });
    $("btnRail").onclick = function () { document.querySelector(".sidebar").classList.toggle("hidden"); };
    $("btnNewProfile").onclick = function () {
        openNameDialog("profile", function (val) { callVoid("createProfile", val, ""); });
    };
    $("btnSettings").onclick = function () {
        callP("getHotkeyText").then(function (text) {
            if (text && $("settingsHotkey")) $("settingsHotkey").textContent = text;
        });
        callP("getLauncherHotkeyText").then(function (text) {
            if (text && $("settingsLauncherHotkey")) $("settingsLauncherHotkey").textContent = text;
        });
        openDialog("dlgSettings");
    };

    /* profile selector: switch + right-click rename/delete */
    $("profileSelect").addEventListener("change", function () {
        var pid = +$("profileSelect").value;
        state.activeProfileId = pid;
        state.selectedId = null;
        state.multi.clear();
        state.catFilter = null;
        callVoid("setActiveProfile", pid);
    });
    $("profileSelect").addEventListener("contextmenu", function (e) {
        e.preventDefault();
        var p = currentProfile();
        if (!p) return;
        ctxTarget = p;
        ctxShow(e.clientX, e.clientY,
            '<button class="ctx-item" data-oa="rename">' + svg("pencil") + 'Rename</button>' +
            '<button class="ctx-item danger" data-oa="delete">' + svg("trash") + 'Delete</button>', "profile");
    });

    /* header Import / Export actions */
    $("btnImport").onclick = function () { callVoid("fileAction", "import-json"); };
    $("btnExport").onclick = function () { callVoid("fileAction", "export-json"); };
    $("btnHotkeyChange").onclick = function () { callVoid("changeHotkey"); };
    $("btnLauncherHotkeyChange").onclick = function () { callVoid("changeLauncherHotkey"); };
    $("btnLicenses").onclick = function () {
        callP("getThirdPartyNotices").then(function (text) {
            if (text && $("licensesBody")) $("licensesBody").textContent = text;
            openDialog("dlgLicenses");
        });
    };

    document.addEventListener("click", function (e) {
        if (!$("ctx").classList.contains("hidden") && !e.target.closest("#ctx")) {
            hideCtx();
        }
    });

    /* pane filter/sort buttons */
    document.querySelector("#listHead .icon-btn[title='Filter']").onclick = function () { $("filterInput").focus(); };
    document.querySelector("#listHead .icon-btn[title^='Sort']").onclick = function () { cycleSort(); };
    var catSortBtn = document.querySelector("#cat-terms-head-sort, .cat-terms .icon-btn[title='Sort']");
    if (catSortBtn) catSortBtn.onclick = function () { cycleSort(); };

    /* add existing term to category */
    $("btnAddExisting").onclick = function () { openAddTermsDialog(); };
    $("btnAddTermsOk").onclick = function () {
        var boxes = document.querySelectorAll("#addTermsBox input[type=checkbox]:checked");
        var name = state.catFilter;
        boxes.forEach(function (cb) { callVoid("assignCategory", +cb.dataset.addterm, name); });
        closeDialogs();
        if (boxes.length) toast("Added " + boxes.length + " term(s)");
    };

    /* global search */
    $("globalSearch").addEventListener("focus", renderSearchPop);
    $("globalSearch").addEventListener("input", renderSearchPop);
    $("globalSearch").addEventListener("blur", function () { setTimeout(function () { $("searchPop").classList.add("hidden"); }, 150); });
    $("searchClear").onclick = function () { $("globalSearch").value = ""; renderSearchPop(); $("globalSearch").focus(); };
    $("searchPopBody").addEventListener("click", function (e) {
        var r = e.target.closest(".lookup-row"); if (!r) return;
        if (r.dataset.seeall) {
            $("globalSearch").value = ""; $("searchPop").classList.add("hidden");
            state.catFilter = null; setView("terms"); return;
        }
        callP("getTerm", +r.dataset.term).then(function (t) { if (t) openLookupTerm(t); });
    });
    if ($("btnLookup")) $("btnLookup").onclick = openLookupResults;

    /* lookup popup */
    $("btnLookupClose").onclick = closeLookup;
    $("btnLookupEdit").onclick = function () {
        var t = state._lookupTerm;
        if (t) { state.selectedId = t.id; state.editMode = true; state.multi.clear(); closeLookup(); setView("terms"); }
    };
    $("btnLookupFull").onclick = function () {
        var t = state._lookupTerm;
        if (t) { state.selectedId = t.id; state.editMode = false; state.multi.clear(); closeLookup(); setView("terms"); }
    };
    $("lookupBody").addEventListener("click", function (e) {
        var r = e.target.closest(".lookup-row");
        if (r && r.dataset.term) { callP("getTerm", +r.dataset.term).then(function (t) { if (t) openLookupTerm(t); }); }
    });
    $("lookup").addEventListener("keydown", function (e) {
        var rows = [].slice.call(document.querySelectorAll("#lookupBody .lookup-row"));
        if (!rows.length) return;
        var activeIdx = rows.findIndex(function (r) { return r.classList.contains("active"); });
        if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = (activeIdx + 1) % rows.length; }
        else if (e.key === "ArrowUp") { e.preventDefault(); activeIdx = (activeIdx - 1 + rows.length) % rows.length; }
        else if (e.key === "Enter") {
            var r = rows[activeIdx >= 0 ? activeIdx : 0];
            if (r && r.dataset.term) callP("getTerm", +r.dataset.term).then(function (t) { if (t) openLookupTerm(t); });
            return;
        } else return;
        rows.forEach(function (r, i) { r.classList.toggle("active", i === activeIdx); });
        var cur = rows[activeIdx];
        if (cur && cur.offsetTop != null) {
            var body = $("lookupBody");
            if (cur.offsetTop < body.scrollTop || cur.offsetTop > body.scrollTop + body.clientHeight - 40) body.scrollTop = cur.offsetTop - 12;
        }
    });

    /* lookup drag + resize */
    (function () {
        var lk = $("lookup");
        var sx = 0, sy = 0, ox = 0, oy = 0, dn = false;
        $("lookupDrag").addEventListener("pointerdown", function (e) {
            dn = true; ox = lk.offsetLeft; oy = lk.offsetTop; sx = e.clientX; sy = e.clientY;
            lk.style.right = "auto"; lk.style.left = ox + "px"; lk.style.top = oy + "px";
            e.preventDefault();
        });
        window.addEventListener("pointermove", function (e) { if (!dn) return; lk.style.left = (ox + e.clientX - sx) + "px"; lk.style.top = (oy + e.clientY - sy) + "px"; });
        window.addEventListener("pointerup", function () { dn = false; });
        var rsx = 0, rsy = 0, rw = 480, rh = 420, rstart = false;
        var grip = document.querySelector(".grip");
        if (grip) grip.addEventListener("pointerdown", function (e) {
            rstart = true; rsx = e.clientX; rsy = e.clientY; rw = lk.offsetWidth; rh = lk.offsetHeight; e.preventDefault();
        });
        window.addEventListener("pointermove", function (e) {
            if (!rstart) return;
            lk.style.width = Math.max(320, rw + e.clientX - rsx) + "px";
            lk.style.height = Math.max(240, rh + e.clientY - rsy) + "px";
        });
        window.addEventListener("pointerup", function () { rstart = false; });
        lk.style.left = "calc(50% - 240px)";
        lk.style.top = "120px";
    })();

    /* dialogs */
    $("btnNewTerm").onclick = function () { callVoid("openCreateTermWindow", ""); };
    $("btnNewCategory").onclick = function () {
        openNameDialog("category", function (val) { if (val) { callVoid("createCategory", val); } });
    };
    $("btnTermCreate").onclick = function () {
        var name = $("fTermName").value.trim();
        if (!name) { toast("Enter a term name"); return; }
        var full = $("fTermFull").value.trim();
        var cat = $("fTermCat").value || "";
        callP("createTerm", name, full, cat).then(function (t) {
            closeDialogs();
            toast("Created");
            if (t && t.id) { selectTerm(t.id); }
            else { reloadAll(); }
        }).catch(function (e) {
            console.error("JS_CREATE_TERM_ERROR:", e);
            toast("Create failed");
        });
    };
    $("btnNameOk").onclick = function () {
        var val = $("fName").value.trim();
        var content = $("fNameContent").value;
        if (val && dlgCb) dlgCb(val, content);
        closeDialogs();
    };
    // Pressing Enter in a dialog textbox confirms it (Create), instead of requiring a click.
    $("fName").addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); $("btnNameOk").click(); }
    });
    $("fTermName").addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); $("btnTermCreate").click(); }
    });
    $("fTermFull").addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); $("btnTermCreate").click(); }
    });
    $("btnCfOk").onclick = function () { if (dlgCb) dlgCb(); closeDialogs(); };
    $("btnDeleteSel").onclick = function () {
        openConfirm("Delete " + state.multi.size + " terms?", "The selected terms will be permanently removed.", function () {
            var ids = Array.from(state.multi);
            Promise.all(ids.map(function (id) { return callP("deleteTerm", id); })).then(function () {
                state.multi.clear();
                state.selectedId = null;
                reloadAll().then(function () { toast("Deleted"); });
            }).catch(function (e) {
                console.error("JS_DELETE_TERM_ERROR:", e);
                toast("Delete failed");
            });
        });
    };
    document.querySelectorAll("[data-close]").forEach(function (b) { b.onclick = closeDialogs; });
    $("scrim").addEventListener("click", closeDialogs);

    /* keyboard */
    document.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("globalSearch").focus(); renderSearchPop(); }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") { e.preventDefault(); $("btnNewTerm").click(); }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
            var t = e.target;
            if (t && (t.id === "filterInput" || t.id === "catFilter" || t.tagName === "TEXTAREA" || t.tagName === "INPUT")) return;
            if (!(e.target.closest && e.target.closest(".term-row"))) {
                e.preventDefault();
                var vis = currentTerms();
                state.multi.clear();
                vis.forEach(function (x) { state.multi.add(x.id); });
                if (vis.length) showBulk();
            }
        }
        if (e.key === "Escape") {
            if (!$("ctx").classList.contains("hidden")) hideCtx();
            else if (!$("searchPop").classList.contains("hidden")) $("searchPop").classList.add("hidden");
            else if (!$("lookup").classList.contains("hidden")) closeLookup();
            else if (!$("scrim").classList.contains("hidden")) closeDialogs();
            else if (state.editMode) { state.editMode = false; renderDetail(); }
            else { state.multi.clear(); showBulk(); }
        }
    });

    function cycleSort() {
        var order = ["default", "az", "za", "category"];
        var next = order[(order.indexOf(state.sortMode) + 1) % order.length];
        state.sortMode = next;
        toast("Sort: " + (next === "default" ? "Default" : next.toUpperCase()));
        if (state.view === "terms") renderList(); else renderCatTerms();
    }

    setView("terms");
    connectBridge();
}
document.addEventListener("DOMContentLoaded", init);
