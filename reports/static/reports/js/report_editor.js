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

    let config = {};
    const saveTimers = new Map();
    let lastEditorContext = null;
    let lastTableCellContext = null;

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
        const textNode = element.firstChild;
        if (!textNode) {
            range.selectNodeContents(element);
            range.collapse(true);
        } else {
            const safeOffset = Math.min(Math.max(offset, 0), textNode.textContent.length);
            range.setStart(textNode, safeOffset);
            range.collapse(true);
        }
        selection.removeAllRanges();
        selection.addRange(range);
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
        return editable.innerText.trim() === "";
    }

    function collectBlockContent(block) {
        const blockType = block.dataset.blockType;

        if (TEXT_BLOCK_TYPES.has(blockType)) {
            const field = getTextField(block);
            return { text: field ? field.innerText : "" };
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
                (item) => item.innerText
            );
            return { items };
        }

        if (blockType === "table") {
            const headers = Array.from(
                block.querySelectorAll('[data-table-part="header"]')
            ).map((cell) => cell.innerText);
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
                        };
                    }
                    const textCell = cellElement.querySelector('[data-table-part="cell"]');
                    return {
                        type: "text",
                        text: textCell ? textCell.innerText : "",
                    };
                })
            );
            return {
                headers,
                rows,
                show_borders: block.dataset.tableShowBorders !== "false",
            };
        }

        return {};
    }

    function setTextFieldContent(block, text) {
        const field = getTextField(block);
        if (field) {
            field.innerText = text;
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
            label.textContent = text.trim() || "Título sem texto";
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

    function buildTableContent(rowCount, columnCount) {
        const rows = Math.max(1, Math.min(rowCount, 20));
        const cols = Math.max(1, Math.min(columnCount, 12));
        return {
            headers: Array(cols).fill(""),
            rows: Array(Math.max(0, rows - 1))
                .fill(null)
                .map(() => Array(cols).fill("")),
            show_borders: true,
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

    async function ensureCaptionParagraphAfterImage(imageBlock) {
        const nextBlock = imageBlock.nextElementSibling;
        if (
            nextBlock
            && nextBlock.classList.contains("report-editor-block")
            && nextBlock.dataset.blockType === "paragraph"
        ) {
            focusCaptionParagraph(nextBlock);
            return nextBlock;
        }

        return createSiblingBlock(imageBlock, "paragraph", {
            content: { text: "" },
            isCaption: true,
        });
    }

    function getListItems(block) {
        return Array.from(block.querySelectorAll(".report-editor-list-item")).map(
            (item) => item.innerText
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
                const text = field ? field.innerText : "";
                const lines = text.split("\n");
                return { items: lines.length ? lines : [""] };
            }
        }

        if (targetBlockType === "paragraph") {
            if (TEXT_BLOCK_TYPES.has(sourceType)) {
                const field = editable || getTextField(block);
                return { text: field ? field.innerText : "" };
            }
            if (LIST_TYPES.has(sourceType)) {
                const items = getListItems(block);
                return { text: items.join("\n") };
            }
        }

        if (targetBlockType === "heading") {
            if (TEXT_BLOCK_TYPES.has(sourceType)) {
                const field = editable || getTextField(block);
                return { text: field ? field.innerText : "" };
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
            const caret = options.caret ?? field.innerText.length;
            setCaretOffset(field, Math.min(caret, field.innerText.length));
            return;
        }

        if (LIST_TYPES.has(targetBlockType)) {
            const items = block.querySelectorAll(".report-editor-list-item");
            const target = items[options.listItemIndex ?? 0] || items[0];
            if (target) {
                const caret = options.caret;
                if (caret !== undefined) {
                    setCaretOffset(target, Math.min(caret, target.innerText.length));
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
        const text = activeItem.innerText;
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
            const beforeText = text.slice(0, caret);
            const afterText = text.slice(caret);
            beforeItems = items.slice(0, index).concat(beforeText);
            afterItems = items.slice(index + 1);
            newBlockContent = options.content
                ?? buildNewBlockContent(newBlockType, afterText, options);
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
            item.innerText = text;
            list.appendChild(item);
        });
    }

    async function handleListEnter(block, activeItem) {
        clearSaveTimer(block.dataset.nodeId);
        const items = Array.from(block.querySelectorAll(".report-editor-list-item")).map(
            (item) => item.innerText
        );
        const index = getListItemIndex(activeItem);
        const caret = getCaretOffset(activeItem);
        const text = activeItem.innerText;
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
            const before = text.slice(0, caret);
            const after = text.slice(caret);
            items[index] = before;
            items.splice(index + 1, 0, after);
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
            const fullText = editable.innerText;
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
                    const beforeText = fullText.slice(0, caret);
                    const afterText = fullText.slice(caret);
                    setTextFieldContent(block, beforeText);
                    await saveBlock(block);
                    editable.innerText = beforeText;
                    const insertedBlock = await createSiblingBlock(
                        block,
                        newBlockType,
                        siblingInsertOptions(options, { content: insertContent })
                    );
                    if (newBlockType === "table") {
                        focusTableBlock(insertedBlock);
                    }
                    if (afterText) {
                        await createSiblingBlock(insertedBlock, "paragraph", {
                            content: { text: afterText },
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
                const beforeText = fullText.slice(0, caret);
                const afterText = fullText.slice(caret);
                setTextFieldContent(block, beforeText);
                await saveBlock(block);
                editable.innerText = beforeText;
                await createSiblingBlock(
                    block,
                    newBlockType,
                    siblingInsertOptions(options, {
                        insertion: "after",
                        content: { text: afterText },
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
                 data-image-height="${displayHeight}">
                <img src="${safeUrl}"
                     alt="${imagePayload.alt || ""}"
                     class="report-editor-table-cell-img"
                     width="${displayWidth}"
                     height="${displayHeight}"
                     draggable="false">
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
        const items = Array.from(block.querySelectorAll(".report-editor-list-item")).map(
            (item) => item.innerText
        );
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

    function bindEditorEvents(page) {
        page.addEventListener("keydown", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
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
                        updateOutlineHeading(block.dataset.nodeId, field.innerText);
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
            }
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
            if (event.target.closest("[data-insert-block-type]")) {
                event.preventDefault();
            }
        });

        toolbar.addEventListener("click", (event) => {
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
    }

    function focusInitialBlock(page) {
        const target = page.querySelector('[data-autofocus="true"]');
        if (target) {
            placeCaretAtEnd(target);
        }
    }

    const MAX_TABLE_BODY_ROWS = 19;
    const MAX_TABLE_COLUMNS = 12;

    function emptyTableBodyCell() {
        return { type: "text", text: "" };
    }

    function cloneTableContent(content) {
        return {
            headers: [...content.headers],
            rows: content.rows.map((row) => row.map((cell) => {
                if (cell && typeof cell === "object") {
                    return { ...cell };
                }
                return { type: "text", text: String(cell ?? "") };
            })),
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
        resolveTableCellContext,
        clearTableCellContext,
        insertTableRowAfterCursor,
        deleteTableRowAtCursor,
        insertTableColumnAfterCursor,
        deleteTableColumnAtCursor,
        toggleTableBorders,
    };
})();
