// reportline/institution_ic_sp/static/institution_ic_sp/js/case_intake_quick.js
/**
 * Fluxo rápido de intake: casca → editor → análise e montagem em background.
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

    function setQuickBusy(isBusy) {
        quickButton.disabled = isBusy;
        quickButton.classList.toggle("is-analyzing", isBusy);
        quickButton.setAttribute("aria-busy", isBusy ? "true" : "false");
        if (statusPanel) {
            statusPanel.hidden = !isBusy;
        }
        if (isBusy) {
            setStatusMessage("Abrindo editor…");
        }
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
        const docPicker = window.ReportLineCaseIntakeDocuments;
        const files = docPicker?.getFiles?.() || documentsInput.files;
        if (!files || files.length === 0) {
            showToast("Selecione ao menos um documento para continuar.", "warning");
            return;
        }

        const quickShellUrl = form.dataset.quickShellUrl;
        if (!quickShellUrl) {
            showToast("Fluxo rápido indisponível nesta página.", "warning");
            return;
        }

        const docStore = window.ReportLineForensicBootstrapDocuments;
        if (!docStore || !docStore.storePendingDocuments) {
            showToast("Armazenamento local indisponível neste navegador.", "warning");
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

            await docStore.storePendingDocuments(shell.report_id, files);
            window.location.assign(shell.edit_url);
        } catch (error) {
            showToast(error.message || "Falha ao preparar o laudo.", "danger");
            setQuickBusy(false);
        }
    });
})();
