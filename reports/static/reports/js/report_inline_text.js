/**
 * Sanitização e utilitários de HTML inline no editor.
 */
(function () {
    "use strict";

    const ALLOWED_TAGS = new Set([
        "STRONG", "EM", "U", "S", "B", "I", "STRIKE", "DEL", "A", "SUP", "SUB",
    ]);
    const TAG_MAP = {
        B: "STRONG",
        I: "EM",
        STRIKE: "S",
        DEL: "S",
    };
    const ALLOWED_LINK_PREFIXES = ["http://", "https://", "mailto:"];
    const BLOCKED_LINK_PREFIXES = ["javascript:", "data:", "vbscript:"];

    function escapeAttr(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;");
    }

    function normalizeLinkUrl(href) {
        const cleaned = (href || "").trim();
        if (!cleaned) {
            return null;
        }

        const lowered = cleaned.toLowerCase();
        if (BLOCKED_LINK_PREFIXES.some((prefix) => lowered.startsWith(prefix))) {
            return null;
        }

        if (ALLOWED_LINK_PREFIXES.some((prefix) => lowered.startsWith(prefix))) {
            return cleaned;
        }

        if (cleaned.includes("@") && !lowered.startsWith("mailto:")) {
            return `mailto:${cleaned}`;
        }

        return `https://${cleaned.replace(/^\/+/, "")}`;
    }

    function normalizeTagName(tagName) {
        return TAG_MAP[tagName] || tagName;
    }

    function sanitizeNode(node, options) {
        const allowBreaks = options && options.allowBreaks;

        if (node.nodeType === Node.TEXT_NODE) {
            return node.textContent;
        }

        if (node.nodeType !== Node.ELEMENT_NODE) {
            return "";
        }

        if (allowBreaks && node.tagName === "BR") {
            return "<br>";
        }

        if (allowBreaks && (node.tagName === "DIV" || node.tagName === "P")) {
            const inner = Array.from(node.childNodes)
                .map((child) => sanitizeNode(child, options))
                .join("");
            return inner ? `${inner}<br>` : "";
        }

        if (node.tagName === "A") {
            const href = normalizeLinkUrl(node.getAttribute("href") || "");
            const inner = Array.from(node.childNodes).map((child) => sanitizeNode(child, options)).join("");
            if (!href) {
                return inner;
            }
            return `<a href="${escapeAttr(href)}">${inner}</a>`;
        }

        const tagName = normalizeTagName(node.tagName);
        if (!ALLOWED_TAGS.has(node.tagName) && !ALLOWED_TAGS.has(tagName)) {
            return Array.from(node.childNodes).map((child) => sanitizeNode(child, options)).join("");
        }

        const inner = Array.from(node.childNodes).map((child) => sanitizeNode(child, options)).join("");
        const normalized = tagName.toLowerCase();
        return `<${normalized}>${inner}</${normalized}>`;
    }

    function sanitize(html, options) {
        if (!html) {
            return "";
        }
        if (!/[<>]/.test(html)) {
            return html;
        }

        const template = document.createElement("template");
        template.innerHTML = html;
        let result = Array.from(template.content.childNodes)
            .map((child) => sanitizeNode(child, options))
            .join("");

        if (options && options.allowBreaks) {
            while (result.endsWith("<br>")) {
                result = result.slice(0, -4);
            }
        }

        return result;
    }

    function sanitizeHeader(html) {
        return sanitize(html, { allowBreaks: true });
    }

    function getHeaderHtml(element) {
        if (!element) {
            return "";
        }
        return sanitizeHeader(element.innerHTML);
    }

    function setHtml(element, html) {
        if (!element) {
            return;
        }
        element.innerHTML = sanitize(html || "");
    }

    function getHtml(element) {
        if (!element) {
            return "";
        }
        return sanitize(element.innerHTML);
    }

    function getPlainText(element) {
        if (!element) {
            return "";
        }
        return element.textContent || "";
    }

    function splitHtmlAtSelection(editable) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0 || !editable) {
            return {
                beforeHtml: getHtml(editable),
                afterHtml: "",
            };
        }

        const range = selection.getRangeAt(0);
        if (!editable.contains(range.startContainer)) {
            return {
                beforeHtml: getHtml(editable),
                afterHtml: "",
            };
        }

        const beforeRange = range.cloneRange();
        beforeRange.selectNodeContents(editable);
        beforeRange.setEnd(range.startContainer, range.startOffset);

        const afterRange = range.cloneRange();
        afterRange.selectNodeContents(editable);
        afterRange.setStart(range.endContainer, range.endOffset);

        const beforeContainer = document.createElement("div");
        beforeContainer.appendChild(beforeRange.cloneContents());
        const afterContainer = document.createElement("div");
        afterContainer.appendChild(afterRange.cloneContents());

        return {
            beforeHtml: sanitize(beforeContainer.innerHTML),
            afterHtml: sanitize(afterContainer.innerHTML),
        };
    }

    function appendPlainTextWithNewlines(node, parts) {
        if (node.nodeType === Node.TEXT_NODE) {
            parts.text += node.textContent;
            return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) {
            return;
        }
        if (node.tagName === "BR") {
            parts.text += "\n";
            return;
        }
        if (node.tagName === "DIV" || node.tagName === "P") {
            if (parts.text && !parts.text.endsWith("\n")) {
                parts.text += "\n";
            }
            Array.from(node.childNodes).forEach((child) => appendPlainTextWithNewlines(child, parts));
            parts.text += "\n";
            return;
        }
        Array.from(node.childNodes).forEach((child) => appendPlainTextWithNewlines(child, parts));
    }

    function getPlainTextWithNewlinesFromHtml(html) {
        const container = document.createElement("div");
        container.innerHTML = html || "";
        const parts = { text: "" };
        Array.from(container.childNodes).forEach((child) => appendPlainTextWithNewlines(child, parts));
        return parts.text.replace(/\n+$/, "");
    }

    function getLastLinePlainTextFromHtml(html) {
        const text = getPlainTextWithNewlinesFromHtml(html);
        if (!text) {
            return "";
        }
        const lines = text.split("\n");
        return lines[lines.length - 1] || "";
    }

    function fragmentToHtml(fragment) {
        const container = document.createElement("div");
        container.appendChild(fragment.cloneNode(true));
        return sanitize(container.innerHTML);
    }

    function splitHtmlIntoLineFragments(html) {
        const container = document.createElement("div");
        container.innerHTML = html || "";
        const lines = [];
        let current = document.createDocumentFragment();

        function pushLine() {
            lines.push(current);
            current = document.createDocumentFragment();
        }

        function processNode(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                current.appendChild(node.cloneNode());
                return;
            }
            if (node.nodeType !== Node.ELEMENT_NODE) {
                return;
            }
            if (node.tagName === "BR") {
                pushLine();
                return;
            }
            if (node.tagName === "DIV" || node.tagName === "P") {
                if (current.childNodes.length) {
                    pushLine();
                }
                Array.from(node.childNodes).forEach(processNode);
                pushLine();
                return;
            }
            current.appendChild(node.cloneNode(true));
        }

        Array.from(container.childNodes).forEach(processNode);
        if (current.childNodes.length) {
            lines.push(current);
        }
        while (lines.length && !lines[lines.length - 1].childNodes.length) {
            lines.pop();
        }
        return lines;
    }

    function removeLastLineFromHtml(html) {
        const lines = splitHtmlIntoLineFragments(html);
        if (!lines.length) {
            return "";
        }
        lines.pop();
        return lines.map(fragmentToHtml).filter(Boolean).join("<br>");
    }

    function isEmptyHtml(html) {
        if (!html || !html.trim()) {
            return true;
        }
        const container = document.createElement("div");
        container.innerHTML = html;
        return !(container.textContent || "").length;
    }

    window.ReportLineInlineText = {
        sanitize,
        sanitizeHeader,
        getHeaderHtml,
        setHtml,
        getHtml,
        getPlainText,
        splitHtmlAtSelection,
        getLastLinePlainTextFromHtml,
        removeLastLineFromHtml,
        isEmptyHtml,
        normalizeLinkUrl,
    };
})();
