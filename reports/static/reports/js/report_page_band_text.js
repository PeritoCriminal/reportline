// reportline/reports/static/reports/js/report_page_band_text.js
/**
 * Recuo e campos compartilhados de células de texto em cabeçalho/rodapé.
 */
(function () {
    "use strict";

    const MAX_INDENT_LEVEL = 5;

    function clampIndentLevel(level) {
        const parsed = Number.parseInt(String(level), 10);
        if (Number.isNaN(parsed) || parsed < 0) {
            return 0;
        }
        return Math.min(MAX_INDENT_LEVEL, parsed);
    }

    function getIndentLevel(field) {
        return clampIndentLevel(field && field.dataset ? field.dataset.indentLevel : 0);
    }

    function hasFirstLineIndent(field) {
        return Boolean(field && field.dataset && field.dataset.firstLineIndent === "true");
    }

    function applyIndentVisual(field, layout) {
        if (!field) {
            return;
        }
        if (layout.indent_level !== undefined) {
            field.dataset.indentLevel = String(clampIndentLevel(layout.indent_level));
        }
        if (layout.first_line_indent !== undefined) {
            field.dataset.firstLineIndent = layout.first_line_indent ? "true" : "false";
        }
    }

    function collectTextCellPayload(textField, helpers) {
        const align = textField.dataset.textAlign || "left";
        const payload = {
            type: "text",
            text: helpers ? helpers.getHeaderHtml(textField) : textField.innerHTML,
            align,
            indent_level: getIndentLevel(textField),
            first_line_indent: hasFirstLineIndent(textField),
        };
        if (textField.hasAttribute("data-show-page-number")) {
            payload.show_page_number = textField.dataset.showPageNumber === "true";
        }
        if (textField.dataset.muted === "true") {
            payload.muted = true;
        }
        return payload;
    }

    function increaseIndent(field, scheduleSave) {
        const current = getIndentLevel(field);
        if (current >= MAX_INDENT_LEVEL) {
            return;
        }
        applyIndentVisual(field, { indent_level: current + 1 });
        if (scheduleSave) {
            scheduleSave();
        }
    }

    function decreaseIndent(field, scheduleSave) {
        const current = getIndentLevel(field);
        if (current <= 0) {
            return;
        }
        applyIndentVisual(field, { indent_level: current - 1 });
        if (scheduleSave) {
            scheduleSave();
        }
    }

    function toggleFirstLineIndent(field, scheduleSave) {
        applyIndentVisual(field, { first_line_indent: !hasFirstLineIndent(field) });
        if (scheduleSave) {
            scheduleSave();
        }
    }

    function getCaretOffset(element) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0 || !element) {
            return 0;
        }
        const range = selection.getRangeAt(0);
        if (!element.contains(range.startContainer)) {
            return 0;
        }
        const preRange = range.cloneRange();
        preRange.selectNodeContents(element);
        preRange.setEnd(range.startContainer, range.startOffset);
        return preRange.toString().length;
    }

    function setCaretOffset(element, offset) {
        if (!element) {
            return;
        }
        element.focus();
        const selection = window.getSelection();
        if (!selection) {
            return;
        }

        const range = document.createRange();
        let currentOffset = 0;
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let textNode = walker.nextNode();

        while (textNode) {
            const length = textNode.textContent.length;
            if (currentOffset + length >= offset) {
                range.setStart(textNode, offset - currentOffset);
                range.collapse(true);
                selection.removeAllRanges();
                selection.addRange(range);
                return;
            }
            currentOffset += length;
            textNode = walker.nextNode();
        }

        range.selectNodeContents(element);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
    }

    function captureBandTextFocus(root, options) {
        const opts = options || {};
        const textSelector = opts.textSelector || "";
        const extraTextSelector = opts.extraTextSelector || "";
        const selector = extraTextSelector ? `${textSelector}, ${extraTextSelector}` : textSelector;
        if (!root || !selector) {
            return null;
        }

        let field = null;
        const active = document.activeElement;
        if (active && root.contains(active) && active.matches(selector)) {
            field = active;
        } else if (
            opts.lastFocusedField
            && root.contains(opts.lastFocusedField)
            && opts.lastFocusedField.matches(selector)
        ) {
            field = opts.lastFocusedField;
        }

        if (!field) {
            return null;
        }

        return {
            cellIndex: field.dataset.cellIndex,
            extraRowIndex: field.dataset.extraRowIndex,
            caretOffset: getCaretOffset(field),
            isExtra: Boolean(extraTextSelector && field.matches(extraTextSelector)),
        };
    }

    function restoreBandTextFocus(root, state, options) {
        const opts = options || {};
        if (!root || !state) {
            return null;
        }

        let field = null;
        if (state.isExtra && state.extraRowIndex !== undefined && opts.extraTextSelector) {
            field = root.querySelector(
                `${opts.extraTextSelector}[data-extra-row-index="${state.extraRowIndex}"]`
            );
        } else if (state.cellIndex !== undefined && opts.textSelector) {
            field = root.querySelector(
                `${opts.textSelector}[data-cell-index="${state.cellIndex}"]`
            );
        }

        if (!field) {
            return null;
        }

        field.focus();
        setCaretOffset(field, state.caretOffset || 0);
        if (opts.onRestore) {
            opts.onRestore(field);
        }
        return field;
    }

    window.ReportLinePageBandText = {
        MAX_INDENT_LEVEL,
        getIndentLevel,
        hasFirstLineIndent,
        applyIndentVisual,
        collectTextCellPayload,
        increaseIndent,
        decreaseIndent,
        toggleFirstLineIndent,
        getCaretOffset,
        setCaretOffset,
        captureBandTextFocus,
        restoreBandTextFocus,
    };
})();
