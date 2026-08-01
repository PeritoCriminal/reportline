/**
 * Redimensionamento interativo de imagens no editor via alças nos cantos.
 *
 * Atualiza dimensões de exibição no JSON do bloco (sem reprocessar o arquivo).
 */
(function () {
    "use strict";

    let maxImageSidePx = 529;
    const MIN_IMAGE_SIDE_PX = 48;

    let pageElement = null;
    let selectedBlock = null;
    let activeDrag = null;

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function getImageBlock(element) {
        return element ? element.closest(".report-editor-block[data-block-type=\"image\"]") : null;
    }

    function getAspectRatio(block) {
        const naturalWidth = Number(block.dataset.naturalWidth || block.dataset.imageWidth || 0);
        const naturalHeight = Number(block.dataset.naturalHeight || block.dataset.imageHeight || 0);
        if (naturalWidth > 0 && naturalHeight > 0) {
            return naturalWidth / naturalHeight;
        }
        return 1;
    }

    function getBounds(block) {
        const naturalWidth = Number(block.dataset.naturalWidth || block.dataset.imageWidth || 0);
        const naturalHeight = Number(block.dataset.naturalHeight || block.dataset.imageHeight || 0);
        let maxWidth = naturalWidth;
        let maxHeight = naturalHeight;

        if (maxWidth <= 0 || maxHeight <= 0) {
            maxWidth = maxImageSidePx;
            maxHeight = maxImageSidePx;
        }

        const longest = Math.max(maxWidth, maxHeight);
        if (longest > maxImageSidePx) {
            const scale = maxImageSidePx / longest;
            maxWidth = Math.round(maxWidth * scale);
            maxHeight = Math.round(maxHeight * scale);
        }

        const aspectRatio = maxWidth / maxHeight;
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

    function getCurrentSize(block) {
        const img = block.querySelector(".report-editor-block-image-img");
        if (!img) {
            return { width: 0, height: 0 };
        }

        const width = Number.parseInt(block.dataset.imageWidth || img.getAttribute("width") || "0", 10);
        const height = Number.parseInt(block.dataset.imageHeight || img.getAttribute("height") || "0", 10);
        if (width > 0 && height > 0) {
            return { width, height };
        }

        return {
            width: img.clientWidth || img.naturalWidth || 0,
            height: img.clientHeight || img.naturalHeight || 0,
        };
    }

    function applyDisplaySize(block, width, height) {
        const img = block.querySelector(".report-editor-block-image-img");
        if (!img) {
            return;
        }

        block.dataset.imageWidth = String(width);
        block.dataset.imageHeight = String(height);
        img.setAttribute("width", String(width));
        img.setAttribute("height", String(height));
        img.style.width = `${width}px`;
        img.style.height = `${height}px`;
    }

    function normalizeSize(block, width, height) {
        const aspectRatio = getAspectRatio(block);
        const bounds = getBounds(block);
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

    function syncNaturalDimensions(block, img) {
        if (!img.naturalWidth || !img.naturalHeight) {
            return;
        }

        block.dataset.naturalWidth = String(img.naturalWidth);
        block.dataset.naturalHeight = String(img.naturalHeight);

        const storedWidth = Number.parseInt(block.dataset.imageWidth || "0", 10);
        const storedHeight = Number.parseInt(block.dataset.imageHeight || "0", 10);
        if (storedWidth > 0 && storedHeight > 0) {
            applyDisplaySize(block, storedWidth, storedHeight);
            return;
        }

        const normalized = normalizeSize(block, img.naturalWidth, img.naturalHeight);
        applyDisplaySize(block, normalized.width, normalized.height);
    }

    function showHandles(block) {
        const handles = block.querySelector(".report-editor-image-resize-handles");
        if (handles) {
            handles.hidden = false;
        }
    }

    function hideHandles(block) {
        const handles = block.querySelector(".report-editor-image-resize-handles");
        if (handles) {
            handles.hidden = true;
        }
    }

    function selectImageBlock(block) {
        if (selectedBlock === block) {
            return;
        }
        deselectImageBlock();
        selectedBlock = block;
        block.classList.add("is-image-selected");
        showHandles(block);
    }

    function deselectImageBlock() {
        if (!selectedBlock) {
            return;
        }
        selectedBlock.classList.remove("is-image-selected");
        hideHandles(selectedBlock);
        selectedBlock = null;
    }

    function getAnchorPoint(block, handleName) {
        const frame = block.querySelector(".report-editor-block-image-frame");
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

    function sizeFromPointer(block, handleName, pointerX, pointerY, aspectRatio) {
        const anchor = getAnchorPoint(block, handleName);
        let width = Math.abs(pointerX - anchor.x);
        let height = Math.abs(pointerY - anchor.y);

        if (width / height > aspectRatio) {
            width = height * aspectRatio;
        } else {
            height = width / aspectRatio;
        }

        return normalizeSize(block, width, height);
    }

    function startDrag(event, block, handleName) {
        event.preventDefault();
        event.stopPropagation();

        selectImageBlock(block);

        const aspectRatio = getAspectRatio(block);
        const imageWrap = block.querySelector(".report-editor-block-image");
        if (imageWrap) {
            imageWrap.classList.add("is-resizing");
        }

        activeDrag = {
            block,
            handleName,
            aspectRatio,
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
            activeDrag.block,
            activeDrag.handleName,
            event.clientX,
            event.clientY,
            activeDrag.aspectRatio
        );
        applyDisplaySize(activeDrag.block, nextSize.width, nextSize.height);
    }

    async function endDrag(event) {
        if (!activeDrag || event.pointerId !== activeDrag.pointerId) {
            return;
        }

        const block = activeDrag.block;
        const imageWrap = block.querySelector(".report-editor-block-image");
        if (imageWrap) {
            imageWrap.classList.remove("is-resizing");
        }

        clearDragListeners();
        activeDrag = null;

        if (window.ReportLineEditor && window.ReportLineEditor.saveBlock) {
            try {
                await window.ReportLineEditor.saveBlock(block);
            } catch (error) {
                console.error(error);
            }
        }
    }

    function prepareImageBlock(block) {
        const img = block.querySelector(".report-editor-block-image-img");
        if (!img || img.dataset.resizeBound === "true") {
            if (img && img.complete) {
                syncNaturalDimensions(block, img);
            }
            return;
        }

        img.dataset.resizeBound = "true";
        const onReady = () => syncNaturalDimensions(block, img);
        if (img.complete) {
            onReady();
        } else {
            img.addEventListener("load", onReady, { once: true });
        }
    }

    function scanImageBlocks(root) {
        root.querySelectorAll(".report-editor-block[data-block-type=\"image\"]").forEach(prepareImageBlock);
    }

    function bindPage(page) {
        page.addEventListener("click", (event) => {
            const handle = event.target.closest(".report-editor-image-handle");
            if (handle) {
                return;
            }

            const block = getImageBlock(event.target);
            if (block && event.target.closest(".report-editor-block-image-img")) {
                selectImageBlock(block);
                return;
            }

            if (!event.target.closest(".report-editor-block[data-block-type=\"image\"]")) {
                deselectImageBlock();
            }
        });

        page.addEventListener("pointerdown", (event) => {
            const handle = event.target.closest(".report-editor-image-handle");
            if (!handle) {
                return;
            }

            const block = getImageBlock(handle);
            if (!block) {
                return;
            }

            startDrag(event, block, handle.dataset.handle || "se");
        });

        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (!(node instanceof Element)) {
                        return;
                    }
                    if (node.matches(".report-editor-block[data-block-type=\"image\"]")) {
                        prepareImageBlock(node);
                    } else {
                        scanImageBlocks(node);
                    }
                });
            });
        });

        observer.observe(page, { childList: true, subtree: true });
        scanImageBlocks(page);
    }

    function init(options) {
        if (options && options.maxSidePx) {
            maxImageSidePx = options.maxSidePx;
        }
        pageElement = document.getElementById("report-editor-page");
        if (!pageElement) {
            return;
        }
        bindPage(pageElement);
    }

    window.ReportLineImageResize = { init };
})();
