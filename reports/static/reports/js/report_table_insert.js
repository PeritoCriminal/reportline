// reportline/reports/static/reports/js/report_table_insert.js
/**
 * Modal interativo para escolher dimensões da tabela antes da inserção.
 */
(function () {
    "use strict";

    const MAX_ROWS = 10;
    const MAX_COLS = 10;

    let modal = null;
    let gridElement = null;
    let sizeLabel = null;
    let submitButton = null;
    let selectedRows = 1;
    let selectedCols = 1;

    function updateSelection(rows, cols) {
        selectedRows = rows;
        selectedCols = cols;
        if (sizeLabel) {
            sizeLabel.textContent = `${rows} × ${cols}`;
        }
        if (!gridElement) {
            return;
        }
        gridElement.querySelectorAll(".report-table-insert-grid-cell").forEach((cell) => {
            const row = Number.parseInt(cell.dataset.row, 10);
            const col = Number.parseInt(cell.dataset.col, 10);
            cell.classList.toggle("is-selected", row <= rows && col <= cols);
            cell.setAttribute("aria-selected", row <= rows && col <= cols ? "true" : "false");
        });
    }

    function buildGrid() {
        if (!gridElement) {
            return;
        }
        gridElement.innerHTML = "";
        for (let row = 1; row <= MAX_ROWS; row += 1) {
            const rowElement = document.createElement("div");
            rowElement.className = "report-table-insert-grid-row";
            rowElement.setAttribute("role", "row");
            for (let col = 1; col <= MAX_COLS; col += 1) {
                const cell = document.createElement("button");
                cell.type = "button";
                cell.className = "report-table-insert-grid-cell";
                cell.dataset.row = String(row);
                cell.dataset.col = String(col);
                cell.setAttribute("role", "gridcell");
                cell.setAttribute("aria-selected", "false");
                cell.setAttribute("aria-label", `${row} linhas por ${col} colunas`);
                cell.addEventListener("mouseenter", () => {
                    updateSelection(row, col);
                });
                cell.addEventListener("click", () => {
                    updateSelection(row, col);
                    confirmInsert();
                });
                rowElement.appendChild(cell);
            }
            gridElement.appendChild(rowElement);
        }
        updateSelection(1, 1);
    }

    function openModal() {
        if (!modal) {
            return;
        }
        updateSelection(1, 1);
        modal.show();
    }

    function confirmInsert() {
        if (!window.ReportLineEditor || !window.ReportLineEditor.insertTableAtCursor) {
            return;
        }
        window.ReportLineEditor.insertTableAtCursor(selectedRows, selectedCols).catch(console.error);
        if (modal) {
            modal.hide();
        }
    }

    function bindToolbar() {
        document.querySelectorAll("[data-report-table-insert]").forEach((button) => {
            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
            });
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                openModal();
            });
        });
    }

    function init() {
        const modalElement = document.getElementById("reportTableInsertModal");
        gridElement = document.getElementById("report-table-insert-grid");
        sizeLabel = document.getElementById("report-table-insert-size-label");
        submitButton = document.getElementById("report-table-insert-submit");

        if (!modalElement || !gridElement) {
            return;
        }

        modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        buildGrid();
        bindToolbar();

        if (submitButton) {
            submitButton.addEventListener("click", confirmInsert);
        }

        modalElement.addEventListener("hidden.bs.modal", () => {
            updateSelection(1, 1);
        });
    }

    window.ReportLineTableInsert = { init };
})();
