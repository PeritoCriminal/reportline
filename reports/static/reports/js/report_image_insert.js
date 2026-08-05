/**
 * Seleção de arquivo e upload de imagem para inserção no editor.
 */
(function () {
    "use strict";

    let fileInput = null;
    let uploadOptions = {};

    function ensureFileInput() {
        if (fileInput) {
            return fileInput;
        }
        fileInput = document.createElement("input");
        fileInput.type = "file";
        fileInput.accept = "image/jpeg,image/png,image/gif,image/webp";
        fileInput.hidden = true;
        fileInput.addEventListener("change", handleFileSelected);
        document.body.appendChild(fileInput);
        return fileInput;
    }

    async function uploadImage(file) {
        if (!window.ReportLineImageClient) {
            throw new Error("Módulo de upload de imagem indisponível.");
        }
        return window.ReportLineImageClient.uploadReportImage(file, uploadOptions);
    }

    async function handleFileSelected(event) {
        const file = event.target.files && event.target.files[0];
        event.target.value = "";
        if (!file) {
            return;
        }

        try {
            const payload = await uploadImage(file);
            if (window.ReportLineEditor && window.ReportLineEditor.insertImageAtCursor) {
                await window.ReportLineEditor.insertImageAtCursor(payload);
            }
        } catch (error) {
            console.error(error);
        }
    }

    function openFilePicker() {
        ensureFileInput().click();
    }

    function bindToolbar() {
        document.querySelectorAll("[data-report-image-insert]").forEach((button) => {
            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
            });
            button.addEventListener("click", (event) => {
                event.preventDefault();
                openFilePicker();
            });
        });
    }

    function init(options) {
        uploadOptions = options || {};
        bindToolbar();
    }

    window.ReportLineImageInsert = { init };
})();
