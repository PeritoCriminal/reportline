/**
 * Redimensionamento interativo de colunas em tabelas do editor.
 */
(function () {
    "use strict";

    const MIN_COLUMN_WIDTH_PERCENT = 5;

    let pageElement = null;
    let activeDrag = null;

    function equalColumnWidths(columnCount) {
        if (columnCount <= 0) {
            return [];
        }
        const base = Math.floor(100 / columnCount);
        const remainder = 100 % columnCount;
        return Array.from({ length: columnCount }, (_, index) => (
            base + (index < remainder ? 1 : 0)
        ));
    }

    function normalizeColumnWidths(widths, columnCount) {
        if (columnCount <= 0) {
            return [];
        }
        if (!Array.isArray(widths) || widths.length !== columnCount) {
            return equalColumnWidths(columnCount);
        }

        const normalized = widths.map((value) => Math.max(1, Number.parseInt(value, 10) || 1));
        const total = normalized.reduce((sum, value) => sum + value, 0);
        if (total <= 0) {
            return equalColumnWidths(columnCount);
        }
        if (total === 100) {
            return normalized;
        }

        const scaled = normalized.map((value) => Math.max(1, Math.round((value * 100) / total)));
        const diff = 100 - scaled.reduce((sum, value) => sum + value, 0);
        scaled[scaled.length - 1] = Math.max(1, scaled[scaled.length - 1] + diff);
        return normalizeColumnWidths(scaled, columnCount);
    }

    function resizeAdjacentColumns(widths, leftIndex, deltaPercent) {
        if (leftIndex < 0 || leftIndex >= widths.length - 1) {
            return widths;
        }

        const next = [...widths];
        const left = next[leftIndex];
        const right = next[leftIndex + 1];
        let adjustedDelta = deltaPercent;

        let leftNext = left + adjustedDelta;
        let rightNext = right - adjustedDelta;

        if (leftNext < MIN_COLUMN_WIDTH_PERCENT || rightNext < MIN_COLUMN_WIDTH_PERCENT) {
            const maxDelta = Math.min(
                left - MIN_COLUMN_WIDTH_PERCENT,
                right - MIN_COLUMN_WIDTH_PERCENT
            );
            if (maxDelta <= 0) {
                return widths;
            }
            adjustedDelta = Math.max(-maxDelta, Math.min(maxDelta, adjustedDelta));
            leftNext = left + adjustedDelta;
            rightNext = right - adjustedDelta;
        }

        next[leftIndex] = leftNext;
        next[leftIndex + 1] = rightNext;
        return normalizeColumnWidths(next, next.length);
    }

    function getTableBlock(element) {
        return element ? element.closest(".report-editor-block[data-block-type=\"table\"]") : null;
    }

    function parseColumnWidths(block) {
        const raw = block.dataset.tableColumnWidths || "";
        if (raw) {
            return normalizeColumnWidths(
                raw.split(",").map((part) => Number.parseInt(part.trim(), 10)),
                raw.split(",").length
            );
        }

        const cols = block.querySelectorAll("colgroup col");
        if (cols.length) {
            return normalizeColumnWidths(
                Array.from(cols).map((col) => {
                    const match = (col.style.width || "").match(/(\d+)/);
                    return match ? Number.parseInt(match[1], 10) : 1;
                }),
                cols.length
            );
        }

        const headerCount = block.querySelectorAll('[data-table-part="header"]').length;
        return equalColumnWidths(headerCount || 1);
    }

    function applyColumnWidths(block, widths) {
        const normalized = normalizeColumnWidths(widths, widths.length);
        block.dataset.tableColumnWidths = normalized.join(",");

        const cols = block.querySelectorAll("colgroup col");
        normalized.forEach((width, index) => {
            if (cols[index]) {
                cols[index].style.width = `${width}%`;
            }
        });

        repositionResizers(block, normalized);
        return normalized;
    }

    function repositionResizers(block, widths) {
        const wrap = block.querySelector(".report-editor-block-table-wrap");
        if (!wrap) {
            return;
        }

        const resizers = wrap.querySelectorAll(".report-editor-table-column-resizer");
        let cumulative = 0;
        resizers.forEach((handle, index) => {
            cumulative += widths[index];
            handle.style.left = `${cumulative}%`;
        });
    }

    function buildResizers(block) {
        const wrap = block.querySelector(".report-editor-block-table-wrap");
        if (!wrap) {
            return;
        }

        let container = wrap.querySelector(".report-editor-table-column-resizers");
        if (!container) {
            container = document.createElement("div");
            container.className = "report-editor-table-column-resizers";
            container.setAttribute("aria-hidden", "true");
            wrap.appendChild(container);
        }

        const widths = parseColumnWidths(block);
        applyColumnWidths(block, widths);
        container.innerHTML = "";

        for (let index = 0; index < widths.length - 1; index += 1) {
            const handle = document.createElement("div");
            handle.className = "report-editor-table-column-resizer";
            handle.dataset.leftColIndex = String(index);
            handle.setAttribute("role", "separator");
            handle.setAttribute("aria-orientation", "vertical");
            handle.setAttribute("aria-label", `Redimensionar colunas ${index + 1} e ${index + 2}`);
            container.appendChild(handle);
        }

        repositionResizers(block, widths);
    }

    function prepareTableBlock(block) {
        if (!block || block.dataset.columnResizeBound === "true") {
            return;
        }
        block.dataset.columnResizeBound = "true";
        buildResizers(block);

        const table = block.querySelector("table");
        if (table && window.ResizeObserver) {
            const observer = new ResizeObserver(() => {
                repositionResizers(block, parseColumnWidths(block));
            });
            observer.observe(table);
        }
    }

    function scanTableBlocks(root) {
        root.querySelectorAll(".report-editor-block[data-block-type=\"table\"]").forEach(prepareTableBlock);
    }

    function clearDragState() {
        document.body.classList.remove("report-editor-column-resize-active");
        if (activeDrag && activeDrag.wrap) {
            activeDrag.wrap.classList.remove("is-column-resizing");
        }
        if (activeDrag && activeDrag.handle) {
            activeDrag.handle.classList.remove("is-dragging");
        }
        document.removeEventListener("pointermove", moveDrag);
        document.removeEventListener("pointerup", endDrag);
        document.removeEventListener("pointercancel", endDrag);
        activeDrag = null;
    }

    function startDrag(event, block, handle, leftColIndex) {
        event.preventDefault();
        event.stopPropagation();

        const table = block.querySelector("table");
        const wrap = block.querySelector(".report-editor-block-table-wrap");
        if (!table || !wrap) {
            return;
        }

        handle.classList.add("is-dragging");
        wrap.classList.add("is-column-resizing");
        document.body.classList.add("report-editor-column-resize-active");

        activeDrag = {
            block,
            wrap,
            handle,
            leftColIndex,
            startX: event.clientX,
            startWidths: parseColumnWidths(block),
            tableWidth: table.getBoundingClientRect().width,
            pointerId: event.pointerId,
        };

        if (window.ReportLineEditor && window.ReportLineEditor.beginBlockContentRecording) {
            window.ReportLineEditor.beginBlockContentRecording(block);
        }

        if (handle.setPointerCapture) {
            handle.setPointerCapture(event.pointerId);
        }

        document.addEventListener("pointermove", moveDrag);
        document.addEventListener("pointerup", endDrag);
        document.addEventListener("pointercancel", endDrag);
    }

    function moveDrag(event) {
        if (!activeDrag || event.pointerId !== activeDrag.pointerId) {
            return;
        }

        const deltaPx = event.clientX - activeDrag.startX;
        const deltaPercent = Math.round((deltaPx / activeDrag.tableWidth) * 100);
        const nextWidths = resizeAdjacentColumns(
            activeDrag.startWidths,
            activeDrag.leftColIndex,
            deltaPercent
        );
        applyColumnWidths(activeDrag.block, nextWidths);
    }

    async function endDrag(event) {
        if (!activeDrag || event.pointerId !== activeDrag.pointerId) {
            return;
        }

        const block = activeDrag.block;
        clearDragState();

        if (window.ReportLineEditor && window.ReportLineEditor.saveBlock) {
            try {
                await window.ReportLineEditor.saveBlock(block);
            } catch (error) {
                console.error(error);
            }
        }
    }

    function bindPage(page) {
        page.addEventListener("pointerdown", (event) => {
            const handle = event.target.closest(".report-editor-table-column-resizer");
            if (!handle) {
                return;
            }

            const block = getTableBlock(handle);
            if (!block) {
                return;
            }

            const leftColIndex = Number.parseInt(handle.dataset.leftColIndex || "-1", 10);
            if (leftColIndex < 0) {
                return;
            }

            startDrag(event, block, handle, leftColIndex);
        });

        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (!(node instanceof Element)) {
                        return;
                    }
                    if (node.matches(".report-editor-block[data-block-type=\"table\"]")) {
                        prepareTableBlock(node);
                    } else {
                        scanTableBlocks(node);
                    }
                });
            });
        });

        observer.observe(page, { childList: true, subtree: true });
        scanTableBlocks(page);
    }

    function init() {
        pageElement = document.getElementById("report-editor-page");
        if (!pageElement) {
            return;
        }
        bindPage(pageElement);
    }

    window.ReportLineTableColumnResize = { init };
})();
