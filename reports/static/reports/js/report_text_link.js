/**
 * Inserção de link inline em texto selecionado no editor.
 */
(function () {
    "use strict";

    let linkButton = null;
    let modalElement = null;
    let modal = null;
    let form = null;
    let urlInput = null;
    let urlError = null;
    let savedRange = null;
    let pendingContext = null;

    function getInlineText() {
        return window.ReportLineInlineText || null;
    }

    function resolveFormattableContext() {
        if (window.ReportLineTextFormat && window.ReportLineTextFormat.resolveFormattableContext) {
            return window.ReportLineTextFormat.resolveFormattableContext();
        }
        return null;
    }

    function getCurrentSelectionRange() {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            return null;
        }
        return selection.getRangeAt(0);
    }

    function hasMeaningfulSelection(context) {
        if (!context || !context.editable) {
            return false;
        }

        const range = getCurrentSelectionRange();
        if (!range || range.collapsed) {
            return false;
        }

        if (!context.editable.contains(range.commonAncestorContainer)) {
            return false;
        }

        return range.toString().trim().length > 0;
    }

    function saveSelectionRange(context) {
        if (!hasMeaningfulSelection(context)) {
            savedRange = null;
            pendingContext = null;
            return;
        }

        const range = getCurrentSelectionRange();
        savedRange = range ? range.cloneRange() : null;
        pendingContext = context;
    }

    function restoreSelectionRange() {
        if (!savedRange || !pendingContext) {
            return false;
        }

        pendingContext.editable.focus();
        const selection = window.getSelection();
        if (!selection) {
            return false;
        }

        selection.removeAllRanges();
        selection.addRange(savedRange);
        return true;
    }

    function setLinkButtonEnabled(enabled) {
        if (!linkButton) {
            return;
        }
        linkButton.disabled = !enabled;
    }

    function refreshLinkButton() {
        const context = resolveFormattableContext();
        setLinkButtonEnabled(hasMeaningfulSelection(context));
    }

    function clearUrlValidation() {
        if (!urlInput) {
            return;
        }
        urlInput.classList.remove("is-invalid");
    }

    function showUrlValidation(message) {
        if (!urlInput) {
            return;
        }
        urlInput.classList.add("is-invalid");
        if (urlError && message) {
            urlError.textContent = message;
        }
    }

    function normalizeUrl(rawValue) {
        const inlineText = getInlineText();
        if (inlineText && inlineText.normalizeLinkUrl) {
            return inlineText.normalizeLinkUrl(rawValue);
        }
        const cleaned = (rawValue || "").trim();
        return cleaned || null;
    }

    function applyLink(url) {
        if (!restoreSelectionRange() || !pendingContext) {
            return false;
        }

        const normalizedUrl = normalizeUrl(url);
        if (!normalizedUrl) {
            showUrlValidation("Informe um endereço válido.");
            return false;
        }

        try {
            document.execCommand("createLink", false, normalizedUrl);
        } catch (_error) {
            showUrlValidation("Não foi possível aplicar o link.");
            return false;
        }

        const inlineText = getInlineText();
        if (inlineText) {
            pendingContext.editable.innerHTML = inlineText.sanitize(
                pendingContext.editable.innerHTML
            );
        }

        if (window.ReportLineEditor && window.ReportLineEditor.scheduleDebouncedSave) {
            window.ReportLineEditor.scheduleDebouncedSave(pendingContext.block);
        }

        savedRange = null;
        return true;
    }

    function openModal() {
        const context = resolveFormattableContext();
        saveSelectionRange(context);
        if (!savedRange || !modal) {
            return;
        }

        clearUrlValidation();
        if (urlInput) {
            urlInput.value = "";
        }

        modal.show();
        window.setTimeout(() => {
            if (urlInput) {
                urlInput.focus();
            }
        }, 150);
    }

    function handleSubmit(event) {
        event.preventDefault();

        const rawUrl = urlInput ? urlInput.value : "";
        if (!rawUrl.trim()) {
            showUrlValidation("Informe um endereço válido.");
            if (urlInput) {
                urlInput.focus();
            }
            return;
        }

        if (applyLink(rawUrl)) {
            modal.hide();
            refreshLinkButton();
        } else if (urlInput) {
            urlInput.focus();
        }
    }

    function bindEvents(page) {
        if (linkButton) {
            linkButton.addEventListener("mousedown", (event) => {
                event.preventDefault();
                event.stopPropagation();
                saveSelectionRange(resolveFormattableContext());
            });

            linkButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (linkButton.disabled) {
                    return;
                }
                openModal();
            });
        }

        if (form) {
            form.addEventListener("submit", handleSubmit);
        }

        if (urlInput) {
            urlInput.addEventListener("input", clearUrlValidation);
        }

        if (modalElement) {
            modalElement.addEventListener("hidden.bs.modal", () => {
                clearUrlValidation();
                if (pendingContext && pendingContext.editable) {
                    pendingContext.editable.focus();
                }
            });
        }

        page.addEventListener("mouseup", refreshLinkButton);
        page.addEventListener("keyup", refreshLinkButton);

        document.addEventListener("selectionchange", () => {
            if (document.activeElement && document.activeElement.closest("#reportLinkInsertModal")) {
                return;
            }
            refreshLinkButton();
        });
    }

    function init() {
        linkButton = document.querySelector("[data-report-text-link]");
        modalElement = document.getElementById("reportLinkInsertModal");
        form = document.getElementById("report-link-insert-form");
        urlInput = document.getElementById("report-link-insert-url");
        urlError = document.getElementById("report-link-insert-url-error");
        const page = document.getElementById("report-editor-page");

        if (!linkButton || !modalElement || !page || !window.bootstrap) {
            return;
        }

        modal = window.bootstrap.Modal.getOrCreateInstance(modalElement);
        bindEvents(page);
        refreshLinkButton();
    }

    window.ReportLineTextLink = { init };
})();
