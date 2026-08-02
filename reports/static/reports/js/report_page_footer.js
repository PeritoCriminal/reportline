/**
 * Rodapé de página do relatório (modelos, imagens, texto e numeração).
 */
(function () {
    "use strict";

    const DEBOUNCE_MS = 1500;
    const FOOTER_ALIGN_VALUES = new Set(["left", "center", "right"]);

    let updateUrl = "";
    let uploadUrl = "";
    let modal = null;
    let modalElement = null;
    let footerRoot = null;
    let pendingLogoCellIndex = null;
    let fileInput = null;
    let saveTimer = null;
    let isEditing = false;
    let lastFocusedTextField = null;

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function getInlineText() {
        return window.ReportLineInlineText || null;
    }

    function getFooterSurface(root) {
        return root ? root.querySelector("[data-report-page-footer-surface]") : null;
    }

    function collectFooterCells(root) {
        const cells = [];
        root.querySelectorAll(".report-page-footer-row").forEach((row) => {
            row.querySelectorAll(".report-page-footer-cell").forEach((cellElement) => {
                const logoButton = cellElement.querySelector("[data-report-page-footer-logo]");
                if (logoButton) {
                    cells.push({
                        type: "logo",
                        logo_slot: logoButton.dataset.logoSlot || "primary",
                        file: logoButton.dataset.file || "",
                        image_id: logoButton.dataset.imageId || "",
                        width: Number.parseInt(logoButton.dataset.imageWidth || "0", 10) || 0,
                        height: Number.parseInt(logoButton.dataset.imageHeight || "0", 10) || 0,
                        alt: logoButton.dataset.imageAlt || "",
                    });
                    return;
                }

                const textField = cellElement.querySelector("[data-report-page-footer-text]");
                if (textField) {
                    const helpers = getInlineText();
                    const bandText = window.ReportLinePageBandText;
                    if (bandText) {
                        cells.push(bandText.collectTextCellPayload(textField, helpers));
                    } else {
                        const align = textField.dataset.textAlign || "left";
                        const cell = {
                            type: "text",
                            text: helpers ? helpers.getHeaderHtml(textField) : textField.innerHTML,
                            align: FOOTER_ALIGN_VALUES.has(align) ? align : "left",
                            indent_level: Number.parseInt(textField.dataset.indentLevel || "0", 10) || 0,
                            first_line_indent: textField.dataset.firstLineIndent === "true",
                        };
                        if (textField.dataset.showPageNumber === "true") {
                            cell.show_page_number = true;
                        } else if (textField.hasAttribute("data-show-page-number")) {
                            cell.show_page_number = false;
                        }
                        cells.push(cell);
                    }
                }
            });
        });
        return cells;
    }

    function defaultFooterColumnWidths(root) {
        const templateId = root.dataset.footerTemplate || "";
        const cellCount = root.querySelectorAll(".report-page-footer-row .report-page-footer-cell").length;

        if (templateId === "text_only" || cellCount === 1) {
            return [100];
        }
        if (templateId === "logo_text_logo" || cellCount === 3) {
            return [1, 98, 1];
        }
        if (templateId === "text_left_logo_right") {
            return [99, 1];
        }
        return [1, 99];
    }

    function buildPageLayoutPayload(root) {
        return {
            page_layout: {
                footer: {
                    enabled: root.dataset.footerEnabled === "true",
                    template_id: root.dataset.footerTemplate || null,
                    column_widths: defaultFooterColumnWidths(root),
                    cells: collectFooterCells(root),
                },
            },
        };
    }

    async function patchPageLayout(payload) {
        const response = await fetch(updateUrl, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = (data.errors && data.errors.join(" ")) || "Falha ao salvar rodapé.";
            throw new Error(message);
        }
        return data;
    }

    function setEditingState(root, editing) {
        if (!root || root.dataset.footerEnabled !== "true") {
            isEditing = false;
            return;
        }

        isEditing = editing;
        root.dataset.footerEditing = editing ? "true" : "false";

        const surface = getFooterSurface(root);
        if (surface) {
            surface.classList.toggle("report-page-footer--editing", editing);
            surface.classList.toggle("report-page-footer--view", !editing);
            surface.setAttribute(
                "aria-label",
                editing
                    ? "Editando rodapé do documento"
                    : "Rodapé do documento. Clique para editar."
            );
        }

        root.querySelectorAll("[data-report-page-footer-text]").forEach((field) => {
            field.contentEditable = editing ? "true" : "false";
        });

        root.querySelectorAll("[data-report-page-footer-page-number-editor]").forEach((editor) => {
            editor.hidden = !editing;
        });
    }

    function updatePageNumberControlUI(textField) {
        const wrap = textField.closest(".report-page-footer-text-wrap");
        if (!wrap) {
            return;
        }
        const enabled = textField.dataset.showPageNumber === "true";
        const active = wrap.querySelector("[data-report-page-footer-page-number-active]");
        const addButton = wrap.querySelector("[data-report-page-footer-add-page-number]");
        if (active) {
            active.classList.toggle("d-none", !enabled);
        }
        if (addButton) {
            addButton.classList.toggle("d-none", enabled);
        }
    }

    function setFooterPageNumberEnabled(textField, enabled) {
        if (!textField) {
            return;
        }
        textField.dataset.showPageNumber = enabled ? "true" : "false";
        updatePageNumberControlUI(textField);
        flushFooterSave().catch(console.error);
    }

    function syncLastFocusedTextField(root) {
        if (!root || !lastFocusedTextField) {
            return;
        }
        const cellIndex = lastFocusedTextField.dataset.cellIndex;
        if (cellIndex === undefined) {
            return;
        }
        const refreshed = root.querySelector(
            `[data-report-page-footer-text][data-cell-index="${cellIndex}"]`
        );
        if (refreshed) {
            lastFocusedTextField = refreshed;
        }
    }

    function replaceFooterHtml(html, options) {
        const opts = options || {};
        const wasEditing = opts.preserveEditing ? isEditing : false;
        const currentRoot = document.getElementById("report-page-footer-root");
        if (!currentRoot || !html) {
            return;
        }

        currentRoot.insertAdjacentHTML("afterend", html);
        currentRoot.remove();
        footerRoot = document.getElementById("report-page-footer-root");
        bindFooterRoot(footerRoot);
        setEditingState(footerRoot, wasEditing);
        syncLastFocusedTextField(footerRoot);
    }

    function openTemplateModal() {
        if (!modal) {
            return;
        }
        modal.show();
    }

    function placeCaretAtStart(element) {
        if (!element) {
            return;
        }
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

    function focusFooterAfterTemplateApply() {
        const root = document.getElementById("report-page-footer-root");
        if (!root || root.dataset.footerEnabled !== "true") {
            return;
        }

        enterEditMode(root);
        const textField = root.querySelector("[data-report-page-footer-text]");
        if (!textField) {
            return;
        }

        lastFocusedTextField = textField;
        placeCaretAtStart(textField);
    }

    function scheduleFocusAfterTemplateModal(onFocus) {
        if (modal && modalElement) {
            const handleHidden = () => {
                modalElement.removeEventListener("hidden.bs.modal", handleHidden);
                onFocus();
            };
            modalElement.addEventListener("hidden.bs.modal", handleHidden);
            modal.hide();
            return;
        }

        onFocus();
    }

    async function applyTemplate(templateId) {
        const data = await patchPageLayout({
            apply_template: true,
            template_id: templateId,
            section: "footer",
        });
        replaceFooterHtml(data.footer_html, { preserveEditing: false });
        scheduleFocusAfterTemplateModal(focusFooterAfterTemplateApply);
    }

    function scheduleFooterSave() {
        if (saveTimer) {
            window.clearTimeout(saveTimer);
        }
        saveTimer = window.setTimeout(() => {
            saveTimer = null;
            flushFooterSave().catch(console.error);
        }, DEBOUNCE_MS);
    }

    async function flushFooterSave() {
        const root = document.getElementById("report-page-footer-root");
        if (!root || root.dataset.footerEnabled !== "true") {
            return null;
        }

        if (saveTimer) {
            window.clearTimeout(saveTimer);
            saveTimer = null;
        }

        const data = await patchPageLayout(buildPageLayoutPayload(root));
        replaceFooterHtml(data.footer_html, { preserveEditing: isEditing });
        return data;
    }

    async function exitEditMode() {
        if (!isEditing) {
            return;
        }

        try {
            await flushFooterSave();
        } catch (error) {
            console.error(error);
        }

        if (window.ReportLineImageResize && window.ReportLineImageResize.deselectTarget) {
            window.ReportLineImageResize.deselectTarget();
        }

        const root = document.getElementById("report-page-footer-root");
        setEditingState(root, false);
        lastFocusedTextField = null;
    }

    function enterEditMode(root) {
        if (!root || root.dataset.footerEnabled !== "true" || isEditing) {
            return;
        }
        setEditingState(root, true);
    }

    function ensureFileInput() {
        if (fileInput) {
            return fileInput;
        }
        fileInput = document.createElement("input");
        fileInput.type = "file";
        fileInput.accept = "image/jpeg,image/png,image/gif,image/webp";
        fileInput.hidden = true;
        fileInput.addEventListener("change", handleLogoFileSelected);
        document.body.appendChild(fileInput);
        return fileInput;
    }

    async function uploadLogo(file) {
        const formData = new FormData();
        formData.append("image", file);

        const response = await fetch(uploadUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
            body: formData,
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = (data.errors && data.errors.join(" ")) || "Falha ao enviar imagem.";
            throw new Error(message);
        }
        return data;
    }

    async function clearLogoCell(logoSlotElement) {
        if (!isEditing || !logoSlotElement || !logoSlotElement.classList.contains("has-image")) {
            return;
        }
        const cellIndex = Number.parseInt(logoSlotElement.dataset.cellIndex || "0", 10);
        const data = await patchPageLayout({
            clear_logo_cell: cellIndex,
            section: "footer",
        });
        replaceFooterHtml(data.footer_html, { preserveEditing: true });
        if (window.ReportLineImageResize && window.ReportLineImageResize.deselectTarget) {
            window.ReportLineImageResize.deselectTarget();
        }
    }

    async function handleLogoFileSelected(event) {
        const file = event.target.files && event.target.files[0];
        event.target.value = "";
        if (!file || pendingLogoCellIndex === null) {
            return;
        }

        try {
            const imagePayload = await uploadLogo(file);
            const data = await patchPageLayout({
                update_logo_cell: pendingLogoCellIndex,
                image: imagePayload,
                section: "footer",
            });
            pendingLogoCellIndex = null;
            replaceFooterHtml(data.footer_html, { preserveEditing: true });
        } catch (error) {
            console.error(error);
        }
    }

    function openLogoPicker(cellIndex) {
        if (!isEditing) {
            return;
        }
        pendingLogoCellIndex = cellIndex;
        ensureFileInput().click();
    }

    function applyFooterTextAlign(textField, align) {
        if (!textField || !FOOTER_ALIGN_VALUES.has(align)) {
            return;
        }

        textField.dataset.textAlign = align;
        const cell = textField.closest(".report-page-footer-cell");
        if (cell) {
            cell.style.textAlign = align;
        }
        scheduleFooterSave();
    }

    function getActiveFooterTextField() {
        if (!isEditing) {
            return null;
        }
        const context = resolveFooterTextContext();
        if (context) {
            lastFocusedTextField = context.editable;
            return context.editable;
        }
        if (lastFocusedTextField && document.contains(lastFocusedTextField)) {
            return lastFocusedTextField;
        }
        const root = document.getElementById("report-page-footer-root");
        return root
            ? root.querySelector("[data-report-page-footer-text][contenteditable='true']")
            : null;
    }

    function increaseTextIndent() {
        const bandText = window.ReportLinePageBandText;
        const field = getActiveFooterTextField();
        if (!bandText || !field) {
            return;
        }
        bandText.increaseIndent(field);
        flushFooterSave().catch(console.error);
    }

    function decreaseTextIndent() {
        const bandText = window.ReportLinePageBandText;
        const field = getActiveFooterTextField();
        if (!bandText || !field) {
            return;
        }
        bandText.decreaseIndent(field);
        flushFooterSave().catch(console.error);
    }

    function toggleTextFirstLineIndent() {
        const bandText = window.ReportLinePageBandText;
        const field = getActiveFooterTextField();
        if (!bandText || !field) {
            return;
        }
        bandText.toggleFirstLineIndent(field);
        flushFooterSave().catch(console.error);
    }

    function resolveFooterTextContext() {
        if (!isEditing) {
            return null;
        }

        const selection = window.getSelection();
        if (selection && selection.rangeCount > 0) {
            const anchor = selection.anchorNode;
            const editable = anchor && anchor.nodeType === Node.ELEMENT_NODE
                ? anchor.closest("[data-report-page-footer-text]")
                : anchor && anchor.parentElement
                    ? anchor.parentElement.closest("[data-report-page-footer-text]")
                    : null;
            if (editable && editable.contentEditable === "true") {
                return { editable, kind: "page-footer-text" };
            }
        }

        const active = document.activeElement;
        if (active && active.matches("[data-report-page-footer-text][contenteditable='true']")) {
            return { editable: active, kind: "page-footer-text" };
        }

        return null;
    }

    function bindFooterRoot(root) {
        if (!root) {
            return;
        }

        root.querySelectorAll("[data-report-page-footer-open]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                openTemplateModal();
            });
        });

        const surface = getFooterSurface(root);
        if (surface) {
            surface.addEventListener("click", (event) => {
                if (root.dataset.footerEnabled !== "true") {
                    return;
                }

                const logoSlot = event.target.closest("[data-report-page-footer-logo]");
                const hasLogoImage = logoSlot && logoSlot.classList.contains("has-image");
                const clickedLogoImage = Boolean(
                    event.target.closest(".report-page-footer-logo-img, .report-page-footer-logo-frame")
                );

                if (!isEditing) {
                    enterEditMode(root);
                    if (logoSlot && !hasLogoImage) {
                        event.preventDefault();
                        openLogoPicker(Number.parseInt(logoSlot.dataset.cellIndex || "0", 10));
                        return;
                    }
                    if (hasLogoImage && clickedLogoImage) {
                        return;
                    }
                    const textField = event.target.closest("[data-report-page-footer-text]");
                    if (textField) {
                        textField.focus();
                    }
                    return;
                }

                if (logoSlot && !hasLogoImage) {
                    event.preventDefault();
                    openLogoPicker(Number.parseInt(logoSlot.dataset.cellIndex || "0", 10));
                }
            });

            surface.addEventListener("dblclick", (event) => {
                const logoSlot = event.target.closest("[data-report-page-footer-logo].has-image");
                if (!logoSlot) {
                    return;
                }
                if (!event.target.closest(".report-page-footer-logo-img, .report-page-footer-logo-frame")) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                if (!isEditing) {
                    enterEditMode(root);
                }
                openLogoPicker(Number.parseInt(logoSlot.dataset.cellIndex || "0", 10));
            });
        }

        root.querySelectorAll("[data-report-page-footer-text]").forEach((field) => {
            field.addEventListener("focusin", () => {
                lastFocusedTextField = field;
            });

            field.addEventListener("input", scheduleFooterSave);

            field.addEventListener("keydown", (event) => {
                if (!isEditing) {
                    return;
                }
                if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    document.execCommand("insertLineBreak");
                }
            });

            field.addEventListener("paste", (event) => {
                if (!isEditing) {
                    return;
                }
                const helpers = getInlineText();
                if (!helpers) {
                    return;
                }
                event.preventDefault();
                const clipboard = event.clipboardData;
                if (!clipboard) {
                    return;
                }
                const html = clipboard.getData("text/html");
                const plain = clipboard.getData("text/plain");
                if (html) {
                    document.execCommand("insertHTML", false, helpers.sanitizeHeader(html));
                } else {
                    document.execCommand("insertText", false, plain);
                }
            });
        });

        root.querySelectorAll("[data-report-page-footer-remove-page-number]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const wrap = button.closest(".report-page-footer-text-wrap");
                const textField = wrap && wrap.querySelector("[data-report-page-footer-text]");
                setFooterPageNumberEnabled(textField, false);
            });
        });

        root.querySelectorAll("[data-report-page-footer-add-page-number]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const wrap = button.closest(".report-page-footer-text-wrap");
                const textField = wrap && wrap.querySelector("[data-report-page-footer-text]");
                setFooterPageNumberEnabled(textField, true);
            });
        });
    }

    function bindTemplateCards() {
        document.querySelectorAll("[data-report-page-footer-template]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                applyTemplate(button.dataset.reportPageFooterTemplate).catch(console.error);
            });
        });
    }

    function bindToolbar() {
        document.querySelectorAll("[data-report-page-footer-toolbar]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                openTemplateModal();
            });
        });
    }

    function bindGlobalHandlers() {
        document.addEventListener("mousedown", (event) => {
            if (!isEditing) {
                return;
            }
            const root = document.getElementById("report-page-footer-root");
            if (!root) {
                return;
            }
            if (root.contains(event.target)) {
                return;
            }
            if (event.target.closest("#reportPageFooterModal")) {
                return;
            }
            if (event.target.closest("[data-report-page-footer-toolbar], [data-report-page-layout-toolbar]")) {
                return;
            }
            if (event.target.closest(".report-editor-toolbar")) {
                return;
            }
            if (event.target.closest(".report-editor-image-handle")) {
                return;
            }
            exitEditMode().catch(console.error);
        });

        document.addEventListener("keydown", (event) => {
            if (!isEditing || event.key !== "Escape") {
                return;
            }
            exitEditMode().catch(console.error);
        });
    }

    function init(options) {
        updateUrl = options.updateUrl || "";
        uploadUrl = options.uploadUrl || "";
        modalElement = document.getElementById("reportPageFooterModal");
        footerRoot = document.getElementById("report-page-footer-root");

        if (!updateUrl || !uploadUrl || !footerRoot || !window.bootstrap) {
            return;
        }

        modal = window.bootstrap.Modal.getOrCreateInstance(modalElement);
        bindFooterRoot(footerRoot);
        bindTemplateCards();
        bindToolbar();
        bindGlobalHandlers();
        setEditingState(footerRoot, false);
    }

    window.ReportLinePageFooter = {
        init,
        openTemplateModal,
        scheduleFooterSave,
        flushFooterSave,
        isEditing: () => isEditing,
        resolveFooterTextContext,
        applyFooterTextAlign,
        increaseTextIndent,
        decreaseTextIndent,
        toggleTextFirstLineIndent,
        getActiveFooterTextField,
        clearLogoCell,
    };
})();
