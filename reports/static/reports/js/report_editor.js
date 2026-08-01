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
    const HEADING_CONVERTIBLE_TYPES = new Set(["heading", "paragraph"]);
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

    async function convertBlockToHeading(block, editable, titleLevel) {
        clearSaveTimer(block.dataset.nodeId);
        const field = editable || getTextField(block);
        const text = field ? field.innerText : "";
        const nodeId = block.dataset.nodeId;
        const caret = field ? getCaretOffset(field) : text.length;

        const data = await apiRequest(updateNodeUrl(nodeId), "PATCH", {
            content: { text },
            block_type: "heading",
            title_level: titleLevel,
        });

        let targetBlock = block;
        if (data.html) {
            targetBlock = replaceBlockFromHtml(nodeId, data.html) || block;
        } else {
            block.dataset.blockType = "heading";
            block.dataset.titleLevel = String(titleLevel);
        }

        const headingField = targetBlock.querySelector('[data-field="text"]');
        if (headingField) {
            setCaretOffset(headingField, caret);
        }

        await refreshOutlineTree();
        return targetBlock;
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

        if (LIST_TYPES.has(block.dataset.blockType)) {
            await saveBlock(block);
            await createSiblingBlock(block, newBlockType, siblingInsertOptions(options));
            return;
        }

        if (block.dataset.blockType === "image" || block.dataset.blockType === "table") {
            await saveBlock(block);
            await createSiblingBlock(block, newBlockType, siblingInsertOptions(options));
            return;
        }

        if (TEXT_BLOCK_TYPES.has(block.dataset.blockType) && editable) {
            const fullText = editable.innerText;
            const caret = getCaretOffset(editable);
            const atStart = caret === 0;
            const atEnd = caret >= fullText.length;

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
        await createSiblingBlock(block, newBlockType, siblingInsertOptions(options));
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

            if (
                blockType === "heading"
                && HEADING_CONVERTIBLE_TYPES.has(context.block.dataset.blockType)
            ) {
                convertBlockToHeading(
                    context.block,
                    context.editable,
                    titleLevel
                ).catch(console.error);
                return;
            }

            const insertOptions = {};
            if (titleLevelRaw !== undefined && titleLevelRaw !== "") {
                insertOptions.titleLevel = titleLevel;
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

    window.ReportLineEditor = { init };
})();
