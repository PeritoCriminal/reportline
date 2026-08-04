/**
 * Atalho de desenvolvimento para preencher parágrafos vazios com lorem ipsum.
 *
 * Em um parágrafo vazio do corpo do laudo, digite um comando e pressione Enter:
 *
 * - ``ipsum100`` — um parágrafo com 100 caracteres, ponto final, parágrafo vazio
 *   seguinte com o cursor no início;
 * - ``3ipsum100`` — três parágrafos de 100 caracteres (cada um com ponto final) e
 *   parágrafo vazio no fim;
 * - ``3ipsum100-300`` — três parágrafos com comprimento aleatório entre 100 e 300
 *   caracteres, ponto final em cada um e parágrafo vazio no fim.
 *
 * Os números são exemplos; qualquer inteiro positivo vale. A contagem de parágrafos
 * aceita no máximo um dígito; valores com mais dígitos geram 9 parágrafos.
 *
 * TODO(produção): remover este arquivo, a inclusão condicional em
 * ``reports/templates/reports/report_editor.html`` e qualquer referência a
 * ``report_editor_dev_ipsum.js`` antes do deploy em produção.
 */
(function () {
    "use strict";

    const IPSUM_PATTERN = /^(\d*)ipsum(\d+)(?:-(\d+))?$/i;
    const MAX_PARAGRAPH_COUNT = 9;
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

    function randomInt(min, max) {
        const lower = Math.min(min, max);
        const upper = Math.max(min, max);
        return lower + Math.floor(Math.random() * (upper - lower + 1));
    }

    function parseParagraphCount(rawCount) {
        if (!rawCount) {
            return 1;
        }
        if (rawCount.length > 1) {
            return MAX_PARAGRAPH_COUNT;
        }
        const parsed = Number.parseInt(rawCount, 10);
        if (!Number.isFinite(parsed) || parsed < 1) {
            return 1;
        }
        return Math.min(parsed, MAX_PARAGRAPH_COUNT);
    }

    function parseIpsumCommand(text) {
        const match = text.match(IPSUM_PATTERN);
        if (!match) {
            return null;
        }

        const count = parseParagraphCount(match[1]);
        const minLen = Number.parseInt(match[2], 10);
        let maxLen = match[3] ? Number.parseInt(match[3], 10) : minLen;

        if (!Number.isFinite(minLen) || minLen < 0) {
            return null;
        }
        if (!Number.isFinite(maxLen) || maxLen < 0) {
            maxLen = minLen;
        }

        return {
            count,
            minLen: Math.min(minLen, maxLen),
            maxLen: Math.max(minLen, maxLen),
        };
    }

    function generateParagraphText(minLen, maxLen) {
        const length = minLen === maxLen ? minLen : randomInt(minLen, maxLen);
        return `${generateLorem(length)}.`;
    }

    function paragraphText(editable) {
        return editable.textContent.replace(/\u00a0/g, " ").trim();
    }

    function buildParagraphTexts(spec) {
        const texts = [];
        for (let index = 0; index < spec.count; index += 1) {
            texts.push(generateParagraphText(spec.minLen, spec.maxLen));
        }
        return texts;
    }

    async function applyIpsum(editable, spec) {
        const block = editable.closest(".report-editor-block");
        if (!block) {
            return;
        }

        const texts = buildParagraphTexts(spec);
        const editor = window.ReportLineEditor;

        editable.textContent = texts[0];
        emptyOnFocus.set(editable, false);
        editable.dispatchEvent(new InputEvent("input", { bubbles: true }));

        if (editor && editor.saveBlock) {
            await editor.saveBlock(block, { skipHistory: true });
        }

        let referenceBlock = block;
        if (editor && editor.insertParagraphAfter) {
            for (let index = 1; index < texts.length; index += 1) {
                referenceBlock = await editor.insertParagraphAfter(referenceBlock, {
                    content: { text: texts[index] },
                });
            }

            await editor.insertParagraphAfter(referenceBlock, {
                content: { text: "" },
                caretAtStart: true,
            });
        }
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

        page.addEventListener(
            "keydown",
            (event) => {
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

                if (!emptyOnFocus.get(editable)) {
                    return;
                }

                const spec = parseIpsumCommand(paragraphText(editable));
                if (!spec) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();
                applyIpsum(editable, spec).catch(console.error);
            },
            true
        );
    }

    document.addEventListener("DOMContentLoaded", function () {
        const page = document.getElementById("report-editor-page");
        if (page) {
            bindDevIpsumShortcut(page);
        }
    });
})();
