/**
 * Formatação inline de texto selecionado (negrito, itálico, sublinhado, riscado,
 * sobrescrito e subscrito).
 */
(function () {
    "use strict";

    const FORMAT_COMMANDS = {
        bold: "bold",
        italic: "italic",
        underline: "underline",
        strikethrough: "strikeThrough",
        superscript: "superscript",
        subscript: "subscript",
    };

    const FORMAT_SHORTCUTS = {
        b: "bold",
        i: "italic",
        u: "underline",
    };

    const FORMATS_REQUIRING_SELECTION = new Set(["superscript", "subscript"]);

    let formatToolbarGroup = null;
    let lastFormatContext = null;

    function getInlineText() {
        return window.ReportLineInlineText || null;
    }

    function resolveFormattableContextFromSelection() {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            return null;
        }

        const anchor = selection.anchorNode;
        if (!anchor || !anchor.parentElement) {
            return null;
        }

        const editable = anchor.nodeType === Node.ELEMENT_NODE
            ? anchor.closest(".report-editor-block-editable")
            : anchor.parentElement.closest(".report-editor-block-editable");

        if (!editable) {
            if (window.ReportLinePageHeader && window.ReportLinePageHeader.resolveHeaderTextContext) {
                const headerContext = window.ReportLinePageHeader.resolveHeaderTextContext();
                if (headerContext) {
                    return { block: null, editable: headerContext.editable, headerText: true };
                }
            }
            if (window.ReportLinePageFooter && window.ReportLinePageFooter.resolveFooterTextContext) {
                const footerContext = window.ReportLinePageFooter.resolveFooterTextContext();
                if (footerContext) {
                    return { block: null, editable: footerContext.editable, footerText: true };
                }
            }
            return null;
        }

        const block = editable.closest(".report-editor-block");
        if (!block) {
            if (editable.matches("[data-report-page-header-text]")) {
                return { block: null, editable, headerText: true };
            }
            if (editable.matches("[data-report-page-footer-text]")) {
                return { block: null, editable, footerText: true };
            }
            return null;
        }

        if (editable.dataset.tablePart && editable.closest(".report-editor-table-cell-has-image")) {
            return null;
        }

        if (editable.dataset.tablePart === "cell" && editable.closest("td.report-editor-table-cell-has-image")) {
            return null;
        }

        const blockType = block.dataset.blockType;
        const isListItem = editable.classList.contains("report-editor-list-item");
        const isTextField = editable.dataset.field === "text";
        const isTableText = editable.classList.contains("report-editor-table-cell");

        if (
            isListItem
            || isTextField
            || isTableText
        ) {
            if (blockType === "image") {
                return null;
            }
            return { block, editable };
        }

        return null;
    }

    function rememberFormatContext(context) {
        if (context && context.editable) {
            lastFormatContext = context;
        }
    }

    function clearFormatContext() {
        lastFormatContext = null;
    }

    function resolveFormattableContext() {
        const fromSelection = resolveFormattableContextFromSelection();
        if (fromSelection) {
            rememberFormatContext(fromSelection);
            return fromSelection;
        }

        if (
            lastFormatContext
            && document.contains(lastFormatContext.editable)
            && isFormatToolbarTarget(document.activeElement)
        ) {
            return lastFormatContext;
        }

        if (window.ReportLineEditor && window.ReportLineEditor.resolveEditorContext) {
            const editorContext = window.ReportLineEditor.resolveEditorContext();
            if (editorContext && editorContext.editable) {
                rememberFormatContext(editorContext);
                return editorContext;
            }
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

        return range.toString().length > 0;
    }

    function isFormatToolbarTarget(target) {
        return Boolean(
            target
            && target.closest
            && formatToolbarGroup
            && formatToolbarGroup.contains(target)
        );
    }

    function setFormatButtonsEnabled(enabled) {
        if (!formatToolbarGroup) {
            return;
        }

        const mainButton = formatToolbarGroup.querySelector("[data-report-text-format-main]");
        const toggleButton = formatToolbarGroup.querySelector("[data-report-text-format-toggle]");
        if (mainButton) {
            mainButton.disabled = !enabled;
        }
        if (toggleButton) {
            toggleButton.disabled = !enabled;
        }

        formatToolbarGroup.querySelectorAll("[data-report-text-format]").forEach((button) => {
            if (button.hasAttribute("data-report-text-format-main")) {
                return;
            }
            button.disabled = !enabled;
        });
    }

    function updateSelectionRequiredButtons(context) {
        if (!formatToolbarGroup) {
            return;
        }

        const hasSelection = hasMeaningfulSelection(context);
        formatToolbarGroup.querySelectorAll("[data-report-text-format]").forEach((button) => {
            const format = button.dataset.reportTextFormat;
            if (!FORMATS_REQUIRING_SELECTION.has(format)) {
                return;
            }
            button.disabled = !context || !context.editable || !hasSelection;
        });
    }

    function updateFormatButtonStates(context) {
        if (!formatToolbarGroup) {
            return;
        }

        formatToolbarGroup.querySelectorAll("[data-report-text-format]").forEach((button) => {
            const format = button.dataset.reportTextFormat;
            const command = FORMAT_COMMANDS[format];
            let active = false;

            if (context && command && document.queryCommandSupported(command)) {
                try {
                    active = document.queryCommandState(command);
                } catch (_error) {
                    active = false;
                }
            }

            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
        });

        const mainButton = formatToolbarGroup.querySelector("[data-report-text-format-main]");
        if (mainButton) {
            let boldActive = false;
            if (context && document.queryCommandSupported("bold")) {
                try {
                    boldActive = document.queryCommandState("bold");
                } catch (_error) {
                    boldActive = false;
                }
            }
            mainButton.classList.toggle("active", boldActive);
            mainButton.setAttribute("aria-pressed", boldActive ? "true" : "false");
        }
    }

    function refreshToolbar(context) {
        const hasContext = Boolean(context && context.editable);
        setFormatButtonsEnabled(hasContext);
        if (hasContext) {
            updateFormatButtonStates(context);
            updateSelectionRequiredButtons(context);
        } else {
            updateFormatButtonStates(null);
        }
    }

    function restoreSelection(context) {
        if (!context || !context.editable) {
            return;
        }

        context.editable.focus();
        const selection = window.getSelection();
        if (!selection || selection.rangeCount > 0) {
            return;
        }

        const range = document.createRange();
        range.selectNodeContents(context.editable);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
    }

    function applyFormat(format) {
        const context = resolveFormattableContext();
        const command = FORMAT_COMMANDS[format];
        if (!context || !command) {
            return Promise.resolve();
        }

        if (FORMATS_REQUIRING_SELECTION.has(format) && !hasMeaningfulSelection(context)) {
            return Promise.resolve();
        }

        restoreSelection(context);

        try {
            document.execCommand(command, false, null);
        } catch (_error) {
            return Promise.resolve();
        }

        const inlineText = getInlineText();
        if (inlineText) {
            if ((context.headerText || context.footerText) && inlineText.getHeaderHtml) {
                context.editable.innerHTML = inlineText.sanitizeHeader(context.editable.innerHTML);
            } else {
                context.editable.innerHTML = inlineText.sanitize(context.editable.innerHTML);
            }
        }

        if (context.headerText && window.ReportLinePageHeader && window.ReportLinePageHeader.scheduleHeaderSave) {
            window.ReportLinePageHeader.scheduleHeaderSave();
        } else if (context.footerText && window.ReportLinePageFooter && window.ReportLinePageFooter.scheduleFooterSave) {
            window.ReportLinePageFooter.scheduleFooterSave();
        } else if (window.ReportLineEditor && window.ReportLineEditor.scheduleDebouncedSave) {
            window.ReportLineEditor.scheduleDebouncedSave(context.block);
        }

        refreshToolbar(context);
        return Promise.resolve();
    }

    function bindFormatButtons() {
        document.querySelectorAll("[data-report-text-format]").forEach((button) => {
            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
                event.stopPropagation();
            });

            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (button.disabled) {
                    return;
                }
                applyFormat(button.dataset.reportTextFormat).catch(console.error);
            });
        });
    }

    function bindKeyboardShortcuts(page) {
        page.addEventListener("keydown", (event) => {
            if (!(event.ctrlKey || event.metaKey) || event.altKey) {
                return;
            }

            const context = resolveFormattableContext();
            if (!context) {
                return;
            }

            const key = event.key.toLowerCase();
            const format = FORMAT_SHORTCUTS[key];
            if (format) {
                event.preventDefault();
                applyFormat(format).catch(console.error);
                return;
            }

            if (key === "x" && event.shiftKey) {
                event.preventDefault();
                applyFormat("strikethrough").catch(console.error);
            }
        }, true);
    }

    function bindPasteSanitizer(page) {
        page.addEventListener("paste", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
                return;
            }

            const inlineText = getInlineText();
            if (!inlineText) {
                return;
            }

            event.preventDefault();
            const clipboard = event.clipboardData;
            if (!clipboard) {
                return;
            }

            const html = clipboard.getData("text/html");
            const plain = clipboard.getData("text/plain");
            const isBandText = editable.matches("[data-report-page-header-text], [data-report-page-footer-text]");
            const sanitizeFn = isBandText && inlineText.sanitizeHeader
                ? inlineText.sanitizeHeader.bind(inlineText)
                : inlineText.sanitize.bind(inlineText);
            if (html) {
                document.execCommand("insertHTML", false, sanitizeFn(html));
            } else {
                document.execCommand("insertText", false, plain);
            }
        });
    }

    function init() {
        formatToolbarGroup = document.querySelector(".report-editor-toolbar-format-group");
        const page = document.getElementById("report-editor-page");
        if (!formatToolbarGroup || !page) {
            return;
        }

        bindFormatButtons();
        bindKeyboardShortcuts(page);
        bindPasteSanitizer(page);

        page.addEventListener("focusin", (event) => {
            refreshToolbar(resolveFormattableContextFromSelection());
        });

        page.addEventListener("mouseup", () => {
            refreshToolbar(resolveFormattableContext());
        });

        page.addEventListener("keyup", () => {
            refreshToolbar(resolveFormattableContext());
        });

        document.addEventListener("selectionchange", () => {
            const context = resolveFormattableContextFromSelection()
                || resolveFormattableContext();
            if (context) {
                refreshToolbar(context);
            }
        });

        document.addEventListener("focusin", (event) => {
            if (event.target.closest("#report-editor-page")) {
                return;
            }
            if (event.target.closest("#report-page-header-root")) {
                return;
            }
            if (event.target.closest("#report-page-footer-root")) {
                return;
            }
            if (!isFormatToolbarTarget(event.target)) {
                clearFormatContext();
                refreshToolbar(null);
            }
        });

        refreshToolbar(null);
    }

    window.ReportLineTextFormat = { init, applyFormat, resolveFormattableContext };
})();
