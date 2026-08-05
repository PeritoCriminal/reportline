/**

 * Cabeçalho de página do relatório (modelos, logos e texto).

 */

(function () {

    "use strict";



    const DEBOUNCE_MS = 1500;

    const HISTORY_DEBOUNCE_MS = 400;

    const HEADER_ALIGN_VALUES = new Set(["left", "center", "right"]);

    const HORIZONTAL_RULE_LINE_PATTERN = /^_{3,}$/;

    const DEFAULT_EXTRA_TEXT_ROW = Object.freeze({
        type: "text",
        text: "",
        align: "left",
        indent_level: 0,
        first_line_indent: false,
        muted: false,
    });

    const HEADER_BAND_FOCUS = {
        textSelector: "[data-report-page-header-text]",
        extraTextSelector: "[data-report-page-header-extra-text]",
    };

    function getBandTextHelpers() {
        return window.ReportLinePageBandText || null;
    }

    function captureHeaderTextFocus(root) {
        const bandText = getBandTextHelpers();
        if (!bandText || !bandText.captureBandTextFocus) {
            return null;
        }
        return bandText.captureBandTextFocus(root, {
            ...HEADER_BAND_FOCUS,
            lastFocusedField: lastFocusedTextField,
        });
    }

    function restoreHeaderTextFocus(root, focusState) {
        const bandText = getBandTextHelpers();
        if (!bandText || !bandText.restoreBandTextFocus || !focusState) {
            return null;
        }
        return bandText.restoreBandTextFocus(root, focusState, {
            ...HEADER_BAND_FOCUS,
            onRestore: (field) => {
                lastFocusedTextField = field;
            },
        });
    }



    let updateUrl = "";

    let uploadUrl = "";

    let modal = null;

    let modalElement = null;

    let headerRoot = null;

    let pendingLogoCellIndex = null;

    let fileInput = null;

    let saveTimer = null;

    let historyTimer = null;

    let pendingLayoutEdit = null;

    let isEditing = false;

    let lastFocusedTextField = null;

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



    function collectHeaderExtraRows(root) {
        const rows = [];
        root.querySelectorAll("[data-report-page-header-extra-row]").forEach((rowElement) => {
            if (rowElement.querySelector(".report-page-header-extra-rule")) {
                rows.push({ type: "rule" });
                return;
            }

            const textField = rowElement.querySelector("[data-report-page-header-extra-text]");
            if (!textField) {
                return;
            }

            const helpers = getInlineText();
            const bandText = window.ReportLinePageBandText;
            if (bandText) {
                rows.push(bandText.collectTextCellPayload(textField, helpers));
            } else {
                const align = textField.dataset.textAlign || "left";
                rows.push({
                    type: "text",
                    text: helpers ? helpers.getHeaderHtml(textField) : textField.innerHTML,
                    align: HEADER_ALIGN_VALUES.has(align) ? align : "left",
                    indent_level: Number.parseInt(textField.dataset.indentLevel || "0", 10) || 0,
                    first_line_indent: textField.dataset.firstLineIndent === "true",
                    muted: textField.dataset.muted === "true",
                });
            }
        });
        return rows;
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

                    const bandText = window.ReportLinePageBandText;

                    if (bandText) {

                        cells.push(bandText.collectTextCellPayload(textField, helpers));

                    } else {

                        const align = textField.dataset.textAlign || "left";

                        cells.push({

                            type: "text",

                            text: helpers ? helpers.getHeaderHtml(textField) : textField.innerHTML,

                            align: HEADER_ALIGN_VALUES.has(align) ? align : "left",

                            indent_level: Number.parseInt(textField.dataset.indentLevel || "0", 10) || 0,

                            first_line_indent: textField.dataset.firstLineIndent === "true",

                        });

                    }

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

                    extra_rows: collectHeaderExtraRows(root),

                },

            },

        };

    }

    function beginHeaderLayoutRecording() {

        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {

            return;

        }

        const root = document.getElementById("report-page-header-root");

        if (!root || root.dataset.headerEnabled !== "true" || pendingLayoutEdit) {

            return;

        }

        pendingLayoutEdit = {

            before: buildPageLayoutPayload(root),

            preserveEditing: isEditing,

        };

    }

    async function applyHeaderLayoutSnapshot(snapshot, preserveEditing) {

        const data = await patchPageLayout(snapshot);

        replaceHeaderHtml(data.html || data.header_html, { preserveEditing });

        return data;

    }

    function recordHeaderLayoutChange(before, after, preserveEditing) {

        if (

            !window.ReportLineUndo

            || window.ReportLineUndo.isApplying()

            || JSON.stringify(before) === JSON.stringify(after)

        ) {

            return;

        }

        window.ReportLineUndo.recordCommand({

            label: "Cabeçalho",

            mergeKey: "page-layout-header",

            undo: () => applyHeaderLayoutSnapshot(before, preserveEditing),

            redo: () => applyHeaderLayoutSnapshot(after, preserveEditing),

        });

    }

    function finalizeHeaderLayoutRecording() {

        if (!pendingLayoutEdit) {

            return;

        }

        const root = document.getElementById("report-page-header-root");

        if (!root) {

            pendingLayoutEdit = null;

            return;

        }

        const after = buildPageLayoutPayload(root);

        const { before, preserveEditing } = pendingLayoutEdit;

        pendingLayoutEdit = null;

        recordHeaderLayoutChange(before, after, preserveEditing);

    }

    async function recordImmediateHeaderLayoutChange(mutator) {

        const root = document.getElementById("report-page-header-root");

        if (!root || !window.ReportLineUndo || window.ReportLineUndo.isApplying()) {

            await mutator();

            return;

        }

        const before = buildPageLayoutPayload(root);

        const preserveEditing = isEditing;

        await mutator();

        const after = buildPageLayoutPayload(root);

        recordHeaderLayoutChange(before, after, preserveEditing);

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



        root.querySelectorAll("[data-report-page-header-text], [data-report-page-header-extra-text]").forEach((field) => {

            field.contentEditable = editing ? "true" : "false";

        });

    }



    function syncLastFocusedTextField(root) {

        if (!root || !lastFocusedTextField) {

            return;

        }

        const cellIndex = lastFocusedTextField.dataset.cellIndex;

        const extraRowIndex = lastFocusedTextField.dataset.extraRowIndex;

        let selector = null;

        if (extraRowIndex !== undefined) {

            selector = `[data-report-page-header-extra-text][data-extra-row-index="${extraRowIndex}"]`;

        } else if (cellIndex !== undefined) {

            selector = `[data-report-page-header-text][data-cell-index="${cellIndex}"]`;

        }

        if (!selector) {

            return;

        }

        const refreshed = root.querySelector(selector);

        if (refreshed) {

            lastFocusedTextField = refreshed;

        }

    }



    function replaceHeaderHtml(html, options) {

        const opts = options || {};

        const wasEditing = opts.preserveEditing ? isEditing : false;

        const currentRoot = document.getElementById("report-page-header-root");

        if (!currentRoot || !html) {

            return;

        }

        const focusState = wasEditing
            ? (opts.focusState || captureHeaderTextFocus(currentRoot))
            : null;

        currentRoot.insertAdjacentHTML("afterend", html);

        currentRoot.remove();

        headerRoot = document.getElementById("report-page-header-root");

        bindHeaderRoot(headerRoot);

        setEditingState(headerRoot, wasEditing);

        if (focusState) {

            restoreHeaderTextFocus(headerRoot, focusState);

        } else {

            syncLastFocusedTextField(headerRoot);

        }

    }



    function openTemplateModal() {

        if (!modal) {

            return;

        }

        modal.show();

    }



    function placeCaretAtEnd(element) {
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
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
    }

    function isHorizontalRuleShortcutLine(lineText) {
        return HORIZONTAL_RULE_LINE_PATTERN.test(lineText || "");
    }

    function isHeaderFieldEmpty(field) {
        const helpers = getInlineText();
        if (helpers && helpers.isEmptyHtml) {
            return helpers.isEmptyHtml(field.innerHTML);
        }
        return !(field.textContent || "").trim();
    }

    function getCaretOffset(editable) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            return 0;
        }
        const range = selection.getRangeAt(0);
        if (!editable.contains(range.startContainer)) {
            return 0;
        }
        const preRange = range.cloneRange();
        preRange.selectNodeContents(editable);
        preRange.setEnd(range.startContainer, range.startOffset);
        return preRange.toString().length;
    }

    function buildExtraTextRowFromField(textField, text) {
        return {
            type: "text",
            text: text || "",
            align: textField.dataset.textAlign || "left",
            indent_level: Number.parseInt(textField.dataset.indentLevel || "0", 10) || 0,
            first_line_indent: textField.dataset.firstLineIndent === "true",
            muted: textField.dataset.muted === "true",
        };
    }

    function isEmptyTextRowPayload(row) {
        if (!row || row.type !== "text") {
            return false;
        }
        const helpers = getInlineText();
        const text = row.text || "";
        if (helpers && helpers.isEmptyHtml) {
            return helpers.isEmptyHtml(text);
        }
        return !text.trim();
    }

    function needsTrailingEmptyRow(rows) {
        if (!rows.length) {
            return true;
        }
        const last = rows[rows.length - 1];
        if (last.type === "rule") {
            return true;
        }
        return !isEmptyTextRowPayload(last);
    }

    function appendTrailingEmptyRowIfNeeded(rows) {
        if (needsTrailingEmptyRow(rows)) {
            rows.push({ ...DEFAULT_EXTRA_TEXT_ROW });
        }
        return rows;
    }

    function pruneEmptyExtraRows(rows) {
        return rows.filter((row) => {
            if (row.type === "rule") {
                return true;
            }
            if (row.type !== "text") {
                return false;
            }
            const helpers = getInlineText();
            const text = row.text || "";
            if (helpers && helpers.isEmptyHtml) {
                return !helpers.isEmptyHtml(text);
            }
            return text.trim().length > 0;
        });
    }

    function isExtraHeaderTextField(field) {
        return Boolean(field && field.matches("[data-report-page-header-extra-text]"));
    }

    function focusExtraTextFieldByIndex(index, options) {
        const opts = options || {};
        const field = document.querySelector(
            `[data-report-page-header-extra-text][data-extra-row-index="${index}"]`
        );
        if (!field) {
            return null;
        }
        lastFocusedTextField = field;
        if (opts.atEnd) {
            placeCaretAtEnd(field);
        } else {
            placeCaretAtStart(field);
        }
        return field;
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

    function focusHeaderAfterTemplateApply() {
        const root = document.getElementById("report-page-header-root");
        if (!root || root.dataset.headerEnabled !== "true") {
            return;
        }

        enterEditMode(root, { focusMainText: true }).catch(console.error);
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

        await recordImmediateHeaderLayoutChange(async () => {

            const data = await patchPageLayout({

                apply_template: true,

                template_id: templateId,

            });

            replaceHeaderHtml(data.html, { preserveEditing: false });

            scheduleFocusAfterTemplateModal(focusHeaderAfterTemplateApply);

        });

    }



    function scheduleHeaderHistoryFinalize() {

        beginHeaderLayoutRecording();

        if (!pendingLayoutEdit) {

            return;

        }

        if (historyTimer) {

            window.clearTimeout(historyTimer);

        }

        historyTimer = window.setTimeout(() => {

            historyTimer = null;

            finalizeHeaderLayoutRecording();

        }, HISTORY_DEBOUNCE_MS);

    }



    function scheduleHeaderSave() {

        scheduleHeaderHistoryFinalize();

        if (saveTimer) {

            window.clearTimeout(saveTimer);

        }

        saveTimer = window.setTimeout(() => {

            saveTimer = null;

            flushHeaderSave({ skipHtmlReplace: true }).catch(console.error);

        }, DEBOUNCE_MS);

    }



    async function flushHeaderUndoState() {

        if (historyTimer) {

            window.clearTimeout(historyTimer);

            historyTimer = null;

        }

        finalizeHeaderLayoutRecording();

    }



    async function flushHeaderSave(options) {

        const opts = options || {};

        const root = document.getElementById("report-page-header-root");

        if (!root || root.dataset.headerEnabled !== "true") {

            return null;

        }



        if (historyTimer) {

            window.clearTimeout(historyTimer);

            historyTimer = null;

            finalizeHeaderLayoutRecording();

        }



        if (saveTimer) {

            window.clearTimeout(saveTimer);

            saveTimer = null;

        }



        const payload = buildPageLayoutPayload(root);

        if (opts.pruneEmptyExtraRows) {
            payload.page_layout.header.extra_rows = pruneEmptyExtraRows(
                payload.page_layout.header.extra_rows || []
            );
        }

        const data = await patchPageLayout(payload);

        if (!opts.skipHtmlReplace) {
            replaceHeaderHtml(data.html || data.header_html, { preserveEditing: isEditing });
        }

        if (pendingLayoutEdit) {

            finalizeHeaderLayoutRecording();

        }

        return data;

    }



    async function exitEditMode() {

        if (!isEditing) {

            return;

        }



        try {

            await flushHeaderSave({ pruneEmptyExtraRows: true });

        } catch (error) {

            console.error(error);

        }



        if (window.ReportLineImageResize && window.ReportLineImageResize.deselectTarget) {

            window.ReportLineImageResize.deselectTarget();

        }



        const root = document.getElementById("report-page-header-root");

        setEditingState(root, false);

        lastFocusedTextField = null;

    }



    async function ensureTrailingExtraTextRow(root, focusOptions) {
        const opts = focusOptions || {};
        if (!root) {
            return;
        }

        const payload = buildPageLayoutPayload(root);
        const rows = payload.page_layout.header.extra_rows || [];
        const beforeLen = rows.length;
        appendTrailingEmptyRowIfNeeded(rows);
        const mutated = rows.length !== beforeLen || beforeLen === 0;

        if (mutated) {
            payload.page_layout.header.extra_rows = rows;
            const data = await patchPageLayout(payload);
            replaceHeaderHtml(data.html || data.header_html, { preserveEditing: true });
            root = document.getElementById("report-page-header-root");
        }

        if (!root) {
            return;
        }

        if (opts.focusMainText) {
            const mainField = root.querySelector("[data-report-page-header-text]");
            if (mainField) {
                lastFocusedTextField = mainField;
                placeCaretAtStart(mainField);
            }
            return;
        }

        const extraFields = root.querySelectorAll("[data-report-page-header-extra-text]");
        if (!extraFields.length) {
            return;
        }

        if (opts.focusExtraRowIndex !== undefined) {
            const index = Math.min(
                Math.max(0, opts.focusExtraRowIndex),
                extraFields.length - 1
            );
            focusExtraTextFieldByIndex(index, { atEnd: Boolean(opts.atEnd) });
            return;
        }

        focusExtraTextFieldByIndex(extraFields.length - 1);
    }

    async function ensureAtLeastOneExtraRow(root, focusExtraRow) {
        await ensureTrailingExtraTextRow(root, {
            focusTrailing: focusExtraRow,
        });
    }

    async function enterEditMode(root, options) {
        const opts = options || {};

        if (!root || root.dataset.headerEnabled !== "true" || isEditing) {

            return;

        }

        setEditingState(root, true);

        await ensureTrailingExtraTextRow(root, {
            focusMainText: Boolean(opts.focusMainText),
            focusExtraRowIndex: opts.focusExtraRowIndex,
            atEnd: Boolean(opts.atEnd),
            focusTrailing: Boolean(opts.focusTrailing),
        });

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

        if (!window.ReportLineImageClient) {

            throw new Error("Módulo de upload de imagem indisponível.");

        }

        return window.ReportLineImageClient.uploadReportImage(file, { uploadUrl });

    }



    async function clearLogoCell(logoSlotElement) {

        if (!isEditing || !logoSlotElement || !logoSlotElement.classList.contains("has-image")) {

            return;

        }

        const cellIndex = Number.parseInt(logoSlotElement.dataset.cellIndex || "0", 10);

        await recordImmediateHeaderLayoutChange(async () => {

            const data = await patchPageLayout({

                clear_logo_cell: cellIndex,

                section: "header",

            });

            replaceHeaderHtml(data.header_html, { preserveEditing: true });

            if (window.ReportLineImageResize && window.ReportLineImageResize.deselectTarget) {

                window.ReportLineImageResize.deselectTarget();

            }

        });

    }



    async function handleLogoFileSelected(event) {

        const file = event.target.files && event.target.files[0];

        event.target.value = "";

        if (!file || pendingLogoCellIndex === null) {

            return;

        }



        try {

            const cellIndex = pendingLogoCellIndex;

            await recordImmediateHeaderLayoutChange(async () => {

                const imagePayload = await uploadLogo(file);

                const data = await patchPageLayout({

                    update_logo_cell: cellIndex,

                    image: imagePayload,

                });

                pendingLogoCellIndex = null;

                replaceHeaderHtml(data.html, { preserveEditing: true });

            });

        } catch (error) {

            pendingLogoCellIndex = null;

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



    function getHeaderTextSelector() {
        return "[data-report-page-header-text], [data-report-page-header-extra-text]";
    }

    function applyHeaderTextAlign(textField, align) {

        if (!textField || !HEADER_ALIGN_VALUES.has(align)) {

            return;

        }



        textField.dataset.textAlign = align;

        const cell = textField.closest(".report-page-header-cell, .report-page-header-extra-row-inner");

        if (cell) {

            cell.style.textAlign = align;

        }

        scheduleHeaderSave();

    }



    function getActiveHeaderTextField() {

        if (!isEditing) {

            return null;

        }

        const context = resolveHeaderTextContext();

        if (context) {

            lastFocusedTextField = context.editable;

            return context.editable;

        }

        if (lastFocusedTextField && document.contains(lastFocusedTextField)) {

            return lastFocusedTextField;

        }

        const root = document.getElementById("report-page-header-root");

        return root
            ? root.querySelector(`${getHeaderTextSelector()}[contenteditable='true']`)
            : null;

    }



    function increaseTextIndent() {

        const bandText = window.ReportLinePageBandText;

        const field = getActiveHeaderTextField();

        if (!bandText || !field) {

            return;

        }

        bandText.increaseIndent(field);

        flushHeaderSave({ skipHtmlReplace: true }).catch(console.error);

    }



    function decreaseTextIndent() {

        const bandText = window.ReportLinePageBandText;

        const field = getActiveHeaderTextField();

        if (!bandText || !field) {

            return;

        }

        bandText.decreaseIndent(field);

        flushHeaderSave({ skipHtmlReplace: true }).catch(console.error);

    }



    function toggleTextFirstLineIndent() {

        const bandText = window.ReportLinePageBandText;

        const field = getActiveHeaderTextField();

        if (!bandText || !field) {

            return;

        }

        bandText.toggleFirstLineIndent(field);

        flushHeaderSave({ skipHtmlReplace: true }).catch(console.error);

    }



    function resolveHeaderTextContext() {

        if (!isEditing) {

            return null;

        }



        const selection = window.getSelection();

        if (selection && selection.rangeCount > 0) {

            const anchor = selection.anchorNode;

            const editable = anchor && anchor.nodeType === Node.ELEMENT_NODE

                ? anchor.closest(getHeaderTextSelector())

                : anchor && anchor.parentElement

                    ? anchor.parentElement.closest(getHeaderTextSelector())

                    : null;

            if (editable && editable.contentEditable === "true") {

                return { editable, kind: "page-header-text" };

            }

        }



        const active = document.activeElement;

        if (active && active.matches(`${getHeaderTextSelector()}[contenteditable='true']`)) {

            return { editable: active, kind: "page-header-text" };

        }



        return null;

    }



    async function mutateHeaderExtraRows(mutator) {

        const root = document.getElementById("report-page-header-root");

        if (!root || root.dataset.headerEnabled !== "true") {

            return;

        }

        const payload = buildPageLayoutPayload(root);

        mutator(payload.page_layout.header.extra_rows);

        await recordImmediateHeaderLayoutChange(async () => {

            const data = await patchPageLayout(payload);

            replaceHeaderHtml(data.html || data.header_html, { preserveEditing: true });

        });

    }



    async function insertExtraRuleAfterCurrent() {

        const field = getActiveHeaderTextField();

        if (!isExtraHeaderTextField(field)) {

            return;

        }

        const rowElement = field.closest("[data-report-page-header-extra-row]");

        const index = Number.parseInt(rowElement?.dataset.extraRowIndex || "0", 10);

        const root = document.getElementById("report-page-header-root");

        const payload = buildPageLayoutPayload(root);

        const rows = payload.page_layout.header.extra_rows;

        if (rows[index] && rows[index].type === "text") {

            rows[index] = buildExtraTextRowFromField(field, getInlineText()

                ? getInlineText().getHeaderHtml(field)

                : field.innerHTML);

        }

        rows.splice(index + 1, 0, { type: "rule" }, { ...DEFAULT_EXTRA_TEXT_ROW });

        appendTrailingEmptyRowIfNeeded(rows);

        await recordImmediateHeaderLayoutChange(async () => {

            const data = await patchPageLayout(payload);

            replaceHeaderHtml(data.html || data.header_html, { preserveEditing: true });

            focusExtraTextFieldByIndex(index + 2);

        });

    }



    function toggleMutedOnCurrentExtraRow() {

        const field = getActiveHeaderTextField();

        if (!isExtraHeaderTextField(field)) {

            return;

        }

        toggleExtraRowMuted(field, null);

    }



    async function handleExtraRowHorizontalRuleShortcut(textField, index, beforeHtml, afterHtml) {

        const helpers = getInlineText();

        const trimmedBefore = helpers

            ? helpers.removeLastLineFromHtml(beforeHtml)

            : beforeHtml;

        const rowEmptied = helpers

            ? helpers.isEmptyHtml(trimmedBefore)

            : !trimmedBefore.trim();

        const root = document.getElementById("report-page-header-root");

        const payload = buildPageLayoutPayload(root);

        const rows = payload.page_layout.header.extra_rows;

        const trailingTextRow = {

            ...DEFAULT_EXTRA_TEXT_ROW,

            text: afterHtml || "",

            align: textField.dataset.textAlign || "left",

            indent_level: Number.parseInt(textField.dataset.indentLevel || "0", 10) || 0,

            first_line_indent: textField.dataset.firstLineIndent === "true",

            muted: textField.dataset.muted === "true",

        };

        if (rowEmptied) {

            rows[index] = { type: "rule" };

            rows.splice(index + 1, 0, trailingTextRow);

        } else {

            rows[index] = buildExtraTextRowFromField(textField, trimmedBefore);

            rows.splice(index + 1, 0, { type: "rule" }, trailingTextRow);

        }

        appendTrailingEmptyRowIfNeeded(rows);

        await recordImmediateHeaderLayoutChange(async () => {

            const data = await patchPageLayout(payload);

            replaceHeaderHtml(data.html || data.header_html, { preserveEditing: true });

            const focusIndex = rowEmptied ? index + 1 : index + 2;

            focusExtraTextFieldByIndex(focusIndex);

        });

    }



    async function handleExtraRowEnter(textField) {

        const helpers = getInlineText();

        const splitResult = helpers

            ? helpers.splitHtmlAtSelection(textField)

            : { beforeHtml: textField.innerHTML, afterHtml: "" };

        const rowElement = textField.closest("[data-report-page-header-extra-row]");

        const index = Number.parseInt(rowElement?.dataset.extraRowIndex || "0", 10);

        if (

            helpers

            && isHorizontalRuleShortcutLine(helpers.getLastLinePlainTextFromHtml(splitResult.beforeHtml))

        ) {

            await handleExtraRowHorizontalRuleShortcut(

                textField,

                index,

                splitResult.beforeHtml,

                splitResult.afterHtml

            );

            return;

        }

        const root = document.getElementById("report-page-header-root");

        const payload = buildPageLayoutPayload(root);

        const rows = payload.page_layout.header.extra_rows;

        if (!rows[index] || rows[index].type !== "text") {

            return;

        }

        rows[index] = buildExtraTextRowFromField(textField, splitResult.beforeHtml);

        rows.splice(

            index + 1,

            0,

            buildExtraTextRowFromField(textField, splitResult.afterHtml || "")

        );

        appendTrailingEmptyRowIfNeeded(rows);

        await recordImmediateHeaderLayoutChange(async () => {

            const data = await patchPageLayout(payload);

            replaceHeaderHtml(data.html || data.header_html, { preserveEditing: true });

            focusExtraTextFieldByIndex(index + 1);

        });

    }



    async function handleExtraRowBackspace(textField, event) {

        if (getCaretOffset(textField) !== 0) {

            return;

        }

        if (!isHeaderFieldEmpty(textField)) {

            return;

        }

        event.preventDefault();

        const rowElement = textField.closest("[data-report-page-header-extra-row]");

        const index = Number.parseInt(rowElement?.dataset.extraRowIndex || "0", 10);

        const root = document.getElementById("report-page-header-root");

        const payload = buildPageLayoutPayload(root);

        const rows = payload.page_layout.header.extra_rows;

        const prevRow = index > 0 ? rows[index - 1] : null;

        if (prevRow && prevRow.type === "rule") {

            rows.splice(index - 1, 1);

            payload.page_layout.header.extra_rows = rows;

            await recordImmediateHeaderLayoutChange(async () => {

                const data = await patchPageLayout(payload);

                replaceHeaderHtml(data.html || data.header_html, { preserveEditing: true });

                focusExtraTextFieldByIndex(index - 1);

            });

            return;

        }

        if (rows.length <= 1) {

            return;

        }

        rows.splice(index, 1);

        appendTrailingEmptyRowIfNeeded(rows);

        payload.page_layout.header.extra_rows = rows;

        await recordImmediateHeaderLayoutChange(async () => {

            const data = await patchPageLayout(payload);

            replaceHeaderHtml(data.html || data.header_html, { preserveEditing: true });

            let focusIndex = index - 1;

            while (focusIndex >= 0 && rows[focusIndex]?.type === "rule") {

                focusIndex -= 1;

            }

            if (focusIndex >= 0 && rows[focusIndex]?.type === "text") {

                focusExtraTextFieldByIndex(focusIndex, { atEnd: true });

            } else {

                focusExtraTextFieldByIndex(rows.length - 1);

            }

        });

    }



    async function addExtraTextRow() {

        await mutateHeaderExtraRows((rows) => {

            rows.push({ ...DEFAULT_EXTRA_TEXT_ROW });

        });

        const root = document.getElementById("report-page-header-root");

        if (!root) {

            return;

        }

        const textField = root.querySelector("[data-report-page-header-extra-text]:last-of-type");

        if (textField) {

            lastFocusedTextField = textField;

            placeCaretAtStart(textField);

        }

    }



    async function removeExtraRow(index) {

        await mutateHeaderExtraRows((rows) => {

            rows.splice(index, 1);

        });

    }



    function toggleExtraRowMuted(textField, toggleButton) {

        if (!textField) {

            return;

        }

        const muted = textField.dataset.muted !== "true";

        textField.dataset.muted = muted ? "true" : "false";

        textField.classList.toggle("report-page-header-extra-text--muted", muted);

        if (toggleButton) {

            toggleButton.classList.toggle("active", muted);

            toggleButton.setAttribute("aria-pressed", muted ? "true" : "false");

        }

        scheduleHeaderSave();

    }



    function bindHeaderTextField(field) {

        field.addEventListener("beforeinput", () => {

            if (isEditing) {

                beginHeaderLayoutRecording();

            }

        });

        field.addEventListener("focusin", () => {

            lastFocusedTextField = field;

            beginHeaderLayoutRecording();

        });

        field.addEventListener("input", scheduleHeaderSave);



        field.addEventListener("keydown", (event) => {

            if (!isEditing) {

                return;

            }

            if (event.key === "Enter" && !event.shiftKey) {

                if (field.matches("[data-report-page-header-extra-text]")) {

                    event.preventDefault();

                    handleExtraRowEnter(field).catch(console.error);

                    return;

                }

                event.preventDefault();

                document.execCommand("insertLineBreak");

                return;

            }

            if (event.key === "Backspace" && field.matches("[data-report-page-header-extra-text]")) {

                handleExtraRowBackspace(field, event).catch(console.error);

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



                const extraRowsArea = event.target.closest("[data-report-page-header-extra-rows]");

                const mainTextField = event.target.closest("[data-report-page-header-text]");

                const extraTextField = event.target.closest("[data-report-page-header-extra-text]");



                if (!isEditing) {

                    const focusExtraRowIndex = extraTextField

                        ? Number.parseInt(extraTextField.dataset.extraRowIndex || "0", 10)

                        : undefined;

                    enterEditMode(root, {
                        focusMainText: Boolean(mainTextField && !extraTextField),
                        focusExtraRowIndex,
                        focusTrailing: Boolean(
                            (extraRowsArea || (!mainTextField && !logoSlot)) && !extraTextField
                        ),
                    }).catch(console.error);

                    if (logoSlot && !hasLogoImage) {

                        event.preventDefault();

                        openLogoPicker(Number.parseInt(logoSlot.dataset.cellIndex || "0", 10));

                        return;

                    }

                    if (hasLogoImage && clickedLogoImage) {

                        return;

                    }

                    return;

                }



                if (extraTextField) {

                    extraTextField.focus();

                    lastFocusedTextField = extraTextField;

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

                    enterEditMode(root, { focusTrailing: true }).catch(console.error);

                }

                openLogoPicker(Number.parseInt(logoSlot.dataset.cellIndex || "0", 10));

            });

        }



        root.querySelectorAll("[data-report-page-header-text], [data-report-page-header-extra-text]").forEach(bindHeaderTextField);

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

            if (event.target.closest("[data-report-page-header-toolbar], [data-report-page-layout-toolbar]")) {

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

        flushHeaderUndoState,

        beginLayoutRecording: beginHeaderLayoutRecording,

        isEditing: () => isEditing,

        resolveHeaderTextContext,

        applyHeaderTextAlign,

        increaseTextIndent,

        decreaseTextIndent,

        toggleTextFirstLineIndent,

        getActiveHeaderTextField,

        clearLogoCell,

        isExtraHeaderTextField,

        insertExtraRuleAfterCurrent,

        toggleMutedOnCurrentExtraRow,

        isExtraTextFocused: () => {

            const field = getActiveHeaderTextField();

            return isExtraHeaderTextField(field);

        },

        replaceLayoutHtml: replaceHeaderHtml,

    };

})();


