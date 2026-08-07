// reportline/reports/static/reports/js/report_outline_sync.js
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

    function applyHeadingNumbers(headingNumbers) {
        if (!headingNumbers) {
            return;
        }
        Object.keys(headingNumbers).forEach(function (nodeId) {
            var number = headingNumbers[nodeId];
            var block = document.getElementById("report-block-" + nodeId);
            if (!block) {
                return;
            }
            var badge = block.querySelector("[data-heading-number]");
            if (badge) {
                badge.textContent = number ? number + "." : "";
            }
        });
    }

    function applyBodyNodeOrder(nodeIds) {
        var page = document.getElementById("report-editor-page");
        if (!page || !nodeIds || !nodeIds.length) {
            return;
        }
        var footer = document.getElementById("report-page-footer-root");
        var anchor = footer || null;
        nodeIds.forEach(function (nodeId) {
            var block = document.getElementById("report-block-" + nodeId);
            if (block && page.contains(block)) {
                page.insertBefore(block, anchor);
            }
        });
    }

    async function applyReorderPayload(data) {
        if (!data) {
            return;
        }
        if (data.body_node_ids) {
            applyBodyNodeOrder(data.body_node_ids);
        }
        if (data.outline_html) {
            var root = getOutlineRoot();
            if (root) {
                root.innerHTML = data.outline_html;
                mountOutlineInteractions(root);
            }
        }
        if (data.heading_numbers) {
            if (window.ReportLineReportConfig && window.ReportLineReportConfig.applyHeadingNumbers) {
                window.ReportLineReportConfig.applyHeadingNumbers(data.heading_numbers);
            } else {
                applyHeadingNumbers(data.heading_numbers);
            }
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
        applyHeadingNumbers(data.heading_numbers);
    }

    document.addEventListener("DOMContentLoaded", function () {
        var root = getOutlineRoot();
        if (root) {
            mountOutlineInteractions(root);
        }
    });

    window.ReportLineOutline = {
        refresh: refreshOutline,
        applyHeadingNumbers: applyHeadingNumbers,
        applyBodyNodeOrder: applyBodyNodeOrder,
        applyReorderPayload: applyReorderPayload,
    };
})();
