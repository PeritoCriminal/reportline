/**
 * Seleção de arquivo e upload de imagem para inserção no editor.
 */
(function () {
    "use strict";

    let fileInput = null;
    let uploadUrl = "";

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

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
        const formData = new FormData();
        formData.append("image", file);

        const response = await fetch(uploadUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
            body: formData,
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = (data.errors && data.errors.join(" ")) || "Falha ao enviar imagem.";
            throw new Error(message);
        }
        return data;
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
        uploadUrl = options.uploadUrl || "";
        bindToolbar();
    }

    window.ReportLineImageInsert = { init };
})();
