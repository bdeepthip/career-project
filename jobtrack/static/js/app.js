// Small helpers used across JobTrack. Loaded from this file (not written
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
