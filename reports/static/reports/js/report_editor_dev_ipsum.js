/**
 * Atalho de desenvolvimento para preencher parágrafos vazios com lorem ipsum.
 *
 * Em um parágrafo vazio, digite ``ipsumN`` (ex.: ``ipsum120``) e pressione
 * Enter para gerar texto lorem com exatamente N caracteres.
 *
 * TODO(produção): remover este arquivo, a inclusão condicional em
 * ``reports/templates/reports/report_editor.html`` e qualquer referência a
 * ``report_editor_dev_ipsum.js`` antes do deploy em produção.
 */
(function () {
    "use strict";

    const IPSUM_PATTERN = /^ipsum(\d+)$/i;
    const MAX_LENGTH = 10000;
    const LOREM_BASE =
        "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor " +
        "incididunt ut labore et dolore magna aliqua Ut enim ad minim veniam quis nostrud " +
        "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat Duis aute " +
        "irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla " +
        "pariatur Excepteur sint occaecat cupidatat non proident sunt in culpa qui officia " +
        "deserunt mollit anim id est laborum";

    const emptyOnFocus = new WeakMap();

    function generateLorem(length) {
        const targetLength = Math.min(Math.max(0, length), MAX_LENGTH);
        if (targetLength === 0) {
            return "";
        }

        let text = "";
        while (text.length < targetLength) {
            if (text) {
                text += " ";
            }
            text += LOREM_BASE;
        }
        return text.slice(0, targetLength);
    }

    function placeCaretAtEnd(element) {
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

    function paragraphText(editable) {
        return editable.textContent.replace(/\u00a0/g, " ").trim();
    }

    function tryGenerateIpsum(editable) {
        if (!emptyOnFocus.get(editable)) {
            return false;
        }

        const match = paragraphText(editable).match(IPSUM_PATTERN);
        if (!match) {
            return false;
        }

        const length = Number.parseInt(match[1], 10);
        editable.textContent = generateLorem(length);
        emptyOnFocus.set(editable, false);
        placeCaretAtEnd(editable);
        editable.dispatchEvent(new InputEvent("input", { bubbles: true }));
        return true;
    }

    function bindDevIpsumShortcut(page) {
        page.addEventListener("focusin", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
                return;
            }

            const block = editable.closest(".report-editor-block");
            if (!block || block.dataset.blockType !== "paragraph") {
                return;
            }

            emptyOnFocus.set(editable, paragraphText(editable) === "");
        });

        page.addEventListener("input", (event) => {
            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
                return;
            }

            const block = editable.closest(".report-editor-block");
            if (!block || block.dataset.blockType !== "paragraph") {
                return;
            }

            if (paragraphText(editable) === "") {
                emptyOnFocus.set(editable, true);
            }
        });

        page.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" || event.shiftKey) {
                return;
            }

            const editable = event.target.closest(".report-editor-block-editable");
            if (!editable) {
                return;
            }

            const block = editable.closest(".report-editor-block");
            if (!block || block.dataset.blockType !== "paragraph") {
                return;
            }

            if (tryGenerateIpsum(editable)) {
                event.preventDefault();
                event.stopPropagation();
            }
        }, true);
    }

    document.addEventListener("DOMContentLoaded", function () {
        const page = document.getElementById("report-editor-page");
        if (page) {
            bindDevIpsumShortcut(page);
        }
    });
})();
