/**
 * Menu de opções do parágrafo selecionado no editor (recuo).
 */
(function () {
    "use strict";

    const MAX_INDENT_LEVEL = 5;

    let paragraphOptionsToggle = null;
    let paragraphToolbarGroup = null;
    let decreaseIndentButton = null;
    let firstLineIndentButton = null;

    function resolveParagraphContext() {
        if (window.ReportLineEditor && window.ReportLineEditor.resolveParagraphContext) {
            return window.ReportLineEditor.resolveParagraphContext();
        }
        return null;
    }

    function isParagraphToolbarTarget(target) {
        return Boolean(
            target
            && target.closest
            && paragraphToolbarGroup
            && paragraphToolbarGroup.contains(target)
        );
    }

    function isParagraphMenuTarget(target) {
        return Boolean(
            target
            && target.closest
            && target.closest(".report-editor-toolbar-paragraph-menu")
        );
    }

    function isParagraphDropdownOpen() {
        return Boolean(
            paragraphOptionsToggle
            && paragraphOptionsToggle.getAttribute("aria-expanded") === "true"
        );
    }

    function getIndentLevel(block) {
        const level = Number.parseInt(block.dataset.indentLevel || "0", 10);
        if (Number.isNaN(level) || level < 0) {
            return 0;
        }
        return Math.min(MAX_INDENT_LEVEL, level);
    }

    function hasFirstLineIndent(context) {
        if (!context || !context.block) {
            return true;
        }
        const paragraph = context.editable
            || context.block.querySelector(".report-editor-block-paragraph");
        if (!paragraph) {
            return true;
        }
        return paragraph.dataset.firstLineIndent !== "false";
    }

    function updateParagraphMenuState(context) {
        if (!context || !context.block) {
            return;
        }

        const level = getIndentLevel(context.block);
        if (decreaseIndentButton) {
            decreaseIndentButton.disabled = level <= 0;
        }

        if (firstLineIndentButton) {
            const active = hasFirstLineIndent(context);
            firstLineIndentButton.classList.toggle("active", active);
            firstLineIndentButton.setAttribute("aria-pressed", active ? "true" : "false");
        }
    }

    function setOptionsToggleState(enabled) {
        if (!paragraphOptionsToggle) {
            return;
        }

        paragraphOptionsToggle.disabled = !enabled;
        if (!enabled) {
            closeParagraphDropdown();
        }
    }

    function updateToolbarVisibility(context) {
        const hasParagraph = Boolean(context && context.block);
        setOptionsToggleState(hasParagraph);
        if (hasParagraph) {
            updateParagraphMenuState(context);
        }
    }

    function closeParagraphDropdown() {
        if (!paragraphOptionsToggle || !window.bootstrap) {
            return;
        }
        window.bootstrap.Dropdown.getOrCreateInstance(paragraphOptionsToggle).hide();
    }

    function refreshToolbarFromFocus(target) {
        if (
            isParagraphToolbarTarget(target)
            || isParagraphMenuTarget(target)
            || isParagraphDropdownOpen()
        ) {
            updateToolbarVisibility(resolveParagraphContext());
            return;
        }

        if (target && target.closest && target.closest("#report-editor-page")) {
            updateToolbarVisibility(resolveParagraphContext());
            return;
        }

        if (window.ReportLineEditor && window.ReportLineEditor.clearParagraphContext) {
            window.ReportLineEditor.clearParagraphContext();
        }
        updateToolbarVisibility(null);
    }

    function bindIndentAction(selector, handler) {
        document.querySelectorAll(selector).forEach((button) => {
            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
                event.stopPropagation();
            });
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (button.disabled) {
                    return;
                }
                handler()
                    .then(() => {
                        const context = resolveParagraphContext();
                        updateParagraphMenuState(context);
                        closeParagraphDropdown();
                    })
                    .catch(console.error);
            });
        });
    }

    function init() {
        paragraphToolbarGroup = document.querySelector(".report-editor-toolbar-paragraph-group");
        paragraphOptionsToggle = document.querySelector("[data-report-paragraph-options-toggle]");
        decreaseIndentButton = document.querySelector('[data-report-paragraph-indent="decrease"]');
        firstLineIndentButton = document.querySelector("[data-report-paragraph-first-line-indent]");
        const page = document.getElementById("report-editor-page");

        if (!paragraphOptionsToggle || !page) {
            return;
        }

        bindIndentAction('[data-report-paragraph-indent="increase"]', () => {
            if (!window.ReportLineEditor || !window.ReportLineEditor.increaseParagraphIndent) {
                return Promise.resolve();
            }
            return window.ReportLineEditor.increaseParagraphIndent();
        });

        bindIndentAction('[data-report-paragraph-indent="decrease"]', () => {
            if (!window.ReportLineEditor || !window.ReportLineEditor.decreaseParagraphIndent) {
                return Promise.resolve();
            }
            return window.ReportLineEditor.decreaseParagraphIndent();
        });

        if (firstLineIndentButton) {
            firstLineIndentButton.addEventListener("mousedown", (event) => {
                event.preventDefault();
                event.stopPropagation();
            });
            firstLineIndentButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (!window.ReportLineEditor || !window.ReportLineEditor.toggleParagraphFirstLineIndent) {
                    return;
                }
                window.ReportLineEditor.toggleParagraphFirstLineIndent()
                    .then(() => {
                        updateParagraphMenuState(resolveParagraphContext());
                        closeParagraphDropdown();
                    })
                    .catch(console.error);
            });
        }

        paragraphOptionsToggle.addEventListener("mousedown", (event) => {
            event.stopPropagation();
            updateToolbarVisibility(resolveParagraphContext());
        });

        paragraphOptionsToggle.addEventListener("show.bs.dropdown", () => {
            updateToolbarVisibility(resolveParagraphContext());
        });

        paragraphOptionsToggle.addEventListener("hidden.bs.dropdown", () => {
            refreshToolbarFromFocus(document.activeElement);
        });

        page.addEventListener("focusin", (event) => {
            refreshToolbarFromFocus(event.target);
        });

        document.addEventListener("focusin", (event) => {
            if (event.target.closest("#report-editor-page")) {
                return;
            }
            refreshToolbarFromFocus(event.target);
        });
    }

    window.ReportLineParagraphOptions = { init };
})();
