// reportline/reports/static/reports/js/trace_collection_continuation.js
/**
 * Coleta interativa de vestígios (Elementos Observados) após a seção de local.
 */
(function () {
    "use strict";

    const TRACE_ANALYZE_STATUS_MESSAGES = [
        "Lendo imagens do vestígio…",
        "Identificando características observadas…",
        "Preparando descrição para o laudo…",
    ];
    const TRACE_ANALYZE_STATUS_ROTATE_MS = 2200;
    const TRACE_COLLECTION_CANCELLED = "TRACE_COLLECTION_CANCELLED";

    let decisionModal = null;
    let observationModal = null;
    let decisionModalElement = null;
    let observationModalElement = null;
    let decisionTitle = null;
    let decisionMessage = null;
    let decisionAcceptButton = null;
    let decisionDeclineButton = null;
    let dropzone = null;
    let fileInput = null;
    let previewGrid = null;
    let promptInput = null;
    let errorBox = null;
    let submitButton = null;
    let cancelButton = null;
    let analyzeStatusPanel = null;
    let analyzeStatusText = null;
    let toastContainer = null;
    let pendingFiles = [];
    let isSubmitting = false;
    let domInitialized = false;
    let statusRotateTimer = null;
    let statusMessageIndex = 0;

    const imagePreview = window.ReportLineImageUploadPreview;

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function showToast(message, variant) {
        if (!toastContainer) {
            toastContainer = document.querySelector(".toast-container");
        }
        if (!toastContainer) {
            toastContainer = document.createElement("div");
            toastContainer.className = "toast-container position-fixed top-0 end-0 p-3";
            toastContainer.style.zIndex = "1080";
            document.body.appendChild(toastContainer);
        }
        if (!window.bootstrap?.Toast) {
            return;
        }
        const tone = variant || "info";
        const toastElement = document.createElement("div");
        toastElement.className = `toast align-items-center text-bg-${tone} border-0`;
        toastElement.setAttribute("role", "alert");
        toastElement.setAttribute("aria-live", "assertive");
        toastElement.setAttribute("aria-atomic", "true");
        toastElement.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button"
                        class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"
                        aria-label="Fechar"></button>
            </div>`;
        toastContainer.appendChild(toastElement);
        const toast = window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 6000 });
        toastElement.addEventListener("hidden.bs.toast", () => toastElement.remove());
        toast.show();
    }

    function setError(message) {
        if (!errorBox) {
            return;
        }
        errorBox.textContent = message || "";
        errorBox.hidden = !message;
    }

    function showModal(modalInstance) {
        modalInstance.show();
    }

    function hideModal(modalInstance) {
        modalInstance.hide();
    }

    function setAnalyzeMessage(message) {
        if (!analyzeStatusText) {
            return;
        }
        analyzeStatusText.classList.add("is-changing");
        window.setTimeout(() => {
            analyzeStatusText.textContent = message;
            analyzeStatusText.classList.remove("is-changing");
        }, 120);
    }

    function startAnalyzeRotation() {
        statusMessageIndex = 0;
        setAnalyzeMessage(TRACE_ANALYZE_STATUS_MESSAGES[0]);
        statusRotateTimer = window.setInterval(() => {
            statusMessageIndex = (statusMessageIndex + 1) % TRACE_ANALYZE_STATUS_MESSAGES.length;
            setAnalyzeMessage(TRACE_ANALYZE_STATUS_MESSAGES[statusMessageIndex]);
        }, TRACE_ANALYZE_STATUS_ROTATE_MS);
    }

    function stopAnalyzeRotation() {
        if (statusRotateTimer !== null) {
            window.clearInterval(statusRotateTimer);
            statusRotateTimer = null;
        }
    }

    function setModalFormDisabled(disabled) {
        [dropzone, fileInput, promptInput].forEach((control) => {
            if (!control) {
                return;
            }
            if (control === dropzone) {
                control.classList.toggle("pe-none", disabled);
                control.setAttribute("aria-disabled", disabled ? "true" : "false");
                return;
            }
            control.disabled = disabled;
        });
        previewGrid?.querySelectorAll(".report-image-upload-preview-remove").forEach((button) => {
            button.disabled = disabled;
        });
        imagePreview?.setGridDisabled(previewGrid, disabled);
    }

    function beginTraceAnalysis() {
        isSubmitting = true;
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.classList.add("is-analyzing");
            submitButton.setAttribute("aria-busy", "true");
        }
        if (analyzeStatusPanel) {
            analyzeStatusPanel.hidden = false;
        }
        setModalFormDisabled(true);
    }

    function endTraceAnalysis() {
        isSubmitting = false;
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.classList.remove("is-analyzing");
            submitButton.setAttribute("aria-busy", "false");
        }
        if (analyzeStatusPanel) {
            analyzeStatusPanel.hidden = true;
        }
        setModalFormDisabled(false);
    }

    function resetObservationForm() {
        imagePreview?.revokePreviewUrls(pendingFiles);
        pendingFiles = [];
        if (promptInput) {
            promptInput.value = "";
        }
        setError("");
        if (previewGrid) {
            previewGrid.innerHTML = "";
            previewGrid.hidden = true;
        }
        if (fileInput) {
            fileInput.value = "";
        }
    }

    function renderPreviewGrid() {
        imagePreview?.renderPreviewGrid(previewGrid, pendingFiles, {
            disabled: isSubmitting,
            onRemove: (index) => {
                const removed = pendingFiles.splice(index, 1)[0];
                imagePreview?.revokePreviewUrls([removed]);
                renderPreviewGrid();
            },
        });
    }

    function addFiles(fileList) {
        const incoming = Array.from(fileList || []).filter((file) => file.type.startsWith("image/"));
        if (!incoming.length) {
            setError("Selecione arquivos de imagem válidos.");
            return;
        }
        setError("");
        pendingFiles = pendingFiles.concat(
            incoming.map((file) => imagePreview.createPendingItem(file))
        );
        renderPreviewGrid();
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

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload || {}),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = Array.isArray(data.errors) ? data.errors.join(" ") : "Falha na requisição.";
            throw new Error(message);
        }
        return data;
    }

    async function uploadImage(uploadUrl, file) {
        const formData = new FormData();
        formData.append("image", file);
        const response = await fetch(uploadUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
            },
            body: formData,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.image_id) {
            throw new Error("Não foi possível enviar a imagem.");
        }
        return data.image_id;
    }

    function bindDropzone() {
        bindDropzoneEvents();
    }

    function waitForTraceDecision(config) {
        return new Promise((resolve, reject) => {
            const askAnother = Boolean(config.askAnotherTrace || (config.tracesCount || 0) > 0);
            if (decisionTitle) {
                decisionTitle.textContent = askAnother
                    ? "Incluir outro vestígio?"
                    : "Acrescentar vestígio?";
            }
            if (decisionMessage) {
                decisionMessage.textContent = askAnother
                    ? "Deseja registrar mais um elemento observado no local?"
                    : "Deseja registrar vestígios ou elementos observados no local?";
            }

            function cleanup() {
                decisionAcceptButton?.removeEventListener("click", onAccept);
                decisionDeclineButton?.removeEventListener("click", onDecline);
            }

            function onAccept() {
                cleanup();
                hideModal(decisionModal);
                resolve({ addTrace: true });
            }

            function onDecline() {
                cleanup();
                hideModal(decisionModal);
                resolve({ addTrace: false });
            }

            decisionAcceptButton?.addEventListener("click", onAccept);
            decisionDeclineButton?.addEventListener("click", onDecline);
            showModal(decisionModal);
        });
    }

    function waitForObservationSubmit() {
        return new Promise((resolve, reject) => {
            function cleanup() {
                submitButton?.removeEventListener("click", onSubmit);
                cancelButton?.removeEventListener("click", onCancel);
            }

            function onCancel() {
                cleanup();
                const error = new Error("Coleta de vestígios adiada.");
                error.code = TRACE_COLLECTION_CANCELLED;
                reject(error);
            }

            function onSubmit() {
                const prompt = promptInput?.value?.trim() || "";
                const pendingUploads = pendingFiles.slice();
                if (!prompt && !pendingUploads.length) {
                    setError("Informe imagens ou orientações sobre o vestígio.");
                    return;
                }
                cleanup();
                resolve({ prompt, pendingUploads });
            }

            submitButton?.addEventListener("click", onSubmit);
            cancelButton?.addEventListener("click", onCancel);
        });
    }

    async function persistTraceDecision(config, addTrace) {
        return postJson(config.traceDecisionUrl, { add_trace: addTrace });
    }

    async function persistTraceObservation(config, draft) {
        const payload = {
            prompt: draft.prompt || "",
        };
        const pendingUploads = draft.pendingUploads || [];
        if (pendingUploads.length && imagePreview) {
            payload.images = imagePreview.buildImagesPayload(pendingUploads);
        } else {
            payload.image_ids = [];
        }
        return postJson(config.traceAddUrl, payload);
    }

    async function collectTraceObservation(config) {
        if (!config?.traceAddUrl) {
            throw new Error("Coleta de vestígios indisponível nesta tela.");
        }

        resetObservationForm();
        showModal(observationModal);

        while (true) {
            let draft;
            try {
                draft = await waitForObservationSubmit();
            } catch (error) {
                hideModal(observationModal);
                throw error;
            }

            beginTraceAnalysis();
            let succeeded = false;
            try {
                const uploads = draft.pendingUploads;
                if (uploads.length) {
                    for (let index = 0; index < uploads.length; index += 1) {
                        const pendingItem = uploads[index];
                        const label =
                            uploads.length === 1
                                ? "Enviando imagem do vestígio…"
                                : `Enviando imagem ${index + 1} de ${uploads.length}…`;
                        setAnalyzeMessage(label);
                        const imageId = await uploadImage(config.imageUploadUrl, pendingItem.file);
                        pendingItem.imageId = imageId;
                    }
                }

                if (uploads.length) {
                    startAnalyzeRotation();
                } else {
                    setAnalyzeMessage("Analisando orientações do vestígio…");
                }

                const response = await persistTraceObservation(config, draft);
                succeeded = true;
                hideModal(observationModal);
                return response;
            } catch (error) {
                setError(error.message || "Não foi possível analisar o vestígio.");
            } finally {
                stopAnalyzeRotation();
                endTraceAnalysis();
                if (succeeded) {
                    hideModal(observationModal);
                }
            }
        }
    }

    /**
     * Pergunta se o perito deseja incluir vestígio e persiste recusa quando aplicável.
     *
     * @param {object} config
     * @returns {Promise<object>}
     */
    async function askDecision(config) {
        if (!config?.traceDecisionUrl) {
            throw new Error("Decisão de vestígios indisponível nesta tela.");
        }
        const choice = await waitForTraceDecision(config);
        if (!choice.addTrace) {
            const response = await persistTraceDecision(config, false);
            if (response.todo_message) {
                showToast(response.todo_message, "info");
            }
            return response;
        }
        await persistTraceDecision(config, true);
        return { state: config.state, addTrace: true };
    }

    function initDomReferences() {
        if (domInitialized) {
            return true;
        }

        decisionModalElement = document.getElementById("traceDecisionModal");
        observationModalElement = document.getElementById("traceObservationModal");
        decisionTitle = document.getElementById("trace-decision-modal-title");
        decisionMessage = document.getElementById("trace-decision-modal-message");
        decisionAcceptButton = document.getElementById("trace-decision-accept");
        decisionDeclineButton = document.getElementById("trace-decision-decline");
        dropzone = document.getElementById("trace-observation-dropzone");
        fileInput = document.getElementById("trace-observation-file-input");
        previewGrid = document.getElementById("trace-observation-preview-grid");
        promptInput = document.getElementById("trace-observation-prompt-input");
        errorBox = document.getElementById("trace-observation-error");
        submitButton = document.getElementById("trace-observation-submit");
        cancelButton = document.getElementById("trace-observation-cancel");
        analyzeStatusPanel = document.getElementById("trace-observation-analyze-status");
        analyzeStatusText = document.getElementById("trace-observation-analyze-status-text");

        bindDropzone();

        if (!decisionModalElement || !observationModalElement || !window.bootstrap?.Modal) {
            return false;
        }

        decisionModal = window.bootstrap.Modal.getOrCreateInstance(decisionModalElement, {
            backdrop: "static",
            keyboard: false,
        });
        observationModal = window.bootstrap.Modal.getOrCreateInstance(observationModalElement, {
            backdrop: "static",
            keyboard: false,
        });
        domInitialized = true;
        return true;
    }

    window.ReportLineTraceCollectionContinuation = {
        initDomReferences,
        askDecision,
        collectTraceObservation,
        showToast,
        TRACE_COLLECTION_CANCELLED,
    };
})();
