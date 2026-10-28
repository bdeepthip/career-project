// Small helpers used across GAJ. Loaded from this file (not written
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
// scrolled or tapped in the last 3 minutes, tell GAJ to count 30 seconds.
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
