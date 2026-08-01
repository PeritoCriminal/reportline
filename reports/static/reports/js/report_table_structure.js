/**
 * Inserção e exclusão de linhas/colunas em tabelas do editor.
 */
(function () {
    "use strict";

    let tableOptionsToggle = null;
    let deleteRowButton = null;
    let toggleBordersButton = null;
    let toggleHeaderButton = null;
    let tableToolbarGroup = null;

    function resolveTableCellContext() {
        if (window.ReportLineEditor && window.ReportLineEditor.resolveTableCellContext) {
            return window.ReportLineEditor.resolveTableCellContext();
        }
        return null;
    }

    function clearTableCellContext() {
        if (window.ReportLineEditor && window.ReportLineEditor.clearTableCellContext) {
            window.ReportLineEditor.clearTableCellContext();
        }
    }

    function isTableToolbarTarget(target) {
        return Boolean(
            target
            && target.closest
            && tableToolbarGroup
            && tableToolbarGroup.contains(target)
        );
    }

    function tableBordersVisible(block) {
        return block && block.dataset.tableShowBorders !== "false";
    }

    function tableHeaderVisible(block) {
        return block && block.dataset.tableShowHeader !== "false";
    }

    function updateBorderToggleState(block) {
        if (!toggleBordersButton || !block) {
            return;
        }

        const visible = tableBordersVisible(block);
        toggleBordersButton.querySelectorAll("[data-table-border-glyph]").forEach((glyph) => {
            glyph.hidden = glyph.dataset.tableBorderGlyph !== (visible ? "hide" : "show");
        });
        toggleBordersButton.querySelectorAll("[data-table-border-label]").forEach((label) => {
            label.hidden = label.dataset.tableBorderLabel !== (visible ? "hide" : "show");
        });
    }

    function updateHeaderToggleState(block) {
        if (!toggleHeaderButton || !block) {
            return;
        }

        const visible = tableHeaderVisible(block);
        toggleHeaderButton.querySelectorAll("[data-table-header-glyph]").forEach((glyph) => {
            glyph.hidden = glyph.dataset.tableHeaderGlyph !== (visible ? "hide" : "show");
        });
        toggleHeaderButton.querySelectorAll("[data-table-header-label]").forEach((label) => {
            label.hidden = label.dataset.tableHeaderLabel !== (visible ? "hide" : "show");
        });
    }

    function closeTableDropdown() {
        if (!tableOptionsToggle || !window.bootstrap) {
            return;
        }
        window.bootstrap.Dropdown.getOrCreateInstance(tableOptionsToggle).hide();
    }

    function isTableDropdownOpen() {
        return Boolean(
            tableOptionsToggle
            && tableOptionsToggle.getAttribute("aria-expanded") === "true"
        );
    }

    function updateToolbarVisibility(context) {
        const inTable = Boolean(context && context.block);

        if (tableOptionsToggle) {
            tableOptionsToggle.hidden = !inTable;
        }

        if (deleteRowButton) {
            deleteRowButton.disabled = !inTable || context.part !== "cell";
        }

        if (context && context.block) {
            updateBorderToggleState(context.block);
            updateHeaderToggleState(context.block);
        }
    }

    function refreshToolbarFromFocus(target) {
        if (isTableToolbarTarget(target) || isTableDropdownOpen()) {
            updateToolbarVisibility(resolveTableCellContext());
            return;
        }

        if (target && target.closest && target.closest("#report-editor-page")) {
            updateToolbarVisibility(resolveTableCellContext());
            return;
        }

        clearTableCellContext();
        updateToolbarVisibility(null);
    }

    function bindStructureAction(selector, handler) {
        document.querySelectorAll(selector).forEach((button) => {
            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
            });
            button.addEventListener("click", (event) => {
                event.preventDefault();
                handler()
                    .then(() => {
                        closeTableDropdown();
                    })
                    .catch(console.error);
            });
        });
    }

    function init() {
        tableToolbarGroup = document.querySelector(".report-editor-toolbar-table-group");
        tableOptionsToggle = document.querySelector("[data-report-table-options-toggle]");
        deleteRowButton = document.querySelector("[data-report-table-delete-row]");
        toggleBordersButton = document.querySelector("[data-report-table-toggle-borders]");
        toggleHeaderButton = document.querySelector("[data-report-table-toggle-header]");
        const page = document.getElementById("report-editor-page");

        if (!tableOptionsToggle || !page) {
            return;
        }

        bindStructureAction("[data-report-table-add-row]", () => {
            if (!window.ReportLineEditor || !window.ReportLineEditor.insertTableRowAfterCursor) {
                return Promise.resolve();
            }
            return window.ReportLineEditor.insertTableRowAfterCursor();
        });

        bindStructureAction("[data-report-table-delete-row]", () => {
            if (!window.ReportLineEditor || !window.ReportLineEditor.deleteTableRowAtCursor) {
                return Promise.resolve();
            }
            return window.ReportLineEditor.deleteTableRowAtCursor();
        });

        bindStructureAction("[data-report-table-add-col]", () => {
            if (!window.ReportLineEditor || !window.ReportLineEditor.insertTableColumnAfterCursor) {
                return Promise.resolve();
            }
            return window.ReportLineEditor.insertTableColumnAfterCursor();
        });

        bindStructureAction("[data-report-table-delete-col]", () => {
            if (!window.ReportLineEditor || !window.ReportLineEditor.deleteTableColumnAtCursor) {
                return Promise.resolve();
            }
            return window.ReportLineEditor.deleteTableColumnAtCursor();
        });

        bindStructureAction("[data-report-table-toggle-borders]", () => {
            if (!window.ReportLineEditor || !window.ReportLineEditor.toggleTableBorders) {
                return Promise.resolve();
            }
            return window.ReportLineEditor.toggleTableBorders();
        });

        bindStructureAction("[data-report-table-toggle-header]", () => {
            if (!window.ReportLineEditor || !window.ReportLineEditor.toggleTableHeader) {
                return Promise.resolve();
            }
            return window.ReportLineEditor.toggleTableHeader();
        });

        tableOptionsToggle.addEventListener("mousedown", () => {
            updateToolbarVisibility(resolveTableCellContext());
        });

        tableOptionsToggle.addEventListener("show.bs.dropdown", () => {
            updateToolbarVisibility(resolveTableCellContext());
        });

        tableOptionsToggle.addEventListener("hidden.bs.dropdown", () => {
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

    window.ReportLineTableStructure = { init };
})();
