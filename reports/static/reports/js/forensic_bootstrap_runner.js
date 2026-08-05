/**
 * Montagem em background do laudo pericial no editor (Fase 3).
 */
(function () {
    "use strict";

    const STATE_SHELL_CREATED = "shell_created";
    const STATE_ANALYZED = "analyzed";
    const STATE_BUILDING = "building";
    const STATE_PROMPTING = "prompting";
    const STATE_READY = "ready";
    const REVEAL_STORAGE_KEY = "forensicBootstrapReveal";
    const STATUS_MESSAGES = [
        "Lendo documentos com IA…",
        "Extraindo dados administrativos…",
        "Montando estrutura do laudo…",
    ];
    const STATUS_ROTATE_MS = 2200;
    const BLOCK_REVEAL_MS = 110;

    let config = null;
    let shell = null;
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

    function setOverlayActive(isActive) {
        document.body.classList.toggle("forensic-bootstrap-build-active", isActive);
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
        setStatusMessage(STATUS_MESSAGES[0]);
        if (statusPanel) {
            statusPanel.hidden = false;
        }
        statusRotateTimer = window.setInterval(() => {
            statusMessageIndex = (statusMessageIndex + 1) % STATUS_MESSAGES.length;
            setStatusMessage(STATUS_MESSAGES[statusMessageIndex]);
        }, STATUS_ROTATE_MS);
    }

    function stopStatusRotation() {
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
    }

    function showBuildOverlay() {
        if (shell) {
            shell.hidden = false;
        }
        setOverlayActive(true);
        startStatusRotation();
    }

    function hideBuildOverlay() {
        stopStatusRotation();
        if (shell) {
            shell.hidden = true;
        }
        setOverlayActive(false);
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

    function markRevealOnReload() {
        if (!config || !config.reportId) {
            return;
        }
        try {
            sessionStorage.setItem(REVEAL_STORAGE_KEY, String(config.reportId));
        } catch (_error) {
            /* ignore quota errors */
        }
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

    async function runBuild() {
        if (!config.buildUrl) {
            throw new Error("Montagem indisponível nesta tela.");
        }
        return postJson(config.buildUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
                "Content-Type": "application/json",
            },
            body: "{}",
        });
    }

    async function pollUntilBuilt() {
        if (!config.statusUrl) {
            return;
        }
        for (let attempt = 0; attempt < 120; attempt += 1) {
            const response = await fetch(config.statusUrl, { credentials: "same-origin" });
            if (!response.ok) {
                await new Promise((resolve) => window.setTimeout(resolve, 1000));
                continue;
            }
            const payload = await response.json();
            if (payload.state === STATE_BUILDING) {
                await new Promise((resolve) => window.setTimeout(resolve, 1000));
                continue;
            }
            if (payload.state === STATE_PROMPTING || payload.state === STATE_READY) {
                return payload;
            }
            throw new Error("Montagem interrompida. Recarregue a página.");
        }
        throw new Error("A montagem está demorando mais que o esperado.");
    }

    async function runBootstrapPipeline() {
        if (isRunning) {
            return;
        }
        isRunning = true;
        showBuildOverlay();
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
                const warnings = Array.isArray(analyzePayload.warnings) ? analyzePayload.warnings : [];
                warnings.forEach((warning) => console.warn(warning));
            } else if (config.state !== STATE_ANALYZED) {
                if (config.state === STATE_BUILDING) {
                    await pollUntilBuilt();
                    markRevealOnReload();
                    window.location.reload();
                    return;
                }
                return;
            }

            setStatusMessage("Montando estrutura do laudo…");
            await runBuild();
            markRevealOnReload();
            window.location.reload();
        } catch (error) {
            showError(error.message || "Falha ao preparar o laudo.");
            isRunning = false;
        }
    }

    function revealBuiltBlocks(reportId) {
        let storedId = "";
        try {
            storedId = sessionStorage.getItem(REVEAL_STORAGE_KEY) || "";
        } catch (_error) {
            storedId = "";
        }
        if (!storedId || storedId !== String(reportId)) {
            return;
        }
        try {
            sessionStorage.removeItem(REVEAL_STORAGE_KEY);
        } catch (_error) {
            /* ignore */
        }

        const blocks = Array.from(document.querySelectorAll(".report-editor-block"));
        if (!blocks.length) {
            return;
        }

        document.body.classList.add("forensic-bootstrap-reveal-active");
        blocks.forEach((block, index) => {
            block.classList.add("forensic-bootstrap-block-pending");
            window.setTimeout(() => {
                block.classList.remove("forensic-bootstrap-block-pending");
                block.classList.add("forensic-bootstrap-block-reveal");
            }, index * BLOCK_REVEAL_MS);
        });

        const totalMs = blocks.length * BLOCK_REVEAL_MS + 400;
        window.setTimeout(() => {
            document.body.classList.remove("forensic-bootstrap-reveal-active");
            blocks.forEach((block) => block.classList.remove("forensic-bootstrap-block-reveal"));
        }, totalMs);
    }

    function init(options) {
        config = options || {};
        shell = document.getElementById("forensic-bootstrap-build-shell");
        statusPanel = document.getElementById("forensic-bootstrap-build-status");
        statusText = document.getElementById("forensic-bootstrap-build-status-text");
        errorBox = document.getElementById("forensic-bootstrap-build-error");

        revealBuiltBlocks(config.reportId);

        if (!config.state) {
            return;
        }

        if (
            config.state === STATE_SHELL_CREATED ||
            config.state === STATE_ANALYZED ||
            config.state === STATE_BUILDING
        ) {
            runBootstrapPipeline().catch(console.error);
        }
    }

    window.ReportLineForensicBootstrapRunner = { init };
})();
