/**
 * Redimensionamento da largura total da tabela pelas bordas externas.
 *
 * Mantém independente o redimensionamento de colunas internas
 * (report_table_column_resize.js).
 */
(function () {
    "use strict";

    const MIN_DISPLAY_WIDTH = 20;
    const MAX_DISPLAY_WIDTH = 100;
    const DEFAULT_DISPLAY_WIDTH = 100;

    let activeDrag = null;

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function getTableBlock(element) {
        return element ? element.closest(".report-editor-block[data-block-type=\"table\"]") : null;
    }

    function parseDisplayWidth(block) {
        const raw = Number.parseInt(block.dataset.tableDisplayWidth || "0", 10);
        if (raw >= MIN_DISPLAY_WIDTH && raw <= MAX_DISPLAY_WIDTH) {
            return raw;
        }
        return DEFAULT_DISPLAY_WIDTH;
    }

    function getWrapMarginsForAlign(align) {
        if (align === "center" || align === "justify") {
            return { marginLeft: "auto", marginRight: "auto" };
        }
        if (align === "right") {
            return { marginLeft: "auto", marginRight: "0" };
        }
        return { marginLeft: "0", marginRight: "auto" };
    }

    function getAnchorMarginsForEdge(edge, align) {
        if (edge === "left") {
            return getWrapMarginsForAlign("right");
        }
        return getWrapMarginsForAlign(align === "right" ? "right" : "left");
    }

    function applyDisplayWidth(block, widthPercent, options = {}) {
        const wrap = block.querySelector(".report-editor-block-table-wrap");
        if (!wrap) {
            return widthPercent;
        }

        const normalized = clamp(
            Math.round(widthPercent),
            MIN_DISPLAY_WIDTH,
            MAX_DISPLAY_WIDTH
        );
        const align = block.dataset.textAlign || "left";
        const edge = options.anchorEdge || null;
        const margins = edge
            ? getAnchorMarginsForEdge(edge, align)
            : getWrapMarginsForAlign(align);

        block.dataset.tableDisplayWidth = String(normalized);
        wrap.style.width = `${normalized}%`;
        wrap.style.marginLeft = margins.marginLeft;
        wrap.style.marginRight = margins.marginRight;
        return normalized;
    }

    function prepareTableBlock(block) {
        if (!block || block.dataset.tableWidthBound === "true") {
            applyDisplayWidth(block, parseDisplayWidth(block));
            return;
        }
        block.dataset.tableWidthBound = "true";
        applyDisplayWidth(block, parseDisplayWidth(block));
    }

    function scanTableBlocks(root) {
        root.querySelectorAll(".report-editor-block[data-block-type=\"table\"]").forEach(prepareTableBlock);
    }

    function clearDragState() {
        document.body.classList.remove("report-editor-table-width-resize-active");
        if (activeDrag && activeDrag.wrap) {
            activeDrag.wrap.classList.remove("is-table-width-resizing");
        }
        if (activeDrag && activeDrag.handle) {
            activeDrag.handle.classList.remove("is-dragging");
        }
        document.removeEventListener("pointermove", moveDrag);
        document.removeEventListener("pointerup", endDrag);
        document.removeEventListener("pointercancel", endDrag);
        activeDrag = null;
    }

    function startDrag(event, block, handle, edge) {
        event.preventDefault();
        event.stopPropagation();

        const wrap = block.querySelector(".report-editor-block-table-wrap");
        if (!wrap) {
            return;
        }

        handle.classList.add("is-dragging");
        wrap.classList.add("is-table-width-resizing");
        document.body.classList.add("report-editor-table-width-resize-active");

        activeDrag = {
            block,
            wrap,
            handle,
            edge,
            startX: event.clientX,
            startWidth: parseDisplayWidth(block),
            containerWidth: block.getBoundingClientRect().width,
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
        const deltaPercent = Math.round((deltaPx / activeDrag.containerWidth) * 100);
        let nextWidth = activeDrag.startWidth;

        if (activeDrag.edge === "right") {
            nextWidth = activeDrag.startWidth + deltaPercent;
        } else {
            nextWidth = activeDrag.startWidth - deltaPercent;
        }

        applyDisplayWidth(activeDrag.block, nextWidth, { anchorEdge: activeDrag.edge });
    }

    async function endDrag(event) {
        if (!activeDrag || event.pointerId !== activeDrag.pointerId) {
            return;
        }

        const block = activeDrag.block;
        clearDragState();
        applyDisplayWidth(block, parseDisplayWidth(block));

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
            const handle = event.target.closest(".report-editor-table-width-resizer");
            if (!handle) {
                return;
            }

            const block = getTableBlock(handle);
            if (!block) {
                return;
            }

            const edge = handle.dataset.tableWidthEdge;
            if (edge !== "left" && edge !== "right") {
                return;
            }

            startDrag(event, block, handle, edge);
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
        const pageElement = document.getElementById("report-editor-page");
        if (!pageElement) {
            return;
        }
        bindPage(pageElement);
    }

    function refreshTableDisplayLayout(block) {
        if (!block || block.dataset.blockType !== "table") {
            return;
        }
        applyDisplayWidth(block, parseDisplayWidth(block));
    }

    window.ReportLineTableWidthResize = {
        init,
        applyDisplayWidth,
        refreshTableDisplayLayout,
    };
})();
