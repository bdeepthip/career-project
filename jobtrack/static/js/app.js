// Small helpers used across Roleflow. Loaded from this file (not written
// inside the HTML) so the Content-Security-Policy can block any inline script.

// Any form with data-confirm="..." asks before submitting.
// The message comes from an HTML attribute (auto-escaped), never
// from text pasted into JavaScript, so a company name can't run code.
document.addEventListener("submit", function (event) {
    var message = event.target.dataset.confirm;
    if (message && !window.confirm(message)) {
        event.preventDefault();
    }
});

document.addEventListener("click", function (event) {
    // data-copy="<input id>": copy that input's text
    var copyButton = event.target.closest("[data-copy]");
    if (copyButton) {
        var input = document.getElementById(copyButton.dataset.copy);
        input.select();
        var done = function () {
            var label = copyButton.textContent;
            copyButton.textContent = "Copied";
            setTimeout(function () { copyButton.textContent = label; }, 1500);
        };
        if (navigator.clipboard) {
            navigator.clipboard.writeText(input.value).then(done, function () {
                document.execCommand("copy"); done();
            });
        } else {
            document.execCommand("copy"); done();
        }
        return;
    }

    // data-open-dialog="<dialog id>": open that dialog
    var opener = event.target.closest("[data-open-dialog]");
    if (opener) {
        document.getElementById(opener.dataset.openDialog).showModal();
    }
});

// ---------- Mobile menu ----------

document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-toggle-nav]");
    if (!toggle) return;
    var open = document.body.classList.toggle("nav-open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
});

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && document.body.classList.contains("nav-open")) {
        document.body.classList.remove("nav-open");
        var toggle = document.querySelector("[data-toggle-nav]");
        if (toggle) { toggle.setAttribute("aria-expanded", "false"); toggle.focus(); }
    }
});


// ---------- Screen time ----------
// Every 30 seconds, if this tab is visible and the person moved, typed,
// scrolled or tapped in the last 3 minutes, tell Roleflow to count 30 seconds.
// Idle tabs and background tabs never count.

(function () {
    if (!document.querySelector("[data-screen-meter]")) return;  // only when logged in

    var lastActive = Date.now();
    var markActive = function () { lastActive = Date.now(); };
    ["pointermove", "pointerdown", "keydown", "scroll", "touchstart"].forEach(function (name) {
        window.addEventListener(name, markActive, { passive: true });
    });

    var csrf = document.querySelector('meta[name="csrf-token"]');

    function ping() {
        if (document.visibilityState !== "visible") return;
        if (Date.now() - lastActive > 3 * 60 * 1000) return;

        fetch("/activity/ping", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrf ? csrf.content : "",
            },
            body: JSON.stringify({ tz_offset_minutes: new Date().getTimezoneOffset() }),
            credentials: "same-origin",
        }).then(function (response) {
            return response.ok ? response.json() : null;
        }).then(function (data) {
            if (!data) return;
            document.querySelectorAll("[data-screen-time]").forEach(function (el) {
                el.textContent = data.display;
            });
            document.querySelectorAll("[data-screen-bar]").forEach(function (el) {
                el.value = data.percent;
                el.textContent = data.percent + "%";
            });
        }).catch(function () { /* offline: try again next time */ });
    }

    setInterval(ping, 30 * 1000);
})();


// ---------- Open conversation: show new messages without reloading ----------

(function () {
    var thread = document.querySelector("[data-thread]");
    if (!thread) return;

    var latest = document.getElementById("latest");
    if (latest) latest.scrollIntoView({ block: "end" });

    setInterval(function () {
        if (document.visibilityState !== "visible") return;
        var current = document.querySelector("[data-thread]");
        fetch(current.dataset.latestUrl, { credentials: "same-origin" })
            .then(function (response) { return response.ok ? response.text() : null; })
            .then(function (html) {
                if (!html) return;
                var holder = document.createElement("div");
                holder.innerHTML = html;   // our own server-rendered, auto-escaped HTML
                var fresh = holder.querySelector("[data-thread]");
                if (fresh && fresh.dataset.count !== current.dataset.count) {
                    current.replaceWith(fresh);
                    var last = document.getElementById("latest");
                    if (last) last.scrollIntoView({ block: "end", behavior: "smooth" });
                }
            })
            .catch(function () { /* offline: try again next time */ });
    }, 8000);
})();


// ---------- Light / dark theme ----------
// The choice is kept in a cookie, so the server renders the right
// theme on the next page load and the page never flashes.

document.addEventListener("click", function (event) {
    if (!event.target.closest("[data-theme-toggle]")) return;
    var root = document.documentElement;
    var next = root.dataset.theme === "light" ? "dark" : "light";
    root.dataset.theme = next;
    document.cookie = "theme=" + next + "; path=/; max-age=31536000; SameSite=Lax";
});


// ---------- Board: drag a card to another column ----------

(function () {
    var board = document.querySelector("[data-board]");
    if (!board) return;

    var csrf = document.querySelector('meta[name="csrf-token"]');
    var announcer = document.querySelector("[data-board-status]");
    var dragged = null;

    // With JavaScript on, changing the menu moves the card straight away,
    // so the Move button is only needed without JavaScript.
    board.querySelectorAll("[data-card-submit]").forEach(function (button) {
        button.hidden = true;
    });

    function refreshCounts() {
        board.querySelectorAll("[data-column]").forEach(function (column) {
            var n = column.querySelectorAll("[data-card]").length;
            column.querySelector("[data-column-count]").textContent = n;
            column.classList.toggle("is-empty", n === 0);
        });
    }

    function moveCard(card, status) {
        var from = card.closest("[data-column]");
        var to = board.querySelector('[data-column="' + status + '"]');
        if (!to || from === to) return;

        to.querySelector("[data-column-cards]").prepend(card);
        card.querySelector("[data-card-select]").value = status;
        card.classList.add("is-landed");
        setTimeout(function () { card.classList.remove("is-landed"); }, 600);
        refreshCounts();

        var body = new URLSearchParams();
        body.set("status", status);
        fetch(card.dataset.moveUrl, {
            method: "POST",
            headers: {
                "Accept": "application/json",
                "X-CSRFToken": csrf ? csrf.content : "",
            },
            body: body,
            credentials: "same-origin",
        }).then(function (response) {
            if (!response.ok) throw new Error("move failed");
            var name = card.querySelector("strong").textContent;
            if (announcer) announcer.textContent = "Moved " + name + " to " + status + ".";
        }).catch(function () {
            // Put the card back so the board shows what is really saved
            from.querySelector("[data-column-cards]").prepend(card);
            card.querySelector("[data-card-select]").value = from.dataset.column;
            refreshCounts();
            if (announcer) announcer.textContent = "That move didn't save. Try again.";
        });
    }

    board.addEventListener("dragstart", function (event) {
        dragged = event.target.closest("[data-card]");
        if (!dragged) return;
        dragged.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", "");
    });

    board.addEventListener("dragend", function () {
        if (dragged) dragged.classList.remove("is-dragging");
        dragged = null;
        board.querySelectorAll(".is-over").forEach(function (c) { c.classList.remove("is-over"); });
    });

    board.addEventListener("dragover", function (event) {
        var column = event.target.closest("[data-column]");
        if (!column || !dragged) return;
        event.preventDefault();
        board.querySelectorAll(".is-over").forEach(function (c) {
            if (c !== column) c.classList.remove("is-over");
        });
        column.classList.add("is-over");
    });

    board.addEventListener("drop", function (event) {
        var column = event.target.closest("[data-column]");
        if (!column || !dragged) return;
        event.preventDefault();
        column.classList.remove("is-over");
        moveCard(dragged, column.dataset.column);
    });

    board.addEventListener("change", function (event) {
        var select = event.target.closest("[data-card-select]");
        if (!select) return;
        moveCard(select.closest("[data-card]"), select.value);
    });

    refreshCounts();
})();
