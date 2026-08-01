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
        return block.querySelector('[data-field="text"], [data-field="alt"]');
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
            const altField = block.querySelector('[data-field="alt"]');
            return {
                alt: altField ? altField.innerText : "",
                file: block.dataset.file || "",
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
                Array.from(rowElement.querySelectorAll('[data-table-part="cell"]')).map(
                    (cell) => cell.innerText
                )
            );
            return { headers, rows };
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

        if (LIST_TYPES.has(block.dataset.blockType)) {
            await saveBlock(block);
            await createSiblingBlock(
                block,
                newBlockType,
                siblingInsertOptions(options, { content: tableContent ?? options.content })
            );
            return;
        }

        if (block.dataset.blockType === "image" || block.dataset.blockType === "table") {
            await saveBlock(block);
            const newBlock = await createSiblingBlock(
                block,
                newBlockType,
                siblingInsertOptions(options, { content: tableContent ?? options.content })
            );
            if (newBlockType === "table") {
                focusTableBlock(newBlock);
            }
            return;
        }

        if (TEXT_BLOCK_TYPES.has(block.dataset.blockType) && editable) {
            const fullText = editable.innerText;
            const caret = getCaretOffset(editable);
            const atStart = caret === 0;
            const atEnd = caret >= fullText.length;

            if (newBlockType === "table") {
                if (atStart) {
                    const tableBlock = await createSiblingBlock(
                        block,
                        "table",
                        siblingInsertOptions(options, {
                            insertion: "before",
                            content: tableContent,
                        })
                    );
                    focusTableBlock(tableBlock);
                    return;
                }

                if (!atEnd) {
                    const beforeText = fullText.slice(0, caret);
                    const afterText = fullText.slice(caret);
                    setTextFieldContent(block, beforeText);
                    await saveBlock(block);
                    editable.innerText = beforeText;
                    const tableBlock = await createSiblingBlock(
                        block,
                        "table",
                        siblingInsertOptions(options, { content: tableContent })
                    );
                    focusTableBlock(tableBlock);
                    if (afterText) {
                        await createSiblingBlock(tableBlock, "paragraph", {
                            content: { text: afterText },
                            caretAtStart: true,
                        });
                    }
                    return;
                }

                const tableBlock = await createSiblingBlock(
                    block,
                    "table",
                    siblingInsertOptions(options, { content: tableContent })
                );
                focusTableBlock(tableBlock);
                return;
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
            siblingInsertOptions(options, { content: tableContent ?? options.content })
        );
        if (newBlockType === "table") {
            focusTableBlock(newBlock);
        }
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
            await createSiblingBlock(block, "paragraph");
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

    window.ReportLineEditor = { init, insertTableAtCursor };
})();
