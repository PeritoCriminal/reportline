// reportline/reports/static/reports/js/report_image_options.js
/**
 * Menu de opções da imagem selecionada no editor (alinhamento e legenda).
 */
(function () {
    "use strict";

    let imageOptionsToggle = null;
    let imageToolbarGroup = null;
    let editorPage = null;
    let lastImageTarget = null;

    function resolveImageSelectionContext() {
        if (window.ReportLineEditor && window.ReportLineEditor.resolveImageSelectionContext) {
            return window.ReportLineEditor.resolveImageSelectionContext();
        }
        return null;
    }

    function clearImageSelectionContext() {
        lastImageTarget = null;
        if (window.ReportLineEditor && window.ReportLineEditor.clearImageSelectionContext) {
            window.ReportLineEditor.clearImageSelectionContext();
        }
        if (window.ReportLineEditor && window.ReportLineEditor.syncAllAddCaptionControls) {
            window.ReportLineEditor.syncAllAddCaptionControls();
        }
    }

    function resolveImageBlockFromTarget(target) {
        if (!target || target.type !== "block" || !target.root) {
            return null;
        }
        return target.root.closest('.report-editor-block[data-block-type="image"]') || target.root;
    }

    function imageHasCaption(imageBlock) {
        if (window.ReportLineEditor && window.ReportLineEditor.imageHasCaption) {
            return window.ReportLineEditor.imageHasCaption(imageBlock);
        }
        const next = imageBlock && imageBlock.nextElementSibling;
        return Boolean(next && next.dataset.isCaption === "true");
    }

    function isImageToolbarTarget(target) {
        return Boolean(
            target
            && target.closest
            && imageToolbarGroup
            && imageToolbarGroup.contains(target)
        );
    }

    function isImageMenuTarget(target) {
        return Boolean(
            target
            && target.closest
            && target.closest(".report-editor-toolbar-image-menu")
        );
    }

    function isImageDropdownOpen() {
        return Boolean(
            imageOptionsToggle
            && imageOptionsToggle.getAttribute("aria-expanded") === "true"
        );
    }

    function getImageAlign(target) {
        if (!target || !target.root) {
            return "center";
        }

        const storedAlign = target.root.dataset.textAlign || "center";
        return ["left", "center", "right"].includes(storedAlign) ? storedAlign : "center";
    }

    function updateImageAlignMenuState(target) {
        const activeAlign = getImageAlign(target);
        document.querySelectorAll("[data-report-image-align]").forEach((button) => {
            const isActive = button.dataset.reportImageAlign === activeAlign;
            button.classList.toggle("active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
    }

    function updateAddCaptionMenuState(target) {
        const imageBlock = resolveImageBlockFromTarget(target);
        const canAdd = Boolean(imageBlock && !imageHasCaption(imageBlock));
        document.querySelectorAll("[data-report-image-add-caption-item]").forEach((item) => {
            item.classList.toggle("d-none", !canAdd);
        });
    }

    function setOptionsToggleState(toggle, enabled) {
        if (!toggle) {
            return;
        }

        toggle.disabled = !enabled;
        if (!enabled) {
            closeImageDropdown();
        }
    }

    function updateToolbarVisibility(target) {
        const imageBlock = resolveImageBlockFromTarget(target);
        const hasSelection = Boolean(imageBlock);

        setOptionsToggleState(imageOptionsToggle, hasSelection);

        if (hasSelection) {
            updateImageAlignMenuState(target);
            updateAddCaptionMenuState(target);
        } else {
            updateAddCaptionMenuState(null);
        }

        if (window.ReportLineEditor && window.ReportLineEditor.syncAllAddCaptionControls) {
            window.ReportLineEditor.syncAllAddCaptionControls();
        }
    }

    function closeImageDropdown() {
        if (!imageOptionsToggle || !window.bootstrap) {
            return;
        }
        window.bootstrap.Dropdown.getOrCreateInstance(imageOptionsToggle).hide();
    }

    async function addCaptionToSelectedImage(target) {
        const imageBlock = resolveImageBlockFromTarget(target);
        if (
            !imageBlock
            || imageHasCaption(imageBlock)
            || !window.ReportLineEditor
            || !window.ReportLineEditor.ensureCaptionParagraphAfterImage
        ) {
            return;
        }

        await window.ReportLineEditor.ensureCaptionParagraphAfterImage(imageBlock);
        updateAddCaptionMenuState(target);
        closeImageDropdown();
    }

    function refreshToolbarFromSelection(target) {
        if (
            isImageToolbarTarget(document.activeElement)
            || isImageMenuTarget(document.activeElement)
            || isImageDropdownOpen()
        ) {
            updateToolbarVisibility(target || lastImageTarget || resolveImageSelectionContext());
            return;
        }

        if (!target) {
            clearImageSelectionContext();
        }
        updateToolbarVisibility(target);
    }

    function init() {
        imageToolbarGroup = document.querySelector(".report-editor-toolbar-image-group");
        imageOptionsToggle = document.querySelector("[data-report-image-options-toggle]");
        editorPage = document.getElementById("report-editor-page");

        if (!imageOptionsToggle) {
            return;
        }

        document.querySelectorAll("[data-report-image-align]").forEach((button) => {
            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
                event.stopPropagation();
            });
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                const align = button.dataset.reportImageAlign;
                const target = lastImageTarget || resolveImageSelectionContext();
                if (
                    !target
                    || !window.ReportLineEditor
                    || !window.ReportLineEditor.setImageAlign
                ) {
                    return;
                }

                window.ReportLineEditor.setImageAlign(align, target)
                    .then(() => {
                        updateImageAlignMenuState(target);
                        closeImageDropdown();
                    })
                    .catch(console.error);
            });
        });

        document.querySelectorAll("[data-report-image-add-caption]").forEach((button) => {
            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
                event.stopPropagation();
            });
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                const target = lastImageTarget || resolveImageSelectionContext();
                addCaptionToSelectedImage(target).catch(console.error);
            });
        });

        if (editorPage) {
            editorPage.addEventListener("click", (event) => {
                const inlineButton = event.target.closest("[data-report-image-add-caption-inline]");
                if (!inlineButton) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                const imageBlock = inlineButton.closest('.report-editor-block[data-block-type="image"]');
                if (!imageBlock) {
                    return;
                }

                addCaptionToSelectedImage({ type: "block", root: imageBlock }).catch(console.error);
            });
        }

        imageOptionsToggle.addEventListener("mousedown", (event) => {
            event.stopPropagation();
            updateToolbarVisibility(lastImageTarget || resolveImageSelectionContext());
        });

        imageOptionsToggle.addEventListener("show.bs.dropdown", () => {
            updateToolbarVisibility(lastImageTarget || resolveImageSelectionContext());
        });

        imageOptionsToggle.addEventListener("hidden.bs.dropdown", () => {
            refreshToolbarFromSelection(lastImageTarget || resolveImageSelectionContext());
        });

        document.addEventListener("reportline:image-selection-changed", (event) => {
            lastImageTarget = event.detail ? event.detail.target : null;
            if (lastImageTarget && window.ReportLineEditor && window.ReportLineEditor.rememberImageSelection) {
                window.ReportLineEditor.rememberImageSelection(lastImageTarget);
            }
            refreshToolbarFromSelection(lastImageTarget);
        });
    }

    window.ReportLineImageOptions = { init };
})();
