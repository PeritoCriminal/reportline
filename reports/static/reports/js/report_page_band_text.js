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

    window.ReportLinePageBandText = {
        MAX_INDENT_LEVEL,
        getIndentLevel,
        hasFirstLineIndent,
        applyIndentVisual,
        collectTextCellPayload,
        increaseIndent,
        decreaseIndent,
        toggleFirstLineIndent,
    };
})();
