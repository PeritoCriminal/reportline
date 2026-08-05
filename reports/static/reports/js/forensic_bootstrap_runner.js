/**
 * Montagem em background do laudo pericial no editor (Fase 3).
 *
 * Executa analyze, coleta prompts pendentes e monta blocos incrementalmente
 * na tela com efeito de escrita visível bloco a bloco.
 */
(function () {
    "use strict";

    const STATE_SHELL_CREATED = "shell_created";
    const STATE_ANALYZED = "analyzed";
    const STATE_COLLECTING_PROMPTS = "collecting_prompts";
    const STATE_BUILDING = "building";
    const ANALYZE_STATUS_MESSAGES = [
        "Lendo documentos com IA…",
        "Extraindo dados administrativos…",
        "Preparando montagem do laudo…",
    ];
    const ANALYZE_STATUS_ROTATE_MS = 2200;
    const TIMING_PROFILE_STORAGE_KEY = "reportline.forensic_bootstrap.timing_profile";
    const TIMING_PROFILE_COMPLETED_KEY = "reportline.forensic_bootstrap.completed_once";

    /**
     * Perfis de ritmo da montagem incremental.
     *
     * Intervalos [mínimo, máximo] em ms; cada pausa sorteia dentro do intervalo.
     * FIRST_RUN — onboarding (~1,5 s de montagem típica com 8 passos animados).
     * RETURNING — retorno experiente (streaming rápido, próximo ao instantâneo).
     */
    const TIMING_PROFILES = {
        FIRST_RUN: {
            TYPEWRITER_MS: [2, 4],
            /** Teto por bloco longo (ex.: preâmbulo); acelera caractere a caractere se ultrapassar. */
            TYPEWRITER_BLOCK_MAX_MS: 220,
            LIST_ITEM_MS: [12, 24],
            STEP_PAUSE_MS: [8, 18],
            MIN_STEP_MS: [40, 70],
            ANALYZE_CLOSE_MS: [40, 70],
            LIVE_BUILD_WARMUP_MS: [28, 48],
            BLOCK_PENDING_MS: [10, 20],
            BLOCK_REVEAL_MS: [12, 24],
            BLOCK_REVEAL_SHORT_MS: [8, 18],
            BLOCK_REVEAL_NO_EDIT_MS: [10, 20],
            LIST_TRANSITION_MS: [32, 55],
        },
        RETURNING: {
            TYPEWRITER_MS: [1, 2],
            LIST_ITEM_MS: [4, 16],
            STEP_PAUSE_MS: [6, 22],
            MIN_STEP_MS: [10, 40],
            ANALYZE_CLOSE_MS: [5, 20],
            LIVE_BUILD_WARMUP_MS: [5, 18],
            BLOCK_PENDING_MS: [2, 7],
            BLOCK_REVEAL_MS: [4, 14],
            BLOCK_REVEAL_SHORT_MS: [4, 15],
            BLOCK_REVEAL_NO_EDIT_MS: [5, 18],
            LIST_TRANSITION_MS: [3, 12],
        },
    };

    let timing = TIMING_PROFILES.RETURNING;
    let config = null;
    let shell = null;
    let progressPill = null;
    let progressPillText = null;
    let statusPanel = null;
    let statusText = null;
    let errorBox = null;
    let statusRotateTimer = null;
    let statusMessageIndex = 0;
    let isRunning = false;

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    function randomMs(min, max) {
        return min + Math.random() * (max - min);
    }

    function pickRandomMs([min, max]) {
        return randomMs(min, max);
    }

    async function sleepRandom(range) {
        await sleep(pickRandomMs(range));
    }

    function pickTypewriterCharDelay(plainTextLength) {
        const range = timing.TYPEWRITER_MS;
        const blockMax = timing.TYPEWRITER_BLOCK_MAX_MS;
        if (!plainTextLength || blockMax == null) {
            return pickRandomMs(range);
        }
        const idealAvg = (range[0] + range[1]) / 2;
        if (plainTextLength * idealAvg <= blockMax) {
            return pickRandomMs(range);
        }
        const scaled = blockMax / plainTextLength;
        const variance = scaled * 0.12;
        return randomMs(Math.max(0.5, scaled - variance), scaled + variance);
    }

    function isKnownTimingProfile(name) {
        return Boolean(name && Object.prototype.hasOwnProperty.call(TIMING_PROFILES, name));
    }

    function readStoredTimingProfile() {
        try {
            const stored = window.localStorage.getItem(TIMING_PROFILE_STORAGE_KEY);
            return isKnownTimingProfile(stored) ? stored : null;
        } catch (_error) {
            return null;
        }
    }

    function hasCompletedBootstrapBefore() {
        try {
            return window.localStorage.getItem(TIMING_PROFILE_COMPLETED_KEY) === "1";
        } catch (_error) {
            return false;
        }
    }

    function resolveTimingProfile(options) {
        if (options && isKnownTimingProfile(options.timingProfile)) {
            return options.timingProfile;
        }
        const stored = readStoredTimingProfile();
        if (stored) {
            return stored;
        }
        return hasCompletedBootstrapBefore() ? "RETURNING" : "FIRST_RUN";
    }

    function applyTimingProfile(profileName) {
        timing = TIMING_PROFILES[profileName] || TIMING_PROFILES.RETURNING;
    }

    function persistTimingProfile(profileName) {
        if (!isKnownTimingProfile(profileName)) {
            return;
        }
        try {
            window.localStorage.setItem(TIMING_PROFILE_STORAGE_KEY, profileName);
        } catch (_error) {
            /* ignore quota / private mode */
        }
    }

    function markBootstrapCompletedOnce() {
        try {
            window.localStorage.setItem(TIMING_PROFILE_COMPLETED_KEY, "1");
        } catch (_error) {
            /* ignore */
        }
    }

    function setTimingProfile(profileName, persist) {
        if (!isKnownTimingProfile(profileName)) {
            throw new Error(`Perfil de animação desconhecido: ${profileName}`);
        }
        applyTimingProfile(profileName);
        if (persist !== false) {
            persistTimingProfile(profileName);
        }
    }

    function setStatusMessage(message, stepIndex, totalSteps) {
        let label = message || "";
        if (stepIndex && totalSteps) {
            label = `${stepIndex}/${totalSteps} · ${label}`;
        }
        if (statusText) {
            statusText.classList.add("is-changing");
            window.setTimeout(() => {
                statusText.textContent = label;
                statusText.classList.remove("is-changing");
            }, 5);
        }
        if (progressPillText) {
            progressPillText.textContent = label;
        }
    }

    function startAnalyzeStatusRotation() {
        statusMessageIndex = 0;
        setStatusMessage(ANALYZE_STATUS_MESSAGES[0]);
        if (statusPanel) {
            statusPanel.hidden = false;
        }
        statusRotateTimer = window.setInterval(() => {
            statusMessageIndex = (statusMessageIndex + 1) % ANALYZE_STATUS_MESSAGES.length;
            setStatusMessage(ANALYZE_STATUS_MESSAGES[statusMessageIndex]);
        }, ANALYZE_STATUS_ROTATE_MS);
    }

    function stopAnalyzeStatusRotation() {
        if (statusRotateTimer !== null) {
            window.clearInterval(statusRotateTimer);
            statusRotateTimer = null;
        }
    }

    function showError(message) {
        if (!errorBox) {
            return;
        }
        errorBox.textContent = message;
        errorBox.hidden = !message;
        if (shell) {
            shell.hidden = false;
        }
        document.body.classList.remove("forensic-bootstrap-live-build");
        document.body.classList.add("forensic-bootstrap-build-active");
    }

    function showAnalyzeOverlay() {
        if (shell) {
            shell.hidden = false;
        }
        if (progressPill) {
            progressPill.hidden = true;
        }
        document.body.classList.remove("forensic-bootstrap-live-build");
        document.body.classList.add("forensic-bootstrap-build-active");
        startAnalyzeStatusRotation();
    }

    function showLiveBuildMode(firstMessage) {
        stopAnalyzeStatusRotation();
        if (shell) {
            shell.hidden = true;
        }
        if (progressPill) {
            progressPill.hidden = false;
        }
        document.body.classList.remove("forensic-bootstrap-build-active");
        document.body.classList.add("forensic-bootstrap-live-build");
        setStatusMessage(firstMessage || "Montando laudo…");
    }

    function hideBuildUi() {
        stopAnalyzeStatusRotation();
        if (shell) {
            shell.hidden = true;
        }
        if (progressPill) {
            progressPill.hidden = true;
        }
        document.body.classList.remove("forensic-bootstrap-build-active");
        document.body.classList.remove("forensic-bootstrap-live-build");
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

    function buildAnalyzeFormData(files) {
        const formData = new FormData();
        Array.from(files || []).forEach((file) => {
            formData.append("documents", file);
        });
        return formData;
    }

    async function runAnalyze(files) {
        if (!config.analyzeUrl) {
            throw new Error("Análise indisponível nesta tela.");
        }
        return postJson(config.analyzeUrl, {
            method: "POST",
            headers: { "X-CSRFToken": getCsrfToken() },
            body: buildAnalyzeFormData(files),
        });
    }

    function getBodyInsertAnchor() {
        const page = document.getElementById("report-editor-page");
        const footer = document.getElementById("report-page-footer-root");
        if (!page) {
            return null;
        }
        return { page, footer };
    }

    function removeEmptyBodyPlaceholder() {
        const placeholder = document.querySelector(".report-editor-page-empty");
        if (placeholder) {
            placeholder.remove();
        }
    }

    async function closeAnalyzeOverlay() {
        stopAnalyzeStatusRotation();
        if (shell) {
            shell.classList.add("is-closing");
        }
        await sleepRandom(timing.ANALYZE_CLOSE_MS);
        if (shell) {
            shell.hidden = true;
            shell.classList.remove("is-closing");
        }
        document.body.classList.remove("forensic-bootstrap-build-active");
    }

    async function transitionToLiveBuild(firstMessage) {
        await closeAnalyzeOverlay();
        showLiveBuildMode(firstMessage);
        const canvas = document.querySelector(".report-editor-canvas");
        if (canvas) {
            canvas.scrollTo({ top: 0, behavior: "smooth" });
        }
        await sleepRandom(timing.LIVE_BUILD_WARMUP_MS);
    }

    function insertBlockHtml(html) {
        const anchor = getBodyInsertAnchor();
        if (!anchor || !html) {
            return null;
        }
        removeEmptyBodyPlaceholder();

        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const blockElement = template.content.firstElementChild;
        if (!blockElement) {
            return null;
        }

        if (anchor.footer) {
            anchor.footer.before(blockElement);
        } else {
            anchor.page.appendChild(blockElement);
        }
        return blockElement;
    }

    function scrollBlockIntoView(blockElement) {
        const canvas = document.querySelector(".report-editor-canvas");
        if (!canvas || !blockElement) {
            return;
        }
        blockElement.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    async function typewriterEditable(editable, targetHtml, plainText) {
        editable.innerHTML = "";
        editable.classList.add("forensic-bootstrap-typewriter-active");
        for (let index = 0; index < plainText.length; index += 1) {
            editable.textContent = plainText.slice(0, index + 1);
            await sleep(pickTypewriterCharDelay(plainText.length));
        }
        editable.innerHTML = targetHtml;
        editable.classList.remove("forensic-bootstrap-typewriter-active");
    }

    async function animateListBlock(blockElement) {
        const items = Array.from(blockElement.querySelectorAll(".report-editor-list-item"));
        items.forEach((item) => {
            item.style.opacity = "0";
            item.style.transform = "translateY(0.25rem)";
        });
        blockElement.classList.add("forensic-bootstrap-block-reveal");
        for (const item of items) {
            const transitionMs = Math.round(pickRandomMs(timing.LIST_TRANSITION_MS));
            item.style.transition = `opacity ${transitionMs}ms ease, transform ${transitionMs}ms ease`;
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
            await sleepRandom(timing.LIST_ITEM_MS);
        }
    }

    async function animateBlockAppearance(blockElement, animated) {
        if (!blockElement) {
            return;
        }

        if (animated === false) {
            blockElement.classList.add("forensic-bootstrap-block-reveal");
            return;
        }

        const editable = blockElement.querySelector(".report-editor-block-editable");
        const blockType = blockElement.dataset.blockType || "";
        let targetHtml = "";
        let plainText = "";

        blockElement.classList.add("forensic-bootstrap-block-pending");
        if (editable) {
            targetHtml = editable.innerHTML;
            plainText = (editable.textContent || "").trim();
            editable.innerHTML = "";
        }

        scrollBlockIntoView(blockElement);
        await sleepRandom(timing.BLOCK_PENDING_MS);
        blockElement.classList.remove("forensic-bootstrap-block-pending");
        blockElement.classList.add("forensic-bootstrap-block-writing");

        if (blockType === "unordered_list" || blockType === "ordered_list") {
            if (editable) {
                editable.innerHTML = targetHtml;
            }
            await animateListBlock(blockElement);
            blockElement.classList.remove("forensic-bootstrap-block-writing");
            return;
        }

        if (!editable) {
            blockElement.classList.add("forensic-bootstrap-block-reveal");
            await sleepRandom(timing.BLOCK_REVEAL_NO_EDIT_MS);
            blockElement.classList.remove("forensic-bootstrap-block-reveal", "forensic-bootstrap-block-writing");
            return;
        }

        if (!plainText) {
            blockElement.classList.add("forensic-bootstrap-block-reveal");
            await sleepRandom(timing.BLOCK_REVEAL_SHORT_MS);
            blockElement.classList.remove("forensic-bootstrap-block-reveal", "forensic-bootstrap-block-writing");
            return;
        }

        await typewriterEditable(editable, targetHtml, plainText);
        blockElement.classList.remove("forensic-bootstrap-block-writing");
        blockElement.classList.add("forensic-bootstrap-block-reveal");
        await sleepRandom(timing.BLOCK_REVEAL_MS);
        blockElement.classList.remove("forensic-bootstrap-block-reveal");
    }

    async function enforceMinStepDuration(stepStartedAt) {
        const targetMs = pickRandomMs(timing.MIN_STEP_MS);
        const elapsed = Date.now() - stepStartedAt;
        if (elapsed < targetMs) {
            await sleep(targetMs - elapsed);
        }
    }

    function applyOutlinePayload(payload) {
        if (!payload || !window.ReportLineOutline) {
            return;
        }
        window.ReportLineOutline.applyReorderPayload({
            outline_html: payload.outline_html,
            heading_numbers: payload.heading_numbers,
        });
    }

    function updateHeaderReportNumber(text) {
        const headerNumberCell = document.querySelector(
            '[data-report-page-header-extra-text][data-extra-row-index="1"]'
        );
        if (headerNumberCell && text) {
            headerNumberCell.textContent = text;
        }
    }

    function updateReportTitle(title) {
        if (!title) {
            return;
        }
        document.title = document.title.replace(/^Editar relatório — .+? —/, `Editar relatório — ${title} —`);
    }

    async function runBuildStep() {
        if (!config.buildStepUrl) {
            throw new Error("Montagem incremental indisponível nesta tela.");
        }
        return postJson(config.buildStepUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
                "Content-Type": "application/json",
            },
            body: "{}",
        });
    }

    async function runIncrementalBuild(alreadyLive) {
        if (!alreadyLive) {
            await transitionToLiveBuild("Montando estrutura do laudo…");
        }

        let done = false;
        while (!done) {
            const stepStartedAt = Date.now();
            const payload = await runBuildStep();
            const stepIndex = payload.step_index || 0;
            const totalSteps = payload.total_steps || 0;
            if (payload.step_label) {
                setStatusMessage(payload.step_label, stepIndex, totalSteps);
            }

            const blocksHtml = Array.isArray(payload.blocks_html) ? payload.blocks_html : [];
            const animated = payload.animated !== false;
            for (const html of blocksHtml) {
                const blockElement = insertBlockHtml(html);
                await animateBlockAppearance(blockElement, animated);
                if (animated) {
                    await sleepRandom(timing.STEP_PAUSE_MS);
                }
            }

            applyOutlinePayload(payload);
            if (payload.header_report_number_text) {
                updateHeaderReportNumber(payload.header_report_number_text);
            }
            if (payload.report_title) {
                updateReportTitle(payload.report_title);
            }

            done = Boolean(payload.done);
            config.state = payload.state || config.state;
            if (animated) {
                await enforceMinStepDuration(stepStartedAt);
            }
        }
    }

    function buildPromptFlowConfig(promptConfig) {
        return Object.assign({}, config, promptConfig, {
            state: STATE_COLLECTING_PROMPTS,
        });
    }

    async function runPromptCollection(promptConfig) {
        if (!window.ReportLineForensicBootstrap?.runPromptFlow) {
            throw new Error("Coleta de dados indisponível nesta tela.");
        }
        await closeAnalyzeOverlay();
        await window.ReportLineForensicBootstrap.runPromptFlow(buildPromptFlowConfig(promptConfig));
        config.state = STATE_ANALYZED;
    }

    async function runBootstrapPipeline() {
        if (isRunning) {
            return;
        }
        isRunning = true;
        showAnalyzeOverlay();
        showError("");

        try {
            if (config.state === STATE_SHELL_CREATED) {
                const docStore = window.ReportLineForensicBootstrapDocuments;
                if (!docStore || !docStore.takePendingDocuments) {
                    throw new Error("Documentos do intake não encontrados. Volte ao intake e tente novamente.");
                }
                const files = await docStore.takePendingDocuments(config.reportId);
                if (!files.length) {
                    throw new Error("Documentos do intake não encontrados. Volte ao intake e tente novamente.");
                }
                const analyzePayload = await runAnalyze(files);
                config.state = analyzePayload.state || STATE_ANALYZED;
                if (analyzePayload.prompt_config) {
                    await runPromptCollection(analyzePayload.prompt_config);
                }
            }

            if (config.state === STATE_COLLECTING_PROMPTS) {
                await runPromptCollection({
                    finalizeUrl: config.finalizeUrl,
                    metadata: config.metadata,
                    pendingPrompts: config.pendingPrompts,
                });
            }

            if (config.state === STATE_ANALYZED || config.state === STATE_BUILDING) {
                const alreadyLive = config.state === STATE_BUILDING;
                if (alreadyLive) {
                    showLiveBuildMode("Retomando montagem do laudo…");
                }
                await runIncrementalBuild(alreadyLive);
            }

            hideBuildUi();
            markBootstrapCompletedOnce();
            if (!readStoredTimingProfile()) {
                persistTimingProfile("RETURNING");
            }
            isRunning = false;
        } catch (error) {
            showError(error.message || "Falha ao preparar o laudo.");
            isRunning = false;
        }
    }

    function init(options) {
        config = options || {};
        applyTimingProfile(resolveTimingProfile(config));
        shell = document.getElementById("forensic-bootstrap-build-shell");
        progressPill = document.getElementById("forensic-bootstrap-build-progress-pill");
        progressPillText = document.getElementById("forensic-bootstrap-build-progress-text");
        statusPanel = document.getElementById("forensic-bootstrap-build-status");
        statusText = document.getElementById("forensic-bootstrap-build-status-text");
        errorBox = document.getElementById("forensic-bootstrap-build-error");

        if (!config.state) {
            return;
        }

        if (
            config.state === STATE_SHELL_CREATED ||
            config.state === STATE_COLLECTING_PROMPTS ||
            config.state === STATE_ANALYZED ||
            config.state === STATE_BUILDING
        ) {
            runBootstrapPipeline().catch(console.error);
        }
    }

    window.ReportLineForensicBootstrapRunner = {
        init,
        TIMING_PROFILES,
        setTimingProfile,
        getTimingProfile() {
            return readStoredTimingProfile() || resolveTimingProfile(config);
        },
    };
})();
