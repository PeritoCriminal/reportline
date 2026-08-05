/**

 * Prompts inline do bootstrap pericial no editor de laudos.

 *

 * Acumula respostas localmente e persiste em lote ao concluir a fila,

 * com pré-visualização imediata de campos simples (ex.: número do laudo).

 */

(function () {

    "use strict";



    const STATE_PROMPTING = "prompting";

    const UPPERCASE_TEXT_FIELDS = new Set(["report_number", "occurrence_report"]);



    let config = null;

    let shell = null;

    let form = null;

    let input = null;

    let label = null;

    let help = null;

    let title = null;

    let progress = null;

    let errorBox = null;

    let skipButton = null;

    let submitButton = null;



    let promptQueue = [];

    let queueIndex = 0;

    let localMetadata = {};

    let localAnswers = {};

    let localSkipped = [];

    let currentPrompt = null;

    let isFinalizing = false;



    function getCsrfToken() {

        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);

        return match ? decodeURIComponent(match[1]) : "";

    }



    function normalizeTextField(fieldName, value) {

        const cleaned = (value || "").trim();

        if (UPPERCASE_TEXT_FIELDS.has(fieldName)) {

            return cleaned.toUpperCase();

        }

        return cleaned;

    }



    function parseReportYear() {

        const raw = localMetadata.report_year;

        const parsed = parseInt(String(raw || ""), 10);

        return Number.isFinite(parsed) && parsed > 0 ? parsed : new Date().getFullYear();

    }



    function formatMainTitleText(reportNumber) {

        const number = normalizeTextField("report_number", reportNumber);

        const year = parseReportYear();

        if (number && year) {

            return `LAUDO PERICIAL Nº ${number}/${year}`;

        }

        if (number) {

            return `LAUDO PERICIAL Nº ${number}`;

        }

        return "LAUDO PERICIAL";

    }



    function formatHeaderReportNumberText(reportNumber) {

        const number = normalizeTextField("report_number", reportNumber);

        const year = parseReportYear();

        if (number && year) {

            return `Laudo pericial nº ${number}/${year}`;

        }

        if (number) {

            return `Laudo pericial nº ${number}`;

        }

        return "Laudo pericial";

    }



    function showError(message) {

        if (!errorBox) {

            return;

        }

        if (message) {

            errorBox.textContent = message;

            errorBox.hidden = false;

            if (input) {

                input.classList.add("is-invalid");

            }

            return;

        }

        errorBox.textContent = "";

        errorBox.hidden = true;

        if (input) {

            input.classList.remove("is-invalid");

        }

    }



    function setBusy(isBusy) {

        if (skipButton) {

            skipButton.disabled = isBusy;

        }

        if (submitButton) {

            submitButton.disabled = isBusy;

        }

        if (input) {

            input.disabled = isBusy;

        }

        const overlayActive = Boolean(currentPrompt && !isBusy && !isFinalizing);

        document.body.classList.toggle("forensic-bootstrap-prompt-active", overlayActive);

    }



    function updateProgress() {

        if (!progress) {

            return;

        }

        if (!promptQueue.length) {

            progress.textContent = "";

            progress.hidden = true;

            return;

        }

        progress.hidden = false;
        progress.textContent = `${queueIndex + 1} de ${promptQueue.length} · `;
    }



    function applyPromptDescriptor(prompt) {

        currentPrompt = prompt;

        if (!prompt) {

            if (shell) {

                shell.hidden = true;

            }

            document.body.classList.remove("forensic-bootstrap-prompt-active");

            return;

        }



        if (shell) {

            shell.hidden = false;

        }

        if (title) {

            title.textContent = "Complementar dados do laudo";

        }

        if (label) {

            label.textContent = prompt.label || "Campo";

        }

        if (help) {

            help.textContent = prompt.help_text || "";

        }

        if (input) {

            input.type = prompt.input_type || "text";

            input.value = "";

            input.placeholder = prompt.placeholder || "";

            input.classList.remove("is-invalid");

            input.focus();

        }

        showError("");

        updateProgress();

        document.body.classList.add("forensic-bootstrap-prompt-active");

    }



    function applyLocalPreview(fieldName, rawValue) {

        if (fieldName !== "report_number") {

            return;

        }



        const normalized = normalizeTextField(fieldName, rawValue);

        localMetadata.report_number = normalized;



        const mainTitleEditable = document.querySelector(

            '[data-is-main-title="true"] .report-editor-block-editable'

        );

        if (mainTitleEditable) {

            mainTitleEditable.textContent = formatMainTitleText(normalized);

        }



        const headerNumberCell = document.querySelector(

            '[data-report-page-header-extra-text][data-extra-row-index="1"]'

        );

        if (headerNumberCell) {

            headerNumberCell.textContent = formatHeaderReportNumberText(normalized);

        }

    }



    function advanceQueue() {

        queueIndex += 1;

        if (queueIndex < promptQueue.length) {

            applyPromptDescriptor(promptQueue[queueIndex]);

            setBusy(false);

            return;

        }

        finalizeBatch().catch(console.error);

    }



    async function finalizeBatch() {

        if (!config || !config.finalizeUrl || isFinalizing) {

            return;

        }



        isFinalizing = true;

        setBusy(true);

        showError("");



        if (title) {

            title.textContent = "Salvando dados do laudo…";

        }

        if (progress) {

            progress.textContent = "Aguarde";

        }



        try {

            const response = await fetch(config.finalizeUrl, {

                method: "POST",

                headers: {

                    "Content-Type": "application/json",

                    "X-CSRFToken": getCsrfToken(),

                },

                credentials: "same-origin",

                body: JSON.stringify({

                    answers: localAnswers,

                    skipped: localSkipped,

                }),

            });



            const payload = await response.json().catch(() => ({}));

            if (!response.ok) {

                const errors = payload.errors || ["Não foi possível salvar os dados."];

                throw new Error(Array.isArray(errors) ? errors.join(" ") : String(errors));

            }



            if (payload.reload) {

                window.location.reload();

                return;

            }



            applyPromptDescriptor(null);

        } catch (error) {

            isFinalizing = false;

            if (title) {

                title.textContent = "Complementar dados do laudo";

            }

            updateProgress();

            showError(error.message || "Falha ao concluir.");

            setBusy(false);

        }

    }



    function handleSubmit(event) {

        event.preventDefault();

        if (!input || !currentPrompt || isFinalizing) {

            return;

        }



        const rawValue = (input.value || "").trim();

        if (!rawValue) {

            showError("Informe um valor ou use Pular.");

            return;

        }



        setBusy(true);

        const fieldName = currentPrompt.field;

        localAnswers[fieldName] = rawValue;

        applyLocalPreview(fieldName, rawValue);

        advanceQueue();

    }



    function handleSkip() {

        if (!currentPrompt || isFinalizing) {

            return;

        }



        setBusy(true);

        localSkipped.push(currentPrompt.field);

        advanceQueue();

    }



    function init(options) {

        config = options || {};

        shell = document.getElementById("forensic-bootstrap-prompt-shell");

        form = document.getElementById("forensic-bootstrap-prompt-form");

        input = document.getElementById("forensic-bootstrap-prompt-input");

        label = document.getElementById("forensic-bootstrap-prompt-label");

        help = document.getElementById("forensic-bootstrap-prompt-help");

        title = document.getElementById("forensic-bootstrap-prompt-title");

        progress = document.getElementById("forensic-bootstrap-prompt-progress");

        errorBox = document.getElementById("forensic-bootstrap-prompt-error");

        skipButton = document.getElementById("forensic-bootstrap-prompt-skip");

        submitButton = document.getElementById("forensic-bootstrap-prompt-submit");



        if (!shell || !form || config.state !== STATE_PROMPTING) {

            return;

        }



        promptQueue = Array.isArray(config.pendingPrompts) ? config.pendingPrompts.slice() : [];

        localMetadata = Object.assign({}, config.metadata || {});

        queueIndex = 0;

        localAnswers = {};

        localSkipped = [];



        if (!promptQueue.length) {

            return;

        }



        applyPromptDescriptor(promptQueue[0]);



        form.addEventListener("submit", handleSubmit);

        if (skipButton) {

            skipButton.addEventListener("click", handleSkip);

        }

    }



    window.ReportLineForensicBootstrap = { init };

})();

