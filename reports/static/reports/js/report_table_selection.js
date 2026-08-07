// reportline/reports/static/reports/js/report_table_selection.js
/**
 * Seleção múltipla de células em tabelas do editor.
 *
 * Suporta Shift+clique e arraste para selecionar região retangular
 * (cabeçalho e corpo). Exporta estado para operações estruturais.
 */
(function () {
    "use strict";

    /** @type {{ block: HTMLElement, anchor: TableCellCoord, focus: TableCellCoord } | null} */
    let activeSelection = null;
    let dragState = null;
    let pageElement = null;

    /**
     * @typedef {{ part: "header" | "cell", rowIndex: number, colIndex: number }} TableCellCoord
     */

    function getTableBlock(element) {
        return element ? element.closest(".report-editor-block[data-block-type=\"table\"]") : null;
    }

    function resolveCellCoord(element, block) {
        if (!element || !block || !block.contains(element)) {
            return null;
        }

        const editable = element.closest(".report-editor-table-cell[data-table-part]");
        if (editable && block.contains(editable)) {
            return {
                part: editable.dataset.tablePart === "header" ? "header" : "cell",
                rowIndex: editable.dataset.tablePart === "cell"
                    ? Number.parseInt(editable.dataset.rowIndex || "0", 10)
                    : -1,
                colIndex: Number.parseInt(editable.dataset.colIndex || "0", 10),
            };
        }

        const bodyCell = element.closest("td[data-row-index][data-col-index]");
        if (bodyCell && block.contains(bodyCell)) {
            return {
                part: "cell",
                rowIndex: Number.parseInt(bodyCell.dataset.rowIndex || "0", 10),
                colIndex: Number.parseInt(bodyCell.dataset.colIndex || "0", 10),
            };
        }

        const headerCell = element.closest("th[data-col-index]");
        if (headerCell && block.contains(headerCell)) {
            return {
                part: "header",
                rowIndex: -1,
                colIndex: Number.parseInt(headerCell.dataset.colIndex || "0", 10),
            };
        }

        const imageCell = element.closest(".report-editor-table-cell-image");
        if (imageCell && block.contains(imageCell)) {
            const container = imageCell.closest("td[data-row-index][data-col-index]");
            if (container) {
                return {
                    part: "cell",
                    rowIndex: Number.parseInt(container.dataset.rowIndex || "0", 10),
                    colIndex: Number.parseInt(container.dataset.colIndex || "0", 10),
                };
            }
        }

        return null;
    }

    function normalizeRange(anchor, focus) {
        const minCol = Math.min(anchor.colIndex, focus.colIndex);
        const maxCol = Math.max(anchor.colIndex, focus.colIndex);
        const anchorRow = anchor.part === "header" ? -1 : anchor.rowIndex;
        const focusRow = focus.part === "header" ? -1 : focus.rowIndex;
        const minRow = Math.min(anchorRow, focusRow);
        const maxRow = Math.max(anchorRow, focusRow);

        return { minRow, maxRow, minCol, maxCol };
    }

    function cellInRange(coord, range) {
        if (coord.colIndex < range.minCol || coord.colIndex > range.maxCol) {
            return false;
        }

        const row = coord.part === "header" ? -1 : coord.rowIndex;
        return row >= range.minRow && row <= range.maxRow;
    }

    function countSelectedCells(range) {
        const rowCount = range.maxRow - range.minRow + 1;
        const colCount = range.maxCol - range.minCol + 1;
        return rowCount * colCount;
    }

    function clearSelectionVisual(block) {
        if (!block) {
            return;
        }
        block.querySelectorAll(".is-table-cell-selected").forEach((cell) => {
            cell.classList.remove("is-table-cell-selected");
            cell.removeAttribute("aria-selected");
        });
    }

    function applySelectionVisual(block, anchor, focus) {
        clearSelectionVisual(block);
        if (!anchor || !focus) {
            return;
        }

        const range = normalizeRange(anchor, focus);
        const table = block.querySelector("table");
        if (!table) {
            return;
        }

        table.querySelectorAll("th[data-col-index], td[data-row-index]").forEach((cellElement) => {
            const part = cellElement.matches("th") ? "header" : "cell";
            const coord = {
                part,
                rowIndex: part === "cell"
                    ? Number.parseInt(cellElement.dataset.rowIndex || "0", 10)
                    : -1,
                colIndex: Number.parseInt(cellElement.dataset.colIndex || "0", 10),
            };

            if (cellInRange(coord, range)) {
                cellElement.classList.add("is-table-cell-selected");
                cellElement.setAttribute("aria-selected", "true");
            }
        });
    }

    function setSelection(block, anchor, focus) {
        if (!block || !anchor || !focus) {
            activeSelection = null;
            return;
        }

        activeSelection = { block, anchor, focus };
        applySelectionVisual(block, anchor, focus);

        document.dispatchEvent(new CustomEvent("reportline:table-selection-changed", {
            detail: { selection: getSelectionSnapshot() },
        }));
    }

    function clearSelection() {
        if (activeSelection && activeSelection.block) {
            clearSelectionVisual(activeSelection.block);
        }
        activeSelection = null;
        dragState = null;

        document.dispatchEvent(new CustomEvent("reportline:table-selection-changed", {
            detail: { selection: null },
        }));
    }

    function getSelectionSnapshot() {
        if (!activeSelection) {
            return null;
        }

        const { block, anchor, focus } = activeSelection;
        const range = normalizeRange(anchor, focus);
        const bodyRowIndices = [];
        const colIndices = [];

        for (let row = range.minRow; row <= range.maxRow; row += 1) {
            if (row >= 0) {
                bodyRowIndices.push(row);
            }
        }

        for (let col = range.minCol; col <= range.maxCol; col += 1) {
            colIndices.push(col);
        }

        return {
            block,
            anchor: { ...anchor },
            focus: { ...focus },
            range,
            isMulti: countSelectedCells(range) > 1,
            includesHeader: range.minRow <= -1 && range.maxRow >= -1,
            bodyRowIndices,
            colIndices,
        };
    }

    function getSelectedCellElements(block) {
        if (!block) {
            return [];
        }
        return Array.from(
            block.querySelectorAll("th.is-table-cell-selected, td.is-table-cell-selected")
        );
    }

    function getSelectedTextEditables(block) {
        const targetBlock = block || (activeSelection ? activeSelection.block : null);
        if (!targetBlock) {
            return [];
        }

        return getSelectedCellElements(targetBlock)
            .map((cellElement) => cellElement.querySelector(".report-editor-table-cell[data-table-part]"))
            .filter(Boolean);
    }

    function getSelectedAlignTargets(block) {
        const targetBlock = block || (activeSelection ? activeSelection.block : null);
        if (!targetBlock) {
            return [];
        }

        const targets = [];
        getSelectedCellElements(targetBlock).forEach((cellElement) => {
            const textEditable = cellElement.querySelector(".report-editor-table-cell[data-table-part]");
            if (textEditable) {
                targets.push({ kind: "text", element: textEditable });
                return;
            }

            const imageCell = cellElement.querySelector(".report-editor-table-cell-image");
            if (imageCell) {
                targets.push({ kind: "image", element: imageCell });
            }
        });
        return targets;
    }

    function hasMultiCellSelection() {
        const snapshot = getSelectionSnapshot();
        return Boolean(snapshot && snapshot.isMulti);
    }

    function isSameCoord(a, b) {
        return a.part === b.part && a.rowIndex === b.rowIndex && a.colIndex === b.colIndex;
    }

    function getTableCellContainer(block, coord) {
        if (!block || !coord) {
            return null;
        }

        if (coord.part === "header") {
            return block.querySelector(`th[data-col-index="${coord.colIndex}"]`);
        }

        return block.querySelector(
            `td[data-row-index="${coord.rowIndex}"][data-col-index="${coord.colIndex}"]`
        );
    }

    function getTableCellPasteAnchor() {
        const snapshot = getSelectionSnapshot();
        if (snapshot) {
            return {
                block: snapshot.block,
                startRow: snapshot.range.minRow,
                startCol: snapshot.range.minCol,
            };
        }

        const active = document.activeElement;
        const editable = active && active.closest
            ? active.closest(".report-editor-table-cell[data-table-part]")
            : null;
        if (!editable) {
            return null;
        }

        const block = editable.closest(".report-editor-block[data-block-type=\"table\"]");
        if (!block) {
            return null;
        }

        const part = editable.dataset.tablePart;
        return {
            block,
            startRow: part === "header" ? -1 : Number.parseInt(editable.dataset.rowIndex || "0", 10),
            startCol: Number.parseInt(editable.dataset.colIndex || "0", 10),
        };
    }

    function isSelectionPreservedTarget(target) {
        if (!target || !target.closest) {
            return false;
        }

        return Boolean(
            target.closest(".report-editor-toolbar-table-group")
            || target.closest(".report-editor-toolbar-format-group")
            || target.closest(".report-editor-toolbar-align-group")
        );
    }

    function handleMouseDown(event) {
        if (event.button !== 0) {
            return;
        }

        const block = getTableBlock(event.target);
        if (!block || !pageElement || !pageElement.contains(block)) {
            return;
        }

        if (event.target.closest(".report-editor-table-column-resizer, .report-editor-table-width-resizer")) {
            return;
        }

        const coord = resolveCellCoord(event.target, block);
        if (!coord) {
            return;
        }

        if (event.shiftKey) {
            const coord = resolveCellCoord(event.target, block);
            if (!coord) {
                return;
            }

            event.preventDefault();
            let anchor = coord;
            if (activeSelection && activeSelection.block === block) {
                anchor = activeSelection.anchor;
            } else if (
                window.ReportLineEditor
                && window.ReportLineEditor.resolveTableCellContext
            ) {
                const context = window.ReportLineEditor.resolveTableCellContext();
                if (context && context.block === block) {
                    anchor = {
                        part: context.part === "header" ? "header" : "cell",
                        rowIndex: context.part === "cell" ? context.rowIndex : -1,
                        colIndex: context.colIndex,
                    };
                }
            }

            setSelection(block, anchor, coord);
            return;
        }

        dragState = {
            block,
            anchor: coord,
            startedOnCoord: coord,
            isDragging: false,
        };
    }

    function handleMouseMove(event) {
        if (!dragState) {
            return;
        }

        const coord = resolveCellCoord(event.target, dragState.block);
        if (!coord) {
            return;
        }

        if (!dragState.isDragging && !isSameCoord(coord, dragState.startedOnCoord)) {
            dragState.isDragging = true;
        }

        if (dragState.isDragging) {
            dragState.block.classList.add("is-table-cell-dragging");
            event.preventDefault();
            setSelection(dragState.block, dragState.anchor, coord);
        }
    }

    function handleMouseUp(event) {
        if (!dragState) {
            return;
        }

        const { block, anchor, startedOnCoord, isDragging } = dragState;
        dragState = null;
        block.classList.remove("is-table-cell-dragging");

        if (isDragging) {
            event.preventDefault();
            const focusCoord = resolveCellCoord(event.target, block) || anchor;
            setSelection(block, anchor, focusCoord);
            return;
        }

        if (activeSelection && activeSelection.block !== block) {
            clearSelection();
        } else if (activeSelection && activeSelection.block === block) {
            clearSelection();
        }
    }

    function handleKeyDown(event) {
        if (event.key === "Escape") {
            clearSelection();
        }
    }

    function handleFocusIn(event) {
        const block = getTableBlock(event.target);
        if (!block) {
            if (activeSelection && !isSelectionPreservedTarget(event.target)) {
                clearSelection();
            }
            return;
        }

        if (dragState && dragState.isDragging) {
            return;
        }

        if (event.shiftKey && activeSelection && activeSelection.block === block) {
            const coord = resolveCellCoord(event.target, block);
            if (coord) {
                setSelection(block, activeSelection.anchor, coord);
            }
            return;
        }

        if (activeSelection && activeSelection.block === block) {
            const snapshot = getSelectionSnapshot();
            if (snapshot && snapshot.isMulti) {
                clearSelection();
            }
        }
    }

    function handleClickOutside(event) {
        if (!activeSelection) {
            return;
        }

        const insideTable = event.target.closest(".report-editor-block[data-block-type=\"table\"]");
        if (
            (!insideTable || insideTable !== activeSelection.block)
            && !isSelectionPreservedTarget(event.target)
        ) {
            clearSelection();
        }
    }

    function resyncSelectionVisual(block) {
        if (!activeSelection || activeSelection.block !== block) {
            clearSelectionVisual(block);
            return;
        }

        applySelectionVisual(block, activeSelection.anchor, activeSelection.focus);
    }

    function observeTableBlocks(root) {
        if (!root) {
            return;
        }

        root.querySelectorAll(".report-editor-block[data-block-type=\"table\"]").forEach((block) => {
            resyncSelectionVisual(block);
        });
    }

    function init() {
        pageElement = document.getElementById("report-editor-page");
        if (!pageElement) {
            return;
        }

        pageElement.addEventListener("mousedown", handleMouseDown);
        document.addEventListener("mousemove", handleMouseMove);
        document.addEventListener("mouseup", handleMouseUp);
        pageElement.addEventListener("focusin", handleFocusIn);
        pageElement.addEventListener("click", handleClickOutside);
        document.addEventListener("keydown", handleKeyDown);

        if (window.MutationObserver) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType !== Node.ELEMENT_NODE) {
                            return;
                        }
                        if (node.matches && node.matches(".report-editor-block[data-block-type=\"table\"]")) {
                            resyncSelectionVisual(node);
                        } else if (node.querySelectorAll) {
                            observeTableBlocks(node);
                        }
                    });
                });
            });
            observer.observe(pageElement, { childList: true, subtree: true });
        }

        observeTableBlocks(pageElement);
    }

    window.ReportLineTableSelection = {
        init,
        clearSelection,
        getSelection: getSelectionSnapshot,
        hasMultiCellSelection,
        getSelectedTextEditables,
        getSelectedAlignTargets,
        getTableCellContainer,
        getTableCellPasteAnchor,
    };
})();
