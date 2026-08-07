// reportline/reports/static/reports/js/forensic_bootstrap_prompts.js
/**
 * Prompts inline do bootstrap pericial no editor de laudos.
 *
 * Acumula respostas localmente e persiste em lote ao concluir a fila.
 * Usado antes da montagem visual do corpo (collecting_prompts), após
 * montagem legada (prompting) ou na continuação de exame de local.
 */
(function () {
    "use strict";

    const STATE_COLLECTING_PROMPTS = "collecting_prompts";
    const STATE_PROMPTING = "prompting";
    const STATE_COLLECTING_SCENE_CONTINUATION = "collecting_scene_continuation";
    const UPPERCASE_TEXT_FIELDS = new Set([
        "report_number",
        "occurrence_report",
        "police_inquiry",
        "attendance_protocol",
    ]);
    const INFORMANT_BRIEFING_DESCRIPTOR = {
        field: "informant_briefing",
        label: "Informes prestados",
        input_type: "textarea",
        help_text: "Resuma objetivamente os esclarecimentos recebidos, sem narrar dinâmica dos fatos.",
        placeholder: "Ex.: informou ter constatado o imóvel fechado ao retornar da viagem.",
    };

    let config = null;
    let shell = null;
    let form = null;
    let input = null;
    let select = null;
    let textarea = null;
    let label = null;
    let help = null;
    let title = null;
    let progress = null;
    let errorBox = null;
    let skipButton = null;
    let submitButton = null;

    let promptQueue = [];
    let queueIndex = 0;
    let localData = {};
    let localAnswers = {};
    let localSkipped = [];
    let currentPrompt = null;
    let isFinalizing = false;
    let flowResolve = null;
    let flowReject = null;
    let listenersBound = false;
    let activeControl = null;

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
        select = document.getElementById("forensic-bootstrap-prompt-select");
        textarea = document.getElementById("forensic-bootstrap-prompt-textarea");
        label = document.getElementById("forensic-bootstrap-prompt-label");
        help = document.getElementById("forensic-bootstrap-prompt-help");
        title = document.getElementById("forensic-bootstrap-prompt-title");
        progress = document.getElementById("forensic-bootstrap-prompt-progress");
        errorBox = document.getElementById("forensic-bootstrap-prompt-error");
        skipButton = document.getElementById("forensic-bootstrap-prompt-skip");
        submitButton = document.getElementById("forensic-bootstrap-prompt-submit");
    }

    function hideAllControls() {
        [input, select, textarea].forEach((control) => {
            if (!control) {
                return;
            }
            control.classList.add("d-none");
            control.classList.remove("is-invalid");
            control.disabled = false;
        });
    }

    function showError(message) {
        if (!errorBox) {
            return;
        }
        if (message) {
            errorBox.textContent = message;
            errorBox.hidden = false;
            if (activeControl) {
                activeControl.classList.add("is-invalid");
            }
            return;
        }
        errorBox.textContent = "";
        errorBox.hidden = true;
        if (activeControl) {
            activeControl.classList.remove("is-invalid");
        }
    }

    function setBusy(isBusy) {
        if (skipButton) {
            skipButton.disabled = isBusy;
        }
        if (submitButton) {
            submitButton.disabled = isBusy;
        }
        [input, select, textarea].forEach((control) => {
            if (control) {
                control.disabled = isBusy;
            }
        });
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

    function personalizeAttendancePrompt(prompt) {
        const descriptor = Object.assign({}, prompt);
        if (descriptor.field === "informant_provided_info" && localData.access_granted_by) {
            descriptor.label = `${localData.access_granted_by} prestou informes?`;
            descriptor.help_text =
                `Indique se ${localData.access_granted_by} prestou esclarecimentos sobre o atendimento.`;
        }
        if (descriptor.field === "informant_briefing" && localData.access_granted_by) {
            descriptor.label = `Informes prestados por ${localData.access_granted_by}`;
        }
        return descriptor;
    }

    function populateSelectChoices(choices, selectedValue) {
        if (!select) {
            return;
        }
        select.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Selecione…";
        select.appendChild(placeholder);
        (choices || []).forEach((choice) => {
            const option = document.createElement("option");
            option.value = choice.value;
            option.textContent = choice.label;
            select.appendChild(option);
        });
        select.value = selectedValue || "";
    }

    function activateControl(prompt) {
        hideAllControls();
        const existingValue = (localData[prompt.field] || "").trim();
        const inputType = prompt.input_type || "text";

        if (inputType === "select") {
            activeControl = select;
            populateSelectChoices(prompt.choices, existingValue || prompt.default_value || "");
            if (label) {
                label.setAttribute("for", "forensic-bootstrap-prompt-select");
            }
            select.classList.remove("d-none");
            select.focus();
            return;
        }

        if (inputType === "textarea") {
            activeControl = textarea;
            textarea.value = existingValue || prompt.default_value || "";
            textarea.placeholder = prompt.placeholder || "";
            if (label) {
                label.setAttribute("for", "forensic-bootstrap-prompt-textarea");
            }
            textarea.classList.remove("d-none");
            textarea.focus();
            return;
        }

        activeControl = input;
        input.type = inputType;
        input.value = existingValue || prompt.default_value || "";
        input.placeholder = prompt.placeholder || "";
        if (label) {
            label.setAttribute("for", "forensic-bootstrap-prompt-input");
        }
        input.classList.remove("d-none");
        input.focus();
        if (input.type === "date" || input.type === "datetime-local") {
            try {
                input.setSelectionRange(0, 0);
            } catch (_error) {
                /* inputs nativos de data/hora não suportam seleção programática */
            }
        }
    }

    function applyPromptDescriptor(prompt) {
        currentPrompt = prompt ? personalizeAttendancePrompt(prompt) : null;
        if (!currentPrompt) {
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
            title.textContent = config.flowTitle || "Complementar dados do laudo";
        }
        if (label) {
            label.textContent = currentPrompt.label || "Campo";
        }
        if (help) {
            help.textContent = currentPrompt.help_text || "";
        }
        activateControl(currentPrompt);
        showError("");
        updateProgress();
        setBusy(false);
        document.body.classList.add("forensic-bootstrap-prompt-active");
    }

    function maybeInjectInformantBriefingPrompt() {
        if (localData.informant_provided_info !== "yes") {
            return;
        }
        const alreadyQueued = promptQueue.some((item) => item.field === "informant_briefing");
        const alreadyAnswered = Boolean(localAnswers.informant_briefing);
        const skipped = localSkipped.includes("informant_briefing");
        if (alreadyQueued || alreadyAnswered || skipped) {
            return;
        }
        promptQueue.splice(queueIndex + 1, 0, Object.assign({}, INFORMANT_BRIEFING_DESCRIPTOR));
    }

    function maybeRemoveInformantBriefingPrompt() {
        if (localData.informant_provided_info === "yes") {
            return;
        }
        promptQueue = promptQueue.filter((item, index) => {
            if (item.field !== "informant_briefing") {
                return true;
            }
            return index <= queueIndex;
        });
        delete localAnswers.informant_briefing;
        localData.informant_briefing = "";
    }

    function advanceQueue() {
        if (currentPrompt?.field === "informant_provided_info") {
            if (localData.informant_provided_info === "yes") {
                maybeInjectInformantBriefingPrompt();
            } else {
                maybeRemoveInformantBriefingPrompt();
            }
        }

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
            title.textContent = "Salvando dados…";
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
                title.textContent = config.flowTitle || "Complementar dados do laudo";
            }
            updateProgress();
            showError(error.message || "Falha ao concluir.");
            setBusy(false);
            failFlow(error);
        }
    }

    function readActiveValue() {
        if (!activeControl) {
            return "";
        }
        return (activeControl.value || "").trim();
    }

    function handleSubmit(event) {
        event.preventDefault();
        if (!activeControl || !currentPrompt || isFinalizing) {
            return;
        }

        const rawValue = readActiveValue();
        if (!rawValue) {
            showError("Informe um valor ou use Pular.");
            return;
        }

        setBusy(true);
        const fieldName = currentPrompt.field;
        localAnswers[fieldName] = rawValue;
        localData[fieldName] = normalizeTextField(fieldName, rawValue);
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

    function resolveAllowedStates(options) {
        if (Array.isArray(options.allowedStates) && options.allowedStates.length) {
            return new Set(options.allowedStates);
        }
        return new Set([STATE_COLLECTING_PROMPTS, STATE_PROMPTING]);
    }

    function startPromptFlow(options) {
        config = options || {};
        bindDom();
        bindListeners();

        const allowedStates = resolveAllowedStates(config);
        if (!shell || !form || !allowedStates.has(config.state)) {
            throw new Error("Prompts indisponíveis nesta etapa.");
        }

        promptQueue = Array.isArray(config.pendingPrompts) ? config.pendingPrompts.slice() : [];
        localData = Object.assign({}, config.localData || config.metadata || config.attendanceContext || {});
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

    function runAttendanceContextPromptFlow(options) {
        const merged = Object.assign({}, options || {}, {
            state: STATE_COLLECTING_SCENE_CONTINUATION,
            allowedStates: [STATE_COLLECTING_SCENE_CONTINUATION],
            flowTitle: "Contexto de atendimento",
            finalizeUrl: options?.attendanceContextFinalizeUrl || options?.finalizeUrl,
            pendingPrompts: options?.pendingAttendanceContextPrompts || options?.pendingPrompts || [],
            localData: options?.attendanceContext || {},
        });
        return runPromptFlow(merged);
    }

    function init(options) {
        const result = startPromptFlow(options);
        if (result) {
            result.catch(console.error);
        }
    }

    window.ReportLineForensicBootstrap = {
        init,
        runPromptFlow,
        runAttendanceContextPromptFlow,
    };
})();
