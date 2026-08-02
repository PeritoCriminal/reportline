/**
 * Editor interativo de relatórios modulares.
 *
 * Enter divide ou insere blocos conforme posição do cursor; Shift+Enter
 * mantém quebra de linha no mesmo bloco; Backspace remove bloco vazio.
 */
(function () {
    "use strict";

    const LIST_TYPES = new Set(["ordered_list", "unordered_list"]);
    const TEXT_BLOCK_TYPES = new Set(["heading", "paragraph", "link"]);
    const IN_PLACE_CONVERTIBLE_TYPES = new Set([
        "heading",
        "paragraph",
        "ordered_list",
        "unordered_list",
    ]);
    const DEBOUNCE_MS = 1500;
    const TEXT_ALIGN_VALUES = new Set(["left", "center", "right", "justify"]);

    let config = {};
    const saveTimers = new Map();
    let lastEditorContext = null;
    let lastTableCellContext = null;
    let lastImageSelection = null;
    let lastParagraphContext = null;

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function updateNodeUrl(nodeId) {
        return config.updateNodeUrlTemplate.replace("{node_id}", nodeId);
    }

    function placeCaretAtEnd(element) {
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

    function placeCaretAtStart(element) {
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

    function getCaretOffset(element) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            return 0;
        }
        const range = selection.getRangeAt(0);
        if (!element.contains(range.startContainer)) {
            return 0;
        }
        const preRange = range.cloneRange();
        preRange.selectNodeContents(element);
        preRange.setEnd(range.startContainer, range.startOffset);
        return preRange.toString().length;
    }

    function setCaretOffset(element, offset) {
        element.focus();
        const selection = window.getSelection();
        if (!selection) {
            return;
        }

        const range = document.createRange();
        let currentOffset = 0;
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let textNode = walker.nextNode();

        while (textNode) {
            const length = textNode.textContent.length;
            if (currentOffset + length >= offset) {
                range.setStart(textNode, offset - currentOffset);
                range.collapse(true);
                selection.removeAllRanges();
                selection.addRange(range);
                return;
            }
            currentOffset += length;
            textNode = walker.nextNode();
        }

        range.selectNodeContents(element);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
    }

    function getInlineTextHelpers() {
        return window.ReportLineInlineText || null;
    }

    function getEditableHtml(editable) {
        if (!editable) {
            return "";
        }
        const helpers = getInlineTextHelpers();
        return helpers ? helpers.getHtml(editable) : editable.innerHTML;
    }

    function setEditableHtml(editable, html) {
        if (!editable) {
            return;
        }
        const helpers = getInlineTextHelpers();
        if (helpers) {
            helpers.setHtml(editable, html);
            return;
        }
        editable.innerHTML = html || "";
    }

    function getEditablePlainText(editable) {
        if (!editable) {
            return "";
        }
        const helpers = getInlineTextHelpers();
        return helpers ? helpers.getPlainText(editable) : (editable.textContent || "");
    }

    function splitEditableAtCaret(editable) {
        const helpers = getInlineTextHelpers();
        if (helpers) {
            return helpers.splitHtmlAtSelection(editable);
        }

        return {
            beforeHtml: editable ? editable.innerHTML : "",
            afterHtml: "",
        };
    }

    function getActiveBlock() {
        const context = resolveInsertContext();
        return context ? context.block : null;
    }

    function rememberEditorContext(block, editable) {
        lastEditorContext = { block, editable };
    }

    function resolveInsertContext() {
        const active = document.activeElement;
        if (active && active.closest) {
            const editable = active.closest(".report-editor-block-editable");
            const block = active.closest(".report-editor-block");
            if (block && editable && block.contains(editable)) {
                return { block, editable };
            }
            if (block) {
                return { block, editable: getTextField(block) };
            }
        }

        if (lastEditorContext && document.contains(lastEditorContext.block)) {
            return lastEditorContext;
        }

        const blocks = document.querySelectorAll("#report-editor-page .report-editor-block");
        const lastBlock = blocks.length ? blocks[blocks.length - 1] : null;
        if (!lastBlock) {
            return null;
        }
        return { block: lastBlock, editable: getTextField(lastBlock) };
    }

    function getTextField(block) {
        if (block.dataset.blockType === "image") {
            return null;
        }
        return block.querySelector('[data-field="text"]');
    }

    function isEditableEmpty(editable) {
        return getEditablePlainText(editable).trim() === "";
    }

    function collectBlockContent(block) {
        const blockType = block.dataset.blockType;

        if (TEXT_BLOCK_TYPES.has(blockType)) {
            const field = getTextField(block);
            return { text: field ? getEditableHtml(field) : "" };
        }

        if (blockType === "image") {
            const img = block.querySelector(".report-editor-block-image-img");
            return {
                alt: img ? (img.getAttribute("alt") || "") : "",
                file: block.dataset.file || "",
                image_id: block.dataset.imageId || "",
                width: Number.parseInt(block.dataset.imageWidth || "0", 10) || 0,
                height: Number.parseInt(block.dataset.imageHeight || "0", 10) || 0,
            };
        }

        if (LIST_TYPES.has(blockType)) {
            const items = Array.from(block.querySelectorAll(".report-editor-list-item")).map(
                (item) => getEditableHtml(item)
            );
            return { items };
        }

        if (blockType === "table") {
            const headers = Array.from(
                block.querySelectorAll('[data-table-part="header"]')
            ).map((cell) => ({
                text: getEditableHtml(cell),
                align: cell.dataset.textAlign || "left",
            }));
            const rows = Array.from(block.querySelectorAll("tbody tr")).map((rowElement) =>
                Array.from(rowElement.querySelectorAll("td")).map((cellElement) => {
                    const imageWrapper = cellElement.querySelector('[data-cell-type="image"]');
                    if (imageWrapper) {
                        const img = imageWrapper.querySelector("img");
                        return {
                            type: "image",
                            alt: img ? (img.getAttribute("alt") || "") : "",
                            file: imageWrapper.dataset.file || "",
                            image_id: imageWrapper.dataset.imageId || "",
                            width: Number.parseInt(imageWrapper.dataset.imageWidth || "0", 10) || 0,
                            height: Number.parseInt(imageWrapper.dataset.imageHeight || "0", 10) || 0,
                            align: imageWrapper.dataset.textAlign || "center",
                        };
                    }
                    const textCell = cellElement.querySelector('[data-table-part="cell"]');
                    return {
                        type: "text",
                        text: textCell ? getEditableHtml(textCell) : "",
                        align: textCell ? (textCell.dataset.textAlign || "left") : "left",
                    };
                })
            );
            return {
                headers,
                rows,
                show_borders: block.dataset.tableShowBorders !== "false",
                show_header: block.dataset.tableShowHeader !== "false",
                column_widths: parseTableColumnWidths(block, headers.length),
                display_width: parseTableDisplayWidth(block),
            };
        }

        return {};
    }

    function setTextFieldContent(block, text) {
        const field = getTextField(block);
        if (field) {
            setEditableHtml(field, text);
        }
    }

    async function apiRequest(url, method, body) {
        const response = await fetch(url, {
            method,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
            body: body !== undefined ? JSON.stringify(body) : undefined,
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = (data.errors && data.errors.join(" ")) || "Falha ao salvar bloco.";
            throw new Error(message);
        }
        return data;
    }

    function updateOutlineHeading(nodeId, text) {
        const label = document.querySelector(
            `.report-editor-outline-link[href="#report-block-${nodeId}"] .report-editor-outline-label`
        );
        if (label) {
            label.textContent = (text || "").trim() || "Título sem texto";
            const link = label.closest(".report-editor-outline-link");
            if (link) {
                const number = link.querySelector(".report-editor-outline-number");
                const prefix = number ? `${number.textContent.trim()} ` : "";
                link.setAttribute("title", `${prefix}${label.textContent}`.trim());
            }
        }
    }

    function refreshOutlineTree() {
        if (window.ReportLineOutline && window.ReportLineOutline.refresh) {
            return window.ReportLineOutline.refresh().catch(console.error);
        }
        return Promise.resolve();
    }

    async function saveBlock(block, options = {}) {
        const nodeId = block.dataset.nodeId;
        const content = collectBlockContent(block);
        const payload = { content };

        if (options.appendListItem) {
            payload.append_list_item = true;
            payload.items = content.items || [];
        }

        if (options.updateListItems) {
            payload.update_list_items = true;
            payload.items = options.items || content.items || [];
            delete payload.content;
        }

        const data = await apiRequest(updateNodeUrl(nodeId), "PATCH", payload);

        if (block.dataset.blockType === "heading" && content.text !== undefined) {
            updateOutlineHeading(nodeId, content.text);
        }

        return data;
    }

    function scheduleDebouncedSave(block) {
        const nodeId = block.dataset.nodeId;
        if (saveTimers.has(nodeId)) {
            clearTimeout(saveTimers.get(nodeId));
        }
        saveTimers.set(
            nodeId,
            setTimeout(() => {
                saveBlock(block).catch(console.error);
            }, DEBOUNCE_MS)
        );
    }

    function clearSaveTimer(nodeId) {
        if (saveTimers.has(nodeId)) {
            clearTimeout(saveTimers.get(nodeId));
            saveTimers.delete(nodeId);
        }
    }

    function insertBlockHtml(referenceBlock, html, insertion) {
        if (insertion === "before") {
            referenceBlock.insertAdjacentHTML("beforebegin", html);
            return referenceBlock.previousElementSibling;
        }
        referenceBlock.insertAdjacentHTML("afterend", html);
        return referenceBlock.nextElementSibling;
    }

    function focusNewBlock(newBlock, options = {}) {
        const focusTarget = newBlock.querySelector('[data-autofocus="true"]') ||
            newBlock.querySelector(".report-editor-block-editable");
        if (focusTarget) {
            if (options.caretAtStart) {
                placeCaretAtStart(focusTarget);
            } else {
                placeCaretAtEnd(focusTarget);
            }
        }
        return newBlock;
    }

    function replaceBlockFromHtml(nodeId, html) {
        const current = document.getElementById(`report-block-${nodeId}`);
        if (!current) {
            return null;
        }
        current.insertAdjacentHTML("afterend", html);
        const replacement = current.nextElementSibling;
        current.remove();
        return replacement;
    }

    function equalTableColumnWidths(columnCount) {
        if (columnCount <= 0) {
            return [];
        }
        const base = Math.floor(100 / columnCount);
        const remainder = 100 % columnCount;
        return Array.from({ length: columnCount }, (_, index) => (
            base + (index < remainder ? 1 : 0)
        ));
    }

    function parseTableColumnWidths(block, columnCount) {
        const raw = block.dataset.tableColumnWidths || "";
        if (!raw) {
            return equalTableColumnWidths(columnCount);
        }
        const widths = raw.split(",").map((part) => Number.parseInt(part.trim(), 10));
        if (widths.length !== columnCount) {
            return equalTableColumnWidths(columnCount);
        }
        return widths;
    }

    function parseTableDisplayWidth(block) {
        const raw = Number.parseInt(block.dataset.tableDisplayWidth || "0", 10);
        if (raw >= 20 && raw <= 100) {
            return raw;
        }
        return 100;
    }

    function splitTableColumnWidth(widths, colIndex) {
        const next = [...widths];
        const current = next[colIndex];
        const left = Math.floor(current / 2);
        const right = current - left;
        next[colIndex] = left;
        next.splice(colIndex + 1, 0, right);
        return next;
    }

    function mergeTableColumnWidth(widths, colIndex) {
        const next = [...widths];
        const removed = next.splice(colIndex, 1)[0];
        const targetIndex = colIndex < next.length ? colIndex : next.length - 1;
        next[targetIndex] += removed;
        return next;
    }

    function emptyTableBodyCell() {
        return { type: "text", text: "", align: "left" };
    }

    function emptyTableHeaderCell() {
        return { text: "", align: "left" };
    }

    function buildTableContent(rowCount, columnCount) {
        const rows = Math.max(1, Math.min(rowCount, 20));
        const cols = Math.max(1, Math.min(columnCount, 12));
        return {
            headers: Array.from({ length: cols }, () => emptyTableHeaderCell()),
            rows: Array(Math.max(0, rows - 1))
                .fill(null)
                .map(() => Array.from({ length: cols }, () => emptyTableBodyCell())),
            show_borders: true,
            show_header: true,
            column_widths: equalTableColumnWidths(cols),
            display_width: 100,
        };
    }

    function focusTableBlock(block) {
        const cell = block.querySelector(
            '[data-table-part="header"][data-autofocus="true"], [data-table-part="header"]'
        );
        if (cell) {
            placeCaretAtEnd(cell);
        }
    }

    function focusCaptionParagraph(paragraphBlock) {
        const field = paragraphBlock.querySelector('[data-field="text"]');
        if (field) {
            placeCaretAtEnd(field);
            rememberEditorContext(paragraphBlock, field);
        }
    }

    function syncCaptionWidthForImageBlock(imageBlock) {
        if (
            window.ReportLineImageResize
            && window.ReportLineImageResize.syncCaptionWidth
        ) {
            window.ReportLineImageResize.syncCaptionWidth(imageBlock);
        }
    }

    async function ensureCaptionParagraphAfterImage(imageBlock) {
        const nextBlock = imageBlock.nextElementSibling;
        if (nextBlock && nextBlock.dataset.isCaption === "true") {
            focusCaptionParagraph(nextBlock);
            syncCaptionWidthForImageBlock(imageBlock);
            return nextBlock;
        }

        const captionBlock = await createSiblingBlock(imageBlock, "paragraph", {
            content: { text: "" },
            isCaption: true,
            caretAtStart: true,
        });
        syncCaptionWidthForImageBlock(imageBlock);
        return captionBlock;
    }

    function getListItems(block) {
        return Array.from(block.querySelectorAll(".report-editor-list-item")).map(
            (item) => getEditableHtml(item)
        );
    }

    function buildContentForBlockType(block, editable, targetBlockType) {
        const sourceType = block.dataset.blockType;

        if (LIST_TYPES.has(targetBlockType)) {
            if (LIST_TYPES.has(sourceType)) {
                const items = getListItems(block);
                return { items: items.length ? items : [""] };
            }
            if (TEXT_BLOCK_TYPES.has(sourceType)) {
                const field = editable || getTextField(block);
                const text = field ? getEditablePlainText(field) : "";
                const lines = text.split("\n");
                return { items: lines.length ? lines : [""] };
            }
        }

        if (targetBlockType === "paragraph") {
            if (TEXT_BLOCK_TYPES.has(sourceType)) {
                const field = editable || getTextField(block);
                return { text: field ? getEditableHtml(field) : "" };
            }
            if (LIST_TYPES.has(sourceType)) {
                const items = getListItems(block);
                return { text: items.join("\n") };
            }
        }

        if (targetBlockType === "heading") {
            if (TEXT_BLOCK_TYPES.has(sourceType)) {
                const field = editable || getTextField(block);
                return { text: field ? getEditableHtml(field) : "" };
            }
            if (LIST_TYPES.has(sourceType)) {
                const items = getListItems(block);
                const text = items.map((item) => item.trim()).filter(Boolean).join(" ");
                return { text: text || items[0] || "" };
            }
        }

        return collectBlockContent(block);
    }

    function focusConvertedBlock(block, targetBlockType, options = {}) {
        if (TEXT_BLOCK_TYPES.has(targetBlockType)) {
            const field = block.querySelector('[data-field="text"]');
            if (!field) {
                return;
            }
            const caret = options.caret ?? getEditablePlainText(field).length;
            setCaretOffset(field, Math.min(caret, getEditablePlainText(field).length));
            return;
        }

        if (LIST_TYPES.has(targetBlockType)) {
            const items = block.querySelectorAll(".report-editor-list-item");
            const target = items[options.listItemIndex ?? 0] || items[0];
            if (target) {
                const caret = options.caret;
                if (caret !== undefined) {
                    setCaretOffset(target, Math.min(caret, getEditablePlainText(target).length));
                } else {
                    placeCaretAtEnd(target);
                }
            }
        }
    }

    async function convertBlockInPlace(block, editable, targetBlockType, options = {}) {
        const sourceType = block.dataset.blockType;

        if (
            sourceType === targetBlockType
            && targetBlockType !== "heading"
        ) {
            if (editable) {
                placeCaretAtEnd(editable);
            }
            return block;
        }

        if (
            targetBlockType === "heading"
            && sourceType === "heading"
            && options.titleLevel !== undefined
            && Number.parseInt(block.dataset.titleLevel, 10) === options.titleLevel
        ) {
            if (editable) {
                placeCaretAtEnd(editable);
            }
            return block;
        }

        clearSaveTimer(block.dataset.nodeId);

        const nodeId = block.dataset.nodeId;
        const content = buildContentForBlockType(block, editable, targetBlockType);
        const focusOptions = {};

        if (TEXT_BLOCK_TYPES.has(sourceType) && editable) {
            focusOptions.caret = getCaretOffset(editable);
        } else if (
            LIST_TYPES.has(sourceType)
            && editable
            && editable.classList.contains("report-editor-list-item")
        ) {
            focusOptions.listItemIndex = getListItemIndex(editable);
            focusOptions.caret = getCaretOffset(editable);
        }

        const payload = {
            content,
            block_type: targetBlockType,
            text_align: defaultTextAlignForBlock(
                targetBlockType,
                {
                    isMainTitle: targetBlockType === "heading" && isMainTitleHeading(block),
                    isCaption: block.dataset.isCaption === "true",
                }
            ),
        };
        if (targetBlockType === "heading" && options.titleLevel !== undefined) {
            payload.title_level = options.titleLevel;
        }

        const data = await apiRequest(updateNodeUrl(nodeId), "PATCH", payload);

        let targetBlock = block;
        if (data.html) {
            targetBlock = replaceBlockFromHtml(nodeId, data.html) || block;
        } else {
            block.dataset.blockType = targetBlockType;
            if (targetBlockType === "heading" && options.titleLevel !== undefined) {
                block.dataset.titleLevel = String(options.titleLevel);
            }
            if (data.text_align) {
                block.dataset.textAlign = data.text_align;
            }
        }

        focusConvertedBlock(targetBlock, targetBlockType, focusOptions);

        if (sourceType === "heading" || targetBlockType === "heading") {
            await refreshOutlineTree();
        }

        return targetBlock;
    }

    function buildNewBlockContent(blockType, text, options = {}) {
        if (blockType === "table") {
            if (options.content) {
                return options.content;
            }
            return buildTableContent(
                options.tableRows ?? 2,
                options.tableCols ?? 2
            );
        }
        if (LIST_TYPES.has(blockType)) {
            return { items: [text || ""] };
        }
        return { text: text || "" };
    }

    async function patchBlockStructure(block, targetBlockType, content, options = {}) {
        const nodeId = block.dataset.nodeId;
        const payload = {
            content,
            block_type: targetBlockType,
            text_align: defaultTextAlignForBlock(
                targetBlockType,
                {
                    isMainTitle: targetBlockType === "heading" && isMainTitleHeading(block),
                    isCaption: block.dataset.isCaption === "true",
                }
            ),
        };
        if (targetBlockType === "heading" && options.titleLevel !== undefined) {
            payload.title_level = options.titleLevel;
        }

        const data = await apiRequest(updateNodeUrl(nodeId), "PATCH", payload);

        let targetBlock = block;
        if (data.html) {
            targetBlock = replaceBlockFromHtml(nodeId, data.html) || block;
        }

        return targetBlock;
    }

    async function insertBlockFromListCursor(block, activeItem, newBlockType, options = {}) {
        clearSaveTimer(block.dataset.nodeId);

        const listBlockType = block.dataset.blockType;
        const items = getListItems(block);
        const index = getListItemIndex(activeItem);
        const caret = getCaretOffset(activeItem);
        const text = getEditablePlainText(activeItem);
        const atStart = caret === 0;
        const atEnd = caret >= text.length;

        let beforeItems;
        let newBlockContent;
        let afterItems;

        if (atStart) {
            beforeItems = items.slice(0, index);
            afterItems = items.slice(index);
            newBlockContent = options.content
                ?? buildNewBlockContent(newBlockType, "", options);
        } else if (atEnd) {
            beforeItems = items.slice(0, index + 1);
            afterItems = items.slice(index + 1);
            newBlockContent = options.content
                ?? buildNewBlockContent(newBlockType, "", options);
        } else {
            const { beforeHtml, afterHtml } = splitEditableAtCaret(activeItem);
            beforeItems = items.slice(0, index).concat(beforeHtml);
            afterItems = items.slice(index + 1);
            newBlockContent = options.content
                ?? buildNewBlockContent(newBlockType, afterHtml, options);
        }

        const needsHeadingRefresh = newBlockType === "heading";

        if (beforeItems.length === 0) {
            const convertedBlock = await patchBlockStructure(
                block,
                newBlockType,
                newBlockContent,
                options
            );
            focusConvertedBlock(convertedBlock, newBlockType, {
                caret: !atStart && !atEnd ? 0 : undefined,
                listItemIndex: 0,
            });

            if (newBlockType === "table") {
                focusTableBlock(convertedBlock);
            }

            if (afterItems.length > 0) {
                await createSiblingBlock(convertedBlock, listBlockType, {
                    content: { items: afterItems },
                });
            }

            if (needsHeadingRefresh) {
                await refreshOutlineTree();
            }
            return convertedBlock;
        }

        await saveBlock(block, { updateListItems: true, items: beforeItems });
        rebuildListItems(block, beforeItems);

        const insertOptions = siblingInsertOptions(options, {
            content: newBlockContent,
            caretAtStart: !atStart && !atEnd,
        });
        const newBlock = await createSiblingBlock(block, newBlockType, insertOptions);

        if (newBlockType === "table") {
            focusTableBlock(newBlock);
        }

        if (afterItems.length > 0) {
            await createSiblingBlock(newBlock, listBlockType, {
                content: { items: afterItems },
            });
        }

        if (needsHeadingRefresh) {
            await refreshOutlineTree();
        }

        return newBlock;
    }

    function isListItemEditable(editable) {
        return Boolean(
            editable && editable.classList.contains("report-editor-list-item")
        );
    }

    function getParagraphElement(block) {
        if (!block) {
            return null;
        }
        return block.querySelector(".report-editor-block-paragraph");
    }

    function hasParagraphFirstLineIndent(block) {
        const paragraph = getParagraphElement(block);
        if (!paragraph) {
            return true;
        }
        return paragraph.dataset.firstLineIndent !== "false";
    }

    function paragraphLayoutFromReference(referenceBlock, options = {}) {
        const layout = {};
        if (options.indentLevel !== undefined) {
            layout.indentLevel = options.indentLevel;
        } else if (referenceBlock.dataset.blockType === "paragraph" && !options.isCaption) {
            layout.indentLevel = getParagraphIndentLevel(referenceBlock);
        }
        if (options.firstLineIndent !== undefined) {
            layout.firstLineIndent = options.firstLineIndent;
        } else if (referenceBlock.dataset.blockType === "paragraph" && !options.isCaption) {
            layout.firstLineIndent = hasParagraphFirstLineIndent(referenceBlock);
        }
        return layout;
    }

    async function createSiblingBlock(referenceBlock, blockType, options = {}) {
        const payload = {
            block_type: blockType || undefined,
            content: options.content,
        };
        if (options.titleLevel !== undefined) {
            payload.title_level = options.titleLevel;
        }
        if (options.isCaption !== undefined) {
            payload.is_caption = options.isCaption;
        }
        if (options.insertion === "before") {
            payload.before_node_id = referenceBlock.dataset.nodeId;
        } else {
            payload.after_node_id = referenceBlock.dataset.nodeId;
        }

        if (blockType === "paragraph") {
            const layout = paragraphLayoutFromReference(referenceBlock, options);
            if (layout.indentLevel !== undefined) {
                payload.indent_level = layout.indentLevel;
            }
            if (layout.firstLineIndent !== undefined) {
                payload.first_line_indent = layout.firstLineIndent;
            }
        }

        const data = await apiRequest(config.createNodeUrl, "POST", payload);
        const newBlock = insertBlockHtml(referenceBlock, data.html, data.insertion);
        focusNewBlock(newBlock, { caretAtStart: options.caretAtStart });
        if (data.block_type === "heading") {
            await refreshOutlineTree();
        }
        return newBlock;
    }

    function getListItemIndex(listItem) {
        const items = Array.from(
            listItem.closest("[data-field=\"items\"]").querySelectorAll(".report-editor-list-item")
        );
        return items.indexOf(listItem);
    }

    function rebuildListItems(block, items) {
        const list = block.querySelector("[data-field=\"items\"]");
        list.innerHTML = "";
        items.forEach((text, index) => {
            const item = document.createElement("li");
            item.className = "report-editor-block-editable report-editor-list-item";
            item.contentEditable = "true";
            item.dataset.listIndex = String(index);
            item.dataset.placeholder = "Item da lista";
            setEditableHtml(item, text);
            list.appendChild(item);
        });
    }

    async function handleListEnter(block, activeItem) {
        clearSaveTimer(block.dataset.nodeId);
        const items = getListItems(block);
        const index = getListItemIndex(activeItem);
        const caret = getCaretOffset(activeItem);
        const text = getEditablePlainText(activeItem);
        const atStart = caret === 0;
        const atEnd = caret >= text.length;

        if (atStart) {
            items.splice(index, 0, "");
            await saveBlock(block, { updateListItems: true, items });
            rebuildListItems(block, items);
            const newItem = block.querySelectorAll(".report-editor-list-item")[index];
            placeCaretAtEnd(newItem);
            return;
        }

        if (!atEnd) {
            const { beforeHtml, afterHtml } = splitEditableAtCaret(activeItem);
            items[index] = beforeHtml;
            items.splice(index + 1, 0, afterHtml);
            await saveBlock(block, { updateListItems: true, items });
            rebuildListItems(block, items);
            const nextItem = block.querySelectorAll(".report-editor-list-item")[index + 1];
            placeCaretAtStart(nextItem);
            return;
        }

        await saveBlock(block, { appendListItem: true });
        const newItem = document.createElement("li");
        newItem.className = "report-editor-block-editable report-editor-list-item";
        newItem.contentEditable = "true";
        newItem.dataset.listIndex = String(items.length);
        newItem.dataset.placeholder = "Item da lista";
        block.querySelector("[data-field=\"items\"]").appendChild(newItem);
        placeCaretAtEnd(newItem);
    }

    function siblingInsertOptions(options, extra = {}) {
        const merged = { ...extra };
        if (options.titleLevel !== undefined) {
            merged.titleLevel = options.titleLevel;
        }
        return merged;
    }

    async function insertBlockAtCaret(block, editable, newBlockType, options = {}) {
        clearSaveTimer(block.dataset.nodeId);
        const tableContent = newBlockType === "table"
            ? (options.content || buildTableContent(options.tableRows ?? 2, options.tableCols ?? 2))
            : null;
        const imageContent = newBlockType === "image" ? options.content : null;
        const blockContent = imageContent ?? tableContent ?? options.content;

        if (LIST_TYPES.has(block.dataset.blockType)) {
            await saveBlock(block);
            return createSiblingBlock(
                block,
                newBlockType,
                siblingInsertOptions(options, { content: blockContent })
            );
        }

        if (block.dataset.blockType === "image" || block.dataset.blockType === "table") {
            await saveBlock(block);
            const newBlock = await createSiblingBlock(
                block,
                newBlockType,
                siblingInsertOptions(options, { content: blockContent })
            );
            if (newBlockType === "table") {
                focusTableBlock(newBlock);
            }
            return newBlock;
        }

        if (TEXT_BLOCK_TYPES.has(block.dataset.blockType) && editable) {
            const fullText = getEditablePlainText(editable);
            const caret = getCaretOffset(editable);
            const atStart = caret === 0;
            const atEnd = caret >= fullText.length;

            if (newBlockType === "table" || newBlockType === "image") {
                const insertContent = newBlockType === "table" ? tableContent : imageContent;
                if (atStart) {
                    const insertedBlock = await createSiblingBlock(
                        block,
                        newBlockType,
                        siblingInsertOptions(options, {
                            insertion: "before",
                            content: insertContent,
                        })
                    );
                    if (newBlockType === "table") {
                        focusTableBlock(insertedBlock);
                    }
                    return insertedBlock;
                }

                if (!atEnd) {
                    const { beforeHtml, afterHtml } = splitEditableAtCaret(editable);
                    setTextFieldContent(block, beforeHtml);
                    await saveBlock(block);
                    setEditableHtml(editable, beforeHtml);
                    const insertedBlock = await createSiblingBlock(
                        block,
                        newBlockType,
                        siblingInsertOptions(options, { content: insertContent })
                    );
                    if (newBlockType === "table") {
                        focusTableBlock(insertedBlock);
                    }
                    if (afterHtml) {
                        await createSiblingBlock(insertedBlock, "paragraph", {
                            content: { text: afterHtml },
                            caretAtStart: true,
                            isCaption: false,
                        });
                    }
                    return insertedBlock;
                }

                const insertedBlock = await createSiblingBlock(
                    block,
                    newBlockType,
                    siblingInsertOptions(options, { content: insertContent })
                );
                if (newBlockType === "table") {
                    focusTableBlock(insertedBlock);
                }
                return insertedBlock;
            }

            if (atStart) {
                await createSiblingBlock(
                    block,
                    newBlockType,
                    siblingInsertOptions(options, {
                        insertion: "before",
                        content: { text: "" },
                    })
                );
                if (options.keepFocusInPlace) {
                    placeCaretAtStart(editable);
                }
                return;
            }

            if (!atEnd) {
                const { beforeHtml, afterHtml } = splitEditableAtCaret(editable);
                setTextFieldContent(block, beforeHtml);
                await saveBlock(block);
                setEditableHtml(editable, beforeHtml);
                await createSiblingBlock(
                    block,
                    newBlockType,
                    siblingInsertOptions(options, {
                        insertion: "after",
                        content: { text: afterHtml },
                        caretAtStart: true,
                    })
                );
                return;
            }
        }

        await saveBlock(block);
        const newBlock = await createSiblingBlock(
            block,
            newBlockType,
            siblingInsertOptions(options, { content: blockContent })
        );
        if (newBlockType === "table") {
            focusTableBlock(newBlock);
        }
        return newBlock;
    }

    function isTableBodyCellEditable(editable) {
        return Boolean(
            editable
            && editable.classList.contains("report-editor-table-cell")
            && editable.dataset.tablePart === "cell"
        );
    }

    function getTableCellUsableWidth(cellElement) {
        const cellContainer = cellElement.closest("td");
        if (!cellContainer) {
            return 0;
        }
        return Math.max(32, cellContainer.clientWidth);
    }

    function buildTableCellImageHtml(imagePayload, displayWidth, displayHeight) {
        const safeUrl = imagePayload.url || "";
        return `
            <div class="report-editor-table-cell-image"
                 data-cell-type="image"
                 data-file="${imagePayload.file || ""}"
                 data-image-id="${imagePayload.image_id || ""}"
                 data-image-width="${displayWidth}"
                 data-image-height="${displayHeight}"
                 data-text-align="center"
                 style="text-align: center;">
                <div class="report-editor-table-cell-image-frame">
                    <img src="${safeUrl}"
                         alt="${imagePayload.alt || ""}"
                         class="report-editor-table-cell-img"
                         width="${displayWidth}"
                         height="${displayHeight}"
                         style="width: ${displayWidth}px; height: ${displayHeight}px;"
                         draggable="false">
                    <div class="report-editor-image-resize-handles report-editor-table-cell-image-handles"
                         hidden
                         aria-hidden="true">
                        <span class="report-editor-image-handle" data-handle="nw"></span>
                        <span class="report-editor-image-handle" data-handle="ne"></span>
                        <span class="report-editor-image-handle" data-handle="sw"></span>
                        <span class="report-editor-image-handle" data-handle="se"></span>
                    </div>
                </div>
            </div>
        `;
    }

    function computeImageSizeForCell(imagePayload, usableWidth) {
        const sourceWidth = imagePayload.width || 1;
        const sourceHeight = imagePayload.height || 1;
        const aspectRatio = sourceWidth / sourceHeight;
        const displayWidth = Math.max(32, usableWidth);
        const displayHeight = Math.max(1, Math.round(displayWidth / aspectRatio));
        return { width: displayWidth, height: displayHeight };
    }

    async function insertImageInTableCell(block, cellElement, imagePayload) {
        clearSaveTimer(block.dataset.nodeId);
        const cellContainer = cellElement.closest("td");
        if (!cellContainer) {
            return null;
        }

        cellContainer.classList.add("report-editor-table-cell-has-image");
        const usableWidth = getTableCellUsableWidth(cellElement);
        const displaySize = computeImageSizeForCell(imagePayload, usableWidth);
        cellContainer.innerHTML = buildTableCellImageHtml(
            imagePayload,
            displaySize.width,
            displaySize.height
        );
        await saveBlock(block);
        return block;
    }

    async function insertImageAtCursor(imagePayload) {
        const context = resolveInsertContext();
        if (!context || !context.block) {
            return null;
        }

        if (
            context.block.dataset.blockType === "table"
            && isTableBodyCellEditable(context.editable)
        ) {
            return insertImageInTableCell(
                context.block,
                context.editable,
                imagePayload
            );
        }

        const content = {
            alt: imagePayload.alt || "",
            file: imagePayload.file || "",
            image_id: imagePayload.image_id || "",
            width: imagePayload.width || 0,
            height: imagePayload.height || 0,
        };
        const options = { content };
        const sourceType = context.block.dataset.blockType;
        let imageBlock = null;

        if (
            LIST_TYPES.has(sourceType)
            && isListItemEditable(context.editable)
        ) {
            imageBlock = await insertBlockFromListCursor(
                context.block,
                context.editable,
                "image",
                options
            );
        } else {
            imageBlock = await insertBlockAtCaret(
                context.block,
                context.editable,
                "image",
                options
            );
        }

        if (imageBlock) {
            await ensureCaptionParagraphAfterImage(imageBlock);
        }
        return imageBlock;
    }

    async function insertTableAtCursor(rowCount, columnCount) {
        const context = resolveInsertContext();
        if (!context || !context.block) {
            return null;
        }

        const content = buildTableContent(rowCount, columnCount);
        const options = {
            content,
            tableRows: rowCount,
            tableCols: columnCount,
        };
        const sourceType = context.block.dataset.blockType;

        if (
            LIST_TYPES.has(sourceType)
            && isListItemEditable(context.editable)
        ) {
            return insertBlockFromListCursor(
                context.block,
                context.editable,
                "table",
                options
            );
        }

        return insertBlockAtCaret(
            context.block,
            context.editable,
            "table",
            options
        );
    }

    async function handleTextBlockEnter(block, editable) {
        const blockType = block.dataset.blockType;
        const newBlockType = blockType === "heading"
            ? "paragraph"
            : blockType;
        await insertBlockAtCaret(block, editable, newBlockType, { keepFocusInPlace: true });
    }

    async function handleBlockEnter(block, editable) {
        if (LIST_TYPES.has(block.dataset.blockType)) {
            await handleListEnter(block, editable);
            return;
        }
        if (TEXT_BLOCK_TYPES.has(block.dataset.blockType)) {
            await handleTextBlockEnter(block, editable);
            return;
        }
        if (block.dataset.blockType === "image") {
            clearSaveTimer(block.dataset.nodeId);
            await saveBlock(block);
            await ensureCaptionParagraphAfterImage(block);
            return;
        }

        clearSaveTimer(block.dataset.nodeId);
        await saveBlock(block);
        await createSiblingBlock(block, "paragraph");
    }

    async function deleteBlockById(block) {
        const nodeId = block.dataset.nodeId;
        clearSaveTimer(nodeId);
        await apiRequest(updateNodeUrl(nodeId), "DELETE");
        block.remove();
    }

    async function clearTableCellImage(selectedTarget) {
        const tableBlock = selectedTarget.tableBlock;
        const cellImage = selectedTarget.root;
        const cellContainer = cellImage.closest("td");
        if (!tableBlock || !cellContainer) {
            return;
        }

        if (window.ReportLineImageResize && window.ReportLineImageResize.deselectTarget) {
            window.ReportLineImageResize.deselectTarget();
        }

        const rowIndex = cellContainer.dataset.rowIndex || "0";
        const colIndex = cellContainer.dataset.colIndex || "0";
        cellContainer.classList.remove("report-editor-table-cell-has-image");
        cellContainer.innerHTML = `
            <div class="report-editor-block-editable report-editor-table-cell"
                 contenteditable="true"
                 data-table-part="cell"
                 data-row-index="${rowIndex}"
                 data-col-index="${colIndex}"
                 data-text-align="left"
                 data-placeholder="Célula"></div>
        `;
        clearSaveTimer(tableBlock.dataset.nodeId);
        await saveBlock(tableBlock);
        const textCell = cellContainer.querySelector('[data-table-part="cell"]');
        if (textCell) {
            placeCaretAtEnd(textCell);
            rememberEditorContext(tableBlock, textCell);
        }
    }

    async function deleteSelectedImage() {
        if (!window.ReportLineImageResize || !window.ReportLineImageResize.getSelectedTarget) {
            return false;
        }

        const selectedTarget = window.ReportLineImageResize.getSelectedTarget();
        if (!selectedTarget) {
            return false;
        }

        if (selectedTarget.type === "table-cell") {
            await clearTableCellImage(selectedTarget);
            return true;
        }

        const imageBlock = selectedTarget.root;
        if (window.ReportLineImageResize.deselectTarget) {
            window.ReportLineImageResize.deselectTarget();
        }

        const captionBlock = imageBlock.nextElementSibling;
        const hasCaption = captionBlock && captionBlock.dataset.isCaption === "true";
        const previousBlock = imageBlock.previousElementSibling;

        if (hasCaption) {
            await deleteBlockById(captionBlock);
        }
        await deleteBlockById(imageBlock);

        if (previousBlock && previousBlock.classList.contains("report-editor-block")) {
            const editable = previousBlock.querySelector(".report-editor-block-editable");
            if (editable) {
                placeCaretAtEnd(editable);
                rememberEditorContext(previousBlock, editable);
            }
        }
        return true;
    }

    async function deleteEmptyBlock(block) {
        const nodeId = block.dataset.nodeId;
        clearSaveTimer(nodeId);

        const previousBlock = block.previousElementSibling;
        const blockType = block.dataset.blockType;

        await apiRequest(updateNodeUrl(nodeId), "DELETE");

        block.remove();
        if (blockType === "heading") {
            await refreshOutlineTree();
        }

        if (previousBlock && previousBlock.classList.contains("report-editor-block")) {
            const editable = previousBlock.querySelector(".report-editor-block-editable");
            if (editable) {
                placeCaretAtEnd(editable);
            }
        }
    }

    async function handleListBackspace(block, activeItem) {
        const items = getListItems(block);
        const index = getListItemIndex(activeItem);

        if (items.length <= 1) {
            if (isEditableEmpty(activeItem)) {
                await deleteEmptyBlock(block);
            }
            return;
        }

        if (!isEditableEmpty(activeItem) || getCaretOffset(activeItem) !== 0) {
            return;
        }

        items.splice(index, 1);
        clearSaveTimer(block.dataset.nodeId);
        await saveBlock(block, { updateListItems: true, items });
        rebuildListItems(block, items);
        const focusIndex = Math.max(index - 1, 0);
        const target = block.querySelectorAll(".report-editor-list-item")[focusIndex];
        if (target) {
            placeCaretAtEnd(target);
        }
    }

    async function handleBackspace(block, editable) {
        if (getCaretOffset(editable) !== 0 || !isEditableEmpty(editable)) {
            return;
        }

        if (LIST_TYPES.has(block.dataset.blockType) &&
            editable.classList.contains("report-editor-list-item")) {
            await handleListBackspace(block, editable);
            return;
        }

        await deleteEmptyBlock(block);
    }

    function isMainTitleHeading(block) {
        if (!block) {
            return false;
        }
        if (block.dataset.blockType !== "heading") {
            const page = document.getElementById("report-editor-page");
            return !page || !page.querySelector('.report-editor-block[data-block-type="heading"]');
        }
        return block.dataset.isMainTitle === "true";
    }

    function defaultTextAlignForBlock(blockType, options = {}) {
        const isCaption = Boolean(options.isCaption);
        const isMainTitle = Boolean(options.isMainTitle);

        if (blockType === "heading") {
            return isMainTitle ? "center" : "left";
        }
        if (blockType === "paragraph") {
            return isCaption ? "center" : "justify";
        }
        if (LIST_TYPES.has(blockType)) {
            return "left";
        }
        if (blockType === "image") {
            return "center";
        }
        if (blockType === "link") {
            return "justify";
        }
        return "left";
    }

    function applyTextAlignToBlock(block, align) {
        if (!TEXT_ALIGN_VALUES.has(align)) {
            return;
        }
        block.dataset.textAlign = align;
    }

    function applyTextAlignToTableTarget(target, align) {
        if (!TEXT_ALIGN_VALUES.has(align) || !target) {
            return;
        }
        target.dataset.textAlign = align;
        target.style.textAlign = align;
    }

    function resolveAlignmentContext() {
        if (window.ReportLineImageResize && window.ReportLineImageResize.getSelectedTarget) {
            const selectedTarget = window.ReportLineImageResize.getSelectedTarget();
            if (selectedTarget && selectedTarget.type === "block") {
                return { kind: "block", block: selectedTarget.root };
            }
            if (selectedTarget && selectedTarget.type === "table-cell") {
                return {
                    kind: "table-cell-image",
                    block: selectedTarget.tableBlock,
                    target: selectedTarget.root,
                };
            }
        }

        const active = document.activeElement;
        if (active && active.closest) {
            if (
                window.ReportLinePageHeader
                && window.ReportLinePageHeader.isEditing()
                && active.matches("[data-report-page-header-text][contenteditable='true']")
            ) {
                return {
                    kind: "page-header-text",
                    target: active,
                };
            }

            const tableCell = active.closest(".report-editor-table-cell[data-table-part]");
            if (tableCell) {
                const block = tableCell.closest('.report-editor-block[data-block-type="table"]');
                if (block) {
                    return { kind: "table-cell", block, target: tableCell };
                }
            }

            const block = active.closest(".report-editor-block");
            if (block) {
                return { kind: "block", block };
            }
        }

        const insertContext = resolveInsertContext();
        if (insertContext && insertContext.block) {
            if (insertContext.block.dataset.blockType === "table" && insertContext.editable) {
                const tablePart = insertContext.editable.dataset.tablePart;
                if (tablePart === "header" || tablePart === "cell") {
                    return {
                        kind: "table-cell",
                        block: insertContext.block,
                        target: insertContext.editable,
                    };
                }
            }
            return { kind: "block", block: insertContext.block };
        }

        if (window.ReportLinePageHeader && window.ReportLinePageHeader.resolveHeaderTextContext) {
            const headerContext = window.ReportLinePageHeader.resolveHeaderTextContext();
            if (headerContext) {
                return {
                    kind: "page-header-text",
                    target: headerContext.editable,
                };
            }
        }

        return null;
    }

    function getCurrentTextAlign(context) {
        if (!context) {
            return null;
        }
        if (context.kind === "page-header-text") {
            return context.target.dataset.textAlign || "left";
        }
        if (context.kind === "table-cell" || context.kind === "table-cell-image") {
            return context.target.dataset.textAlign
                || (context.kind === "table-cell-image" ? "center" : "left");
        }
        if (context.block.dataset.blockType === "image") {
            return context.block.dataset.textAlign || "center";
        }
        return context.block.dataset.textAlign || "justify";
    }

    function updateAlignmentToolbar(activeAlign) {
        document.querySelectorAll("[data-report-text-align]").forEach((button) => {
            const isActive = button.dataset.reportTextAlign === activeAlign;
            button.classList.toggle("active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
    }

    function refreshAlignmentToolbarState() {
        updateAlignmentToolbar(getCurrentTextAlign(resolveAlignmentContext()));
    }

    async function setTextAlign(align) {
        if (!TEXT_ALIGN_VALUES.has(align)) {
            return;
        }

        const context = resolveAlignmentContext();
        if (!context) {
            return;
        }

        if (context.kind === "page-header-text") {
            if (
                window.ReportLinePageHeader
                && window.ReportLinePageHeader.applyHeaderTextAlign
            ) {
                const headerAlign = ["left", "center", "right"].includes(align) ? align : "left";
                window.ReportLinePageHeader.applyHeaderTextAlign(context.target, headerAlign);
                updateAlignmentToolbar(headerAlign);
            }
            return;
        }

        if (context.kind === "table-cell" || context.kind === "table-cell-image") {
            applyTextAlignToTableTarget(context.target, align);
            if (context.kind === "table-cell-image") {
                applyTableCellImageAlignVisual(context.target, align);
            }
            clearSaveTimer(context.block.dataset.nodeId);
            await saveBlock(context.block);
            updateAlignmentToolbar(align);
            return;
        }

        applyTextAlignToBlock(context.block, align);
        clearSaveTimer(context.block.dataset.nodeId);
        if (context.block.dataset.blockType === "image") {
            await syncCaptionWithImageAlign(context.block, align);
        }
        if (
            context.block.dataset.blockType === "table"
            && window.ReportLineTableWidthResize
            && window.ReportLineTableWidthResize.refreshTableDisplayLayout
        ) {
            window.ReportLineTableWidthResize.refreshTableDisplayLayout(context.block);
        }
        await apiRequest(updateNodeUrl(context.block.dataset.nodeId), "PATCH", {
            text_align: align,
        });
        updateAlignmentToolbar(align);
    }

    function getCaptionBlock(imageBlock) {
        const captionBlock = imageBlock.nextElementSibling;
        if (captionBlock && captionBlock.dataset.isCaption === "true") {
            return captionBlock;
        }
        return null;
    }

    function applyImageBlockAlignVisual(imageBlock, align) {
        const imageWrap = imageBlock.querySelector(".report-editor-block-image");
        const frame = imageBlock.querySelector(".report-editor-block-image-frame");
        const normalized = ["left", "center", "right"].includes(align) ? align : "center";

        if (imageWrap) {
            imageWrap.style.justifyContent = normalized === "left"
                ? "flex-start"
                : normalized === "right"
                    ? "flex-end"
                    : "center";
        }

        if (frame) {
            if (normalized === "left") {
                frame.style.marginLeft = "0";
                frame.style.marginRight = "auto";
            } else if (normalized === "right") {
                frame.style.marginLeft = "auto";
                frame.style.marginRight = "0";
            } else {
                frame.style.marginLeft = "auto";
                frame.style.marginRight = "auto";
            }
        }
    }

    function applyTableCellImageAlignVisual(cellImage, align) {
        const frame = cellImage.querySelector(".report-editor-table-cell-image-frame");
        const normalized = ["left", "center", "right"].includes(align) ? align : "center";

        if (frame) {
            if (normalized === "left") {
                frame.style.marginLeft = "0";
                frame.style.marginRight = "auto";
            } else if (normalized === "right") {
                frame.style.marginLeft = "auto";
                frame.style.marginRight = "0";
            } else {
                frame.style.marginLeft = "auto";
                frame.style.marginRight = "auto";
            }
        }
    }

    async function syncCaptionWithImageAlign(imageBlock, align) {
        if (
            window.ReportLineImageResize
            && window.ReportLineImageResize.syncCaptionLayout
        ) {
            window.ReportLineImageResize.syncCaptionLayout(imageBlock);
        }

        const captionBlock = getCaptionBlock(imageBlock);
        if (!captionBlock) {
            return;
        }

        applyTextAlignToBlock(captionBlock, align);
        await apiRequest(updateNodeUrl(captionBlock.dataset.nodeId), "PATCH", {
            text_align: align,
        });
    }

    async function setImageAlign(align, explicitTarget) {
        const IMAGE_ALIGN_VALUES = new Set(["left", "center", "right"]);
        if (!IMAGE_ALIGN_VALUES.has(align)) {
            return;
        }

        const selectedTarget = explicitTarget || resolveImageSelectionContext();
        if (!selectedTarget || !selectedTarget.root) {
            return;
        }

        if (selectedTarget.type === "block") {
            applyTextAlignToBlock(selectedTarget.root, align);
            applyImageBlockAlignVisual(selectedTarget.root, align);
            clearSaveTimer(selectedTarget.root.dataset.nodeId);
            await syncCaptionWithImageAlign(selectedTarget.root, align);
            await apiRequest(updateNodeUrl(selectedTarget.root.dataset.nodeId), "PATCH", {
                text_align: align,
            });
            selectedTarget.root.focus({ preventScroll: true });
            refreshAlignmentToolbarState();
            return;
        }

        applyTextAlignToTableTarget(selectedTarget.root, align);
        applyTableCellImageAlignVisual(selectedTarget.root, align);
        clearSaveTimer(selectedTarget.tableBlock.dataset.nodeId);
        await saveBlock(selectedTarget.tableBlock);
        selectedTarget.root.focus({ preventScroll: true });
        refreshAlignmentToolbarState();
    }

    async function setTableBlockAlign(align) {
        const TABLE_BLOCK_ALIGN_VALUES = new Set(["left", "center", "right"]);
        if (!TABLE_BLOCK_ALIGN_VALUES.has(align)) {
            return;
        }

        const context = resolveTableCellContext();
        if (!context || !context.block) {
            return;
        }

        const block = context.block;
        applyTextAlignToBlock(block, align);
        clearSaveTimer(block.dataset.nodeId);
        if (
            window.ReportLineTableWidthResize
            && window.ReportLineTableWidthResize.refreshTableDisplayLayout
        ) {
            window.ReportLineTableWidthResize.refreshTableDisplayLayout(block);
        }
        await apiRequest(updateNodeUrl(block.dataset.nodeId), "PATCH", {
            text_align: align,
        });
    }

    const MAX_PARAGRAPH_INDENT_LEVEL = 5;

    function isParagraphToolbarControl(element) {
        return Boolean(
            element
            && element.closest
            && (
                element.closest(".report-editor-toolbar-paragraph-group")
                || element.closest(".report-editor-toolbar-paragraph-menu")
            )
        );
    }

    function resolveParagraphContextFromActiveElement() {
        const active = document.activeElement;
        if (!active || !active.closest) {
            return null;
        }

        const editable = active.closest(".report-editor-block-editable");
        if (!editable) {
            return null;
        }

        const block = editable.closest(".report-editor-block");
        if (!block || block.dataset.blockType !== "paragraph") {
            return null;
        }

        if (block.dataset.isCaption === "true") {
            return null;
        }

        return { block, editable };
    }

    function rememberParagraphContext(context) {
        if (context && context.block) {
            lastParagraphContext = context;
        }
    }

    function clearParagraphContext() {
        lastParagraphContext = null;
    }

    function resolveParagraphContext() {
        const fromActive = resolveParagraphContextFromActiveElement();
        if (fromActive) {
            rememberParagraphContext(fromActive);
            return fromActive;
        }

        if (
            lastParagraphContext
            && document.contains(lastParagraphContext.block)
            && isParagraphToolbarControl(document.activeElement)
        ) {
            return lastParagraphContext;
        }

        return null;
    }

    function getParagraphIndentLevel(block) {
        const level = Number.parseInt(block.dataset.indentLevel || "0", 10);
        if (Number.isNaN(level) || level < 0) {
            return 0;
        }
        return Math.min(MAX_PARAGRAPH_INDENT_LEVEL, level);
    }

    function applyParagraphIndentVisual(block, layout) {
        if (layout.indent_level !== undefined) {
            block.dataset.indentLevel = String(layout.indent_level);
        }
        if (layout.first_line_indent !== undefined) {
            const paragraph = getParagraphElement(block);
            if (paragraph) {
                paragraph.dataset.firstLineIndent = layout.first_line_indent ? "true" : "false";
            }
        }
    }

    async function patchParagraphLayout(block, layout) {
        const payload = {};
        if (layout.indent_level !== undefined) {
            payload.indent_level = layout.indent_level;
        }
        if (layout.first_line_indent !== undefined) {
            payload.first_line_indent = layout.first_line_indent;
        }

        const data = await apiRequest(updateNodeUrl(block.dataset.nodeId), "PATCH", payload);
        applyParagraphIndentVisual(block, {
            indent_level: data.indent_level,
            first_line_indent: data.first_line_indent,
        });
        return data;
    }

    async function increaseParagraphIndent() {
        const context = resolveParagraphContext();
        if (!context) {
            return;
        }

        const current = getParagraphIndentLevel(context.block);
        if (current >= MAX_PARAGRAPH_INDENT_LEVEL) {
            return;
        }

        await patchParagraphLayout(context.block, { indent_level: current + 1 });
    }

    async function decreaseParagraphIndent() {
        const context = resolveParagraphContext();
        if (!context) {
            return;
        }

        const current = getParagraphIndentLevel(context.block);
        if (current <= 0) {
            return;
        }

        await patchParagraphLayout(context.block, { indent_level: current - 1 });
    }

    async function toggleParagraphFirstLineIndent() {
        const context = resolveParagraphContext();
        if (!context) {
            return;
        }

        const current = hasParagraphFirstLineIndent(context.block);
        await patchParagraphLayout(context.block, { first_line_indent: !current });
    }

    function bindImageDeleteShortcut() {
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Backspace" && event.key !== "Delete") {
                return;
            }
            if (
                !window.ReportLineImageResize
                || !window.ReportLineImageResize.getSelectedTarget
                || !window.ReportLineImageResize.getSelectedTarget()
            ) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            deleteSelectedImage().catch(console.error);
        }, true);
    }

    function bindEditorEvents(page) {
        bindImageDeleteShortcut();

        page.addEventListener("keydown", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
                return;
            }

            if (
                window.ReportLineImageResize
                && window.ReportLineImageResize.getSelectedTarget
                && window.ReportLineImageResize.getSelectedTarget()
            ) {
                return;
            }

            const block = editable.closest(".report-editor-block");
            if (!block) {
                return;
            }

            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleBlockEnter(block, editable).catch(console.error);
                return;
            }

            if (event.key === "Backspace") {
                if (getCaretOffset(editable) === 0 && isEditableEmpty(editable)) {
                    event.preventDefault();
                    handleBackspace(block, editable).catch(console.error);
                }
            }
        });

        page.addEventListener("input", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
                return;
            }
            const block = editable.closest(".report-editor-block");
            if (block) {
                if (block.dataset.blockType === "heading") {
                    const field = getTextField(block);
                    if (field) {
                        updateOutlineHeading(block.dataset.nodeId, getEditablePlainText(field));
                    }
                }
                scheduleDebouncedSave(block);
            }
        });

        page.addEventListener("focusin", (event) => {
            const block = event.target.closest(".report-editor-block");
            if (block) {
                block.classList.add("is-active");
                const editable = event.target.closest(".report-editor-block-editable");
                if (editable && block.contains(editable)) {
                    rememberEditorContext(block, editable);
                }
                refreshAlignmentToolbarState();
            }
        });

        page.addEventListener("click", () => {
            refreshAlignmentToolbarState();
        });

        page.addEventListener("focusout", (event) => {
            const block = event.target.closest(".report-editor-block");
            if (block && !block.contains(event.relatedTarget)) {
                block.classList.remove("is-active");
            }
        });
    }

    function bindToolbar(toolbar) {
        toolbar.addEventListener("mousedown", (event) => {
            if (
                event.target.closest("[data-insert-block-type]")
                || event.target.closest("[data-report-text-align]")
                || event.target.closest("[data-report-image-align]")
                || event.target.closest("[data-report-text-format]")
                || event.target.closest("[data-report-text-link]")
                || event.target.closest("[data-report-paragraph-indent]")
                || event.target.closest("[data-report-paragraph-first-line-indent]")
            ) {
                event.preventDefault();
            }
        });

        toolbar.addEventListener("click", (event) => {
            const alignButton = event.target.closest("[data-report-text-align]");
            if (alignButton) {
                setTextAlign(alignButton.dataset.reportTextAlign).catch(console.error);
                return;
            }

            const button = event.target.closest("[data-insert-block-type]");
            if (!button) {
                return;
            }

            const blockType = button.dataset.insertBlockType;
            const titleLevelRaw = button.dataset.titleLevel;
            const titleLevel = titleLevelRaw !== undefined && titleLevelRaw !== ""
                ? Number.parseInt(titleLevelRaw, 10)
                : 0;
            const context = resolveInsertContext();
            if (!context || !context.block) {
                return;
            }

            const sourceType = context.block.dataset.blockType;
            const insertOptions = {};
            if (titleLevelRaw !== undefined && titleLevelRaw !== "") {
                insertOptions.titleLevel = titleLevel;
            }

            if (
                LIST_TYPES.has(sourceType)
                && isListItemEditable(context.editable)
            ) {
                if (blockType === sourceType) {
                    placeCaretAtEnd(context.editable);
                    return;
                }
                insertBlockFromListCursor(
                    context.block,
                    context.editable,
                    blockType,
                    insertOptions
                ).catch(console.error);
                return;
            }

            if (
                IN_PLACE_CONVERTIBLE_TYPES.has(blockType)
                && IN_PLACE_CONVERTIBLE_TYPES.has(sourceType)
            ) {
                convertBlockInPlace(
                    context.block,
                    context.editable,
                    blockType,
                    insertOptions
                ).catch(console.error);
                return;
            }

            insertBlockAtCaret(
                context.block,
                context.editable,
                blockType,
                insertOptions
            ).catch(console.error);
        });

        refreshAlignmentToolbarState();
    }

    function focusInitialBlock(page) {
        const target = page.querySelector('[data-autofocus="true"]');
        if (target) {
            placeCaretAtEnd(target);
        }
    }

    const MAX_TABLE_BODY_ROWS = 19;
    const MAX_TABLE_COLUMNS = 12;

    function cloneTableContent(content) {
        return {
            headers: content.headers.map((header) => {
                if (header && typeof header === "object") {
                    return { ...header };
                }
                return { text: String(header ?? ""), align: "left" };
            }),
            rows: content.rows.map((row) => row.map((cell) => {
                if (cell && typeof cell === "object") {
                    return { ...cell };
                }
                return { type: "text", text: String(cell ?? "") };
            })),
            show_borders: content.show_borders !== false,
            show_header: content.show_header !== false,
            column_widths: [...(content.column_widths || equalTableColumnWidths(content.headers.length))],
            display_width: content.display_width ?? 100,
        };
    }

    function insertRowAfterContent(content, rowIndex) {
        const next = cloneTableContent(content);
        const insertAt = rowIndex < 0 ? 0 : rowIndex + 1;
        if (next.rows.length >= MAX_TABLE_BODY_ROWS) {
            throw new Error("A tabela não pode exceder 19 linhas de corpo.");
        }
        const columnCount = next.headers.length || (next.rows[0] ? next.rows[0].length : 1);
        const newRow = Array.from({ length: columnCount }, () => emptyTableBodyCell());
        next.rows.splice(insertAt, 0, newRow);
        return next;
    }

    function deleteRowContent(content, rowIndex) {
        const next = cloneTableContent(content);
        if (rowIndex < 0 || rowIndex >= next.rows.length) {
            throw new Error("Índice de linha inválido.");
        }
        if (next.rows.length <= 1) {
            throw new Error("A tabela deve manter ao menos uma linha de corpo.");
        }
        next.rows.splice(rowIndex, 1);
        return next;
    }

    function insertColumnAfterContent(content, colIndex) {
        const next = cloneTableContent(content);
        if (colIndex < 0 || colIndex >= next.headers.length) {
            throw new Error("Índice de coluna inválido.");
        }
        if (next.headers.length >= MAX_TABLE_COLUMNS) {
            throw new Error("A tabela não pode exceder 12 colunas.");
        }
        next.column_widths = splitTableColumnWidth(
            next.column_widths || equalTableColumnWidths(next.headers.length),
            colIndex
        );
        next.headers.splice(colIndex + 1, 0, "");
        next.rows = next.rows.map((row) => {
            const cells = [...row];
            cells.splice(colIndex + 1, 0, emptyTableBodyCell());
            return cells;
        });
        return next;
    }

    function deleteColumnContent(content, colIndex) {
        const next = cloneTableContent(content);
        if (colIndex < 0 || colIndex >= next.headers.length) {
            throw new Error("Índice de coluna inválido.");
        }
        if (next.headers.length <= 1) {
            throw new Error("A tabela deve manter ao menos uma coluna.");
        }
        next.column_widths = mergeTableColumnWidth(
            next.column_widths || equalTableColumnWidths(next.headers.length),
            colIndex
        );
        next.headers.splice(colIndex, 1);
        next.rows = next.rows.map((row) => row.filter((_, index) => index !== colIndex));
        return next;
    }

    function isTableToolbarControl(element) {
        return Boolean(
            element
            && element.closest
            && element.closest(".report-editor-toolbar-table-group")
        );
    }

    function isImageToolbarControl(element) {
        return Boolean(
            element
            && element.closest
            && (
                element.closest(".report-editor-toolbar-image-group")
                || element.closest(".report-editor-toolbar-image-menu")
            )
        );
    }

    function rememberImageSelection(target) {
        if (target && target.root) {
            lastImageSelection = target;
        }
    }

    function clearImageSelectionContext() {
        lastImageSelection = null;
    }

    function resolveImageSelectionContext() {
        if (window.ReportLineImageResize && window.ReportLineImageResize.getSelectedTarget) {
            const selectedTarget = window.ReportLineImageResize.getSelectedTarget();
            if (selectedTarget) {
                rememberImageSelection(selectedTarget);
                return selectedTarget;
            }
        }

        if (
            lastImageSelection
            && document.contains(lastImageSelection.root)
            && isImageToolbarControl(document.activeElement)
        ) {
            return lastImageSelection;
        }

        return null;
    }

    function rememberTableCellContext(context) {
        if (context && context.block) {
            lastTableCellContext = context;
        }
    }

    function clearTableCellContext() {
        lastTableCellContext = null;
    }

    function resolveTableCellContextFromActiveElement() {
        const active = document.activeElement;
        if (!active || !active.closest) {
            return null;
        }

        const block = active.closest(".report-editor-block[data-block-type=\"table\"]");
        if (!block) {
            return null;
        }

        const textCell = active.closest(".report-editor-table-cell[data-table-part]");
        if (textCell && block.contains(textCell)) {
            return {
                block,
                part: textCell.dataset.tablePart,
                rowIndex: textCell.dataset.tablePart === "cell"
                    ? Number.parseInt(textCell.dataset.rowIndex, 10)
                    : -1,
                colIndex: Number.parseInt(textCell.dataset.colIndex, 10),
                editable: textCell,
            };
        }

        const bodyCell = active.closest("td[data-row-index]");
        if (bodyCell && block.contains(bodyCell)) {
            return {
                block,
                part: "cell",
                rowIndex: Number.parseInt(bodyCell.dataset.rowIndex, 10),
                colIndex: Number.parseInt(bodyCell.dataset.colIndex, 10),
            };
        }

        const headerCell = active.closest("th[data-col-index]");
        if (headerCell && block.contains(headerCell)) {
            return {
                block,
                part: "header",
                rowIndex: -1,
                colIndex: Number.parseInt(headerCell.dataset.colIndex, 10),
            };
        }

        return null;
    }

    function resolveTableCellContext() {
        const fromActive = resolveTableCellContextFromActiveElement();
        if (fromActive) {
            rememberTableCellContext(fromActive);
            return fromActive;
        }

        if (
            lastTableCellContext
            && document.contains(lastTableCellContext.block)
            && isTableToolbarControl(document.activeElement)
        ) {
            return lastTableCellContext;
        }

        return null;
    }

    async function patchTableContent(block, content, focus) {
        clearSaveTimer(block.dataset.nodeId);
        const nodeId = block.dataset.nodeId;
        const payload = {
            content,
            refresh_html: true,
            focus_table_part: focus.part,
            focus_table_col: focus.colIndex,
        };
        if (focus.part === "cell" && focus.rowIndex !== undefined && focus.rowIndex >= 0) {
            payload.focus_table_row = focus.rowIndex;
        }

        const data = await apiRequest(updateNodeUrl(nodeId), "PATCH", payload);
        if (data.html) {
            const replacement = replaceBlockFromHtml(nodeId, data.html);
            if (replacement) {
                focusNewBlock(replacement);
            }
            return replacement;
        }
        return block;
    }

    async function insertTableRowAfterCursor() {
        const context = resolveTableCellContext();
        if (!context) {
            return null;
        }

        const content = collectBlockContent(context.block);
        const newContent = insertRowAfterContent(content, context.rowIndex);
        const focusRow = context.rowIndex < 0 ? 0 : context.rowIndex + 1;
        return patchTableContent(context.block, newContent, {
            part: "cell",
            rowIndex: focusRow,
            colIndex: context.colIndex,
        });
    }

    async function deleteTableRowAtCursor() {
        const context = resolveTableCellContext();
        if (!context || context.part !== "cell") {
            return null;
        }

        const content = collectBlockContent(context.block);
        const newContent = deleteRowContent(content, context.rowIndex);
        const focusRow = Math.min(context.rowIndex, newContent.rows.length - 1);
        return patchTableContent(context.block, newContent, {
            part: "cell",
            rowIndex: focusRow,
            colIndex: context.colIndex,
        });
    }

    async function insertTableColumnAfterCursor() {
        const context = resolveTableCellContext();
        if (!context) {
            return null;
        }

        const content = collectBlockContent(context.block);
        const newContent = insertColumnAfterContent(content, context.colIndex);
        const focusPart = context.part === "header" ? "header" : "cell";
        const focusRow = context.part === "cell" ? context.rowIndex : undefined;
        return patchTableContent(context.block, newContent, {
            part: focusPart,
            rowIndex: focusRow,
            colIndex: context.colIndex + 1,
        });
    }

    async function deleteTableColumnAtCursor() {
        const context = resolveTableCellContext();
        if (!context) {
            return null;
        }

        const content = collectBlockContent(context.block);
        const newContent = deleteColumnContent(content, context.colIndex);
        const focusCol = Math.min(context.colIndex, newContent.headers.length - 1);
        const focusPart = context.part === "header" ? "header" : "cell";
        return patchTableContent(context.block, newContent, {
            part: focusPart,
            rowIndex: context.part === "cell" ? context.rowIndex : undefined,
            colIndex: focusCol,
        });
    }

    async function toggleTableBorders() {
        const context = resolveTableCellContext();
        if (!context) {
            return null;
        }

        const content = collectBlockContent(context.block);
        content.show_borders = content.show_borders === false;
        const focusPart = context.part === "header" ? "header" : "cell";
        return patchTableContent(context.block, content, {
            part: focusPart,
            rowIndex: context.part === "cell" ? context.rowIndex : undefined,
            colIndex: context.colIndex,
        });
    }

    async function toggleTableHeader() {
        const context = resolveTableCellContext();
        if (!context) {
            return null;
        }

        const content = collectBlockContent(context.block);
        const hidingHeader = content.show_header !== false;
        content.show_header = content.show_header === false;

        let focusPart = context.part === "header" ? "header" : "cell";
        let focusRow = context.part === "cell" ? context.rowIndex : undefined;
        const focusCol = context.colIndex;

        if (hidingHeader && context.part === "header") {
            focusPart = "cell";
            focusRow = 0;
        }

        return patchTableContent(context.block, content, {
            part: focusPart,
            rowIndex: focusRow,
            colIndex: focusCol,
        });
    }

    function init(options) {
        config = options;
        const page = document.getElementById("report-editor-page");
        const toolbar = document.querySelector(".report-editor-toolbar");
        if (!page) {
            return;
        }

        bindEditorEvents(page);
        if (toolbar) {
            bindToolbar(toolbar);
        }
        focusInitialBlock(page);
    }

    window.ReportLineEditor = {
        init,
        insertTableAtCursor,
        insertImageAtCursor,
        saveBlock,
        scheduleDebouncedSave,
        resolveEditorContext: resolveInsertContext,
        resolveTableCellContext,
        clearTableCellContext,
        insertTableRowAfterCursor,
        deleteTableRowAtCursor,
        insertTableColumnAfterCursor,
        deleteTableColumnAtCursor,
        toggleTableBorders,
        toggleTableHeader,
        setTableBlockAlign,
        resolveImageSelectionContext,
        clearImageSelectionContext,
        rememberImageSelection,
        setImageAlign,
        applyImageBlockAlignVisual,
        applyTableCellImageAlignVisual,
        resolveParagraphContext,
        rememberParagraphContext,
        clearParagraphContext,
        increaseParagraphIndent,
        decreaseParagraphIndent,
        toggleParagraphFirstLineIndent,
    };
})();
