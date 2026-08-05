/**
 * Navegação entre blocos de texto do editor com as setas do teclado.
 *
 * Move o foco para o bloco adjacente quando o cursor está no limite
 * horizontal ou vertical do campo editável atual.
 */
(function () {
    "use strict";

    /** @type {HTMLElement | null} */
    let pageElement = null;

    const LIST_BLOCK_TYPES = new Set(["ordered_list", "unordered_list"]);
    const SKIPPABLE_BLOCK_TYPES = new Set(["image", "horizontal_rule", "table"]);

    const KEY_DIRECTION = {
        ArrowLeft: "left",
        ArrowRight: "right",
        ArrowUp: "up",
        ArrowDown: "down",
    };

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

    function getLineTop(element, atStart) {
        const range = document.createRange();
        range.selectNodeContents(element);
        range.collapse(atStart);
        const rects = range.getClientRects();
        return rects.length ? rects[0].top : null;
    }

    function isCaretOnFirstLine(editable) {
        const selection = window.getSelection();
        if (!selection || !selection.rangeCount || !selection.isCollapsed) {
            return false;
        }
        const range = selection.getRangeAt(0);
        if (!editable.contains(range.startContainer)) {
            return false;
        }

        const firstLineTop = getLineTop(editable, true);
        if (firstLineTop === null) {
            return true;
        }

        const caretRects = range.getClientRects();
        if (!caretRects.length) {
            return getCaretOffset(editable) === 0;
        }

        return Math.abs(caretRects[0].top - firstLineTop) < 2;
    }

    function isCaretOnLastLine(editable) {
        const selection = window.getSelection();
        if (!selection || !selection.rangeCount || !selection.isCollapsed) {
            return false;
        }
        const range = selection.getRangeAt(0);
        if (!editable.contains(range.startContainer)) {
            return false;
        }

        const lastLineTop = getLineTop(editable, false);
        if (lastLineTop === null) {
            return true;
        }

        const caretRects = range.getClientRects();
        if (!caretRects.length) {
            const textLength = editable.textContent ? editable.textContent.length : 0;
            return getCaretOffset(editable) >= textLength;
        }

        return Math.abs(caretRects[0].top - lastLineTop) < 2;
    }

    function isEditableEmpty(editable) {
        return (editable.textContent || "").trim() === "";
    }

    function isListItem(editable) {
        return editable.classList.contains("report-editor-list-item");
    }

    function getEditorBlock(element) {
        return element.closest(".report-editor-block");
    }

    function getListItems(block) {
        return Array.from(block.querySelectorAll(".report-editor-list-item"));
    }

    function getBlockFirstEditable(block) {
        if (!block) {
            return null;
        }

        const blockType = block.dataset.blockType;
        if (SKIPPABLE_BLOCK_TYPES.has(blockType)) {
            return null;
        }

        if (LIST_BLOCK_TYPES.has(blockType)) {
            const items = getListItems(block);
            return items.length ? items[0] : null;
        }

        return block.querySelector('[data-field="text"]');
    }

    function getBlockLastEditable(block) {
        if (!block) {
            return null;
        }

        const blockType = block.dataset.blockType;
        if (SKIPPABLE_BLOCK_TYPES.has(blockType)) {
            return null;
        }

        if (LIST_BLOCK_TYPES.has(blockType)) {
            const items = getListItems(block);
            return items.length ? items[items.length - 1] : null;
        }

        return block.querySelector('[data-field="text"]');
    }

    function getPreviousEditorBlock(block) {
        let previous = block.previousElementSibling;
        while (previous) {
            if (previous.classList.contains("report-editor-block")) {
                return previous;
            }
            previous = previous.previousElementSibling;
        }
        return null;
    }

    function getNextEditorBlock(block) {
        let next = block.nextElementSibling;
        while (next) {
            if (next.classList.contains("report-editor-block")) {
                return next;
            }
            next = next.nextElementSibling;
        }
        return null;
    }

    function findPreviousEditableTarget(editable) {
        if (isListItem(editable)) {
            const block = getEditorBlock(editable);
            if (!block) {
                return null;
            }
            const items = getListItems(block);
            const index = items.indexOf(editable);
            if (index > 0) {
                return { editable: items[index - 1], placement: "end" };
            }
        }

        const block = getEditorBlock(editable);
        if (!block) {
            return null;
        }

        let previousBlock = getPreviousEditorBlock(block);
        while (previousBlock) {
            const target = getBlockLastEditable(previousBlock);
            if (target) {
                return { editable: target, placement: "end" };
            }
            previousBlock = getPreviousEditorBlock(previousBlock);
        }

        return null;
    }

    function findNextEditableTarget(editable) {
        if (isListItem(editable)) {
            const block = getEditorBlock(editable);
            if (!block) {
                return null;
            }
            const items = getListItems(block);
            const index = items.indexOf(editable);
            if (index >= 0 && index < items.length - 1) {
                return { editable: items[index + 1], placement: "start" };
            }
        }

        const block = getEditorBlock(editable);
        if (!block) {
            return null;
        }

        let nextBlock = getNextEditorBlock(block);
        while (nextBlock) {
            const target = getBlockFirstEditable(nextBlock);
            if (target) {
                return { editable: target, placement: "start" };
            }
            nextBlock = getNextEditorBlock(nextBlock);
        }

        return null;
    }

    function shouldNavigateFromEditable(editable, key) {
        if (isEditableEmpty(editable)) {
            return true;
        }

        switch (key) {
            case "ArrowLeft":
                return getCaretOffset(editable) === 0;
            case "ArrowRight":
                return getCaretOffset(editable) >= (editable.textContent || "").length;
            case "ArrowUp":
                return isCaretOnFirstLine(editable);
            case "ArrowDown":
                return isCaretOnLastLine(editable);
            default:
                return false;
        }
    }

    function focusEditableTarget(target, placement) {
        if (!target) {
            return;
        }

        if (placement === "end") {
            placeCaretAtEnd(target);
        } else {
            placeCaretAtStart(target);
        }
    }

    function isBodyBlockEditable(editable) {
        if (!pageElement || !pageElement.contains(editable)) {
            return false;
        }
        if (!editable.classList.contains("report-editor-block-editable")) {
            return false;
        }
        if (editable.closest(".report-editor-table-cell[data-table-part]")) {
            return false;
        }
        if (editable.closest(".report-page-header-text, .report-page-footer-text")) {
            return false;
        }
        return Boolean(getEditorBlock(editable));
    }

    function handleKeyDown(event) {
        const direction = KEY_DIRECTION[event.key];
        if (!direction || event.defaultPrevented) {
            return;
        }

        if (event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) {
            return;
        }

        const editable = event.target.closest
            ? event.target.closest(".report-editor-block-editable")
            : null;
        if (!editable || !isBodyBlockEditable(editable)) {
            return;
        }

        if (!shouldNavigateFromEditable(editable, event.key)) {
            return;
        }

        let target = null;
        if (direction === "left" || direction === "up") {
            target = findPreviousEditableTarget(editable);
        } else {
            target = findNextEditableTarget(editable);
        }

        if (!target) {
            return;
        }

        event.preventDefault();
        focusEditableTarget(target.editable, target.placement);
    }

    function init() {
        pageElement = document.getElementById("report-editor-page");
        if (!pageElement) {
            return;
        }

        pageElement.addEventListener("keydown", handleKeyDown, true);
    }

    window.ReportLineBlockNavigation = {
        init,
    };
})();
