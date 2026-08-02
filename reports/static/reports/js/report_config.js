/**
 * Modal de configuração do laudo (numeração e recuo).
 */
(function () {
    "use strict";

    let configUrl = "";
    let modalElement = null;
    let modal = null;
    let form = null;
    let numberHeadingsInput = null;
    let numberCaptionsInput = null;
    let firstLineIndentInput = null;
    let pendingApplyPayload = null;
    let pendingConfigBefore = null;
    let lastAppliedConfig = null;

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function showToast(message, variant) {
        let container = document.querySelector(".toast-container");
        if (!container) {
            container = document.createElement("div");
            container.className = "toast-container position-fixed top-0 end-0 p-3";
            container.style.zIndex = "1080";
            container.setAttribute("aria-live", "polite");
            container.setAttribute("aria-atomic", "true");
            document.body.appendChild(container);
        }

        const toastClass = variant === "danger" ? "text-bg-danger" : "text-bg-success";
        const iconClass = variant === "danger"
            ? "bi-exclamation-triangle-fill"
            : "bi-check-circle-fill";
        const toastElement = document.createElement("div");
        toastElement.className = `toast align-items-center ${toastClass} border-0 mb-2`;
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
        container.appendChild(toastElement);
        bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 4000 }).show();
        toastElement.addEventListener("hidden.bs.toast", () => toastElement.remove());
    }

    function populateForm(config) {
        if (!config) {
            return;
        }
        if (numberHeadingsInput) {
            numberHeadingsInput.checked = Boolean(config.number_headings);
        }
        if (numberCaptionsInput) {
            numberCaptionsInput.checked = Boolean(config.number_captions);
        }
        if (firstLineIndentInput) {
            firstLineIndentInput.checked = Boolean(config.first_line_indent);
        }
    }

    function configPayloadFromData(data) {
        return {
            number_headings: Boolean(data.number_headings),
            number_captions: Boolean(data.number_captions),
            first_line_indent: Boolean(data.first_line_indent),
        };
    }

    function captureConfigFromForm() {
        return {
            number_headings: Boolean(numberHeadingsInput && numberHeadingsInput.checked),
            number_captions: Boolean(numberCaptionsInput && numberCaptionsInput.checked),
            first_line_indent: Boolean(firstLineIndentInput && firstLineIndentInput.checked),
        };
    }

    function applyFirstLineIndent(enabled) {
        document.querySelectorAll(
            '.report-editor-block[data-block-type="paragraph"]:not([data-is-caption="true"]) .report-editor-block-paragraph'
        ).forEach((paragraph) => {
            paragraph.dataset.firstLineIndent = enabled ? "true" : "false";
        });
    }

    function applyCaptionNumbers(captionNumbers) {
        document.querySelectorAll('.report-editor-block[data-is-caption="true"]').forEach((block) => {
            const line = block.querySelector(".report-editor-block-caption-line");
            if (!line) {
                return;
            }

            const nodeId = block.dataset.nodeId;
            const number = captionNumbers && captionNumbers[nodeId];
            let prefix = line.querySelector("[data-caption-number]");
            if (number) {
                if (!prefix) {
                    prefix = document.createElement("span");
                    prefix.className = "report-editor-caption-number user-select-none";
                    prefix.dataset.captionNumber = "1";
                    prefix.setAttribute("aria-hidden", "true");
                    line.insertBefore(prefix, line.firstChild);
                }
                prefix.textContent = `Figura ${number} - `;
            } else if (prefix) {
                prefix.remove();
            }
        });
    }

    async function applyConfigEffects(data) {
        if (!data) {
            return;
        }

        applyFirstLineIndent(data.first_line_indent);
        applyCaptionNumbers(data.caption_numbers);
        applyHeadingNumbers(data.heading_numbers);
        await refreshOutline(data.outline_html);
    }

    function applyHeadingNumbers(headingNumbers) {
        const headingBlocks = Array.from(
            document.querySelectorAll('.report-editor-block[data-block-type="heading"]')
        );
        let mainTitleAssigned = false;

        headingBlocks.forEach((block) => {
            const nodeId = block.dataset.nodeId;
            const number = (headingNumbers && headingNumbers[nodeId]) || "";
            const badge = block.querySelector("[data-heading-number]");
            if (badge) {
                badge.textContent = number ? `${number}.` : "";
            }
            if (number) {
                block.removeAttribute("data-is-main-title");
            } else if (!mainTitleAssigned) {
                block.dataset.isMainTitle = "true";
                mainTitleAssigned = true;
            } else {
                block.removeAttribute("data-is-main-title");
            }
        });
    }

    async function refreshOutline(outlineHtml) {
        const root = document.getElementById("report-editor-outline-root");
        if (!root || !outlineHtml) {
            if (window.ReportLineOutline && window.ReportLineOutline.refresh) {
                await window.ReportLineOutline.refresh();
            }
            return;
        }

        root.innerHTML = outlineHtml;
        if (window.ReportLineOutlineAccordion) {
            window.ReportLineOutlineAccordion.mount(root);
        }
        if (window.ReportLineOutlineDnD) {
            window.ReportLineOutlineDnD.mount(root);
        }
    }

    async function patchConfig(payload) {
        const response = await fetch(configUrl, {
            method: "PATCH",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = (data.errors && data.errors.join(" ")) || "Falha ao salvar configuração.";
            throw new Error(message);
        }

        return data;
    }

    async function applyConfigSnapshot(snapshot) {
        const data = await patchConfig(snapshot);
        await applyConfigEffects(data);
        populateForm(data);
        lastAppliedConfig = data;
        return data;
    }

    function recordConfigHistory(beforeSnapshot, afterSnapshot) {
        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {
            return;
        }
        window.ReportLineUndo.recordCommand({
            label: "Configuração do laudo",
            undo: () => applyConfigSnapshot(beforeSnapshot),
            redo: () => applyConfigSnapshot(afterSnapshot),
        });
    }

    async function saveConfig(event) {
        event.preventDefault();

        const payload = captureConfigFromForm();
        const data = await patchConfig(payload);
        pendingApplyPayload = data;

        if (modal) {
            modal.hide();
        }
    }

    function openModal() {
        if (!modal) {
            return;
        }
        pendingConfigBefore = lastAppliedConfig
            ? configPayloadFromData(lastAppliedConfig)
            : captureConfigFromForm();
        modal.show();
    }

    function init(options) {
        configUrl = (options && options.configUrl) || "";
        modalElement = document.getElementById("reportConfigModal");
        form = document.getElementById("report-config-form");
        numberHeadingsInput = document.getElementById("report-config-number-headings");
        numberCaptionsInput = document.getElementById("report-config-number-captions");
        firstLineIndentInput = document.getElementById("report-config-first-line-indent");

        if (!configUrl || !modalElement || !form) {
            return;
        }

        modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        lastAppliedConfig = options && options.initialConfig ? options.initialConfig : null;
        populateForm(lastAppliedConfig);

        modalElement.addEventListener("hidden.bs.modal", () => {
            if (!pendingApplyPayload) {
                return;
            }

            const data = pendingApplyPayload;
            pendingApplyPayload = null;
            const beforeSnapshot = pendingConfigBefore || configPayloadFromData(data);
            const afterSnapshot = configPayloadFromData(data);
            pendingConfigBefore = null;

            applyConfigEffects(data)
                .then(() => {
                    lastAppliedConfig = data;
                    populateForm(data);
                    recordConfigHistory(beforeSnapshot, afterSnapshot);
                    showToast("Configuração salva com sucesso.", "success");
                })
                .catch(console.error);
        });

        document.querySelectorAll("[data-report-config-open]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                openModal();
            });
        });

        form.addEventListener("submit", (event) => {
            saveConfig(event).catch((error) => {
                showToast(error.message || "Falha ao salvar configuração.", "danger");
            });
        });
    }

    window.ReportLineReportConfig = {
        init,
        populateForm,
        applyCaptionNumbers,
        applyHeadingNumbers,
        applyConfigEffects,
    };
})();
