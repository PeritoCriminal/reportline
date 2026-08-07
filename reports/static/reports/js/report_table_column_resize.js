// reportline/reports/static/reports/js/report_table_column_resize.js
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

    function getTableColumnCount(block) {
        let count = 0;

        const raw = block.dataset.tableColumnWidths || "";
        if (raw) {
            const parts = raw.split(",").map((part) => part.trim()).filter(Boolean);
            if (parts.length) {
                count = Math.max(count, parts.length);
            }
        }

        const cols = block.querySelectorAll("colgroup col");
        if (cols.length) {
            count = Math.max(count, cols.length);
        }

        const headerCount = block.querySelectorAll('[data-table-part="header"]').length;
        if (headerCount) {
            count = Math.max(count, headerCount);
        }

        const firstRow = block.querySelector("tbody tr");
        if (firstRow) {
            const bodyCount = firstRow.querySelectorAll("td").length;
            if (bodyCount) {
                count = Math.max(count, bodyCount);
            }
        }

        return count || 1;
    }

    function parseColumnWidths(block) {
        const columnCount = getTableColumnCount(block);
        const raw = block.dataset.tableColumnWidths || "";
        if (raw) {
            return normalizeColumnWidths(
                raw.split(",").map((part) => Number.parseInt(part.trim(), 10)),
                columnCount,
            );
        }

        const cols = block.querySelectorAll("colgroup col");
        if (cols.length) {
            return normalizeColumnWidths(
                Array.from(cols).map((col) => {
                    const match = (col.style.width || "").match(/(\d+)/);
                    return match ? Number.parseInt(match[1], 10) : 1;
                }),
                columnCount,
            );
        }

        return equalColumnWidths(columnCount);
    }

    function getTableElement(block) {
        return block.querySelector("table.report-editor-block-table");
    }

    function ensureColgroup(block, columnCount) {
        const table = getTableElement(block);
        if (!table || columnCount <= 0) {
            return [];
        }

        let colgroup = table.querySelector("colgroup");
        if (!colgroup) {
            colgroup = document.createElement("colgroup");
            table.insertBefore(colgroup, table.firstChild);
        }

        while (colgroup.children.length < columnCount) {
            colgroup.appendChild(document.createElement("col"));
        }
        while (colgroup.children.length > columnCount) {
            colgroup.removeChild(colgroup.lastElementChild);
        }

        return Array.from(colgroup.querySelectorAll("col"));
    }

    function syncTableCellImages(block) {
        block.querySelectorAll(".report-editor-table-cell-image").forEach((wrapper) => {
            const img = wrapper.querySelector(".report-editor-table-cell-img");
            if (!img) {
                return;
            }

            const storedWidth = Number.parseInt(wrapper.dataset.imageWidth || "0", 10);
            const storedHeight = Number.parseInt(wrapper.dataset.imageHeight || "0", 10);
            const cellWidth = wrapper.closest("td")?.clientWidth || 0;

            if (storedWidth > 0 && storedHeight > 0) {
                if (
                    wrapper.classList.contains("is-image-selected")
                    || wrapper.closest(".is-resizing")
                ) {
                    return;
                }
                const aspectRatio = storedWidth / storedHeight;
                const displayWidth = cellWidth > 0
                    ? Math.min(storedWidth, cellWidth)
                    : storedWidth;
                const displayHeight = Math.max(1, Math.round(displayWidth / aspectRatio));
                img.style.width = `${displayWidth}px`;
                img.style.height = `${displayHeight}px`;
                img.style.maxWidth = "100%";
                return;
            }

            img.style.width = "100%";
            img.style.maxWidth = "100%";
            img.style.height = "auto";
        });
    }

    function applyColumnWidths(block, widths) {
        const normalized = normalizeColumnWidths(widths, widths.length);
        block.dataset.tableColumnWidths = normalized.join(",");

        const cols = ensureColgroup(block, normalized.length);
        normalized.forEach((width, index) => {
            if (cols[index]) {
                cols[index].style.width = `${width}%`;
            }
        });

        syncTableCellImages(block);
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
        if (activeDrag && activeDrag.block === block) {
            repositionResizers(block, parseColumnWidths(block));
            return;
        }

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
        if (!block) {
            return;
        }

        const columnCount = getTableColumnCount(block);
        ensureColgroup(block, columnCount);
        syncTableCellImages(block);

        if (block.dataset.columnResizeBound === "true") {
            const columnCount = getTableColumnCount(block);
            ensureColgroup(block, columnCount);
            syncTableCellImages(block);

            const wrap = block.querySelector(".report-editor-block-table-wrap");
            const container = wrap ? wrap.querySelector(".report-editor-table-column-resizers") : null;
            const expectedHandles = Math.max(0, columnCount - 1);
            const currentHandles = container
                ? container.querySelectorAll(".report-editor-table-column-resizer").length
                : 0;

            if (currentHandles !== expectedHandles) {
                buildResizers(block);
            } else {
                repositionResizers(block, parseColumnWidths(block));
            }
            return;
        }
        block.dataset.columnResizeBound = "true";
        buildResizers(block);

        const table = getTableElement(block);
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

    function resetColumnResizeUi() {
        document.body.classList.remove("report-editor-column-resize-active");
        document.querySelectorAll(".report-editor-block-table-wrap.is-column-resizing").forEach((wrap) => {
            wrap.classList.remove("is-column-resizing");
        });
        document.querySelectorAll(".report-editor-table-column-resizer.is-dragging").forEach((handle) => {
            handle.classList.remove("is-dragging");
        });
    }

    function releaseDragPointerCapture() {
        if (!activeDrag || !activeDrag.handle) {
            return;
        }
        try {
            if (
                activeDrag.handle.hasPointerCapture
                && activeDrag.handle.hasPointerCapture(activeDrag.pointerId)
            ) {
                activeDrag.handle.releasePointerCapture(activeDrag.pointerId);
            }
        } catch (error) {
            // O handle pode ter sido removido do DOM durante o arraste.
        }
    }

    function clearDragState() {
        releaseDragPointerCapture();
        resetColumnResizeUi();
        document.removeEventListener("pointermove", moveDrag);
        document.removeEventListener("pointerup", endDrag);
        document.removeEventListener("pointercancel", endDrag);
        activeDrag = null;
    }

    function abortDrag() {
        resetColumnResizeUi();
        if (!activeDrag) {
            document.removeEventListener("pointermove", moveDrag);
            document.removeEventListener("pointerup", endDrag);
            document.removeEventListener("pointercancel", endDrag);
            return;
        }
        clearDragState();
    }

    function startDrag(event, block, handle, leftColIndex) {
        event.preventDefault();
        event.stopPropagation();

        const table = getTableElement(block);
        const wrap = block.querySelector(".report-editor-block-table-wrap");
        if (!table || !wrap) {
            return;
        }

        handle.classList.add("is-dragging");
        wrap.classList.add("is-column-resizing");
        document.body.classList.remove("report-editor-table-width-resize-active");
        document.body.classList.add("report-editor-column-resize-active");

        if (window.ReportLineTableWidthResize && window.ReportLineTableWidthResize.abortDrag) {
            window.ReportLineTableWidthResize.abortDrag();
        }
        if (window.ReportLineImageResize && window.ReportLineImageResize.abortDrag) {
            window.ReportLineImageResize.abortDrag();
        }

        activeDrag = {
            block,
            wrap,
            handle,
            leftColIndex,
            startX: event.clientX,
            startWidths: parseColumnWidths(block),
            tableWidth: wrap.getBoundingClientRect().width || table.getBoundingClientRect().width,
            pointerId: event.pointerId,
        };

        if (window.ReportLineEditor && window.ReportLineEditor.beginBlockContentRecording) {
            window.ReportLineEditor.beginBlockContentRecording(block);
        }

        document.addEventListener("pointermove", moveDrag);
        document.addEventListener("pointerup", endDrag);
        document.addEventListener("pointercancel", endDrag);
    }

    function moveDrag(event) {
        if (!activeDrag) {
            return;
        }
        if (event.pointerId !== undefined && event.pointerId !== activeDrag.pointerId) {
            return;
        }

        event.preventDefault();

        const deltaPx = event.clientX - activeDrag.startX;
        if (!activeDrag.tableWidth) {
            return;
        }
        const deltaPercent = Math.round((deltaPx / activeDrag.tableWidth) * 100);
        const nextWidths = resizeAdjacentColumns(
            activeDrag.startWidths,
            activeDrag.leftColIndex,
            deltaPercent
        );
        applyColumnWidths(activeDrag.block, nextWidths);
    }

    async function endDrag(event) {
        if (!activeDrag) {
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

    function bindGlobalDragSafetyHandlers() {
        window.addEventListener("pointerup", (event) => {
            if (activeDrag) {
                endDrag(event);
            }
        }, true);
        window.addEventListener("blur", abortDrag);
        window.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                abortDrag();
            }
        });
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
        document.body.classList.remove("report-editor-column-resize-active");
        bindGlobalDragSafetyHandlers();
        bindPage(pageElement);
    }

    window.ReportLineTableColumnResize = { init, abortDrag };
})();
