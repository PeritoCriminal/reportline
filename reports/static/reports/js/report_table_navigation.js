/**
 * Navegação entre células de tabela com as setas do teclado.
 *
 * Move o foco para a célula adjacente quando o cursor está no limite
 * horizontal ou vertical da célula atual; em células com imagem, as setas
 * navegam diretamente para a célula vizinha.
 */
(function () {
    "use strict";

    /** @type {HTMLElement | null} */
    let pageElement = null;

    const KEY_DIRECTION = {
        ArrowLeft: "left",
        ArrowRight: "right",
        ArrowUp: "up",
        ArrowDown: "down",
    };

    function getCaretOffset(element) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
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

    function placeCaretAtStart(element) {
        element.focus();
        const selection = window.getSelection();
        if (!selection) {
            return;
        }
        const range = document.createRange();
        range.selectNodeContents(element);
        range.collapse(true);
        selection.removeAllRanges();
        selection.addRange(range);
    }

    function placeCaretAtEnd(element) {
        element.focus();
        const selection = window.getSelection();
        if (!selection) {
            return;
        }
        const range = document.createRange();
        range.selectNodeContents(element);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
    }

    function getLineTop(element, atStart) {
        const range = document.createRange();
        range.selectNodeContents(element);
        range.collapse(atStart);
        const rects = range.getClientRects();
        return rects.length ? rects[0].top : null;
    }

    function isCaretOnFirstLine(editable) {
        const selection = window.getSelection();
        if (!selection || !selection.rangeCount || !selection.isCollapsed) {
            return false;
        }
        const range = selection.getRangeAt(0);
        if (!editable.contains(range.startContainer)) {
            return false;
        }

        const firstLineTop = getLineTop(editable, true);
        if (firstLineTop === null) {
            return true;
        }

        const caretRects = range.getClientRects();
        if (!caretRects.length) {
            return getCaretOffset(editable) === 0;
        }

        return Math.abs(caretRects[0].top - firstLineTop) < 2;
    }

    function isCaretOnLastLine(editable) {
        const selection = window.getSelection();
        if (!selection || !selection.rangeCount || !selection.isCollapsed) {
            return false;
        }
        const range = selection.getRangeAt(0);
        if (!editable.contains(range.startContainer)) {
            return false;
        }

        const lastLineTop = getLineTop(editable, false);
        if (lastLineTop === null) {
            return true;
        }

        const caretRects = range.getClientRects();
        if (!caretRects.length) {
            const textLength = editable.textContent ? editable.textContent.length : 0;
            return getCaretOffset(editable) >= textLength;
        }

        return Math.abs(caretRects[0].top - lastLineTop) < 2;
    }

    function isEditableEmpty(editable) {
        return (editable.textContent || "").trim() === "";
    }

    function tableHeaderVisible(block) {
        return block.dataset.tableShowHeader !== "false";
    }

    function getTableColumnCount(block) {
        return block.querySelectorAll("thead th[data-col-index]").length;
    }

    function getTableRowCount(block) {
        return block.querySelectorAll("tbody tr").length;
    }

    function resolveCoordFromTextEditable(editable) {
        return {
            part: editable.dataset.tablePart,
            rowIndex: editable.dataset.tablePart === "cell"
                ? Number.parseInt(editable.dataset.rowIndex || "0", 10)
                : -1,
            colIndex: Number.parseInt(editable.dataset.colIndex || "0", 10),
        };
    }

    function resolveCoordFromImageCell(imageCell) {
        const container = imageCell.closest("td[data-row-index][data-col-index]");
        if (!container) {
            return null;
        }

        return {
            part: "cell",
            rowIndex: Number.parseInt(container.dataset.rowIndex || "0", 10),
            colIndex: Number.parseInt(container.dataset.colIndex || "0", 10),
        };
    }

    function getAdjacentCoord(block, current, direction) {
        const colCount = getTableColumnCount(block);
        const rowCount = getTableRowCount(block);
        const showHeader = tableHeaderVisible(block);
        const { part, rowIndex, colIndex } = current;

        switch (direction) {
            case "left":
                if (colIndex > 0) {
                    return { part, rowIndex, colIndex: colIndex - 1 };
                }
                return null;
            case "right":
                if (colIndex < colCount - 1) {
                    return { part, rowIndex, colIndex: colIndex + 1 };
                }
                return null;
            case "up":
                if (part === "cell" && rowIndex > 0) {
                    return { part: "cell", rowIndex: rowIndex - 1, colIndex };
                }
                if (part === "cell" && rowIndex === 0 && showHeader) {
                    return { part: "header", rowIndex: -1, colIndex };
                }
                return null;
            case "down":
                if (part === "header") {
                    return rowCount > 0
                        ? { part: "cell", rowIndex: 0, colIndex }
                        : null;
                }
                if (part === "cell" && rowIndex < rowCount - 1) {
                    return { part: "cell", rowIndex: rowIndex + 1, colIndex };
                }
                return null;
            default:
                return null;
        }
    }

    function findNavigableTarget(block, coord) {
        if (coord.part === "header") {
            const headerEditable = block.querySelector(
                `th[data-col-index="${coord.colIndex}"] .report-editor-table-cell[data-table-part="header"]`
            );
            if (headerEditable) {
                return { type: "text", element: headerEditable };
            }
            return null;
        }

        const container = block.querySelector(
            `td[data-row-index="${coord.rowIndex}"][data-col-index="${coord.colIndex}"]`
        );
        if (!container) {
            return null;
        }

        const textEditable = container.querySelector(
            '.report-editor-table-cell[data-table-part="cell"]'
        );
        if (textEditable) {
            return { type: "text", element: textEditable };
        }

        const imageCell = container.querySelector(".report-editor-table-cell-image");
        if (imageCell) {
            return { type: "image", element: imageCell };
        }

        return null;
    }

    function caretPlacementForEntry(direction) {
        switch (direction) {
            case "left":
            case "up":
                return "end";
            case "right":
            case "down":
                return "start";
            default:
                return "start";
        }
    }

    function clearTableSelection() {
        if (window.ReportLineTableSelection && window.ReportLineTableSelection.clearSelection) {
            window.ReportLineTableSelection.clearSelection();
        }
    }

    function focusTableCellTarget(block, coord, caretPlacement) {
        const target = findNavigableTarget(block, coord);
        if (!target) {
            return false;
        }

        clearTableSelection();

        if (target.type === "text") {
            if (window.ReportLineImageResize && window.ReportLineImageResize.deselectTarget) {
                window.ReportLineImageResize.deselectTarget();
            }

            if (caretPlacement === "start") {
                placeCaretAtStart(target.element);
            } else {
                placeCaretAtEnd(target.element);
            }
            return true;
        }

        if (
            target.type === "image"
            && window.ReportLineImageResize
            && window.ReportLineImageResize.selectTargetElement
        ) {
            window.ReportLineImageResize.selectTargetElement(target.element);
            return true;
        }

        return false;
    }

    function shouldNavigateFromTextCell(editable, key) {
        if (isEditableEmpty(editable)) {
            return true;
        }

        switch (key) {
            case "ArrowLeft":
                return getCaretOffset(editable) === 0;
            case "ArrowRight":
                return getCaretOffset(editable) >= (editable.textContent || "").length;
            case "ArrowUp":
                return isCaretOnFirstLine(editable);
            case "ArrowDown":
                return isCaretOnLastLine(editable);
            default:
                return false;
        }
    }

    function handleKeyDown(event) {
        const direction = KEY_DIRECTION[event.key];
        if (!direction || event.defaultPrevented) {
            return;
        }

        if (event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) {
            return;
        }

        const active = document.activeElement;
        const imageCell = active && active.closest
            ? active.closest(".report-editor-table-cell-image")
            : null;

        if (imageCell) {
            const block = imageCell.closest('.report-editor-block[data-block-type="table"]');
            if (!block || !pageElement || !pageElement.contains(block)) {
                return;
            }

            const coord = resolveCoordFromImageCell(imageCell);
            if (!coord) {
                return;
            }

            const nextCoord = getAdjacentCoord(block, coord, direction);
            if (!nextCoord) {
                return;
            }

            event.preventDefault();
            focusTableCellTarget(block, nextCoord, caretPlacementForEntry(direction));
            return;
        }

        const editable = event.target.closest
            ? event.target.closest(".report-editor-table-cell[data-table-part]")
            : null;
        if (!editable) {
            return;
        }

        const block = editable.closest('.report-editor-block[data-block-type="table"]');
        if (!block || !pageElement || !pageElement.contains(block)) {
            return;
        }

        if (!shouldNavigateFromTextCell(editable, event.key)) {
            return;
        }

        const coord = resolveCoordFromTextEditable(editable);
        const nextCoord = getAdjacentCoord(block, coord, direction);
        if (!nextCoord) {
            return;
        }

        event.preventDefault();
        focusTableCellTarget(block, nextCoord, caretPlacementForEntry(direction));
    }

    function init() {
        pageElement = document.getElementById("report-editor-page");
        if (!pageElement) {
            return;
        }

        pageElement.addEventListener("keydown", handleKeyDown, true);
    }

    window.ReportLineTableNavigation = {
        init,
    };
})();
