// reportline/reports/static/reports/js/report_text_format.js
/**
 * Formatação inline de texto selecionado (negrito, itálico, sublinhado, riscado,
 * sobrescrito, subscrito e tamanhos de fonte 10/11/12/13 pt).
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

    const FONT_SIZE_FORMATS = {
        "font-xs": "report-inline-font-xs",
        "font-sm": "report-inline-font-sm",
        "font-lg": "report-inline-font-lg",
    };

    const FONT_SIZE_CLASS_NAMES = Object.values(FONT_SIZE_FORMATS);

    const FONT_SIZE_FORMAT_KEYS = new Set(["font-xs", "font-sm", "font-md", "font-lg"]);

    const FORMAT_SHORTCUTS = {
        b: "bold",
        i: "italic",
        u: "underline",
    };

    const FORMATS_REQUIRING_SELECTION = new Set([
        "superscript",
        "subscript",
        "font-xs",
        "font-sm",
        "font-md",
        "font-lg",
    ]);

    let formatToolbarGroup = null;
    let lastFormatContext = null;

    function getInlineText() {
        return window.ReportLineInlineText || null;
    }

    function captureSelectionOffsets(editable) {
        const inlineText = getInlineText();
        if (!inlineText || !inlineText.getSelectionOffsets) {
            return null;
        }
        return inlineText.getSelectionOffsets(editable);
    }

    function restoreSelectionOffsets(editable, offsets) {
        const inlineText = getInlineText();
        if (!inlineText || !inlineText.setSelectionOffsets || !offsets) {
            return false;
        }
        return inlineText.setSelectionOffsets(editable, offsets);
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
            if (editable.matches("[data-report-page-header-text], [data-report-page-header-extra-text]")) {
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

    function resolveTableMultiFormatContext() {
        if (
            !window.ReportLineTableSelection
            || !window.ReportLineTableSelection.hasMultiCellSelection
            || !window.ReportLineTableSelection.hasMultiCellSelection()
        ) {
            return null;
        }

        const selection = window.ReportLineTableSelection.getSelection();
        const editables = window.ReportLineTableSelection.getSelectedTextEditables();
        if (!selection || editables.length === 0) {
            return null;
        }

        return {
            block: selection.block,
            editable: editables[0],
            editables,
            tableMulti: true,
        };
    }

    function selectAllContents(element) {
        element.focus();
        const selection = window.getSelection();
        if (!selection) {
            return;
        }
        const range = document.createRange();
        range.selectNodeContents(element);
        selection.removeAllRanges();
        selection.addRange(range);
    }

    function isFontSizeSpan(element) {
        return Boolean(
            element
            && element.nodeType === Node.ELEMENT_NODE
            && element.tagName === "SPAN"
            && FONT_SIZE_CLASS_NAMES.some((className) => element.classList.contains(className))
        );
    }

    function unwrapFontSizeSpan(span) {
        const parent = span.parentNode;
        if (!parent) {
            return;
        }
        while (span.firstChild) {
            parent.insertBefore(span.firstChild, span);
        }
        parent.removeChild(span);
    }

    function unwrapFontSizeSpans(root) {
        if (!root) {
            return;
        }
        const spans = root.querySelectorAll
            ? root.querySelectorAll(
                "span.report-inline-font-xs, span.report-inline-font-sm, span.report-inline-font-lg"
            )
            : [];
        Array.from(spans).reverse().forEach(unwrapFontSizeSpan);
    }

    function resolveFontSizeFormatFromNode(node) {
        if (!node) {
            return "font-md";
        }

        const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
        if (!element || !element.closest) {
            return "font-md";
        }

        const span = element.closest(
            "span.report-inline-font-xs, span.report-inline-font-sm, span.report-inline-font-lg"
        );
        if (!span) {
            return "font-md";
        }
        if (span.classList.contains("report-inline-font-xs")) {
            return "font-xs";
        }
        if (span.classList.contains("report-inline-font-sm")) {
            return "font-sm";
        }
        if (span.classList.contains("report-inline-font-lg")) {
            return "font-lg";
        }
        return "font-md";
    }

    function resolveActiveFontSizeFormat(context) {
        if (!context || !context.editable) {
            return null;
        }

        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            return null;
        }

        const range = selection.getRangeAt(0);
        if (!context.editable.contains(range.commonAncestorContainer)) {
            return null;
        }

        const startFormat = resolveFontSizeFormatFromNode(range.startContainer);
        const endFormat = resolveFontSizeFormatFromNode(range.endContainer);
        if (startFormat === endFormat) {
            return startFormat;
        }
        return null;
    }

    function applyFontSizeToEditable(editable, format) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            return false;
        }

        const range = selection.getRangeAt(0);
        if (range.collapsed || !editable.contains(range.commonAncestorContainer)) {
            return false;
        }

        const extracted = range.extractContents();
        const wrapper = document.createElement("div");
        wrapper.appendChild(extracted);
        unwrapFontSizeSpans(wrapper);

        const fragment = document.createDocumentFragment();
        if (format === "font-md") {
            while (wrapper.firstChild) {
                fragment.appendChild(wrapper.firstChild);
            }
        } else {
            const span = document.createElement("span");
            span.className = FONT_SIZE_FORMATS[format];
            while (wrapper.firstChild) {
                span.appendChild(wrapper.firstChild);
            }
            fragment.appendChild(span);
        }

        const insertedNodes = Array.from(fragment.childNodes);
        range.insertNode(fragment);

        if (insertedNodes.length > 0) {
            const restored = document.createRange();
            restored.setStartBefore(insertedNodes[0]);
            restored.setEndAfter(insertedNodes[insertedNodes.length - 1]);
            selection.removeAllRanges();
            selection.addRange(restored);
        } else {
            range.collapse(false);
            selection.removeAllRanges();
            selection.addRange(range);
        }
        return true;
    }

    function applyFontSizeToTableMultiSelection(format) {
        const context = resolveTableMultiFormatContext();
        if (!context) {
            return false;
        }

        const inlineText = getInlineText();
        if (
            window.ReportLineEditor
            && window.ReportLineEditor.beginBlockContentRecording
        ) {
            window.ReportLineEditor.beginBlockContentRecording(context.block, context.editable);
        }

        let applied = false;
        context.editables.forEach((editable) => {
            selectAllContents(editable);
            if (applyFontSizeToEditable(editable, format)) {
                applied = true;
            }
            if (inlineText) {
                editable.innerHTML = inlineText.sanitize(editable.innerHTML);
            }
        });

        if (!applied) {
            return false;
        }

        if (window.ReportLineEditor && window.ReportLineEditor.scheduleDebouncedSave) {
            window.ReportLineEditor.scheduleDebouncedSave(context.block);
        }

        return true;
    }

    function applyFontSize(format, context) {
        if (applyFontSizeToTableMultiSelection(format)) {
            refreshToolbar(resolveTableMultiFormatContext());
            return Promise.resolve();
        }

        if (!context || !context.editable) {
            return Promise.resolve();
        }

        if (!hasMeaningfulSelection(context)) {
            return Promise.resolve();
        }

        const selectionOffsets = captureSelectionOffsets(context.editable);
        restoreSelection(context);

        if (!applyFontSizeToEditable(context.editable, format)) {
            return Promise.resolve();
        }

        const inlineText = getInlineText();
        if (inlineText) {
            if ((context.headerText || context.footerText) && inlineText.sanitizeHeader) {
                context.editable.innerHTML = inlineText.sanitizeHeader(context.editable.innerHTML);
            } else {
                context.editable.innerHTML = inlineText.sanitize(context.editable.innerHTML);
            }
        }

        if (!restoreSelectionOffsets(context.editable, selectionOffsets)) {
            restoreSelection(context);
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

    function applyFormatToTableMultiSelection(format) {
        if (FONT_SIZE_FORMAT_KEYS.has(format)) {
            return applyFontSizeToTableMultiSelection(format);
        }

        const context = resolveTableMultiFormatContext();
        const command = FORMAT_COMMANDS[format];
        if (!context || !command) {
            return false;
        }

        const inlineText = getInlineText();
        if (
            window.ReportLineEditor
            && window.ReportLineEditor.beginBlockContentRecording
        ) {
            window.ReportLineEditor.beginBlockContentRecording(context.block, context.editable);
        }

        context.editables.forEach((editable) => {
            selectAllContents(editable);
            try {
                document.execCommand(command, false, null);
            } catch (_error) {
                return;
            }

            if (inlineText) {
                editable.innerHTML = inlineText.sanitize(editable.innerHTML);
            }
        });

        if (window.ReportLineEditor && window.ReportLineEditor.scheduleDebouncedSave) {
            window.ReportLineEditor.scheduleDebouncedSave(context.block);
        }

        return true;
    }

    function resolveFormattableContext() {
        const multiContext = resolveTableMultiFormatContext();
        if (multiContext) {
            rememberFormatContext(multiContext);
            return multiContext;
        }

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

        if (context && context.tableMulti) {
            formatToolbarGroup.querySelectorAll("[data-report-text-format]").forEach((button) => {
                const format = button.dataset.reportTextFormat;
                if (FORMATS_REQUIRING_SELECTION.has(format)) {
                    button.disabled = false;
                }
            });
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
            let active = false;

            if (FONT_SIZE_FORMAT_KEYS.has(format)) {
                const activeFontSize = resolveActiveFontSizeFormat(context);
                active = Boolean(context && activeFontSize === format);
            } else {
                const command = FORMAT_COMMANDS[format];
                if (context && command && document.queryCommandSupported(command)) {
                    try {
                        active = document.queryCommandState(command);
                    } catch (_error) {
                        active = false;
                    }
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
        const multiContext = resolveTableMultiFormatContext();
        const effectiveContext = multiContext || context;
        const hasContext = Boolean(
            multiContext
            || (context && context.editable)
        );
        setFormatButtonsEnabled(hasContext);
        if (hasContext) {
            updateFormatButtonStates(effectiveContext);
            updateSelectionRequiredButtons(effectiveContext);
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
        if (FONT_SIZE_FORMAT_KEYS.has(format)) {
            const context = resolveFormattableContext();
            return applyFontSize(format, context);
        }

        if (applyFormatToTableMultiSelection(format)) {
            refreshToolbar(resolveTableMultiFormatContext());
            return Promise.resolve();
        }

        const context = resolveFormattableContext();
        const command = FORMAT_COMMANDS[format];
        if (!context || !command) {
            return Promise.resolve();
        }

        if (FORMATS_REQUIRING_SELECTION.has(format) && !hasMeaningfulSelection(context)) {
            return Promise.resolve();
        }

        const selectionOffsets = captureSelectionOffsets(context.editable);
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

        if (!restoreSelectionOffsets(context.editable, selectionOffsets)) {
            restoreSelection(context);
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
        if (formatToolbarGroup) {
            formatToolbarGroup.addEventListener("mousedown", (event) => {
                event.preventDefault();
            });
        }

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

            const context = resolveTableMultiFormatContext() || resolveFormattableContext();
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
            const isBandText = editable.matches("[data-report-page-header-text], [data-report-page-header-extra-text], [data-report-page-footer-text]");
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
            const context = resolveTableMultiFormatContext()
                || resolveFormattableContextFromSelection()
                || resolveFormattableContext();
            if (context) {
                refreshToolbar(context);
            }
        });

        document.addEventListener("reportline:table-selection-changed", () => {
            refreshToolbar(resolveTableMultiFormatContext() || resolveFormattableContext());
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
