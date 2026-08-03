/**
 * Paginação client-side do preview de leitura do laudo.
 *
 * Distribui blocos do corpo em folhas A4, repetindo cabeçalho e rodapé
 * configurados e atualizando a numeração "Página N de T".
 */
(function () {
    "use strict";

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
            currentPage.body.appendChild(block);
            if (
                currentPage.body.scrollHeight > maxBodyHeight
                && currentPage.body.children.length > 1
            ) {
                const overflowBlock = currentPage.body.lastElementChild;
                currentPage.body.removeChild(overflowBlock);
                currentPage = appendSheet(pagesContainer, headerTemplate, footerTemplate);
                pages.push(currentPage);
                currentPage.body.appendChild(overflowBlock);
            }
        });

        updatePageNumbers(pages, pages.length);
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
