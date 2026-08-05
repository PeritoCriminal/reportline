/**
 * Sanitização e utilitários de HTML inline no editor.
 */
(function () {
    "use strict";

    const ALLOWED_TAGS = new Set([
        "STRONG", "EM", "U", "S", "B", "I", "STRIKE", "DEL", "A", "SUP", "SUB", "SPAN",
    ]);
    const ALLOWED_FONT_SIZE_CLASSES = new Set([
        "report-inline-font-xs",
        "report-inline-font-sm",
        "report-inline-font-lg",
    ]);
    const ALLOWED_FONT_FAMILY_CLASSES = new Set([
        "report-inline-font-serif",
    ]);
    const FONT_SIZE_CLASS_PRIORITY = [
        "report-inline-font-xs",
        "report-inline-font-sm",
        "report-inline-font-lg",
    ];
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

    function resolveFontSpanClasses(classNames) {
        const tokens = (classNames || "").split(/\s+/).filter(Boolean);
        const sizeClasses = tokens.filter((name) => ALLOWED_FONT_SIZE_CLASSES.has(name));
        const familyClasses = tokens.filter((name) => ALLOWED_FONT_FAMILY_CLASSES.has(name));
        if (!sizeClasses.length && !familyClasses.length) {
            return null;
        }

        const resolved = [];
        FONT_SIZE_CLASS_PRIORITY.some((sizeClass) => {
            if (sizeClasses.includes(sizeClass)) {
                resolved.push(sizeClass);
                return true;
            }
            return false;
        });
        if (familyClasses.includes("report-inline-font-serif")) {
            resolved.push("report-inline-font-serif");
        }
        return resolved.length ? resolved.join(" ") : null;
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

        if (node.tagName === "SPAN") {
            const fontClasses = resolveFontSpanClasses(node.getAttribute("class") || "");
            const inner = Array.from(node.childNodes).map((child) => sanitizeNode(child, options)).join("");
            if (!fontClasses) {
                return inner;
            }
            return `<span class="${fontClasses}">${inner}</span>`;
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
        element.innerHTML = sanitize(html || "", { allowBreaks: true });
    }

    function getHtml(element) {
        if (!element) {
            return "";
        }
        return sanitize(element.innerHTML, { allowBreaks: true });
    }

    function getPlainText(element) {
        if (!element) {
            return "";
        }
        return element.textContent || "";
    }

    function splitElementAtPlainTextOffset(element, offset) {
        if (!element) {
            return { beforeHtml: "", afterHtml: "" };
        }

        const totalLength = (element.textContent || "").length;
        const safeOffset = Math.max(0, Math.min(offset, totalLength));

        if (safeOffset <= 0) {
            return { beforeHtml: "", afterHtml: getHtml(element) };
        }
        if (safeOffset >= totalLength) {
            return { beforeHtml: getHtml(element), afterHtml: "" };
        }

        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let remaining = safeOffset;
        let splitNode = null;
        let splitOffset = 0;

        while (walker.nextNode()) {
            const node = walker.currentNode;
            const length = node.textContent.length;
            if (remaining <= length) {
                splitNode = node;
                splitOffset = remaining;
                break;
            }
            remaining -= length;
        }

        if (!splitNode) {
            return { beforeHtml: getHtml(element), afterHtml: "" };
        }

        const beforeRange = document.createRange();
        beforeRange.selectNodeContents(element);
        beforeRange.setEnd(splitNode, splitOffset);

        const afterRange = document.createRange();
        afterRange.selectNodeContents(element);
        afterRange.setStart(splitNode, splitOffset);

        const beforeContainer = document.createElement("div");
        beforeContainer.appendChild(beforeRange.cloneContents());
        const afterContainer = document.createElement("div");
        afterContainer.appendChild(afterRange.cloneContents());

        return {
            beforeHtml: sanitize(beforeContainer.innerHTML, { allowBreaks: true }),
            afterHtml: sanitize(afterContainer.innerHTML, { allowBreaks: true }),
        };
    }

    function splitHtmlAtPlainTextOffset(html, offset) {
        const container = document.createElement("div");
        container.innerHTML = html || "";
        return splitElementAtPlainTextOffset(container, offset);
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
            beforeHtml: sanitize(beforeContainer.innerHTML, { allowBreaks: true }),
            afterHtml: sanitize(afterContainer.innerHTML, { allowBreaks: true }),
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
        return sanitize(container.innerHTML, { allowBreaks: true });
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
        getPlainTextWithNewlinesFromHtml,
        splitHtmlAtSelection,
        splitElementAtPlainTextOffset,
        splitHtmlAtPlainTextOffset,
        splitHtmlIntoLineFragments,
        fragmentToHtml,
        getLastLinePlainTextFromHtml,
        removeLastLineFromHtml,
        isEmptyHtml,
        normalizeLinkUrl,
    };
})();
