/**
 * Pilha de undo/redo do editor de laudos (fases 1–4).
 */
(function () {
    "use strict";

    const MAX_STACK_SIZE = 100;
    const MERGE_MS = 2000;

    let undoStack = [];
    let redoStack = [];
    let applying = false;
    let undoButton = null;
    let redoButton = null;
    let pageElement = null;

    function isMacPlatform() {
        return /Mac|iPhone|iPad|iPod/.test(navigator.platform || "");
    }

    function updateToolbarState() {
        if (undoButton) {
            undoButton.disabled = applying || undoStack.length === 0;
        }
        if (redoButton) {
            redoButton.disabled = applying || redoStack.length === 0;
        }
    }

    function trimStack(stack) {
        while (stack.length > MAX_STACK_SIZE) {
            stack.shift();
        }
    }

    function pushCommand(command) {
        if (applying || !command) {
            return;
        }

        if (command.mergeKey && undoStack.length > 0) {
            const previous = undoStack[undoStack.length - 1];
            if (
                previous.mergeKey === command.mergeKey
                && Date.now() - previous.timestamp < MERGE_MS
            ) {
                previous.redo = command.redo;
                previous.timestamp = Date.now();
                redoStack = [];
                updateToolbarState();
                return;
            }
        }

        undoStack.push({
            label: command.label || "",
            mergeKey: command.mergeKey || "",
            undo: command.undo,
            redo: command.redo,
            timestamp: Date.now(),
        });
        trimStack(undoStack);
        redoStack = [];
        updateToolbarState();
    }

    async function undo() {
        if (applying) {
            return;
        }

        if (window.ReportLineEditor && window.ReportLineEditor.flushUndoState) {
            await window.ReportLineEditor.flushUndoState();
        }

        if (undoStack.length === 0) {
            updateToolbarState();
            return;
        }

        const entry = undoStack.pop();
        applying = true;
        try {
            await entry.undo();
            redoStack.push(entry);
            trimStack(redoStack);
        } catch (error) {
            undoStack.push(entry);
            console.error(error);
        } finally {
            applying = false;
            updateToolbarState();
        }
    }

    async function redo() {
        if (applying) {
            return;
        }

        if (window.ReportLineEditor && window.ReportLineEditor.flushUndoState) {
            await window.ReportLineEditor.flushUndoState();
        }

        if (redoStack.length === 0) {
            updateToolbarState();
            return;
        }

        const entry = redoStack.pop();
        applying = true;
        try {
            await entry.redo();
            undoStack.push(entry);
            trimStack(undoStack);
        } catch (error) {
            redoStack.push(entry);
            console.error(error);
        } finally {
            applying = false;
            updateToolbarState();
        }
    }

    function bindShortcuts() {
        document.addEventListener("keydown", (event) => {
            if (!pageElement || !pageElement.isConnected) {
                return;
            }

            const modifier = isMacPlatform() ? event.metaKey : event.ctrlKey;
            if (!modifier || event.altKey) {
                return;
            }

            const key = event.key.toLowerCase();
            if (key === "z" && !event.shiftKey) {
                event.preventDefault();
                undo().catch(console.error);
                return;
            }

            if (key === "y" || (key === "z" && event.shiftKey)) {
                event.preventDefault();
                redo().catch(console.error);
            }
        });
    }

    function bindToolbar() {
        if (undoButton) {
            undoButton.addEventListener("click", (event) => {
                event.preventDefault();
                undo().catch(console.error);
            });
        }
        if (redoButton) {
            redoButton.addEventListener("click", (event) => {
                event.preventDefault();
                redo().catch(console.error);
            });
        }
    }

    function init(options) {
        pageElement = document.getElementById("report-editor-page");
        undoButton = document.querySelector("[data-report-undo]");
        redoButton = document.querySelector("[data-report-redo]");
        bindToolbar();
        bindShortcuts();
        updateToolbarState();
    }

    function recordBlockContentChange(payload) {
        pushCommand({
            label: payload.label || "Editar bloco",
            mergeKey: payload.mergeKey !== undefined
                ? payload.mergeKey
                : `content-${payload.nodeId}`,
            undo: payload.undo,
            redo: payload.redo,
        });
    }

    function recordCommand(payload) {
        pushCommand({
            label: payload.label || "",
            mergeKey: payload.mergeKey !== undefined ? payload.mergeKey : "",
            undo: payload.undo,
            redo: payload.redo,
        });
    }

    function recordBlockInsert(payload) {
        pushCommand({
            label: "Inserir bloco",
            mergeKey: "",
            undo: payload.undo,
            redo: payload.redo,
        });
    }

    function recordBlockDelete(payload) {
        pushCommand({
            label: "Excluir bloco",
            mergeKey: "",
            undo: payload.undo,
            redo: payload.redo,
        });
    }

    window.ReportLineUndo = {
        init,
        isApplying: () => applying,
        undo,
        redo,
        recordBlockContentChange,
        recordCommand,
        recordBlockInsert,
        recordBlockDelete,
        updateToolbarState,
    };
})();
