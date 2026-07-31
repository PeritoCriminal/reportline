/**
 * Sincronização assíncrona do sumário lateral com o documento em edição.
 */
(function () {
    "use strict";

    function getOutlineRoot() {
        return document.getElementById("report-editor-outline-root");
    }

    function mountOutlineInteractions(container) {
        if (window.ReportLineOutlineAccordion) {
            window.ReportLineOutlineAccordion.mount(container);
        }
        if (window.ReportLineOutlineDnD) {
            window.ReportLineOutlineDnD.mount(container);
        }
    }

    async function refreshOutline() {
        var cfg = window.REPORT_EDITOR_OUTLINE || {};
        var root = getOutlineRoot();
        if (!cfg.outlineUrl || !root) {
            return;
        }

        var response = await fetch(cfg.outlineUrl, {
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        });
        var data = await response.json().catch(function () {
            return {};
        });
        if (!response.ok || !data.html) {
            throw new Error("Falha ao atualizar sumário.");
        }

        root.innerHTML = data.html;
        mountOutlineInteractions(root);
    }

    document.addEventListener("DOMContentLoaded", function () {
        var root = getOutlineRoot();
        if (root) {
            mountOutlineInteractions(root);
        }
    });

    window.ReportLineOutline = {
        refresh: refreshOutline,
    };
})();
