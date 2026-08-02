/**

 * Cabeçalho de página do relatório (modelos, logos e texto).

 */

(function () {

    "use strict";



    const DEBOUNCE_MS = 1500;

    const HEADER_ALIGN_VALUES = new Set(["left", "center", "right"]);



    let updateUrl = "";

    let uploadUrl = "";

    let modal = null;

    let modalElement = null;

    let headerRoot = null;

    let pendingLogoCellIndex = null;

    let fileInput = null;

    let saveTimer = null;

    let isEditing = false;



    function getCsrfToken() {

        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);

        return match ? decodeURIComponent(match[1]) : "";

    }



    function getInlineText() {

        return window.ReportLineInlineText || null;

    }



    function getHeaderSurface(root) {

        return root ? root.querySelector("[data-report-page-header-surface]") : null;

    }



    function collectHeaderCells(root) {

        const cells = [];

        root.querySelectorAll(".report-page-header-row").forEach((row) => {

            row.querySelectorAll(".report-page-header-cell").forEach((cellElement) => {

                const logoButton = cellElement.querySelector("[data-report-page-header-logo]");

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



                const textField = cellElement.querySelector("[data-report-page-header-text]");

                if (textField) {

                    const helpers = getInlineText();

                    const align = textField.dataset.textAlign || "left";

                    cells.push({

                        type: "text",

                        text: helpers ? helpers.getHeaderHtml(textField) : textField.innerHTML,

                        align: HEADER_ALIGN_VALUES.has(align) ? align : "left",

                    });

                }

            });

        });

        return cells;

    }



    function defaultHeaderColumnWidths(root) {
        const templateId = root.dataset.headerTemplate || "";
        const cellCount = root.querySelectorAll(".report-page-header-row .report-page-header-cell").length;

        if (templateId === "logo_text_logo" || cellCount === 3) {
            return [1, 98, 1];
        }
        if (templateId === "text_left_logo_right") {
            return [99, 1];
        }
        return [1, 99];
    }

    function readHeaderColumnWidths(root) {
        const cols = root.querySelectorAll(".report-page-header-table col");
        if (!cols.length) {
            return defaultHeaderColumnWidths(root);
        }

        const widths = Array.from(cols).map((col) => {
            const match = (col.getAttribute("style") || "").match(/([\d.]+)%/);
            return match ? Number.parseFloat(match[1]) : 0;
        });

        return widths.some((value) => value <= 0)
            ? defaultHeaderColumnWidths(root)
            : widths;
    }

    function buildPageLayoutPayload(root) {

        return {

            page_layout: {

                header: {

                    enabled: root.dataset.headerEnabled === "true",

                    template_id: root.dataset.headerTemplate || null,

                    column_widths: readHeaderColumnWidths(root),

                    cells: collectHeaderCells(root),

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

            const message = (data.errors && data.errors.join(" ")) || "Falha ao salvar cabeçalho.";

            throw new Error(message);

        }

        return data;

    }



    function setEditingState(root, editing) {

        if (!root || root.dataset.headerEnabled !== "true") {

            isEditing = false;

            return;

        }



        isEditing = editing;

        root.dataset.headerEditing = editing ? "true" : "false";



        const surface = getHeaderSurface(root);

        if (surface) {

            surface.classList.toggle("report-page-header--editing", editing);

            surface.classList.toggle("report-page-header--view", !editing);

            surface.setAttribute(

                "aria-label",

                editing

                    ? "Editando cabeçalho do documento"

                    : "Cabeçalho do documento. Clique para editar."

            );

        }



        root.querySelectorAll("[data-report-page-header-text]").forEach((field) => {

            field.contentEditable = editing ? "true" : "false";

        });

    }



    function replaceHeaderHtml(html, options) {

        const opts = options || {};

        const wasEditing = opts.preserveEditing ? isEditing : false;

        const currentRoot = document.getElementById("report-page-header-root");

        if (!currentRoot || !html) {

            return;

        }

        currentRoot.insertAdjacentHTML("afterend", html);

        currentRoot.remove();

        headerRoot = document.getElementById("report-page-header-root");

        bindHeaderRoot(headerRoot);

        setEditingState(headerRoot, wasEditing);

    }



    function openTemplateModal() {

        if (!modal) {

            return;

        }

        modal.show();

    }



    async function applyTemplate(templateId) {

        const data = await patchPageLayout({

            apply_template: true,

            template_id: templateId,

        });

        replaceHeaderHtml(data.html, { preserveEditing: false });

        if (modal) {

            modal.hide();

        }

    }



    function scheduleHeaderSave() {

        if (saveTimer) {

            window.clearTimeout(saveTimer);

        }

        saveTimer = window.setTimeout(() => {

            saveTimer = null;

            flushHeaderSave().catch(console.error);

        }, DEBOUNCE_MS);

    }



    async function flushHeaderSave() {

        const root = document.getElementById("report-page-header-root");

        if (!root || root.dataset.headerEnabled !== "true") {

            return null;

        }



        if (saveTimer) {

            window.clearTimeout(saveTimer);

            saveTimer = null;

        }



        const data = await patchPageLayout(buildPageLayoutPayload(root));

        replaceHeaderHtml(data.html, { preserveEditing: isEditing });

        return data;

    }



    async function exitEditMode() {

        if (!isEditing) {

            return;

        }



        try {

            await flushHeaderSave();

        } catch (error) {

            console.error(error);

        }



        if (window.ReportLineImageResize && window.ReportLineImageResize.deselectTarget) {

            window.ReportLineImageResize.deselectTarget();

        }



        const root = document.getElementById("report-page-header-root");

        setEditingState(root, false);

    }



    function enterEditMode(root) {

        if (!root || root.dataset.headerEnabled !== "true" || isEditing) {

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

            });

            pendingLogoCellIndex = null;

            replaceHeaderHtml(data.html, { preserveEditing: true });

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



    function applyHeaderTextAlign(textField, align) {

        if (!textField || !HEADER_ALIGN_VALUES.has(align)) {

            return;

        }



        textField.dataset.textAlign = align;

        const cell = textField.closest(".report-page-header-cell");

        if (cell) {

            cell.style.textAlign = align;

        }

        scheduleHeaderSave();

    }



    function resolveHeaderTextContext() {

        if (!isEditing) {

            return null;

        }



        const selection = window.getSelection();

        if (selection && selection.rangeCount > 0) {

            const anchor = selection.anchorNode;

            const editable = anchor && anchor.nodeType === Node.ELEMENT_NODE

                ? anchor.closest("[data-report-page-header-text]")

                : anchor && anchor.parentElement

                    ? anchor.parentElement.closest("[data-report-page-header-text]")

                    : null;

            if (editable && editable.contentEditable === "true") {

                return { editable, kind: "page-header-text" };

            }

        }



        const active = document.activeElement;

        if (active && active.matches("[data-report-page-header-text][contenteditable='true']")) {

            return { editable: active, kind: "page-header-text" };

        }



        return null;

    }



    function bindHeaderRoot(root) {

        if (!root) {

            return;

        }



        root.querySelectorAll("[data-report-page-header-open]").forEach((button) => {

            button.addEventListener("click", (event) => {

                event.preventDefault();

                openTemplateModal();

            });

        });



        const surface = getHeaderSurface(root);

        if (surface) {

            surface.addEventListener("click", (event) => {

                if (root.dataset.headerEnabled !== "true") {

                    return;

                }

                const logoSlot = event.target.closest("[data-report-page-header-logo]");

                const hasLogoImage = logoSlot && logoSlot.classList.contains("has-image");

                const clickedLogoImage = Boolean(
                    event.target.closest(".report-page-header-logo-img, .report-page-header-logo-frame")
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

                    const textField = event.target.closest("[data-report-page-header-text]");

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

                const logoSlot = event.target.closest("[data-report-page-header-logo].has-image");

                if (!logoSlot) {

                    return;

                }

                if (!event.target.closest(".report-page-header-logo-img, .report-page-header-logo-frame")) {

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



        root.querySelectorAll("[data-report-page-header-text]").forEach((field) => {

            field.addEventListener("input", scheduleHeaderSave);



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

    }



    function bindTemplateCards() {

        document.querySelectorAll("[data-report-page-header-template]").forEach((button) => {

            button.addEventListener("click", (event) => {

                event.preventDefault();

                applyTemplate(button.dataset.reportPageHeaderTemplate).catch(console.error);

            });

        });

    }



    function bindToolbar() {

        document.querySelectorAll("[data-report-page-header-toolbar]").forEach((button) => {

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

            const root = document.getElementById("report-page-header-root");

            if (!root) {

                return;

            }

            if (root.contains(event.target)) {

                return;

            }

            if (event.target.closest("#reportPageHeaderModal")) {

                return;

            }

            if (event.target.closest("[data-report-page-header-toolbar]")) {

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

        modalElement = document.getElementById("reportPageHeaderModal");

        headerRoot = document.getElementById("report-page-header-root");



        if (!updateUrl || !uploadUrl || !headerRoot || !window.bootstrap) {

            return;

        }



        modal = window.bootstrap.Modal.getOrCreateInstance(modalElement);

        bindHeaderRoot(headerRoot);

        bindTemplateCards();

        bindToolbar();

        bindGlobalHandlers();

        setEditingState(headerRoot, false);

    }



    window.ReportLinePageHeader = {

        init,

        openTemplateModal,

        scheduleHeaderSave,

        flushHeaderSave,

        isEditing: () => isEditing,

        resolveHeaderTextContext,

        applyHeaderTextAlign,

    };

})();


