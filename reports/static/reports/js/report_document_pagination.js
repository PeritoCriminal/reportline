/**
 * Paginação client-side do preview de leitura do laudo.
 *
 * Distribui blocos do corpo em folhas A4, repetindo cabeçalho e rodapé
 * configurados, atualizando a numeração "Página N de T" e permitindo
 * quebra de parágrafos e listas entre páginas com controle de linhas mínimas.
 */
(function () {
    "use strict";

    const MIN_FRAGMENT_LINES = 2;
    const MIN_FRAGMENT_ITEMS = 2;
    const LINE_TOP_TOLERANCE_PX = 2;

    function paginateDocument() {
        const root = document.querySelector(".report-document-preview");
        const source = document.querySelector(".report-document-pagination-source");
        const pagesContainer = document.getElementById("report-document-pages");
        if (!root || !source || !pagesContainer) {
            return;
        }

        const headerTemplate = document.getElementById("report-document-header-template");
        const footerTemplate = document.getElementById("report-document-footer-template");
        const bodySource = source.querySelector(".report-document-body");
        const blocks = bodySource ? Array.from(bodySource.children) : [];

        pagesContainer.innerHTML = "";

        const probeSheet = buildProbeSheet(headerTemplate, footerTemplate);
        document.body.appendChild(probeSheet);
        const bodyProbe = probeSheet.querySelector(".report-document-page-sheet-body");
        const maxBodyHeight = bodyProbe ? bodyProbe.clientHeight : 0;
        document.body.removeChild(probeSheet);

        if (maxBodyHeight <= 0) {
            return;
        }

        const pages = [];
        let currentPage = appendSheet(pagesContainer, headerTemplate, footerTemplate);
        pages.push(currentPage);

        blocks.forEach((block) => {
            currentPage = placeBlock(
                currentPage,
                block,
                maxBodyHeight,
                pagesContainer,
                headerTemplate,
                footerTemplate,
                pages
            );
        });

        updatePageNumbers(pages, pages.length);
    }

    function placeBlock(
        currentPage,
        block,
        maxBodyHeight,
        pagesContainer,
        headerTemplate,
        footerTemplate,
        pages
    ) {
        currentPage.body.appendChild(block);

        if (currentPage.body.scrollHeight <= maxBodyHeight) {
            return currentPage;
        }

        const overflowBlock = currentPage.body.lastElementChild;
        if (!overflowBlock) {
            return currentPage;
        }

        const tailBlock = splitOverflowBlock(overflowBlock, currentPage.body, maxBodyHeight);
        if (tailBlock) {
            currentPage = appendSheet(pagesContainer, headerTemplate, footerTemplate);
            pages.push(currentPage);
            return placeBlock(
                currentPage,
                tailBlock,
                maxBodyHeight,
                pagesContainer,
                headerTemplate,
                footerTemplate,
                pages
            );
        }

        if (currentPage.body.children.length > 1) {
            currentPage.body.removeChild(overflowBlock);
            currentPage = appendSheet(pagesContainer, headerTemplate, footerTemplate);
            pages.push(currentPage);
            return placeBlock(
                currentPage,
                overflowBlock,
                maxBodyHeight,
                pagesContainer,
                headerTemplate,
                footerTemplate,
                pages
            );
        }

        return currentPage;
    }

    function splitOverflowBlock(block, bodyElement, maxBodyHeight) {
        if (isSplittableParagraphBlock(block)) {
            return splitParagraphBlock(block, bodyElement, maxBodyHeight);
        }
        if (isSplittableListBlock(block)) {
            return splitListBlock(block, bodyElement, maxBodyHeight);
        }
        return null;
    }

    function isSplittableParagraphBlock(block) {
        if (!block || !block.classList.contains("report-document-block--paragraph")) {
            return false;
        }
        if (block.dataset.isCaption === "true") {
            return false;
        }
        return Boolean(block.querySelector(".report-document-paragraph"));
    }

    function isSplittableListBlock(block) {
        if (!block) {
            return false;
        }
        const blockType = block.dataset.blockType;
        if (blockType !== "ordered_list" && blockType !== "unordered_list") {
            return false;
        }
        return Boolean(block.querySelector(".report-document-list-item"));
    }

    function getInlineTextApi() {
        const inlineApi = window.ReportLineInlineText;
        if (!inlineApi || !inlineApi.splitElementAtPlainTextOffset) {
            return null;
        }
        return inlineApi;
    }

    function getCaretTopAtOffset(element, offset) {
        const range = document.createRange();
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let remaining = offset;

        while (walker.nextNode()) {
            const node = walker.currentNode;
            const length = node.textContent.length;
            if (remaining <= length) {
                range.setStart(node, remaining);
                range.collapse(true);
                const rects = range.getClientRects();
                return rects.length ? Math.round(rects[0].top) : null;
            }
            remaining -= length;
        }

        return null;
    }

    function getVisualLineStartOffsets(element) {
        const totalLength = (element.textContent || "").length;
        if (totalLength === 0) {
            return [0];
        }

        const lineStarts = [0];
        let lastTop = getCaretTopAtOffset(element, 0);

        for (let offset = 1; offset < totalLength; offset += 1) {
            const top = getCaretTopAtOffset(element, offset);
            if (
                top !== null
                && lastTop !== null
                && Math.abs(top - lastTop) > LINE_TOP_TOLERANCE_PX
            ) {
                lineStarts.push(offset);
            }
            if (top !== null) {
                lastTop = top;
            }
        }

        return lineStarts;
    }

    function splitOffsetForHeadLineCount(lineStarts, headLineCount, totalLength) {
        if (headLineCount <= 0) {
            return 0;
        }
        if (headLineCount >= lineStarts.length) {
            return totalLength;
        }
        return lineStarts[headLineCount];
    }

    function blockFitsInBody(bodyElement, maxBodyHeight) {
        return bodyElement.scrollHeight <= maxBodyHeight;
    }

    function copyBlockAttributes(sourceBlock, targetBlock) {
        Array.from(sourceBlock.attributes).forEach((attribute) => {
            if (attribute.name === "id") {
                return;
            }
            targetBlock.setAttribute(attribute.name, attribute.value);
        });
    }

    function findBestVisualLineSplit(element, bodyElement, maxBodyHeight, fitsCheck) {
        const inlineApi = getInlineTextApi();
        if (!inlineApi || !element) {
            return null;
        }

        const originalHtml = element.innerHTML;
        const totalLength = (element.textContent || "").length;
        if (totalLength <= 0) {
            return null;
        }

        element.innerHTML = originalHtml;
        const lineStarts = getVisualLineStartOffsets(element);
        const lineCount = lineStarts.length;

        if (lineCount <= MIN_FRAGMENT_LINES) {
            return null;
        }

        const minHeadLines = MIN_FRAGMENT_LINES;
        const maxHeadLines = lineCount - MIN_FRAGMENT_LINES;
        let bestHeadLines = 0;

        for (let headLineCount = minHeadLines; headLineCount <= maxHeadLines; headLineCount += 1) {
            const splitOffset = splitOffsetForHeadLineCount(
                lineStarts,
                headLineCount,
                totalLength
            );
            if (splitOffset <= 0 || splitOffset >= totalLength) {
                continue;
            }

            element.innerHTML = originalHtml;
            const { beforeHtml } = inlineApi.splitElementAtPlainTextOffset(
                element,
                splitOffset
            );
            element.innerHTML = beforeHtml;

            if (fitsCheck(bodyElement, maxBodyHeight)) {
                bestHeadLines = headLineCount;
            }
        }

        element.innerHTML = originalHtml;

        if (bestHeadLines <= 0) {
            return null;
        }

        const splitOffset = splitOffsetForHeadLineCount(
            lineStarts,
            bestHeadLines,
            totalLength
        );
        const tailLineCount = lineCount - bestHeadLines;

        if (
            bestHeadLines < MIN_FRAGMENT_LINES
            || tailLineCount < MIN_FRAGMENT_LINES
            || splitOffset <= 0
            || splitOffset >= totalLength
        ) {
            return null;
        }

        return { splitOffset, inlineApi, originalHtml };
    }

    function applyVisualLineSplit(element, splitPlan) {
        const { splitOffset, inlineApi, originalHtml } = splitPlan;
        element.innerHTML = originalHtml;
        const { beforeHtml, afterHtml } = inlineApi.splitElementAtPlainTextOffset(
            element,
            splitOffset
        );
        element.innerHTML = beforeHtml;
        return afterHtml;
    }

    function createParagraphContinuationBlock(sourceBlock, html) {
        const sourceParagraph = sourceBlock.querySelector(".report-document-paragraph");
        if (!sourceParagraph) {
            return null;
        }

        const tailBlock = document.createElement("div");
        tailBlock.className = sourceBlock.className;
        copyBlockAttributes(sourceBlock, tailBlock);
        tailBlock.classList.add("report-document-block--continued");
        tailBlock.removeAttribute("id");

        const tailParagraph = document.createElement("p");
        tailParagraph.className = sourceParagraph.className
            .replace(/\breport-document-paragraph--first-line-indent\b/g, "")
            .trim();
        tailParagraph.innerHTML = html;
        tailBlock.appendChild(tailParagraph);
        return tailBlock;
    }

    function splitParagraphBlock(block, bodyElement, maxBodyHeight) {
        const paragraph = block.querySelector(".report-document-paragraph");
        if (!paragraph) {
            return null;
        }

        const splitPlan = findBestVisualLineSplit(
            paragraph,
            bodyElement,
            maxBodyHeight,
            blockFitsInBody
        );
        if (!splitPlan) {
            return null;
        }

        const afterHtml = applyVisualLineSplit(paragraph, splitPlan);
        if (!afterHtml) {
            paragraph.innerHTML = splitPlan.originalHtml;
            return null;
        }

        return createParagraphContinuationBlock(block, afterHtml);
    }

    function getListElement(block) {
        return block.querySelector(".report-document-list");
    }

    function getListItems(block) {
        const list = getListElement(block);
        if (!list) {
            return [];
        }
        return Array.from(list.querySelectorAll(":scope > .report-document-list-item"));
    }

    function createListContinuationBlock(sourceBlock, listItems, orderedStart) {
        const sourceList = getListElement(sourceBlock);
        if (!sourceList || !listItems.length) {
            return null;
        }

        const tailBlock = document.createElement("div");
        tailBlock.className = sourceBlock.className;
        copyBlockAttributes(sourceBlock, tailBlock);
        tailBlock.classList.add("report-document-block--continued");
        tailBlock.removeAttribute("id");

        const tailList = document.createElement(sourceList.tagName.toLowerCase());
        tailList.className = sourceList.className;
        if (sourceList.tagName === "OL" && orderedStart > 1) {
            tailList.setAttribute("start", String(orderedStart));
        }

        listItems.forEach((item) => {
            tailList.appendChild(item);
        });
        tailBlock.appendChild(tailList);
        return tailBlock;
    }

    function setListItemsVisible(items, fromIndex, visible) {
        for (let index = fromIndex; index < items.length; index += 1) {
            items[index].style.display = visible ? "" : "none";
        }
    }

    function splitListBlockByItems(block, bodyElement, maxBodyHeight) {
        const list = getListElement(block);
        const items = getListItems(block);
        const itemCount = items.length;

        if (!list || itemCount < MIN_FRAGMENT_ITEMS * 2) {
            return null;
        }

        let bestHeadCount = 0;

        for (
            let headCount = MIN_FRAGMENT_ITEMS;
            headCount <= itemCount - MIN_FRAGMENT_ITEMS;
            headCount += 1
        ) {
            setListItemsVisible(items, headCount, false);

            if (blockFitsInBody(bodyElement, maxBodyHeight)) {
                bestHeadCount = headCount;
            }

            setListItemsVisible(items, headCount, true);
        }

        if (bestHeadCount <= 0) {
            return null;
        }

        const tailItems = items.slice(bestHeadCount);
        tailItems.forEach((item) => {
            list.removeChild(item);
        });

        return createListContinuationBlock(block, tailItems, bestHeadCount + 1);
    }

    function splitLastListItemByLines(block, bodyElement, maxBodyHeight) {
        const items = getListItems(block);
        if (!items.length) {
            return null;
        }

        const lastItem = items[items.length - 1];
        const splitPlan = findBestVisualLineSplit(
            lastItem,
            bodyElement,
            maxBodyHeight,
            blockFitsInBody
        );
        if (!splitPlan) {
            return null;
        }

        const afterHtml = applyVisualLineSplit(lastItem, splitPlan);
        if (!afterHtml) {
            lastItem.innerHTML = splitPlan.originalHtml;
            return null;
        }

        const tailItem = document.createElement("li");
        tailItem.className = lastItem.className;
        tailItem.innerHTML = afterHtml;

        const itemIndex = items.indexOf(lastItem);
        const orderedStart = itemIndex + 1;

        return createListContinuationBlock(block, [tailItem], orderedStart);
    }

    function splitListBlock(block, bodyElement, maxBodyHeight) {
        const tailByItems = splitListBlockByItems(block, bodyElement, maxBodyHeight);
        if (tailByItems) {
            return tailByItems;
        }
        return splitLastListItemByLines(block, bodyElement, maxBodyHeight);
    }

    function appendSheet(container, headerTemplate, footerTemplate) {
        const sheet = createSheet(headerTemplate, footerTemplate);
        container.appendChild(sheet.element);
        return sheet;
    }

    function createSheet(headerTemplate, footerTemplate) {
        const element = document.createElement("article");
        element.className = "report-document-page-sheet";

        const headerSlot = document.createElement("div");
        headerSlot.className = "report-document-page-sheet-header";
        appendTemplateContent(headerTemplate, headerSlot);

        const body = document.createElement("div");
        body.className = "report-document-page-sheet-body";

        const footerSlot = document.createElement("div");
        footerSlot.className = "report-document-page-sheet-footer";
        appendTemplateContent(footerTemplate, footerSlot);

        element.appendChild(headerSlot);
        element.appendChild(body);
        element.appendChild(footerSlot);

        return { element, body, headerSlot, footerSlot };
    }

    function appendTemplateContent(template, target) {
        if (!template || !template.content) {
            return;
        }
        const clone = template.content.cloneNode(true);
        if (clone.childNodes.length) {
            target.appendChild(clone);
        }
    }

    function buildProbeSheet(headerTemplate, footerTemplate) {
        const sheet = createSheet(headerTemplate, footerTemplate);
        sheet.element.classList.add("report-document-page-sheet--probe");
        sheet.element.setAttribute("aria-hidden", "true");
        sheet.element.style.position = "absolute";
        sheet.element.style.visibility = "hidden";
        sheet.element.style.pointerEvents = "none";
        sheet.element.style.left = "-100000px";
        sheet.element.style.top = "0";
        return sheet.element;
    }

    function updatePageNumbers(pages, total) {
        const safeTotal = Math.max(1, total);
        pages.forEach((page, index) => {
            const current = index + 1;
            page.element.querySelectorAll("[data-report-page-current]").forEach((node) => {
                node.textContent = String(current);
            });
            page.element.querySelectorAll("[data-report-page-total]").forEach((node) => {
                node.textContent = String(safeTotal);
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", paginateDocument);
    } else {
        paginateDocument();
    }
})();
