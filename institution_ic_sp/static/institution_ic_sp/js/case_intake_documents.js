// reportline/institution_ic_sp/static/institution_ic_sp/js/case_intake_documents.js
/**
 * Seleção e arrastar/soltar de documentos no intake de laudo pericial.
 *
 * Mantém lista de arquivos escolhidos, sincroniza o input oculto do formulário
 * e expõe API mínima para o fluxo rápido de abertura do laudo.
 */
(function () {
    "use strict";

    const ACCEPTED_MIME_PREFIXES = ["image/"];
    const ACCEPTED_MIME_TYPES = new Set(["application/pdf"]);
    const ACCEPTED_EXTENSIONS = /\.(pdf|png|jpe?g|webp)$/i;

    let dropzone = null;
    let fileInput = null;
    let fileListElement = null;
    let errorBox = null;
    let pendingFiles = [];
    let domInitialized = false;

    function isAcceptedDocument(file) {
        if (!file) {
            return false;
        }
        if (ACCEPTED_MIME_TYPES.has(file.type)) {
            return true;
        }
        if (ACCEPTED_MIME_PREFIXES.some((prefix) => file.type.startsWith(prefix))) {
            return true;
        }
        return ACCEPTED_EXTENSIONS.test(file.name || "");
    }

    function formatFileSize(bytes) {
        if (!Number.isFinite(bytes) || bytes <= 0) {
            return "";
        }
        if (bytes < 1024) {
            return `${bytes} B`;
        }
        if (bytes < 1024 * 1024) {
            return `${(bytes / 1024).toFixed(1)} KB`;
        }
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    function fileIconClass(file) {
        if (file.type === "application/pdf" || /\.pdf$/i.test(file.name || "")) {
            return "bi-file-earmark-pdf";
        }
        if (file.type.startsWith("image/")) {
            return "bi-file-earmark-image";
        }
        return "bi-file-earmark-text";
    }

    function setError(message) {
        if (!errorBox) {
            return;
        }
        errorBox.textContent = message || "";
        errorBox.hidden = !message;
    }

    function syncInputFiles() {
        if (!fileInput || typeof DataTransfer === "undefined") {
            return;
        }
        const transfer = new DataTransfer();
        pendingFiles.forEach((file) => transfer.items.add(file));
        fileInput.files = transfer.files;
    }

    function renderFileList() {
        if (!fileListElement) {
            return;
        }
        fileListElement.innerHTML = "";
        if (!pendingFiles.length) {
            fileListElement.hidden = true;
            syncInputFiles();
            return;
        }

        fileListElement.hidden = false;
        pendingFiles.forEach((file, index) => {
            const item = document.createElement("li");
            item.className = "intake-documents-file-item";

            const icon = document.createElement("i");
            icon.className = `bi ${fileIconClass(file)} intake-documents-file-icon`;
            icon.setAttribute("aria-hidden", "true");

            const meta = document.createElement("div");
            meta.className = "intake-documents-file-meta";

            const name = document.createElement("span");
            name.className = "intake-documents-file-name";
            name.textContent = file.name;
            name.title = file.name;

            const size = document.createElement("span");
            size.className = "intake-documents-file-size";
            size.textContent = formatFileSize(file.size);

            meta.appendChild(name);
            meta.appendChild(size);

            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.className = "btn btn-sm btn-outline-danger intake-documents-file-remove";
            removeButton.setAttribute("aria-label", `Remover ${file.name}`);
            removeButton.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
            removeButton.addEventListener("click", () => {
                pendingFiles.splice(index, 1);
                renderFileList();
            });

            item.appendChild(icon);
            item.appendChild(meta);
            item.appendChild(removeButton);
            fileListElement.appendChild(item);
        });
        syncInputFiles();
    }

    function addFiles(fileList) {
        const incoming = Array.from(fileList || []).filter(isAcceptedDocument);
        if (!incoming.length) {
            setError("Selecione arquivos PDF ou imagem (JPG, PNG, WEBP).");
            return;
        }
        setError("");
        pendingFiles = pendingFiles.concat(incoming);
        renderFileList();
    }

    function bindDropzoneEvents() {
        if (!dropzone || !fileInput || dropzone.dataset.eventsBound === "true") {
            return;
        }
        dropzone.dataset.eventsBound = "true";

        dropzone.addEventListener("click", () => fileInput.click());
        dropzone.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                fileInput.click();
            }
        });
        fileInput.addEventListener("change", () => {
            addFiles(fileInput.files);
            fileInput.value = "";
        });
        dropzone.addEventListener("dragover", (event) => {
            event.preventDefault();
            dropzone.classList.add("is-dragover");
        });
        dropzone.addEventListener("dragleave", () => {
            dropzone.classList.remove("is-dragover");
        });
        dropzone.addEventListener("drop", (event) => {
            event.preventDefault();
            event.stopPropagation();
            dropzone.classList.remove("is-dragover");
            addFiles(event.dataTransfer?.files);
        });
    }

    function initDomReferences() {
        if (domInitialized) {
            return true;
        }

        dropzone = document.getElementById("intake-documents-dropzone");
        fileInput = document.getElementById("id_documents");
        fileListElement = document.getElementById("intake-documents-file-list");
        errorBox = document.getElementById("intake-documents-error");

        if (!dropzone || !fileInput) {
            return false;
        }

        bindDropzoneEvents();
        domInitialized = true;
        return true;
    }

    function getFiles() {
        return pendingFiles.slice();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initDomReferences);
    } else {
        initDomReferences();
    }

    window.ReportLineCaseIntakeDocuments = {
        initDomReferences,
        getFiles,
    };
})();
