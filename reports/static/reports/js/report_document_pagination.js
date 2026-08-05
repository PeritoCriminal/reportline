/**
 * Paginação client-side do preview de leitura do laudo.
 *
 * Distribui blocos do corpo em folhas A4, repetindo cabeçalho e rodapé
 * configurados, atualizando a numeração "Página N de T" e permitindo
 * quebra de parágrafos longos entre páginas com controle de linhas mínimas.
 */
(function () {
    "use strict";

    const MIN_FRAGMENT_LINES = 2;

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

        if (isSplittableParagraphBlock(overflowBlock)) {
            const tailBlock = splitParagraphBlock(overflowBlock, currentPage.body, maxBodyHeight);
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

    function isSplittableParagraphBlock(block) {
        if (!block || !block.classList.contains("report-document-block--paragraph")) {
            return false;
        }
        if (block.dataset.isCaption === "true") {
            return false;
        }
        return Boolean(block.querySelector(".report-document-paragraph"));
    }

    function countVisualLines(element) {
        if (!element || !(element.textContent || "").length) {
            return 0;
        }

        const range = document.createRange();
        range.selectNodeContents(element);
        const rects = range.getClientRects();
        if (!rects.length) {
            return 1;
        }

        const lineTops = new Set();
        for (let index = 0; index < rects.length; index += 1) {
            lineTops.add(Math.round(rects[index].top));
        }
        return lineTops.size || 1;
    }

    function paragraphFitsInBody(bodyElement, maxBodyHeight) {
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

    function applySplitToParagraph(paragraph, splitOffset, inlineApi) {
        const { beforeHtml, afterHtml } = inlineApi.splitElementAtPlainTextOffset(
            paragraph,
            splitOffset
        );
        paragraph.innerHTML = beforeHtml;
        return afterHtml;
    }

    function findSplitOffsetForOrphansWidows(
        paragraph,
        bodyElement,
        maxBodyHeight,
        splitOffset,
        totalLength,
        inlineApi
    ) {
        const originalHtml = paragraph.innerHTML;
        let adjustedOffset = splitOffset;

        function measureAtOffset(offset) {
            paragraph.innerHTML = originalHtml;
            const { beforeHtml, afterHtml } = inlineApi.splitElementAtPlainTextOffset(
                paragraph,
                offset
            );
            paragraph.innerHTML = beforeHtml;
            const headLines = countVisualLines(paragraph);

            const tailProbe = document.createElement("p");
            tailProbe.className = paragraph.className
                .replace(/\breport-document-paragraph--first-line-indent\b/g, "")
                .trim();
            tailProbe.style.visibility = "hidden";
            tailProbe.style.position = "absolute";
            tailProbe.style.pointerEvents = "none";
            tailProbe.style.left = "-100000px";
            tailProbe.style.width = `${paragraph.getBoundingClientRect().width}px`;
            tailProbe.innerHTML = afterHtml;
            paragraph.parentElement.appendChild(tailProbe);
            const tailLines = countVisualLines(tailProbe);
            tailProbe.remove();

            paragraph.innerHTML = originalHtml;
            return { headLines, tailLines, beforeHtml, afterHtml };
        }

        while (adjustedOffset > 1) {
            paragraph.innerHTML = originalHtml;
            const { beforeHtml } = inlineApi.splitElementAtPlainTextOffset(
                paragraph,
                adjustedOffset
            );
            paragraph.innerHTML = beforeHtml;
            if (!paragraphFitsInBody(bodyElement, maxBodyHeight)) {
                break;
            }

            const { headLines, tailLines } = measureAtOffset(adjustedOffset);
            if (
                headLines >= MIN_FRAGMENT_LINES
                && tailLines >= MIN_FRAGMENT_LINES
            ) {
                return adjustedOffset;
            }

            if (tailLines < MIN_FRAGMENT_LINES) {
                adjustedOffset -= 1;
                continue;
            }
            if (headLines < MIN_FRAGMENT_LINES) {
                break;
            }
            break;
        }

        paragraph.innerHTML = originalHtml;
        return splitOffset;
    }

    function splitParagraphBlock(block, bodyElement, maxBodyHeight) {
        const paragraph = block.querySelector(".report-document-paragraph");
        const inlineApi = window.ReportLineInlineText;
        if (!paragraph || !inlineApi || !inlineApi.splitElementAtPlainTextOffset) {
            return null;
        }

        const originalHtml = paragraph.innerHTML;
        const totalLength = (paragraph.textContent || "").length;
        if (totalLength <= 0) {
            return null;
        }

        paragraph.innerHTML = originalHtml;
        if (countVisualLines(paragraph) <= 1) {
            return null;
        }

        let low = 1;
        let high = totalLength;
        let bestOffset = 0;

        while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            paragraph.innerHTML = originalHtml;
            const { beforeHtml } = inlineApi.splitElementAtPlainTextOffset(paragraph, mid);
            paragraph.innerHTML = beforeHtml;

            if (paragraphFitsInBody(bodyElement, maxBodyHeight)) {
                bestOffset = mid;
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }

        paragraph.innerHTML = originalHtml;

        if (bestOffset <= 0 || bestOffset >= totalLength) {
            return null;
        }

        bestOffset = findSplitOffsetForOrphansWidows(
            paragraph,
            bodyElement,
            maxBodyHeight,
            bestOffset,
            totalLength,
            inlineApi
        );

        paragraph.innerHTML = originalHtml;
        const afterHtml = applySplitToParagraph(paragraph, bestOffset, inlineApi);
        if (!afterHtml) {
            paragraph.innerHTML = originalHtml;
            return null;
        }

        return createParagraphContinuationBlock(block, afterHtml);
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
