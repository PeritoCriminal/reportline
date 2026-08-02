/**
 * Editor interativo de relatórios modulares.
 *
 * Enter divide ou insere blocos conforme posição do cursor; Shift+Enter
 * mantém quebra de linha no mesmo bloco; Backspace remove bloco vazio no início;
 * Delete remove parágrafo vazio ou totalmente selecionado; Backspace/Delete adjacentes
 * removem linha horizontal entre blocos de texto; undo/redo via ReportLineUndo
 * (fase 1: texto/blocos; fase 2: listas, recuo, alinhamento; fase 3: tabela, imagem, faixas).
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
    const HISTORY_DEBOUNCE_MS = 400;
    const TEXT_ALIGN_VALUES = new Set(["left", "center", "right", "justify"]);

    let config = {};
    const saveTimers = new Map();
    const historyTimers = new Map();
    const pendingTextEdits = new Map();
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

    function getLastLinePlainTextFromHtml(html) {
        const helpers = getInlineTextHelpers();
        return helpers ? helpers.getLastLinePlainTextFromHtml(html) : "";
    }

    function removeLastLineFromHtml(html) {
        const helpers = getInlineTextHelpers();
        return helpers ? helpers.removeLastLineFromHtml(html) : html;
    }

    function isEmptyHtml(html) {
        const helpers = getInlineTextHelpers();
        if (helpers) {
            return helpers.isEmptyHtml(html);
        }
        return !html || !html.trim();
    }

    const HORIZONTAL_RULE_LINE_PATTERN = /^_{3,}$/;

    function isHorizontalRuleShortcutLine(lineText) {
        return HORIZONTAL_RULE_LINE_PATTERN.test(lineText || "");
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

    function getEditableSelectionOffsets(editable) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            return null;
        }

        const range = selection.getRangeAt(0);
        if (!editable.contains(range.startContainer) || !editable.contains(range.endContainer)) {
            return null;
        }

        const startRange = range.cloneRange();
        startRange.selectNodeContents(editable);
        startRange.setEnd(range.startContainer, range.startOffset);

        const endRange = range.cloneRange();
        endRange.selectNodeContents(editable);
        endRange.setEnd(range.endContainer, range.endOffset);

        return {
            start: startRange.toString().length,
            end: endRange.toString().length,
            length: getEditablePlainText(editable).length,
        };
    }

    function isEditableFullySelected(editable) {
        if (isEditableEmpty(editable)) {
            return true;
        }

        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
            return false;
        }

        const offsets = getEditableSelectionOffsets(editable);
        if (!offsets) {
            return false;
        }

        return offsets.start === 0 && offsets.end >= offsets.length;
    }

    function getNextEditorBlock(block) {
        let next = block.nextElementSibling;
        while (next && !next.classList.contains("report-editor-block")) {
            next = next.nextElementSibling;
        }
        return next || null;
    }

    function getPreviousEditorBlock(block) {
        let previous = block.previousElementSibling;
        while (previous && !previous.classList.contains("report-editor-block")) {
            previous = previous.previousElementSibling;
        }
        return previous || null;
    }

    function isTextBlockEligibleForHorizontalRuleRemoval(block) {
        return (
            TEXT_BLOCK_TYPES.has(block.dataset.blockType)
            && block.dataset.isCaption !== "true"
        );
    }

    function isCaretCollapsedAtEnd(editable) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0 || !selection.isCollapsed) {
            return false;
        }

        const offsets = getEditableSelectionOffsets(editable);
        if (!offsets) {
            return false;
        }

        return offsets.start >= offsets.length;
    }

    function shouldBackspaceRemoveAdjacentHorizontalRule(block, editable) {
        if (!isTextBlockEligibleForHorizontalRuleRemoval(block)) {
            return false;
        }
        if (getCaretOffset(editable) !== 0 || isEditableEmpty(editable)) {
            return false;
        }

        const previousBlock = getPreviousEditorBlock(block);
        return Boolean(
            previousBlock && previousBlock.dataset.blockType === "horizontal_rule"
        );
    }

    function shouldDeleteRemoveAdjacentHorizontalRule(block, editable) {
        if (!isTextBlockEligibleForHorizontalRuleRemoval(block)) {
            return false;
        }
        if (!isCaretCollapsedAtEnd(editable)) {
            return false;
        }

        const nextBlock = getNextEditorBlock(block);
        return Boolean(nextBlock && nextBlock.dataset.blockType === "horizontal_rule");
    }

    async function deleteHorizontalRuleBlock(block) {
        if (!block || block.dataset.blockType !== "horizontal_rule") {
            return;
        }
        await deleteBlockById(block);
    }

    async function handleBackspaceAdjacentHorizontalRule(block, editable) {
        if (!shouldBackspaceRemoveAdjacentHorizontalRule(block, editable)) {
            return false;
        }

        const horizontalRuleBlock = getPreviousEditorBlock(block);
        await deleteHorizontalRuleBlock(horizontalRuleBlock);
        placeCaretAtStart(editable);
        rememberEditorContext(block, editable);
        return true;
    }

    async function handleDeleteAdjacentHorizontalRule(block, editable) {
        if (!shouldDeleteRemoveAdjacentHorizontalRule(block, editable)) {
            return false;
        }

        const horizontalRuleBlock = getNextEditorBlock(block);
        await deleteHorizontalRuleBlock(horizontalRuleBlock);
        placeCaretAtEnd(editable);
        rememberEditorContext(block, editable);
        return true;
    }

    function focusBlockAtStart(block) {
        if (!block) {
            return false;
        }

        const editable = block.querySelector(".report-editor-block-editable");
        if (editable) {
            placeCaretAtStart(editable);
            rememberEditorContext(block, editable);
            return true;
        }

        if (
            block.dataset.blockType === "image"
            && window.ReportLineImageResize
            && window.ReportLineImageResize.selectTargetElement
        ) {
            const target = block.querySelector(
                ".report-editor-block-image-img, .report-editor-block-image"
            );
            if (target) {
                window.ReportLineImageResize.selectTargetElement(target);
                return true;
            }
        }

        return false;
    }

    function buildNodeInsertAnchor(block) {
        const previousBlock = getPreviousEditorBlock(block);
        if (previousBlock) {
            return { type: "after", nodeId: previousBlock.dataset.nodeId };
        }

        const nextBlock = getNextEditorBlock(block);
        if (nextBlock) {
            return { type: "before", nodeId: nextBlock.dataset.nodeId };
        }

        return null;
    }

    function buildNodeSnapshot(block) {
        const anchor = buildNodeInsertAnchor(block);
        if (!anchor) {
            return null;
        }

        const field = getTextField(block);
        return {
            anchor,
            nodeId: block.dataset.nodeId,
            blockType: block.dataset.blockType,
            content: collectBlockContent(block),
            isCaption: block.dataset.isCaption === "true",
            titleLevel: block.dataset.titleLevel,
            indentLevel: block.dataset.indentLevel,
            firstLineIndent: block.dataset.firstLineIndent === "true",
            fieldHtml: field ? getEditableHtml(field) : "",
        };
    }

    function buildCreatePayload(referenceBlock, blockType, options = {}) {
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
        return payload;
    }

    function buildSnapshotFromCreatePayload(createPayload, block) {
        const anchor = createPayload.before_node_id
            ? { type: "before", nodeId: createPayload.before_node_id }
            : { type: "after", nodeId: createPayload.after_node_id };
        const field = getTextField(block);
        return {
            anchor,
            nodeId: block.dataset.nodeId,
            blockType: block.dataset.blockType,
            content: createPayload.content,
            isCaption: Boolean(createPayload.is_caption) || block.dataset.isCaption === "true",
            titleLevel: createPayload.title_level,
            indentLevel: createPayload.indent_level,
            firstLineIndent: createPayload.first_line_indent,
            fieldHtml: field ? getEditableHtml(field) : "",
        };
    }

    function applyImageContentVisual(block, content) {
        if (!block || block.dataset.blockType !== "image") {
            return;
        }

        if (content.file !== undefined) {
            block.dataset.file = content.file || "";
        }
        if (content.image_id !== undefined) {
            block.dataset.imageId = content.image_id || "";
        }
        if (content.width) {
            block.dataset.imageWidth = String(content.width);
        }
        if (content.height) {
            block.dataset.imageHeight = String(content.height);
        }

        const img = block.querySelector(".report-editor-block-image-img");
        if (img) {
            if (content.alt !== undefined) {
                img.setAttribute("alt", content.alt || "");
            }
            if (content.width && content.height) {
                img.width = content.width;
                img.height = content.height;
                img.style.width = `${content.width}px`;
                img.style.height = `${content.height}px`;
            }
        }
    }

    function recordTableContentHistory(nodeId, beforeContent, afterContent, tableFocus) {
        if (
            !window.ReportLineUndo
            || window.ReportLineUndo.isApplying()
            || JSON.stringify(beforeContent) === JSON.stringify(afterContent)
        ) {
            return;
        }

        window.ReportLineUndo.recordCommand({
            label: "Editar tabela",
            mergeKey: "",
            undo: () => applyBlockContentForHistory(
                nodeId,
                beforeContent,
                null,
                "table",
                { tableFocus }
            ),
            redo: () => applyBlockContentForHistory(
                nodeId,
                afterContent,
                null,
                "table",
                { tableFocus }
            ),
        });
    }

    async function applyBlockContentForHistory(nodeId, content, fieldHtml, blockType, focusOptions = {}) {
        const block = document.getElementById(`report-block-${nodeId}`);
        if (!block) {
            return;
        }

        clearSaveTimer(nodeId);
        pendingTextEdits.delete(nodeId);

        if (blockType === "table" && content.headers) {
            const tableFocus = focusOptions.tableFocus || {
                part: "cell",
                rowIndex: 0,
                colIndex: 0,
            };
            await patchTableContent(block, content, tableFocus, { skipHistory: true });
            return;
        }

        if (blockType === "image") {
            applyImageContentVisual(block, content);
            const data = await apiRequest(updateNodeUrl(nodeId), "PATCH", { content });
            applyCaptionNumbersFromResponse(data);
            return;
        }

        let patchPayload;
        if (LIST_TYPES.has(blockType) && content.items) {
            rebuildListItems(block, content.items);
            patchPayload = {
                update_list_items: true,
                items: content.items,
            };
        } else {
            const field = getTextField(block);
            if (field) {
                const html = fieldHtml !== undefined && fieldHtml !== null
                    ? fieldHtml
                    : (content.text || "");
                setEditableHtml(field, html);
            }
            patchPayload = { content };
        }

        const data = await apiRequest(updateNodeUrl(nodeId), "PATCH", patchPayload);
        applyCaptionNumbersFromResponse(data);

        if (blockType === "heading" && content.text !== undefined) {
            const field = getTextField(block);
            if (field) {
                updateOutlineHeading(nodeId, getEditablePlainText(field));
            }
        }

        if (focusOptions.listItemIndex !== undefined) {
            const items = block.querySelectorAll(".report-editor-list-item");
            const target = items[focusOptions.listItemIndex];
            if (target) {
                if (focusOptions.caretAtStart) {
                    placeCaretAtStart(target);
                } else if (focusOptions.caret !== undefined) {
                    setCaretOffset(
                        target,
                        Math.min(focusOptions.caret, getEditablePlainText(target).length)
                    );
                } else {
                    placeCaretAtEnd(target);
                }
                rememberEditorContext(block, target);
            }
        } else {
            const field = getTextField(block);
            if (field && focusOptions.caret !== undefined) {
                setCaretOffset(
                    field,
                    Math.min(focusOptions.caret, getEditablePlainText(field).length)
                );
                rememberEditorContext(block, field);
            }
        }
    }

    function captureParagraphLayout(block) {
        const paragraph = getParagraphElement(block);
        return {
            indent_level: getParagraphIndentLevel(block),
            first_line_indent: paragraph ? paragraph.dataset.firstLineIndent !== "false" : true,
        };
    }

    async function applyParagraphLayoutForHistory(block, layout) {
        await patchParagraphLayout(block, layout, { skipHistory: true });
    }

    function recordParagraphLayoutHistory(block, beforeLayout, afterLayout) {
        if (
            !window.ReportLineUndo
            || window.ReportLineUndo.isApplying()
            || JSON.stringify(beforeLayout) === JSON.stringify(afterLayout)
        ) {
            return;
        }

        window.ReportLineUndo.recordCommand({
            label: "Recuo do parágrafo",
            undo: () => applyParagraphLayoutForHistory(block, beforeLayout),
            redo: () => applyParagraphLayoutForHistory(block, afterLayout),
        });
    }

    function captureBlockState(block) {
        return {
            nodeId: block.dataset.nodeId,
            blockType: block.dataset.blockType,
            content: collectBlockContent(block),
            titleLevel: block.dataset.titleLevel,
            textAlign: block.dataset.textAlign,
            isCaption: block.dataset.isCaption === "true",
            isMainTitle: block.dataset.isMainTitle === "true",
            indentLevel: block.dataset.indentLevel,
            firstLineIndent: block.dataset.firstLineIndent === "true",
        };
    }

    async function applyBlockStateForHistory(state, focusOptions = {}) {
        const block = document.getElementById(`report-block-${state.nodeId}`);
        if (!block) {
            return null;
        }

        clearSaveTimer(state.nodeId);
        pendingTextEdits.delete(state.nodeId);

        const payload = {
            content: state.content,
            block_type: state.blockType,
            text_align: state.textAlign || defaultTextAlignForBlock(
                state.blockType,
                {
                    isMainTitle: state.blockType === "heading" && state.isMainTitle,
                    isCaption: state.isCaption,
                }
            ),
        };

        if (state.blockType === "heading" && state.titleLevel !== undefined && state.titleLevel !== "") {
            payload.title_level = Number.parseInt(state.titleLevel, 10);
        }
        if (state.blockType === "paragraph") {
            if (state.indentLevel !== undefined && state.indentLevel !== "") {
                payload.indent_level = Number.parseInt(state.indentLevel, 10);
            }
            payload.first_line_indent = state.firstLineIndent;
        }

        const data = await apiRequest(updateNodeUrl(state.nodeId), "PATCH", payload);

        let targetBlock = block;
        if (data.html) {
            targetBlock = replaceBlockFromHtml(state.nodeId, data.html) || block;
        } else {
            targetBlock.dataset.blockType = state.blockType;
            if (state.textAlign) {
                targetBlock.dataset.textAlign = state.textAlign;
            }
            if (LIST_TYPES.has(state.blockType) && state.content.items) {
                rebuildListItems(targetBlock, state.content.items);
            }
            if (state.blockType === "paragraph") {
                applyParagraphIndentVisual(targetBlock, {
                    indent_level: state.indentLevel !== undefined && state.indentLevel !== ""
                        ? Number.parseInt(state.indentLevel, 10)
                        : undefined,
                    first_line_indent: state.firstLineIndent,
                });
            }
        }

        applyCaptionNumbersFromResponse(data);

        if (state.blockType === "heading" || block.dataset.blockType === "heading") {
            await refreshOutlineTree();
        }

        focusConvertedBlock(targetBlock, state.blockType, focusOptions);
        return targetBlock;
    }

    function recordBlockStateChange(beforeState, afterState, undoFocus, redoFocus) {
        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {
            return;
        }

        window.ReportLineUndo.recordCommand({
            label: "Converter bloco",
            undo: () => applyBlockStateForHistory(beforeState, undoFocus),
            redo: () => applyBlockStateForHistory(afterState, redoFocus),
        });
    }

    async function applyTextAlignForHistory(block, align) {
        applyTextAlignToBlock(block, align);
        clearSaveTimer(block.dataset.nodeId);
        if (block.dataset.blockType === "image") {
            await syncCaptionWithImageAlign(block, align);
        }
        if (
            block.dataset.blockType === "table"
            && window.ReportLineTableWidthResize
            && window.ReportLineTableWidthResize.refreshTableDisplayLayout
        ) {
            window.ReportLineTableWidthResize.refreshTableDisplayLayout(block);
        }
        await apiRequest(updateNodeUrl(block.dataset.nodeId), "PATCH", {
            text_align: align,
        });
        updateAlignmentToolbar(align);
    }

    function recordTextAlignHistory(block, beforeAlign, afterAlign) {
        if (
            !window.ReportLineUndo
            || window.ReportLineUndo.isApplying()
            || beforeAlign === afterAlign
        ) {
            return;
        }

        window.ReportLineUndo.recordCommand({
            label: "Alinhamento",
            mergeKey: `align-${block.dataset.nodeId}`,
            undo: () => applyTextAlignForHistory(block, beforeAlign),
            redo: () => applyTextAlignForHistory(block, afterAlign),
        });
    }

    function recordImmediateBlockContentChange(block, beforeContent, focusOptions = {}) {
        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {
            return;
        }

        const nodeId = block.dataset.nodeId;
        const blockType = block.dataset.blockType;
        const afterContent = collectBlockContent(block);

        if (JSON.stringify(beforeContent) === JSON.stringify(afterContent)) {
            return;
        }

        window.ReportLineUndo.recordBlockContentChange({
            nodeId,
            label: "Editar lista",
            mergeKey: "",
            undo: () => applyBlockContentForHistory(
                nodeId,
                beforeContent,
                null,
                blockType,
                focusOptions.undo || {}
            ),
            redo: () => applyBlockContentForHistory(
                nodeId,
                afterContent,
                null,
                blockType,
                focusOptions.redo || {}
            ),
        });
    }

    function recordHorizontalRuleInsertHistory(spec) {
        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {
            return;
        }

        let liveParagraphId = spec.paragraphNodeId || spec.beforeParagraphSnapshot?.nodeId;
        let liveHrId = spec.hrNodeId;
        let liveAfterParaId = spec.afterParagraphNodeId;

        window.ReportLineUndo.recordCommand({
            label: "Inserir linha horizontal",
            undo: async () => {
                const hrBlock = document.getElementById(`report-block-${liveHrId}`);
                const afterPara = document.getElementById(`report-block-${liveAfterParaId}`);
                if (hrBlock) {
                    await deleteBlockById(hrBlock, { skipHistory: true });
                }
                if (afterPara) {
                    await deleteBlockById(afterPara, { skipHistory: true });
                }

                if (spec.mode === "replace") {
                    const restored = await restoreNodeFromSnapshot(
                        spec.beforeParagraphSnapshot,
                        { skipHistory: true }
                    );
                    liveParagraphId = restored.dataset.nodeId;
                    focusBlockAtStart(restored);
                    return;
                }

                const paragraph = document.getElementById(`report-block-${liveParagraphId}`);
                if (paragraph) {
                    await applyBlockContentForHistory(
                        liveParagraphId,
                        spec.beforeContent,
                        spec.beforeContent.text,
                        "paragraph",
                        { caretAtStart: false }
                    );
                    focusBlockAtStart(paragraph.querySelector(".report-editor-block-editable"));
                }
            },
            redo: async () => {
                if (spec.mode === "replace") {
                    const paragraph = document.getElementById(`report-block-${liveParagraphId}`);
                    if (!paragraph) {
                        return;
                    }
                    const hrBlock = await createSiblingBlock(paragraph, "horizontal_rule", {
                        skipHistory: true,
                    });
                    liveHrId = hrBlock.dataset.nodeId;
                    await deleteBlockById(paragraph, { skipHistory: true });
                    const newPara = await createSiblingBlock(hrBlock, "paragraph", {
                        content: { text: spec.afterHtml || "" },
                        caretAtStart: true,
                        skipHistory: true,
                    });
                    liveAfterParaId = newPara.dataset.nodeId;
                    return;
                }

                const paragraph = document.getElementById(`report-block-${liveParagraphId}`);
                if (!paragraph) {
                    return;
                }

                setTextFieldContent(paragraph, spec.trimmedContent.text || "");
                await saveBlock(paragraph, { skipHistory: true });

                const hrBlock = await createSiblingBlock(paragraph, "horizontal_rule", {
                    skipHistory: true,
                });
                liveHrId = hrBlock.dataset.nodeId;
                const newPara = await createSiblingBlock(hrBlock, "paragraph", {
                    content: { text: spec.afterHtml || "" },
                    caretAtStart: true,
                    skipHistory: true,
                });
                liveAfterParaId = newPara.dataset.nodeId;
            },
        });
    }

    function recordImageBlocksDeleteHistory(spec) {
        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {
            return;
        }

        let liveImageId = spec.imageSnapshot.nodeId;
        let liveCaptionId = spec.captionSnapshot ? spec.captionSnapshot.nodeId : null;

        window.ReportLineUndo.recordCommand({
            label: "Excluir imagem",
            undo: async () => {
                const restoredImage = await restoreNodeFromSnapshot(
                    spec.imageSnapshot,
                    { skipHistory: true }
                );
                liveImageId = restoredImage.dataset.nodeId;
                syncAddCaptionControl(restoredImage);

                if (spec.captionSnapshot) {
                    const captionSnapshot = {
                        ...spec.captionSnapshot,
                        anchor: { type: "after", nodeId: liveImageId },
                    };
                    const restoredCaption = await restoreNodeFromSnapshot(
                        captionSnapshot,
                        { skipHistory: true }
                    );
                    liveCaptionId = restoredCaption.dataset.nodeId;
                }

                if (spec.previousBlock && spec.previousBlock.classList.contains("report-editor-block")) {
                    const editable = spec.previousBlock.querySelector(".report-editor-block-editable");
                    if (editable) {
                        placeCaretAtEnd(editable);
                        rememberEditorContext(spec.previousBlock, editable);
                    }
                } else {
                    focusBlockAtStart(restoredImage);
                }
            },
            redo: async () => {
                if (liveCaptionId) {
                    const captionBlock = document.getElementById(`report-block-${liveCaptionId}`);
                    if (captionBlock) {
                        await deleteBlockById(captionBlock, { skipHistory: true });
                    }
                }
                const imageBlock = document.getElementById(`report-block-${liveImageId}`);
                if (imageBlock) {
                    await deleteBlockById(imageBlock, { skipHistory: true });
                }
            },
        });
    }

    async function restoreNodeFromSnapshot(snapshot, options = {}) {
        const payload = {
            block_type: snapshot.blockType,
            content: snapshot.content,
        };

        if (snapshot.isCaption) {
            payload.is_caption = true;
        }
        if (snapshot.titleLevel !== undefined && snapshot.titleLevel !== "") {
            payload.title_level = Number.parseInt(snapshot.titleLevel, 10);
        }
        if (snapshot.indentLevel !== undefined && snapshot.indentLevel !== "") {
            payload.indent_level = Number.parseInt(snapshot.indentLevel, 10);
        }
        if (snapshot.firstLineIndent !== undefined) {
            payload.first_line_indent = snapshot.firstLineIndent;
        }

        if (snapshot.anchor.type === "before") {
            payload.before_node_id = snapshot.anchor.nodeId;
        } else {
            payload.after_node_id = snapshot.anchor.nodeId;
        }

        const referenceBlock = document.getElementById(`report-block-${snapshot.anchor.nodeId}`);
        if (!referenceBlock) {
            throw new Error("Não foi possível restaurar o bloco excluído.");
        }

        const data = await apiRequest(config.createNodeUrl, "POST", payload);
        const insertion = snapshot.anchor.type === "before" ? "before" : "after";
        const newBlock = insertBlockHtml(referenceBlock, data.html, insertion);
        applyCaptionNumbersFromResponse(data);

        const field = getTextField(newBlock);
        if (field && snapshot.fieldHtml) {
            setEditableHtml(field, snapshot.fieldHtml);
            await apiRequest(updateNodeUrl(newBlock.dataset.nodeId), "PATCH", {
                content: snapshot.content,
            });
        }

        if (data.block_type === "heading") {
            await refreshOutlineTree();
        }

        if (snapshot.isCaption) {
            const imageBlock = getPreviousEditorBlock(newBlock);
            if (imageBlock && imageBlock.dataset.blockType === "image") {
                syncAddCaptionControl(imageBlock);
            }
        }

        return newBlock;
    }

    function beginTextEditRecording(block, editable) {
        beginBlockContentRecording(block, editable);
    }

    function beginBlockContentRecording(block, editable) {
        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {
            return;
        }

        const blockType = block.dataset.blockType;
        const isTextBlock = TEXT_BLOCK_TYPES.has(blockType);
        const isListBlock = LIST_TYPES.has(blockType);
        const isTableBlock = blockType === "table";
        const isImageBlock = blockType === "image";
        if (!isTextBlock && !isListBlock && !isTableBlock && !isImageBlock) {
            return;
        }

        const nodeId = block.dataset.nodeId;
        if (pendingTextEdits.has(nodeId)) {
            return;
        }

        const pending = {
            nodeId,
            blockType,
            beforeContent: collectBlockContent(block),
        };

        if (isTextBlock && editable) {
            pending.beforeHtml = getEditableHtml(editable);
        } else if (isListBlock && editable && editable.classList.contains("report-editor-list-item")) {
            pending.listItemIndex = getListItemIndex(editable);
        } else if (isTableBlock && editable && editable.dataset.tablePart) {
            pending.tableFocus = {
                part: editable.dataset.tablePart,
                rowIndex: editable.dataset.tablePart === "cell"
                    ? Number.parseInt(editable.dataset.rowIndex || "0", 10)
                    : -1,
                colIndex: Number.parseInt(editable.dataset.colIndex || "0", 10),
            };
        }

        pendingTextEdits.set(nodeId, pending);
    }

    function finalizeTextEditRecording(block) {
        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {
            pendingTextEdits.delete(block.dataset.nodeId);
            return;
        }

        const nodeId = block.dataset.nodeId;
        const pending = pendingTextEdits.get(nodeId);
        if (!pending) {
            return;
        }

        const afterContent = collectBlockContent(block);
        let afterHtml = "";
        if (TEXT_BLOCK_TYPES.has(pending.blockType)) {
            const field = getTextField(block);
            afterHtml = field ? getEditableHtml(field) : "";
        }

        pendingTextEdits.delete(nodeId);

        if (JSON.stringify(pending.beforeContent) === JSON.stringify(afterContent)) {
            return;
        }

        const undoFocus = {};
        const redoFocus = {};
        if (pending.listItemIndex !== undefined) {
            undoFocus.listItemIndex = pending.listItemIndex;
            redoFocus.listItemIndex = pending.listItemIndex;
        }
        if (pending.tableFocus) {
            undoFocus.tableFocus = pending.tableFocus;
            redoFocus.tableFocus = pending.tableFocus;
        }

        const mergeKey = pending.blockType === "table" || pending.blockType === "image"
            ? `content-${nodeId}`
            : undefined;

        window.ReportLineUndo.recordBlockContentChange({
            nodeId,
            mergeKey,
            label: pending.blockType === "table" ? "Editar tabela" : undefined,
            undo: () => applyBlockContentForHistory(
                nodeId,
                pending.beforeContent,
                pending.beforeHtml,
                pending.blockType,
                undoFocus
            ),
            redo: () => applyBlockContentForHistory(
                nodeId,
                afterContent,
                afterHtml,
                pending.blockType,
                redoFocus
            ),
        });
    }

    async function flushPendingTextEdit(block) {
        if (!block) {
            return;
        }
        const nodeId = block.dataset.nodeId;
        clearHistoryTimer(nodeId);
        if (pendingTextEdits.has(nodeId)) {
            finalizeTextEditRecording(block);
        }
        clearSaveTimer(nodeId);
        await saveBlock(block, { skipHistory: true });
    }

    function clearHistoryTimer(nodeId) {
        if (historyTimers.has(nodeId)) {
            clearTimeout(historyTimers.get(nodeId));
            historyTimers.delete(nodeId);
        }
    }

    function scheduleDebouncedHistoryFinalize(block) {
        const nodeId = block.dataset.nodeId;
        if (!pendingTextEdits.has(nodeId)) {
            return;
        }
        clearHistoryTimer(nodeId);
        historyTimers.set(
            nodeId,
            setTimeout(() => {
                historyTimers.delete(nodeId);
                const liveBlock = document.getElementById(`report-block-${nodeId}`);
                if (liveBlock) {
                    finalizeTextEditRecording(liveBlock);
                }
            }, HISTORY_DEBOUNCE_MS)
        );
    }

    async function flushUndoState() {
        for (const nodeId of [...historyTimers.keys()]) {
            clearHistoryTimer(nodeId);
        }

        for (const nodeId of [...pendingTextEdits.keys()]) {
            const block = document.getElementById(`report-block-${nodeId}`);
            if (block) {
                finalizeTextEditRecording(block);
            }
        }

        const savePromises = [];

        if (window.ReportLinePageHeader && window.ReportLinePageHeader.flushHeaderUndoState) {
            savePromises.push(window.ReportLinePageHeader.flushHeaderUndoState());
        }
        if (window.ReportLinePageFooter && window.ReportLinePageFooter.flushFooterUndoState) {
            savePromises.push(window.ReportLinePageFooter.flushFooterUndoState());
        }

        for (const [nodeId, timer] of saveTimers.entries()) {
            clearTimeout(timer);
            const block = document.getElementById(`report-block-${nodeId}`);
            if (block) {
                savePromises.push(saveBlock(block, { skipHistory: true }));
            }
        }
        saveTimers.clear();

        if (window.ReportLinePageHeader && window.ReportLinePageHeader.flushHeaderSave) {
            savePromises.push(window.ReportLinePageHeader.flushHeaderSave());
        }
        if (window.ReportLinePageFooter && window.ReportLinePageFooter.flushFooterSave) {
            savePromises.push(window.ReportLinePageFooter.flushFooterSave());
        }

        await Promise.all(savePromises);
    }

    function recordBlockDeleteHistory(snapshot, focusHints = {}) {
        if (
            !snapshot
            || !window.ReportLineUndo
            || window.ReportLineUndo.isApplying()
        ) {
            return;
        }

        let liveNodeId = snapshot.nodeId;
        window.ReportLineUndo.recordBlockDelete({
            undo: async () => {
                const restored = await restoreNodeFromSnapshot(snapshot, { skipHistory: true });
                liveNodeId = restored.dataset.nodeId;
                if (focusHints.focusNext) {
                    focusBlockAtStart(restored);
                } else if (focusHints.focusPrevious && focusHints.previousBlock) {
                    const editable = focusHints.previousBlock.querySelector(
                        ".report-editor-block-editable"
                    );
                    if (editable) {
                        placeCaretAtEnd(editable);
                        rememberEditorContext(focusHints.previousBlock, editable);
                    }
                } else {
                    focusBlockAtStart(restored);
                }
            },
            redo: async () => {
                const blockElement = document.getElementById(`report-block-${liveNodeId}`);
                if (blockElement) {
                    await deleteBlockById(blockElement, { skipHistory: true });
                }
            },
        });
    }

    function recordBlockInsertHistory(createPayload, newBlock, options = {}) {
        if (
            !window.ReportLineUndo
            || window.ReportLineUndo.isApplying()
            || options.skipHistory
        ) {
            return;
        }

        const snapshot = buildSnapshotFromCreatePayload(createPayload, newBlock);
        let liveNodeId = newBlock.dataset.nodeId;

        window.ReportLineUndo.recordBlockInsert({
            undo: async () => {
                const blockElement = document.getElementById(`report-block-${liveNodeId}`);
                if (blockElement) {
                    await deleteBlockById(blockElement, { skipHistory: true });
                }
            },
            redo: async () => {
                const restored = await restoreNodeFromSnapshot(snapshot, { skipHistory: true });
                liveNodeId = restored.dataset.nodeId;
                focusNewBlock(restored, { caretAtStart: options.caretAtStart });
            },
        });
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

    function applyCaptionNumbersFromResponse(data) {
        if (
            !data
            || !data.caption_numbers
            || !window.ReportLineReportConfig
            || !window.ReportLineReportConfig.applyCaptionNumbers
        ) {
            return;
        }
        window.ReportLineReportConfig.applyCaptionNumbers(data.caption_numbers);
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

        applyCaptionNumbersFromResponse(data);

        if (!options.skipHistory) {
            finalizeTextEditRecording(block);
        } else {
            pendingTextEdits.delete(nodeId);
        }

        return data;
    }

    function clearSaveTimer(nodeId) {
        if (saveTimers.has(nodeId)) {
            clearTimeout(saveTimers.get(nodeId));
            saveTimers.delete(nodeId);
        }
    }

    function scheduleDebouncedSave(block) {
        const nodeId = block.dataset.nodeId;
        if (saveTimers.has(nodeId)) {
            clearTimeout(saveTimers.get(nodeId));
        }
        saveTimers.set(
            nodeId,
            setTimeout(() => {
                saveBlock(block, { skipHistory: true }).catch(console.error);
            }, DEBOUNCE_MS)
        );
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

    function getCaptionBlock(imageBlock) {
        const captionBlock = imageBlock.nextElementSibling;
        if (captionBlock && captionBlock.dataset.isCaption === "true") {
            return captionBlock;
        }
        return null;
    }

    function imageHasCaption(imageBlock) {
        return Boolean(getCaptionBlock(imageBlock));
    }

    function syncAddCaptionControl(imageBlock) {
        if (!imageBlock || imageBlock.dataset.blockType !== "image") {
            return;
        }

        const button = imageBlock.querySelector("[data-report-image-add-caption-inline]");
        if (!button) {
            return;
        }

        const hasCaption = imageHasCaption(imageBlock);
        const selectedTarget = window.ReportLineImageResize
            && window.ReportLineImageResize.getSelectedTarget
            ? window.ReportLineImageResize.getSelectedTarget()
            : null;
        const isSelected = Boolean(
            selectedTarget
            && selectedTarget.type === "block"
            && selectedTarget.root === imageBlock
        );
        const show = !hasCaption && isSelected;

        button.classList.toggle("d-none", !show);
        button.hidden = !show;
    }

    function syncAllAddCaptionControls() {
        document.querySelectorAll('.report-editor-block[data-block-type="image"]').forEach((imageBlock) => {
            syncAddCaptionControl(imageBlock);
        });
    }

    async function ensureCaptionParagraphAfterImage(imageBlock) {
        const nextBlock = imageBlock.nextElementSibling;
        if (nextBlock && nextBlock.dataset.isCaption === "true") {
            focusCaptionParagraph(nextBlock);
            syncCaptionWidthForImageBlock(imageBlock);
            syncAddCaptionControl(imageBlock);
            return nextBlock;
        }

        const captionBlock = await createSiblingBlock(imageBlock, "paragraph", {
            content: { text: "" },
            isCaption: true,
            caretAtStart: true,
        });
        syncCaptionWidthForImageBlock(imageBlock);
        syncAddCaptionControl(imageBlock);
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
        const beforeState = window.ReportLineUndo && !window.ReportLineUndo.isApplying()
            ? captureBlockState(block)
            : null;
        const content = buildContentForBlockType(block, editable, targetBlockType);
        const focusOptions = {};
        const undoFocusOptions = {};

        if (TEXT_BLOCK_TYPES.has(sourceType) && editable) {
            focusOptions.caret = getCaretOffset(editable);
            undoFocusOptions.caret = getCaretOffset(editable);
        } else if (
            LIST_TYPES.has(sourceType)
            && editable
            && editable.classList.contains("report-editor-list-item")
        ) {
            focusOptions.listItemIndex = getListItemIndex(editable);
            focusOptions.caret = getCaretOffset(editable);
            undoFocusOptions.listItemIndex = focusOptions.listItemIndex;
            undoFocusOptions.caret = focusOptions.caret;
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

        if (beforeState) {
            recordBlockStateChange(
                beforeState,
                captureBlockState(targetBlock),
                undoFocusOptions,
                focusOptions
            );
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
        const payload = buildCreatePayload(referenceBlock, blockType, options);

        const data = await apiRequest(config.createNodeUrl, "POST", payload);
        const newBlock = insertBlockHtml(referenceBlock, data.html, data.insertion);
        focusNewBlock(newBlock, { caretAtStart: options.caretAtStart });
        applyCaptionNumbersFromResponse(data);
        recordBlockInsertHistory(payload, newBlock, options);
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
        const beforeContent = collectBlockContent(block);
        const items = getListItems(block);
        const index = getListItemIndex(activeItem);
        const caret = getCaretOffset(activeItem);
        const text = getEditablePlainText(activeItem);
        const atStart = caret === 0;
        const atEnd = caret >= text.length;

        if (atStart) {
            items.splice(index, 0, "");
            await saveBlock(block, { updateListItems: true, items, skipHistory: true });
            rebuildListItems(block, items);
            const newItem = block.querySelectorAll(".report-editor-list-item")[index];
            placeCaretAtEnd(newItem);
            recordImmediateBlockContentChange(block, beforeContent, {
                undo: { listItemIndex: index + 1, caretAtStart: false },
                redo: { listItemIndex: index, caretAtStart: true },
            });
            return;
        }

        if (!atEnd) {
            const { beforeHtml, afterHtml } = splitEditableAtCaret(activeItem);
            items[index] = beforeHtml;
            items.splice(index + 1, 0, afterHtml);
            await saveBlock(block, { updateListItems: true, items, skipHistory: true });
            rebuildListItems(block, items);
            const nextItem = block.querySelectorAll(".report-editor-list-item")[index + 1];
            placeCaretAtStart(nextItem);
            recordImmediateBlockContentChange(block, beforeContent, {
                undo: { listItemIndex: index, caret: beforeHtml.length },
                redo: { listItemIndex: index + 1, caretAtStart: true },
            });
            return;
        }

        await saveBlock(block, { appendListItem: true, skipHistory: true });
        const newItem = document.createElement("li");
        newItem.className = "report-editor-block-editable report-editor-list-item";
        newItem.contentEditable = "true";
        newItem.dataset.listIndex = String(items.length);
        newItem.dataset.placeholder = "Item da lista";
        block.querySelector("[data-field=\"items\"]").appendChild(newItem);
        placeCaretAtEnd(newItem);
        recordImmediateBlockContentChange(block, beforeContent, {
            undo: { listItemIndex: items.length - 1, caretAtStart: false },
            redo: { listItemIndex: items.length, caretAtStart: true },
        });
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

        const beforeContent = cloneTableContent(collectBlockContent(block));
        const tableFocus = {
            part: "cell",
            rowIndex: Number.parseInt(cellContainer.dataset.rowIndex || "0", 10),
            colIndex: Number.parseInt(cellContainer.dataset.colIndex || "0", 10),
        };

        cellContainer.classList.add("report-editor-table-cell-has-image");
        const usableWidth = getTableCellUsableWidth(cellElement);
        const displaySize = computeImageSizeForCell(imagePayload, usableWidth);
        cellContainer.innerHTML = buildTableCellImageHtml(
            imagePayload,
            displaySize.width,
            displaySize.height
        );
        await saveBlock(block, { skipHistory: true });
        recordTableContentHistory(
            block.dataset.nodeId,
            beforeContent,
            cloneTableContent(collectBlockContent(block)),
            tableFocus
        );
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

    async function tryInsertHorizontalRuleFromParagraphEnter(block, editable) {
        if (block.dataset.blockType !== "paragraph") {
            return false;
        }

        const { beforeHtml, afterHtml } = splitEditableAtCaret(editable);
        const lastLine = getLastLinePlainTextFromHtml(beforeHtml);
        if (!isHorizontalRuleShortcutLine(lastLine)) {
            return false;
        }

        clearSaveTimer(block.dataset.nodeId);
        const trimmedBeforeHtml = removeLastLineFromHtml(beforeHtml);
        const paragraphEmptied = isEmptyHtml(trimmedBeforeHtml);
        const beforeParagraphSnapshot = buildNodeSnapshot(block);
        const fullBeforeContent = collectBlockContent(block);

        if (paragraphEmptied) {
            const hrBlock = await createSiblingBlock(block, "horizontal_rule", { skipHistory: true });
            await deleteBlockById(block, { skipHistory: true });
            const newPara = await createSiblingBlock(hrBlock, "paragraph", {
                content: { text: afterHtml || "" },
                caretAtStart: true,
                skipHistory: true,
            });
            recordHorizontalRuleInsertHistory({
                mode: "replace",
                beforeParagraphSnapshot,
                afterHtml: afterHtml || "",
                hrNodeId: hrBlock.dataset.nodeId,
                afterParagraphNodeId: newPara.dataset.nodeId,
            });
            return true;
        }

        setTextFieldContent(block, trimmedBeforeHtml);
        await saveBlock(block, { skipHistory: true });

        const hrBlock = await createSiblingBlock(block, "horizontal_rule", { skipHistory: true });
        const newPara = await createSiblingBlock(hrBlock, "paragraph", {
            content: { text: afterHtml || "" },
            caretAtStart: true,
            skipHistory: true,
        });
        recordHorizontalRuleInsertHistory({
            mode: "split",
            paragraphNodeId: block.dataset.nodeId,
            beforeContent: fullBeforeContent,
            trimmedContent: { text: trimmedBeforeHtml },
            afterHtml: afterHtml || "",
            hrNodeId: hrBlock.dataset.nodeId,
            afterParagraphNodeId: newPara.dataset.nodeId,
        });
        return true;
    }

    async function handleTextBlockEnter(block, editable) {
        if (block.dataset.blockType === "paragraph") {
            const inserted = await tryInsertHorizontalRuleFromParagraphEnter(block, editable);
            if (inserted) {
                return;
            }
        }

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

    async function deleteBlockById(block, options = {}) {
        const nodeId = block.dataset.nodeId;
        clearSaveTimer(nodeId);
        clearHistoryTimer(nodeId);
        pendingTextEdits.delete(nodeId);

        const snapshot = options.skipHistory ? null : buildNodeSnapshot(block);
        const focusHints = options.historyFocus || {};

        const data = await apiRequest(updateNodeUrl(nodeId), "DELETE");
        block.remove();
        applyCaptionNumbersFromResponse(data);

        if (!options.skipHistory && snapshot) {
            recordBlockDeleteHistory(snapshot, focusHints);
        }
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
        const beforeContent = cloneTableContent(collectBlockContent(tableBlock));
        const tableFocus = {
            part: "cell",
            rowIndex: Number.parseInt(rowIndex, 10),
            colIndex: Number.parseInt(colIndex, 10),
        };

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
        await saveBlock(tableBlock, { skipHistory: true });
        recordTableContentHistory(
            tableBlock.dataset.nodeId,
            beforeContent,
            cloneTableContent(collectBlockContent(tableBlock)),
            tableFocus
        );
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

        if (selectedTarget.type === "page-header-logo") {
            if (window.ReportLinePageHeader && window.ReportLinePageHeader.clearLogoCell) {
                await window.ReportLinePageHeader.clearLogoCell(selectedTarget.root);
            }
            return true;
        }

        if (selectedTarget.type === "page-footer-logo") {
            if (window.ReportLinePageFooter && window.ReportLinePageFooter.clearLogoCell) {
                await window.ReportLinePageFooter.clearLogoCell(selectedTarget.root);
            }
            return true;
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
        const imageSnapshot = buildNodeSnapshot(imageBlock);
        const captionSnapshot = hasCaption ? buildNodeSnapshot(captionBlock) : null;

        if (hasCaption) {
            await deleteBlockById(captionBlock, { skipHistory: true });
        }
        await deleteBlockById(imageBlock, { skipHistory: true });

        if (imageSnapshot) {
            recordImageBlocksDeleteHistory({
                imageSnapshot,
                captionSnapshot,
                previousBlock: previousBlock && previousBlock.classList.contains("report-editor-block")
                    ? previousBlock
                    : null,
            });
        }

        if (previousBlock && previousBlock.classList.contains("report-editor-block")) {
            const editable = previousBlock.querySelector(".report-editor-block-editable");
            if (editable) {
                placeCaretAtEnd(editable);
                rememberEditorContext(previousBlock, editable);
            }
        }
        return true;
    }

    async function deleteEmptyBlock(block, options = {}) {
        const nodeId = block.dataset.nodeId;
        clearSaveTimer(nodeId);
        clearHistoryTimer(nodeId);
        pendingTextEdits.delete(nodeId);

        const focusNext = Boolean(options.focusNext);
        const nextBlock = focusNext ? getNextEditorBlock(block) : null;
        const previousBlock = block.previousElementSibling;
        const blockType = block.dataset.blockType;
        const wasCaption = block.dataset.isCaption === "true";

        const snapshot = options.skipHistory ? null : buildNodeSnapshot(block);
        const focusHints = options.skipHistory
            ? null
            : {
                focusNext,
                focusPrevious: !focusNext,
                previousBlock: !focusNext
                    && previousBlock
                    && previousBlock.classList.contains("report-editor-block")
                    ? previousBlock
                    : null,
            };

        const data = await apiRequest(updateNodeUrl(nodeId), "DELETE");

        block.remove();
        applyCaptionNumbersFromResponse(data);
        if (blockType === "heading") {
            await refreshOutlineTree();
        }

        if (!options.skipHistory && snapshot) {
            recordBlockDeleteHistory(snapshot, focusHints);
        }

        if (wasCaption && previousBlock && previousBlock.dataset.blockType === "image") {
            syncAddCaptionControl(previousBlock);
        }

        if (focusNext) {
            let candidate = nextBlock;
            while (candidate && !focusBlockAtStart(candidate)) {
                candidate = getNextEditorBlock(candidate);
            }
            if (!candidate && previousBlock && previousBlock.classList.contains("report-editor-block")) {
                const editable = previousBlock.querySelector(".report-editor-block-editable");
                if (editable) {
                    placeCaretAtEnd(editable);
                    rememberEditorContext(previousBlock, editable);
                }
            }
            return;
        }

        if (previousBlock && previousBlock.classList.contains("report-editor-block")) {
            const editable = previousBlock.querySelector(".report-editor-block-editable");
            if (editable) {
                placeCaretAtEnd(editable);
                rememberEditorContext(previousBlock, editable);
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

        const beforeContent = collectBlockContent(block);
        items.splice(index, 1);
        clearSaveTimer(block.dataset.nodeId);
        await saveBlock(block, { updateListItems: true, items, skipHistory: true });
        rebuildListItems(block, items);
        const focusIndex = Math.max(index - 1, 0);
        const target = block.querySelectorAll(".report-editor-list-item")[focusIndex];
        if (target) {
            placeCaretAtEnd(target);
        }
        recordImmediateBlockContentChange(block, beforeContent, {
            undo: { listItemIndex: index, caretAtStart: false },
            redo: { listItemIndex: focusIndex, caretAtStart: false },
        });
    }

    async function handleDelete(block, editable) {
        if (block.dataset.blockType !== "paragraph") {
            return;
        }

        if (!isEditableFullySelected(editable)) {
            return;
        }

        await deleteEmptyBlock(block, { focusNext: true });
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

    function resolveBandTextTarget() {
        if (window.ReportLinePageHeader && window.ReportLinePageHeader.isEditing()) {
            const field = window.ReportLinePageHeader.getActiveHeaderTextField
                ? window.ReportLinePageHeader.getActiveHeaderTextField()
                : null;
            if (field) {
                return {
                    kind: "page-header-text",
                    target: field,
                    bandText: true,
                    editable: field,
                    band: "header",
                };
            }
        }

        if (window.ReportLinePageFooter && window.ReportLinePageFooter.isEditing()) {
            const field = window.ReportLinePageFooter.getActiveFooterTextField
                ? window.ReportLinePageFooter.getActiveFooterTextField()
                : null;
            if (field) {
                return {
                    kind: "page-footer-text",
                    target: field,
                    bandText: true,
                    editable: field,
                    band: "footer",
                };
            }
        }

        return null;
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

        const bandContext = resolveBandTextTarget();
        if (bandContext) {
            return { kind: bandContext.kind, target: bandContext.target };
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

            if (
                window.ReportLinePageFooter
                && window.ReportLinePageFooter.isEditing()
                && active.matches("[data-report-page-footer-text][contenteditable='true']")
            ) {
                return {
                    kind: "page-footer-text",
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

        if (window.ReportLinePageFooter && window.ReportLinePageFooter.resolveFooterTextContext) {
            const footerContext = window.ReportLinePageFooter.resolveFooterTextContext();
            if (footerContext) {
                return {
                    kind: "page-footer-text",
                    target: footerContext.editable,
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
        if (context.kind === "page-footer-text") {
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

    const ALIGN_ICONS = {
        left: "bi-text-left",
        center: "bi-text-center",
        right: "bi-text-right",
        justify: "bi-justify",
    };

    const ALIGN_LABELS = {
        left: "Alinhar à esquerda",
        center: "Centralizar",
        right: "Alinhar à direita",
        justify: "Justificar",
    };

    function updateAlignmentToolbar(activeAlign) {
        const alignGroup = document.querySelector(".report-editor-toolbar-align-group");
        const resolvedAlign = activeAlign || "justify";

        if (alignGroup) {
            const mainButton = alignGroup.querySelector("[data-report-text-align-main]");
            if (mainButton) {
                mainButton.dataset.reportTextAlign = resolvedAlign;
                mainButton.title = ALIGN_LABELS[resolvedAlign] || ALIGN_LABELS.justify;
                mainButton.setAttribute("aria-label", mainButton.title);
                const icon = mainButton.querySelector("i");
                if (icon) {
                    icon.className = `bi ${ALIGN_ICONS[resolvedAlign] || ALIGN_ICONS.justify}`;
                }
            }

            alignGroup.querySelectorAll("[data-report-text-align]").forEach((button) => {
                const isActive = Boolean(activeAlign) && button.dataset.reportTextAlign === activeAlign;
                button.classList.toggle("active", isActive);
                button.setAttribute("aria-pressed", isActive ? "true" : "false");
            });
            return;
        }

        document.querySelectorAll("[data-report-text-align]").forEach((button) => {
            const isActive = Boolean(activeAlign) && button.dataset.reportTextAlign === activeAlign;
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

        if (context.kind === "page-footer-text") {
            if (
                window.ReportLinePageFooter
                && window.ReportLinePageFooter.applyFooterTextAlign
            ) {
                const footerAlign = ["left", "center", "right"].includes(align) ? align : "left";
                window.ReportLinePageFooter.applyFooterTextAlign(context.target, footerAlign);
                updateAlignmentToolbar(footerAlign);
            }
            return;
        }

        if (context.kind === "table-cell" || context.kind === "table-cell-image") {
            const beforeContent = cloneTableContent(collectBlockContent(context.block));
            const tableFocus = {
                part: context.target.dataset.tablePart || "cell",
                rowIndex: context.target.dataset.tablePart === "cell"
                    ? Number.parseInt(context.target.dataset.rowIndex || "0", 10)
                    : -1,
                colIndex: Number.parseInt(context.target.dataset.colIndex || "0", 10),
            };

            applyTextAlignToTableTarget(context.target, align);
            if (context.kind === "table-cell-image") {
                applyTableCellImageAlignVisual(context.target, align);
            }
            clearSaveTimer(context.block.dataset.nodeId);
            await saveBlock(context.block, { skipHistory: true });
            recordTableContentHistory(
                context.block.dataset.nodeId,
                beforeContent,
                cloneTableContent(collectBlockContent(context.block)),
                tableFocus
            );
            updateAlignmentToolbar(align);
            return;
        }

        const beforeAlign = context.block.dataset.textAlign
            || defaultTextAlignForBlock(
                context.block.dataset.blockType,
                {
                    isMainTitle: context.block.dataset.blockType === "heading"
                        && context.block.dataset.isMainTitle === "true",
                    isCaption: context.block.dataset.isCaption === "true",
                }
            );

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
        recordTextAlignHistory(context.block, beforeAlign, align);
        updateAlignmentToolbar(align);
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
            const beforeAlign = selectedTarget.root.dataset.textAlign || "center";
            applyTextAlignToBlock(selectedTarget.root, align);
            applyImageBlockAlignVisual(selectedTarget.root, align);
            clearSaveTimer(selectedTarget.root.dataset.nodeId);
            await syncCaptionWithImageAlign(selectedTarget.root, align);
            await apiRequest(updateNodeUrl(selectedTarget.root.dataset.nodeId), "PATCH", {
                text_align: align,
            });
            recordTextAlignHistory(selectedTarget.root, beforeAlign, align);
            selectedTarget.root.focus({ preventScroll: true });
            refreshAlignmentToolbarState();
            return;
        }

        const tableBlock = selectedTarget.tableBlock;
        const beforeContent = cloneTableContent(collectBlockContent(tableBlock));
        const rowIndex = Number.parseInt(
            selectedTarget.root.closest("td")?.dataset.rowIndex || "0",
            10
        );
        const colIndex = Number.parseInt(
            selectedTarget.root.closest("td")?.dataset.colIndex || "0",
            10
        );
        const tableFocus = {
            part: "cell",
            rowIndex,
            colIndex,
        };

        applyTextAlignToTableTarget(selectedTarget.root, align);
        applyTableCellImageAlignVisual(selectedTarget.root, align);
        clearSaveTimer(tableBlock.dataset.nodeId);
        await saveBlock(tableBlock, { skipHistory: true });
        recordTableContentHistory(
            tableBlock.dataset.nodeId,
            beforeContent,
            cloneTableContent(collectBlockContent(tableBlock)),
            tableFocus
        );
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
        const beforeAlign = block.dataset.textAlign || "left";
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
        recordTextAlignHistory(block, beforeAlign, align);
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

    function isLayoutToolbarControl(element) {
        if (!element || !element.closest) {
            return false;
        }
        return (
            isParagraphToolbarControl(element)
            || Boolean(element.closest(".report-editor-toolbar-align-group"))
            || Boolean(element.closest(".report-editor-toolbar-format-group"))
        );
    }

    function resolveParagraphContextFromActiveElement() {
        const active = document.activeElement;
        if (!active || !active.closest) {
            return null;
        }

        if (active.matches("[data-report-page-header-text][contenteditable='true']")) {
            return { bandText: true, editable: active, band: "header" };
        }

        if (active.matches("[data-report-page-footer-text][contenteditable='true']")) {
            return { bandText: true, editable: active, band: "footer" };
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
        if (context && (context.block || context.bandText)) {
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

        const bandContext = resolveBandTextTarget();
        if (bandContext) {
            rememberParagraphContext(bandContext);
            return bandContext;
        }

        if (
            lastParagraphContext
            && (
                (lastParagraphContext.block && document.contains(lastParagraphContext.block))
                || (lastParagraphContext.bandText && document.contains(lastParagraphContext.editable))
            )
            && isLayoutToolbarControl(document.activeElement)
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

    async function patchParagraphLayout(block, layout, options = {}) {
        const beforeLayout = options.skipHistory ? null : captureParagraphLayout(block);
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

        if (!options.skipHistory && beforeLayout) {
            recordParagraphLayoutHistory(block, beforeLayout, captureParagraphLayout(block));
        }

        return data;
    }

    async function increaseParagraphIndent() {
        const context = resolveParagraphContext();
        if (!context) {
            return;
        }

        if (context.bandText) {
            if (context.band === "header" && window.ReportLinePageHeader) {
                window.ReportLinePageHeader.increaseTextIndent();
            } else if (context.band === "footer" && window.ReportLinePageFooter) {
                window.ReportLinePageFooter.increaseTextIndent();
            }
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

        if (context.bandText) {
            if (context.band === "header" && window.ReportLinePageHeader) {
                window.ReportLinePageHeader.decreaseTextIndent();
            } else if (context.band === "footer" && window.ReportLinePageFooter) {
                window.ReportLinePageFooter.decreaseTextIndent();
            }
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

        if (context.bandText) {
            if (context.band === "header" && window.ReportLinePageHeader) {
                window.ReportLinePageHeader.toggleTextFirstLineIndent();
            } else if (context.band === "footer" && window.ReportLinePageFooter) {
                window.ReportLinePageFooter.toggleTextFirstLineIndent();
            }
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
                if (getCaretOffset(editable) === 0) {
                    if (isEditableEmpty(editable)) {
                        event.preventDefault();
                        handleBackspace(block, editable).catch(console.error);
                    } else if (shouldBackspaceRemoveAdjacentHorizontalRule(block, editable)) {
                        event.preventDefault();
                        handleBackspaceAdjacentHorizontalRule(block, editable).catch(console.error);
                    }
                }
                return;
            }

            if (event.key === "Delete") {
                if (
                    block.dataset.blockType === "paragraph"
                    && isEditableFullySelected(editable)
                ) {
                    event.preventDefault();
                    handleDelete(block, editable).catch(console.error);
                    return;
                }
                if (shouldDeleteRemoveAdjacentHorizontalRule(block, editable)) {
                    event.preventDefault();
                    handleDeleteAdjacentHorizontalRule(block, editable).catch(console.error);
                }
            }
        });

        page.addEventListener("beforeinput", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
                return;
            }
            const block = editable.closest(".report-editor-block");
            if (block) {
                beginBlockContentRecording(block, editable);
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
                scheduleDebouncedHistoryFinalize(block);
                scheduleDebouncedSave(block);
            }
        });

        page.addEventListener("focusin", (event) => {
            const block = event.target.closest(".report-editor-block");
            if (block) {
                block.classList.add("is-active");
                const editable = event.target.closest(".report-editor-block-editable");
                if (editable && block.contains(editable)) {
                    beginBlockContentRecording(block, editable);
                    rememberEditorContext(block, editable);
                }
                refreshAlignmentToolbarState();
                return;
            }

            if (event.target.closest("[data-report-page-header-text], [data-report-page-footer-text]")) {
                const bandContext = resolveBandTextTarget();
                if (bandContext) {
                    rememberParagraphContext(bandContext);
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
                flushPendingTextEdit(block).catch(console.error);
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

    async function patchTableContent(block, content, focus, options = {}) {
        clearSaveTimer(block.dataset.nodeId);
        const nodeId = block.dataset.nodeId;
        const beforeContent = options.skipHistory
            ? null
            : cloneTableContent(collectBlockContent(block));
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
        let replacement = block;
        if (data.html) {
            replacement = replaceBlockFromHtml(nodeId, data.html);
            if (replacement) {
                focusNewBlock(replacement);
            }
        }

        if (!options.skipHistory && beforeContent) {
            const afterBlock = document.getElementById(`report-block-${nodeId}`) || replacement;
            recordTableContentHistory(
                nodeId,
                beforeContent,
                cloneTableContent(collectBlockContent(afterBlock)),
                focus
            );
        }

        return replacement;
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
        beginBlockContentRecording,
        flushUndoState,
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
        ensureCaptionParagraphAfterImage,
        imageHasCaption,
        syncAllAddCaptionControls,
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
