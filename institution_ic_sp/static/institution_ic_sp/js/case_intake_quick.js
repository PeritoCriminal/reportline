/**
 * Fluxo rápido de intake: casca → análise → montagem → editor.
 */
(function () {
    "use strict";

    const form = document.getElementById("forensic-intake-form");
    const quickButton = document.getElementById("btn-open-report-quick");
    const documentsInput = document.getElementById("id_documents");
    const statusPanel = document.getElementById("quick-intake-status");
    const statusText = document.getElementById("quick-intake-status-text");
    const toastContainer = document.getElementById("intake-analyze-toast-container");

    if (!form || !quickButton || !documentsInput) {
        return;
    }

    const QUICK_STATUS_MESSAGES = [
        "Preparando laudo…",
        "Lendo documentos com IA…",
        "Montando estrutura do laudo…",
    ];
    const STATUS_ROTATE_MS = 2200;

    let statusRotateTimer = null;
    let statusMessageIndex = 0;

    function getCsrfToken() {
        const csrfInput = form.querySelector("[name=csrfmiddlewaretoken]");
        return csrfInput ? csrfInput.value : "";
    }

    function showToast(message, variant) {
        if (!toastContainer || !window.bootstrap) {
            return;
        }

        const variantClass = variant === "warning" ? "text-bg-warning" : "text-bg-danger";
        const iconClass = "bi-exclamation-triangle-fill";
        const toastElement = document.createElement("div");
        toastElement.className = `toast align-items-center ${variantClass} border-0 mb-2`;
        toastElement.setAttribute("role", "alert");
        toastElement.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${iconClass} me-2" aria-hidden="true"></i>${message}
                </div>
                <button type="button"
                        class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"
                        aria-label="Fechar"></button>
            </div>
        `;
        toastContainer.appendChild(toastElement);
        bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 6000 }).show();
        toastElement.addEventListener("hidden.bs.toast", () => toastElement.remove());
    }

    function setStatusMessage(message) {
        if (!statusText) {
            return;
        }
        statusText.classList.add("is-changing");
        window.setTimeout(() => {
            statusText.textContent = message;
            statusText.classList.remove("is-changing");
        }, 120);
    }

    function startStatusRotation() {
        statusMessageIndex = 0;
        setStatusMessage(QUICK_STATUS_MESSAGES[0]);
        statusRotateTimer = window.setInterval(() => {
            statusMessageIndex = (statusMessageIndex + 1) % QUICK_STATUS_MESSAGES.length;
            setStatusMessage(QUICK_STATUS_MESSAGES[statusMessageIndex]);
        }, STATUS_ROTATE_MS);
    }

    function stopStatusRotation() {
        if (statusRotateTimer !== null) {
            window.clearInterval(statusRotateTimer);
            statusRotateTimer = null;
        }
    }

    function setQuickBusy(isBusy) {
        quickButton.disabled = isBusy;
        quickButton.classList.toggle("is-analyzing", isBusy);
        quickButton.setAttribute("aria-busy", isBusy ? "true" : "false");
        if (statusPanel) {
            statusPanel.hidden = !isBusy;
        }
        if (isBusy) {
            startStatusRotation();
            return;
        }
        stopStatusRotation();
    }

    function buildAnalyzeFormData() {
        const formData = new FormData();
        const supplementary = form.querySelector("[name=supplementary_prompt]");
        if (supplementary) {
            formData.append("supplementary_prompt", supplementary.value || "");
        }
        Array.from(documentsInput.files || []).forEach((file) => {
            formData.append("documents", file);
        });
        return formData;
    }

    async function postJson(url, options) {
        const response = await fetch(url, options);
        let payload = {};
        try {
            payload = await response.json();
        } catch (_error) {
            payload = {};
        }
        if (!response.ok) {
            const errors = payload.errors || payload.error;
            const message = Array.isArray(errors)
                ? errors.join(" ")
                : errors || "Não foi possível concluir a operação.";
            throw new Error(message);
        }
        return payload;
    }

    quickButton.addEventListener("click", async () => {
        const files = documentsInput.files;
        if (!files || files.length === 0) {
            showToast("Selecione ao menos um documento para continuar.", "warning");
            return;
        }

        const quickShellUrl = form.dataset.quickShellUrl;
        if (!quickShellUrl) {
            showToast("Fluxo rápido indisponível nesta página.", "warning");
            return;
        }

        setQuickBusy(true);
        try {
            const shellFormData = new FormData();
            const supplementary = form.querySelector("[name=supplementary_prompt]");
            if (supplementary) {
                shellFormData.append("supplementary_prompt", supplementary.value || "");
            }

            const shell = await postJson(quickShellUrl, {
                method: "POST",
                headers: { "X-CSRFToken": getCsrfToken() },
                body: shellFormData,
            });

            setStatusMessage("Lendo documentos com IA…");
            const analyzePayload = await postJson(shell.analyze_url, {
                method: "POST",
                headers: { "X-CSRFToken": getCsrfToken() },
                body: buildAnalyzeFormData(),
            });

            const warnings = Array.isArray(analyzePayload.warnings) ? analyzePayload.warnings : [];
            warnings.forEach((warning) => showToast(warning, "warning"));

            setStatusMessage("Montando estrutura do laudo…");
            await postJson(shell.build_url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                    "Content-Type": "application/json",
                },
                body: "{}",
            });

            window.location.assign(shell.edit_url);
        } catch (error) {
            showToast(error.message || "Falha ao preparar o laudo.", "danger");
        } finally {
            setQuickBusy(false);
        }
    });
})();
