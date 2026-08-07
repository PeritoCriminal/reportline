// reportline/reports/static/reports/js/report_outline_accordion.js
/**
 * Accordion do sumário lateral do editor de relatórios.
 *
 * Mantém títulos visíveis e colapsa subseções para reduzir poluição visual.
 */
(function () {
    "use strict";

    function setExpanded(button, body, expanded) {
        button.setAttribute("aria-expanded", expanded ? "true" : "false");
        body.hidden = !expanded;
        var expandLabel = button.getAttribute("data-report-outline-expand-label") || "";
        var collapseLabel = button.getAttribute("data-report-outline-collapse-label") || "";
        var label = expanded ? collapseLabel : expandLabel;
        if (label) {
            button.setAttribute("aria-label", label);
            button.setAttribute("title", label);
        }
    }

    function initAccordion(root) {
        var toggles = root.querySelectorAll("[data-report-outline-accordion-toggle='1']");
        toggles.forEach(function (button) {
            if (button.dataset.reportOutlineAccordionBound === "1") {
                return;
            }
            button.dataset.reportOutlineAccordionBound = "1";
            var item = button.closest(".report-editor-outline-item");
            if (!item) {
                return;
            }
            var body = item.querySelector("[data-report-outline-accordion-body='1']");
            if (!body) {
                return;
            }
            setExpanded(button, body, false);
            button.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                var expanded = button.getAttribute("aria-expanded") === "true";
                setExpanded(button, body, !expanded);
            });
        });
    }

    function mount(container) {
        container.querySelectorAll(".report-editor-outline").forEach(function (root) {
            initAccordion(root);
        });
    }

    window.ReportLineOutlineAccordion = { mount: mount };

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("#report-editor-outline-root").forEach(mount);
    });
})();
