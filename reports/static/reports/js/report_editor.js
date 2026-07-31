/**
 * Editor interativo de relatórios modulares.
 *
 * Persiste blocos via Enter e autosave com debounce; Shift+Enter
 * insere quebra de linha no mesmo bloco.
 */
(function () {
    "use strict";

    const LIST_TYPES = new Set(["ordered_list", "unordered_list"]);
    const DEBOUNCE_MS = 1500;

    let config = {};
    const saveTimers = new Map();

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

    function getActiveBlock() {
        const active = document.activeElement;
        if (active && active.closest) {
            const fromFocus = active.closest(".report-editor-block");
            if (fromFocus) {
                return fromFocus;
            }
        }
        const blocks = document.querySelectorAll("#report-editor-page .report-editor-block");
        return blocks.length ? blocks[blocks.length - 1] : null;
    }

    function collectBlockContent(block) {
        const blockType = block.dataset.blockType;

        if (blockType === "heading" || blockType === "paragraph" || blockType === "link") {
            const field = block.querySelector('[data-field="text"]');
            return { text: field ? field.innerText : "" };
        }

        if (LIST_TYPES.has(blockType)) {
            const items = Array.from(block.querySelectorAll(".report-editor-list-item")).map(
                (item) => item.innerText
            );
            return { items };
        }

        if (blockType === "image") {
            const altField = block.querySelector('[data-field="alt"]');
            return {
                alt: altField ? altField.innerText : "",
                file: block.dataset.file || "",
            };
        }

        return {};
    }

    async function apiRequest(url, method, body) {
        const response = await fetch(url, {
            method,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
            body: JSON.stringify(body),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = (data.errors && data.errors.join(" ")) || "Falha ao salvar bloco.";
            throw new Error(message);
        }
        return data;
    }

    function updateOutlineHeading(nodeId, text) {
        const link = document.querySelector(
            `.report-editor-outline-link[href="#report-block-${nodeId}"] span`
        );
        if (link) {
            link.textContent = text.trim() || "Título sem texto";
        }
    }

    async function saveBlock(block, options = {}) {
        const nodeId = block.dataset.nodeId;
        const content = collectBlockContent(block);
        const payload = { content };

        if (options.appendListItem) {
            payload.append_list_item = true;
            payload.items = content.items || [];
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

    function insertBlockAfter(afterBlock, html) {
        afterBlock.insertAdjacentHTML("afterend", html);
        const newBlock = afterBlock.nextElementSibling;
        const focusTarget = newBlock.querySelector('[data-autofocus="true"]') ||
            newBlock.querySelector(".report-editor-block-editable");
        if (focusTarget) {
            placeCaretAtEnd(focusTarget);
        }
        return newBlock;
    }

    async function createSiblingBlock(afterBlock, blockType) {
        const data = await apiRequest(config.createNodeUrl, "POST", {
            after_node_id: afterBlock.dataset.nodeId,
            block_type: blockType || undefined,
        });
        return insertBlockAfter(afterBlock, data.html);
    }

    async function handleListEnter(block, activeItem) {
        await saveBlock(block, { appendListItem: true });

        const list = block.querySelector("[data-field=\"items\"]");
        const items = Array.from(block.querySelectorAll(".report-editor-list-item"));
        const newIndex = items.length;

        const newItem = document.createElement("li");
        newItem.className = "report-editor-block-editable report-editor-list-item";
        newItem.contentEditable = "true";
        newItem.dataset.listIndex = String(newIndex);
        newItem.dataset.placeholder = "Item da lista";
        list.appendChild(newItem);
        placeCaretAtEnd(newItem);
    }

    async function handleBlockEnter(block) {
        const nodeId = block.dataset.nodeId;
        if (saveTimers.has(nodeId)) {
            clearTimeout(saveTimers.get(nodeId));
            saveTimers.delete(nodeId);
        }

        await saveBlock(block);
        await createSiblingBlock(block);
    }

    function bindEditorEvents(page) {
        page.addEventListener("keydown", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable || event.key !== "Enter" || event.shiftKey) {
                return;
            }

            const block = editable.closest(".report-editor-block");
            if (!block) {
                return;
            }

            event.preventDefault();

            if (LIST_TYPES.has(block.dataset.blockType)) {
                handleListEnter(block, editable).catch(console.error);
            } else {
                handleBlockEnter(block).catch(console.error);
            }
        });

        page.addEventListener("input", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
                return;
            }
            const block = editable.closest(".report-editor-block");
            if (block) {
                scheduleDebouncedSave(block);
            }
        });

        page.addEventListener("focusin", (event) => {
            const block = event.target.closest(".report-editor-block");
            if (block) {
                block.classList.add("is-active");
            }
        });

        page.addEventListener("focusout", (event) => {
            const block = event.target.closest(".report-editor-block");
            if (block && !block.contains(event.relatedTarget)) {
                block.classList.remove("is-active");
            }
        });
    }

    function bindToolbar(toolbar, page) {
        toolbar.addEventListener("click", (event) => {
            const button = event.target.closest("[data-insert-block-type]");
            if (!button) {
                return;
            }

            const blockType = button.dataset.insertBlockType;
            const afterBlock = getActiveBlock();
            if (!afterBlock) {
                return;
            }

            saveBlock(afterBlock)
                .then(() => createSiblingBlock(afterBlock, blockType))
                .catch(console.error);
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
            bindToolbar(toolbar, page);
        }
        focusInitialBlock(page);
    }

    window.ReportLineEditor = { init };
})();
