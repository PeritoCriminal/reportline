/**
 * Redimensionamento interativo de imagens no editor via alças nos cantos.
 *
 * Suporta blocos de imagem fora de tabela e imagens dentro de células.
 * Atualiza dimensões de exibição no JSON (sem reprocessar o arquivo).
 */
(function () {
    "use strict";

    let maxImageSidePx = 529;
    let headerLogoInitialHeightPx = 113;
    const MIN_IMAGE_SIDE_PX = 48;

    let pageElement = null;
    let selectedTarget = null;
    let activeDrag = null;

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function resolveResizeTarget(element) {
        if (!element) {
            return null;
        }

        const block = element.closest(".report-editor-block[data-block-type=\"image\"]");
        if (block) {
            return {
                type: "block",
                root: block,
                frameSelector: ".report-editor-block-image-frame",
                imgSelector: ".report-editor-block-image-img",
                resizeWrapSelector: ".report-editor-block-image",
            };
        }

        const cellImage = element.closest(".report-editor-table-cell-image");
        if (cellImage) {
            return {
                type: "table-cell",
                root: cellImage,
                frameSelector: ".report-editor-table-cell-image-frame",
                imgSelector: ".report-editor-table-cell-img",
                resizeWrapSelector: ".report-editor-table-cell-image",
                tableBlock: cellImage.closest(".report-editor-block[data-block-type=\"table\"]"),
            };
        }

        const headerLogo = element.closest(".report-page-header-logo-slot.has-image");
        if (headerLogo) {
            return {
                type: "page-header-logo",
                root: headerLogo,
                frameSelector: ".report-page-header-logo-frame",
                imgSelector: ".report-page-header-logo-img",
                resizeWrapSelector: ".report-page-header-logo-frame",
            };
        }

        return null;
    }

    function getNaturalDimensions(target) {
        const root = target.root;
        let width = Number.parseInt(root.dataset.naturalWidth || "0", 10);
        let height = Number.parseInt(root.dataset.naturalHeight || "0", 10);

        if (width > 0 && height > 0) {
            return { width, height };
        }

        const img = root.querySelector(target.imgSelector);
        if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
            root.dataset.naturalWidth = String(img.naturalWidth);
            root.dataset.naturalHeight = String(img.naturalHeight);
            return { width: img.naturalWidth, height: img.naturalHeight };
        }

        return { width: 0, height: 0 };
    }

    function getAspectRatio(target) {
        const { width, height } = getNaturalDimensions(target);
        if (width > 0 && height > 0) {
            return width / height;
        }

        const current = getCurrentSize(target);
        if (current.width > 0 && current.height > 0) {
            return current.width / current.height;
        }

        return 1;
    }

    function getCellMaxWidth(target) {
        const container = target.root.closest(".report-page-header-cell, td");
        if (target.type === "page-header-logo" && container) {
            const row = container.closest(".report-page-header-row");
            if (row) {
                const rowWidth = row.clientWidth;
                const textCell = row.querySelector(".report-page-header-cell--text");
                const textWidth = textCell ? textCell.clientWidth : 0;
                const reserved = Math.max(0, rowWidth - textWidth);
                return Math.max(MIN_IMAGE_SIDE_PX, reserved || container.clientWidth);
            }
        }

        const td = target.root.closest("td");
        if (!td) {
            return maxImageSidePx;
        }
        return Math.max(MIN_IMAGE_SIDE_PX, td.clientWidth);
    }

    function getBounds(target) {
        const { width: naturalWidth, height: naturalHeight } = getNaturalDimensions(target);
        let maxWidth = naturalWidth;
        let maxHeight = naturalHeight;

        if (maxWidth <= 0 || maxHeight <= 0) {
            const current = getCurrentSize(target);
            maxWidth = current.width || maxImageSidePx;
            maxHeight = current.height || maxImageSidePx;
        }

        const longest = Math.max(maxWidth, maxHeight);
        if (longest > maxImageSidePx) {
            const scale = maxImageSidePx / longest;
            maxWidth = Math.round(maxWidth * scale);
            maxHeight = Math.round(maxHeight * scale);
        }

        if (target.type === "table-cell") {
            maxWidth = Math.min(maxWidth, getCellMaxWidth(target));
            maxHeight = Math.round(
                maxWidth * (maxHeight / Math.max(1, naturalHeight || maxHeight))
            );
        }

        if (target.type === "page-header-logo") {
            maxWidth = Math.min(maxWidth, getCellMaxWidth(target));
            maxHeight = Math.round(
                maxWidth * (maxHeight / Math.max(1, naturalHeight || maxHeight))
            );
        }

        const aspectRatio = maxWidth / Math.max(1, maxHeight);
        const minWidth = aspectRatio >= 1
            ? MIN_IMAGE_SIDE_PX * aspectRatio
            : MIN_IMAGE_SIDE_PX;
        const minHeight = aspectRatio >= 1
            ? MIN_IMAGE_SIDE_PX
            : MIN_IMAGE_SIDE_PX / aspectRatio;

        return {
            maxWidth,
            maxHeight,
            minWidth: Math.min(minWidth, maxWidth),
            minHeight: Math.min(minHeight, maxHeight),
        };
    }

    function getCurrentSize(target) {
        const img = target.root.querySelector(target.imgSelector);
        if (!img) {
            return { width: 0, height: 0 };
        }

        const width = Number.parseInt(target.root.dataset.imageWidth || img.getAttribute("width") || "0", 10);
        const height = Number.parseInt(target.root.dataset.imageHeight || img.getAttribute("height") || "0", 10);
        if (width > 0 && height > 0) {
            return { width, height };
        }

        return {
            width: img.clientWidth || img.naturalWidth || 0,
            height: img.clientHeight || img.naturalHeight || 0,
        };
    }

    function applyDisplaySize(target, width, height) {
        const root = target.root;
        const img = root.querySelector(target.imgSelector);
        if (!img) {
            return;
        }

        root.dataset.imageWidth = String(width);
        root.dataset.imageHeight = String(height);
        img.setAttribute("width", String(width));
        img.setAttribute("height", String(height));
        img.style.width = `${width}px`;
        img.style.height = `${height}px`;

        if (target.type === "block") {
            syncCaptionLayout(target.root);
        }
    }

    function normalizeImageAlign(align) {
        return ["left", "center", "right"].includes(align) ? align : "center";
    }

    function syncCaptionLayout(imageBlock) {
        const captionBlock = imageBlock.nextElementSibling;
        if (!captionBlock || captionBlock.dataset.isCaption !== "true") {
            return;
        }

        const align = normalizeImageAlign(imageBlock.dataset.textAlign || "center");
        captionBlock.dataset.textAlign = align;

        const frame = imageBlock.querySelector(".report-editor-block-image-frame");
        const width = frame ? frame.offsetWidth : 0;
        if (width > 0) {
            captionBlock.style.width = `${width}px`;
        }

        if (align === "left") {
            captionBlock.style.marginLeft = "0";
            captionBlock.style.marginRight = "auto";
        } else if (align === "right") {
            captionBlock.style.marginLeft = "auto";
            captionBlock.style.marginRight = "0";
        } else {
            captionBlock.style.marginLeft = "auto";
            captionBlock.style.marginRight = "auto";
        }
    }

    function syncCaptionWidth(imageBlock) {
        syncCaptionLayout(imageBlock);
    }

    function notifySelectionChanged() {
        document.dispatchEvent(new CustomEvent("reportline:image-selection-changed", {
            detail: { target: selectedTarget },
        }));
    }

    function normalizeSize(target, width, height) {
        const aspectRatio = getAspectRatio(target);
        const bounds = getBounds(target);
        let nextWidth = width;
        let nextHeight = height;

        if (nextWidth / nextHeight > aspectRatio) {
            nextWidth = nextHeight * aspectRatio;
        } else {
            nextHeight = nextWidth / aspectRatio;
        }

        if (nextWidth > bounds.maxWidth) {
            nextWidth = bounds.maxWidth;
            nextHeight = nextWidth / aspectRatio;
        }
        if (nextHeight > bounds.maxHeight) {
            nextHeight = bounds.maxHeight;
            nextWidth = nextHeight * aspectRatio;
        }
        if (nextWidth < bounds.minWidth) {
            nextWidth = bounds.minWidth;
            nextHeight = nextWidth / aspectRatio;
        }
        if (nextHeight < bounds.minHeight) {
            nextHeight = bounds.minHeight;
            nextWidth = nextHeight * aspectRatio;
        }

        return {
            width: Math.round(nextWidth),
            height: Math.round(nextHeight),
        };
    }

    function getInitialHeaderLogoDisplaySize(target, naturalWidth, naturalHeight) {
        const height = headerLogoInitialHeightPx;
        let width = height;
        if (naturalWidth > 0 && naturalHeight > 0) {
            width = Math.round(height * (naturalWidth / naturalHeight));
        }
        return normalizeSize(target, width, height);
    }

    function syncNaturalDimensions(target, img) {
        if (!img.naturalWidth || !img.naturalHeight) {
            return;
        }

        if (!target.root.dataset.naturalWidth || !target.root.dataset.naturalHeight) {
            target.root.dataset.naturalWidth = String(img.naturalWidth);
            target.root.dataset.naturalHeight = String(img.naturalHeight);
        }

        const storedWidth = Number.parseInt(target.root.dataset.imageWidth || "0", 10);
        const storedHeight = Number.parseInt(target.root.dataset.imageHeight || "0", 10);
        if (storedWidth > 0 && storedHeight > 0) {
            applyDisplaySize(target, storedWidth, storedHeight);
            return;
        }

        if (target.type === "page-header-logo") {
            const normalized = getInitialHeaderLogoDisplaySize(
                target,
                img.naturalWidth,
                img.naturalHeight
            );
            applyDisplaySize(target, normalized.width, normalized.height);
            return;
        }

        const normalized = normalizeSize(target, img.naturalWidth, img.naturalHeight);
        applyDisplaySize(target, normalized.width, normalized.height);
    }

    function syncCaptionWidth(imageBlock) {
        syncCaptionLayout(imageBlock);
    }

    function scanCaptionWidths(root) {
        root.querySelectorAll(".report-editor-block[data-block-type=\"image\"]").forEach((imageBlock) => {
            if (
                window.ReportLineEditor
                && window.ReportLineEditor.applyImageBlockAlignVisual
            ) {
                window.ReportLineEditor.applyImageBlockAlignVisual(
                    imageBlock,
                    imageBlock.dataset.textAlign || "center"
                );
            }
            syncCaptionLayout(imageBlock);
        });
        root.querySelectorAll(".report-editor-table-cell-image").forEach((cellImage) => {
            if (
                window.ReportLineEditor
                && window.ReportLineEditor.applyTableCellImageAlignVisual
            ) {
                window.ReportLineEditor.applyTableCellImageAlignVisual(
                    cellImage,
                    cellImage.dataset.textAlign || "center"
                );
            }
        });
    }

    function showHandles(target) {
        const handles = target.root.querySelector(".report-editor-image-resize-handles");
        if (handles) {
            handles.hidden = false;
        }
    }

    function hideHandles(target) {
        const handles = target.root.querySelector(".report-editor-image-resize-handles");
        if (handles) {
            handles.hidden = true;
        }
    }

    function selectTarget(target) {
        if (selectedTarget && selectedTarget.root === target.root) {
            return;
        }
        deselectTarget();
        selectedTarget = target;
        target.root.classList.add("is-image-selected");
        if (!target.root.hasAttribute("tabindex")) {
            target.root.tabIndex = -1;
        }
        target.root.focus({ preventScroll: true });
        showHandles(target);
        notifySelectionChanged();
    }

    function deselectTarget() {
        if (!selectedTarget) {
            return;
        }
        selectedTarget.root.classList.remove("is-image-selected");
        hideHandles(selectedTarget);
        selectedTarget = null;
        notifySelectionChanged();
    }

    function getAnchorPoint(target, handleName) {
        const frame = target.root.querySelector(target.frameSelector);
        if (!frame) {
            return { x: 0, y: 0 };
        }

        const rect = frame.getBoundingClientRect();
        switch (handleName) {
            case "nw":
                return { x: rect.right, y: rect.bottom };
            case "ne":
                return { x: rect.left, y: rect.bottom };
            case "sw":
                return { x: rect.right, y: rect.top };
            case "se":
            default:
                return { x: rect.left, y: rect.top };
        }
    }

    function sizeFromPointer(target, handleName, pointerX, pointerY, aspectRatio) {
        const anchor = getAnchorPoint(target, handleName);
        let width = Math.abs(pointerX - anchor.x);
        let height = Math.abs(pointerY - anchor.y);

        if (width / height > aspectRatio) {
            width = height * aspectRatio;
        } else {
            height = width / aspectRatio;
        }

        return normalizeSize(target, width, height);
    }

    function startDrag(event, target, handleName) {
        event.preventDefault();
        event.stopPropagation();

        selectTarget(target);

        const aspectRatio = getAspectRatio(target);
        const resizeWrap = target.root.querySelector(target.resizeWrapSelector) || target.root;
        resizeWrap.classList.add("is-resizing");

        activeDrag = {
            target,
            handleName,
            aspectRatio,
            resizeWrap,
            pointerId: event.pointerId,
        };

        document.addEventListener("pointermove", moveDrag);
        document.addEventListener("pointerup", endDrag);
        document.addEventListener("pointercancel", endDrag);
    }

    function clearDragListeners() {
        document.removeEventListener("pointermove", moveDrag);
        document.removeEventListener("pointerup", endDrag);
        document.removeEventListener("pointercancel", endDrag);
    }

    function moveDrag(event) {
        if (!activeDrag || event.pointerId !== activeDrag.pointerId) {
            return;
        }

        const nextSize = sizeFromPointer(
            activeDrag.target,
            activeDrag.handleName,
            event.clientX,
            event.clientY,
            activeDrag.aspectRatio
        );
        applyDisplaySize(activeDrag.target, nextSize.width, nextSize.height);
    }

    async function endDrag(event) {
        if (!activeDrag || event.pointerId !== activeDrag.pointerId) {
            return;
        }

        const { target, resizeWrap } = activeDrag;
        resizeWrap.classList.remove("is-resizing");

        clearDragListeners();
        activeDrag = null;

        if (target.type === "page-header-logo") {
            const cellIndex = target.root.dataset.cellIndex;
            if (window.ReportLinePageHeader && window.ReportLinePageHeader.flushHeaderSave) {
                try {
                    await window.ReportLinePageHeader.flushHeaderSave();
                } catch (error) {
                    console.error(error);
                }
            }
            if (cellIndex !== undefined) {
                const slot = document.querySelector(
                    `[data-report-page-header-logo][data-cell-index="${cellIndex}"]`
                );
                if (slot) {
                    selectTargetElement(slot);
                }
            }
            return;
        }

        if (!window.ReportLineEditor || !window.ReportLineEditor.saveBlock) {
            return;
        }

        const blockToSave = target.type === "table-cell"
            ? target.tableBlock
            : target.root;

        if (!blockToSave) {
            return;
        }

        try {
            await window.ReportLineEditor.saveBlock(blockToSave);
        } catch (error) {
            console.error(error);
        }
    }

    function prepareResizeTarget(target) {
        const img = target.root.querySelector(target.imgSelector);
        if (!img) {
            return;
        }

        if (img.dataset.resizeBound === "true") {
            if (img.complete) {
                syncNaturalDimensions(target, img);
            }
            return;
        }

        img.dataset.resizeBound = "true";
        const onReady = () => syncNaturalDimensions(target, img);
        if (img.complete) {
            onReady();
        } else {
            img.addEventListener("load", onReady, { once: true });
        }
    }

    function scanResizeTargets(root) {
        root.querySelectorAll(".report-editor-block[data-block-type=\"image\"]").forEach((element) => {
            prepareResizeTarget(resolveResizeTarget(element));
        });
        root.querySelectorAll(".report-editor-table-cell-image").forEach((element) => {
            prepareResizeTarget(resolveResizeTarget(element));
        });
        root.querySelectorAll(".report-page-header-logo-slot.has-image").forEach((element) => {
            prepareResizeTarget(resolveResizeTarget(element));
        });
        scanCaptionWidths(root);
    }

    function selectTargetElement(element) {
        const target = resolveResizeTarget(element);
        if (target) {
            selectTarget(target);
        }
    }

    function bindPage(page) {
        page.addEventListener("click", (event) => {
            if (event.target.closest(".report-editor-image-handle")) {
                return;
            }

            const target = resolveResizeTarget(event.target);
            if (
                target
                && (
                    event.target.closest(target.imgSelector)
                    || event.target.closest(target.frameSelector)
                )
            ) {
                selectTarget(target);
                return;
            }

            if (!resolveResizeTarget(event.target)) {
                deselectTarget();
            }
        });

        page.addEventListener("pointerdown", (event) => {
            const handle = event.target.closest(".report-editor-image-handle");
            if (!handle) {
                return;
            }

            const target = resolveResizeTarget(handle);
            if (!target) {
                return;
            }

            startDrag(event, target, handle.dataset.handle || "se");
        });

        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (!(node instanceof Element)) {
                        return;
                    }
                    scanResizeTargets(node);
                });
            });
        });

        observer.observe(page, { childList: true, subtree: true });
        scanResizeTargets(page);
    }

    function init(options) {
        if (options && options.maxSidePx) {
            maxImageSidePx = options.maxSidePx;
        }
        if (options && options.headerLogoInitialHeightPx) {
            headerLogoInitialHeightPx = options.headerLogoInitialHeightPx;
        }
        pageElement = document.getElementById("report-editor-page");
        if (!pageElement) {
            return;
        }
        bindPage(pageElement);
    }

    window.ReportLineImageResize = {
        init,
        syncCaptionWidth,
        syncCaptionLayout,
        getSelectedTarget: () => selectedTarget,
        deselectTarget,
        selectTargetElement,
    };
})();
