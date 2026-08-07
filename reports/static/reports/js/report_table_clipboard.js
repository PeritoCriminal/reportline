// reportline/reports/static/reports/js/report_table_clipboard.js
/**
 * Copiar e colar células de tabela (estilo planilha).
 *
 * Suporta seleção múltipla, célula única e colagem a partir de TSV externo.
 */
(function () {
    "use strict";

    const CLIPBOARD_MIME = "application/x-reportline-table-cells+json";

    /** @type {{ grid: Array<Array<object>> } | null} */
    let internalClipboard = null;

    function getInlineText() {
        return window.ReportLineInlineText || null;
    }

    function getEditor() {
        return window.ReportLineEditor || null;
    }

    function getSelectionApi() {
        return window.ReportLineTableSelection || null;
    }

    function htmlToPlainText(html) {
        const inlineText = getInlineText();
        if (inlineText && inlineText.getPlainTextWithNewlinesFromHtml) {
            return inlineText.getPlainTextWithNewlinesFromHtml(html || "");
        }

        const container = document.createElement("div");
        container.innerHTML = html || "";
        return container.textContent || "";
    }

    function plainTextToHtml(text) {
        const inlineText = getInlineText();
        const normalized = String(text || "");
        if (!normalized) {
            return "";
        }

        const escaped = normalized
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        if (inlineText && inlineText.sanitize) {
            return inlineText.sanitize(escaped.replace(/\n/g, "<br>"));
        }

        return escaped.replace(/\n/g, "<br>");
    }

    function gridToTsv(grid) {
        return grid
            .map((row) => row
                .map((cell) => {
                    if (!cell || cell.type !== "text") {
                        return "";
                    }
                    return htmlToPlainText(cell.html).replace(/\t/g, " ").replace(/\r?\n/g, "\n");
                })
                .join("\t"))
            .join("\n");
    }

    function parseTsv(text) {
        const normalized = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
        if (!normalized.trim()) {
            return null;
        }

        return normalized.split("\n").map((line) => line.split("\t").map((value) => ({
            type: "text",
            html: plainTextToHtml(value),
            align: "left",
        })));
    }

    function extractGridFromRange(block, range) {
        const editor = getEditor();
        if (!editor || !editor.extractTableCellClipboardData) {
            return null;
        }

        const grid = [];
        for (let row = range.minRow; row <= range.maxRow; row += 1) {
            const part = row === -1 ? "header" : "cell";
            const rowIndex = row;
            const rowCells = [];

            for (let col = range.minCol; col <= range.maxCol; col += 1) {
                const cellData = editor.extractTableCellClipboardData(
                    block,
                    part,
                    rowIndex,
                    col
                );
                rowCells.push(cellData || { type: "text", html: "", align: "left" });
            }

            grid.push(rowCells);
        }

        return grid;
    }

    function resolveCopyContext() {
        const selectionApi = getSelectionApi();
        const snapshot = selectionApi && selectionApi.getSelection
            ? selectionApi.getSelection()
            : null;

        if (snapshot && snapshot.isMulti) {
            return {
                block: snapshot.block,
                range: snapshot.range,
            };
        }

        const active = document.activeElement;
        const editable = active && active.closest
            ? active.closest(".report-editor-table-cell[data-table-part]")
            : null;
        if (!editable) {
            return null;
        }

        const selection = window.getSelection();
        if (selection && !selection.isCollapsed && selection.toString().length > 0) {
            return null;
        }

        const block = editable.closest(".report-editor-block[data-block-type=\"table\"]");
        if (!block) {
            return null;
        }

        const part = editable.dataset.tablePart;
        const rowIndex = part === "header"
            ? -1
            : Number.parseInt(editable.dataset.rowIndex || "0", 10);
        const colIndex = Number.parseInt(editable.dataset.colIndex || "0", 10);

        return {
            block,
            range: {
                minRow: rowIndex,
                maxRow: rowIndex,
                minCol: colIndex,
                maxCol: colIndex,
            },
        };
    }

    function resolvePasteAnchor() {
        const selectionApi = getSelectionApi();
        if (selectionApi && selectionApi.getTableCellPasteAnchor) {
            return selectionApi.getTableCellPasteAnchor();
        }
        return null;
    }

    function readGridFromClipboardData(clipboardData) {
        if (!clipboardData) {
            return null;
        }

        if (clipboardData.types && clipboardData.types.includes(CLIPBOARD_MIME)) {
            try {
                const payload = JSON.parse(clipboardData.getData(CLIPBOARD_MIME));
                if (payload && Array.isArray(payload.grid) && payload.grid.length > 0) {
                    return payload.grid;
                }
            } catch (_error) {
                return null;
            }
        }

        if (internalClipboard && internalClipboard.grid) {
            return internalClipboard.grid;
        }

        const plain = clipboardData.getData("text/plain");
        return parseTsv(plain);
    }

    function shouldHandleTablePaste(clipboardData) {
        if (internalClipboard && internalClipboard.grid) {
            return true;
        }

        if (clipboardData && clipboardData.types && clipboardData.types.includes(CLIPBOARD_MIME)) {
            return true;
        }

        const selectionApi = getSelectionApi();
        const snapshot = selectionApi && selectionApi.getSelection
            ? selectionApi.getSelection()
            : null;
        if (snapshot && snapshot.isMulti) {
            return true;
        }

        const plain = clipboardData ? clipboardData.getData("text/plain") : "";
        return plain.includes("\t") || plain.includes("\n");
    }

    function handleCopy(event) {
        const context = resolveCopyContext();
        if (!context) {
            return false;
        }

        const grid = extractGridFromRange(context.block, context.range);
        if (!grid || grid.length === 0) {
            return false;
        }

        internalClipboard = { grid };

        if (event.clipboardData) {
            event.clipboardData.setData("text/plain", gridToTsv(grid));
            event.clipboardData.setData(CLIPBOARD_MIME, JSON.stringify({ grid }));
        }

        return true;
    }

    function handlePaste(event) {
        const anchor = resolvePasteAnchor();
        if (!anchor || !shouldHandleTablePaste(event.clipboardData || null)) {
            return false;
        }

        const grid = readGridFromClipboardData(event.clipboardData || null);
        if (!grid || grid.length === 0) {
            return false;
        }

        const editor = getEditor();
        if (!editor || !editor.pasteTableCellGrid) {
            return false;
        }

        editor.pasteTableCellGrid(
            anchor.block,
            anchor.startRow,
            anchor.startCol,
            grid
        ).catch(console.error);
        return true;
    }

    function bindClipboardEvents(page) {
        page.addEventListener("copy", (event) => {
            if (handleCopy(event)) {
                event.preventDefault();
            }
        }, true);

        page.addEventListener("paste", (event) => {
            if (handlePaste(event)) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }, true);

        page.addEventListener("keydown", (event) => {
            if (!(event.ctrlKey || event.metaKey) || event.altKey) {
                return;
            }

            if (event.key.toLowerCase() !== "c") {
                return;
            }

            const context = resolveCopyContext();
            if (!context) {
                return;
            }

            const grid = extractGridFromRange(context.block, context.range);
            if (grid && grid.length > 0) {
                internalClipboard = { grid };
            }
        }, true);
    }

    function init() {
        const page = document.getElementById("report-editor-page");
        if (!page) {
            return;
        }

        bindClipboardEvents(page);
    }

    window.ReportLineTableClipboard = { init };
})();
