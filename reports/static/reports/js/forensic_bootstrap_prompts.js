/**
 * Prompts inline do bootstrap pericial no editor de laudos.
 *
 * Acumula respostas localmente e persiste em lote ao concluir a fila.
 * Usado antes da montagem visual do corpo (collecting_prompts) ou após
 * montagem legada (prompting).
 */
(function () {
    "use strict";

    const STATE_COLLECTING_PROMPTS = "collecting_prompts";
    const STATE_PROMPTING = "prompting";
    const UPPERCASE_TEXT_FIELDS = new Set([
        "report_number",
        "occurrence_report",
        "police_inquiry",
        "attendance_protocol",
    ]);

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
    let flowResolve = null;
    let flowReject = null;
    let listenersBound = false;

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

    function bindDom() {
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
            const existingValue = (localMetadata[prompt.field] || "").trim();
            if (prompt.default_value && !existingValue) {
                input.value = prompt.default_value;
            } else {
                input.value = existingValue;
            }
            input.placeholder = prompt.placeholder || "";
            input.classList.remove("is-invalid");
        }
        showError("");
        updateProgress();
        setBusy(false);
        if (input) {
            input.focus();
            if (input.type === "date" || input.type === "datetime-local") {
                try {
                    input.setSelectionRange(0, 0);
                } catch (_error) {
                    /* inputs nativos de data/hora não suportam seleção programática */
                }
            }
        }
        document.body.classList.add("forensic-bootstrap-prompt-active");
    }

    function advanceQueue() {
        queueIndex += 1;
        if (queueIndex < promptQueue.length) {
            applyPromptDescriptor(promptQueue[queueIndex]);
            return;
        }
        finalizeBatch().catch(console.error);
    }

    function completeFlow(payload) {
        applyPromptDescriptor(null);
        if (flowResolve) {
            flowResolve(payload);
            flowResolve = null;
            flowReject = null;
        }
    }

    function failFlow(error) {
        if (flowReject) {
            flowReject(error);
            flowReject = null;
            flowResolve = null;
        }
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

            isFinalizing = false;
            completeFlow(payload);
        } catch (error) {
            isFinalizing = false;
            if (title) {
                title.textContent = "Complementar dados do laudo";
            }
            updateProgress();
            showError(error.message || "Falha ao concluir.");
            setBusy(false);
            failFlow(error);
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
        localMetadata[fieldName] = normalizeTextField(fieldName, rawValue);
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

    function bindListeners() {
        if (listenersBound || !form) {
            return;
        }
        form.addEventListener("submit", handleSubmit);
        if (skipButton) {
            skipButton.addEventListener("click", handleSkip);
        }
        listenersBound = true;
    }

    function startPromptFlow(options) {
        config = options || {};
        bindDom();
        bindListeners();

        const allowedStates = new Set([STATE_COLLECTING_PROMPTS, STATE_PROMPTING]);
        if (!shell || !form || !allowedStates.has(config.state)) {
            throw new Error("Prompts indisponíveis nesta etapa.");
        }

        promptQueue = Array.isArray(config.pendingPrompts) ? config.pendingPrompts.slice() : [];
        localMetadata = Object.assign({}, config.metadata || {});
        queueIndex = 0;
        localAnswers = {};
        localSkipped = [];
        isFinalizing = false;

        if (!promptQueue.length) {
            return Promise.resolve({ state: config.state });
        }

        applyPromptDescriptor(promptQueue[0]);
        return null;
    }

    function runPromptFlow(options) {
        return new Promise((resolve, reject) => {
            flowResolve = resolve;
            flowReject = reject;
            try {
                const immediate = startPromptFlow(options);
                if (immediate) {
                    resolve(immediate);
                    flowResolve = null;
                    flowReject = null;
                }
            } catch (error) {
                flowResolve = null;
                flowReject = null;
                reject(error);
            }
        });
    }

    function init(options) {
        const result = startPromptFlow(options);
        if (result) {
            result.catch(console.error);
        }
    }

    window.ReportLineForensicBootstrap = { init, runPromptFlow };
})();
