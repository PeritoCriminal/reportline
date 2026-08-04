/**
 * Análise documental no intake comum de laudo pericial.
 *
 * Envia documentos e estado atual do formulário para inferência de metadados
 * e preenche campos vazios antes do submit final.
 */
(function () {
    const form = document.getElementById("forensic-intake-form");
    const analyzeButton = document.getElementById("btn-analyze-documents");
    const documentsInput = document.getElementById("id_documents");
    const statusLabel = document.getElementById("analyze-documents-status");
    const toastContainer = document.getElementById("intake-analyze-toast-container");

    if (!form || !analyzeButton || !documentsInput) {
        return;
    }

    const fieldNames = [
        "report_number",
        "report_year",
        "designation_date",
        "exam_objective",
        "supplementary_prompt",
        "requesting_authority",
        "police_district",
        "occurrence_report",
        "police_inquiry",
        "occurrence_at",
        "requisition_at",
        "attendance_protocol",
        "examiner",
        "examination_at",
        "photography",
        "scanning_3d",
        "sketch",
    ];

    function getField(name) {
        return form.querySelector(`[name="${name}"]`);
    }

    function isEmptyField(field) {
        if (!field) {
            return true;
        }
        return String(field.value || "").trim() === "";
    }

    function setFieldValue(name, value) {
        const field = getField(name);
        if (!field) {
            return;
        }
        if (isEmptyField(field)) {
            field.value = value == null ? "" : String(value);
        }
    }

    function applyMetadata(metadata) {
        fieldNames.forEach((name) => {
            if (Object.prototype.hasOwnProperty.call(metadata, name)) {
                setFieldValue(name, metadata[name]);
            }
        });
    }

    function showToast(message, variant) {
        if (!toastContainer || !window.bootstrap) {
            return;
        }

        const variantClass = variant === "warning" ? "text-bg-warning" : "text-bg-success";
        const iconClass =
            variant === "warning" ? "bi-exclamation-circle-fill" : "bi-check-circle-fill";
        const closeClass = variant === "warning" ? "btn-close" : "btn-close btn-close-white";
        const bodyClass = variant === "warning" ? "toast-body text-dark" : "toast-body";

        const toastElement = document.createElement("div");
        toastElement.className = `toast align-items-center ${variantClass} border-0 mb-2`;
        toastElement.setAttribute("role", "alert");
        toastElement.setAttribute("aria-live", "assertive");
        toastElement.setAttribute("aria-atomic", "true");
        toastElement.dataset.bsDelay = "6000";
        toastElement.dataset.bsAutohide = "true";
        toastElement.innerHTML = `
            <div class="d-flex">
                <div class="${bodyClass}">
                    <i class="bi ${iconClass} me-2" aria-hidden="true"></i>${message}
                </div>
                <button type="button"
                        class="${closeClass} me-2 m-auto"
                        data-bs-dismiss="toast"
                        aria-label="Fechar"></button>
            </div>
        `;

        toastContainer.appendChild(toastElement);
        bootstrap.Toast.getOrCreateInstance(toastElement).show();
        toastElement.addEventListener("hidden.bs.toast", () => toastElement.remove());
    }

    function setAnalyzing(isAnalyzing) {
        analyzeButton.disabled = isAnalyzing;
        if (statusLabel) {
            statusLabel.hidden = !isAnalyzing;
        }
    }

    analyzeButton.addEventListener("click", async () => {
        const files = documentsInput.files;
        if (!files || files.length === 0) {
            showToast("Selecione ao menos um documento para analisar.", "warning");
            return;
        }

        const analyzeUrl = form.dataset.analyzeUrl;
        if (!analyzeUrl) {
            showToast("Análise indisponível nesta página.", "warning");
            return;
        }

        const formData = new FormData(form);
        formData.delete("documents");
        Array.from(files).forEach((file) => formData.append("documents", file));

        const csrfInput = form.querySelector("[name=csrfmiddlewaretoken]");
        const csrfToken = csrfInput ? csrfInput.value : "";

        setAnalyzing(true);
        try {
            const response = await fetch(analyzeUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                body: formData,
            });

            let payload = {};
            try {
                payload = await response.json();
            } catch (_error) {
                payload = {};
            }

            if (!response.ok) {
                const message =
                    payload.error || "Não foi possível analisar os documentos.";
                showToast(message, "warning");
                return;
            }

            if (payload.metadata) {
                applyMetadata(payload.metadata);
            }

            const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
            if (warnings.length > 0) {
                warnings.forEach((warning) => showToast(warning, "warning"));
            } else {
                showToast("Campos vazios atualizados com base nos documentos.", "success");
            }
        } catch (_error) {
            showToast("Falha de comunicação ao analisar documentos.", "warning");
        } finally {
            setAnalyzing(false);
        }
    });
})();
