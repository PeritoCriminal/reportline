/**
 * Inserção e exclusão de linhas/colunas em tabelas do editor.
 */
(function () {
    "use strict";

    let tableOptionsToggle = null;
    let deleteRowButton = null;
    let deleteColButton = null;
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

    function updateTableAlignMenuState(block) {
        if (!block) {
            return;
        }

        const storedAlign = block.dataset.textAlign || "left";
        const activeAlign = ["left", "center", "right"].includes(storedAlign) ? storedAlign : "left";
        document.querySelectorAll("[data-report-table-align]").forEach((button) => {
            const isActive = button.dataset.reportTableAlign === activeAlign;
            button.classList.toggle("active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
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

    function setOptionsToggleState(toggle, enabled) {
        if (!toggle) {
            return;
        }

        toggle.disabled = !enabled;
        if (!enabled) {
            closeTableDropdown();
        }
    }

    function getTableMultiSelection() {
        if (!window.ReportLineTableSelection || !window.ReportLineTableSelection.getSelection) {
            return null;
        }
        return window.ReportLineTableSelection.getSelection();
    }

    function resolveTableToolbarContext() {
        const context = resolveTableCellContext();
        const selection = getTableMultiSelection();
        if (selection && selection.isMulti) {
            return {
                block: selection.block,
                part: selection.includesHeader && selection.bodyRowIndices.length === 0
                    ? "header"
                    : "cell",
                rowIndex: selection.bodyRowIndices.length > 0
                    ? selection.bodyRowIndices[0]
                    : 0,
                colIndex: selection.range.minCol,
                multiSelection: selection,
            };
        }
        return context;
    }

    function canDeleteTableRows(context) {
        if (!context || !context.block) {
            return false;
        }
        if (context.multiSelection && context.multiSelection.bodyRowIndices.length > 0) {
            return true;
        }
        return context.part === "cell";
    }

    function canDeleteTableColumns(context) {
        return Boolean(context && context.block);
    }

    function updateToolbarVisibility(context) {
        const toolbarContext = context || resolveTableToolbarContext();
        const inTable = Boolean(toolbarContext && toolbarContext.block);

        setOptionsToggleState(tableOptionsToggle, inTable);

        if (deleteRowButton) {
            deleteRowButton.disabled = !canDeleteTableRows(toolbarContext);
        }

        if (deleteColButton) {
            deleteColButton.disabled = !canDeleteTableColumns(toolbarContext);
        }

        if (toolbarContext && toolbarContext.block) {
            updateBorderToggleState(toolbarContext.block);
            updateHeaderToggleState(toolbarContext.block);
            updateTableAlignMenuState(toolbarContext.block);
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
        deleteColButton = document.querySelector("[data-report-table-delete-col]");
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

        document.querySelectorAll("[data-report-table-align]").forEach((button) => {
            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
            });
            button.addEventListener("click", (event) => {
                event.preventDefault();
                const align = button.dataset.reportTableAlign;
                if (!window.ReportLineEditor || !window.ReportLineEditor.setTableBlockAlign) {
                    return;
                }
                window.ReportLineEditor.setTableBlockAlign(align)
                    .then(() => {
                        const context = resolveTableCellContext();
                        if (context && context.block) {
                            updateTableAlignMenuState(context.block);
                        }
                        closeTableDropdown();
                    })
                    .catch(console.error);
            });
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

        document.addEventListener("reportline:table-selection-changed", () => {
            updateToolbarVisibility(resolveTableToolbarContext());
        });
    }

    window.ReportLineTableStructure = { init };
})();
