/**
 * Restauração de cabeçalho e rodapé institucionais em laudos periciais.
 */
(function () {
    "use strict";

    let updateUrl = "";
    let isForensicReport = false;

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

    function closeParentModal(trigger) {
        const modalElement = trigger && trigger.closest(".modal");
        if (modalElement && window.bootstrap) {
            bootstrap.Modal.getOrCreateInstance(modalElement).hide();
        }
    }

    function closeParagraphOptionsMenu() {
        const toggle = document.querySelector("[data-report-paragraph-options-toggle]");
        if (!toggle || !window.bootstrap) {
            return;
        }
        bootstrap.Dropdown.getOrCreateInstance(toggle).hide();
    }

    function applyLayoutResponse(data, section) {
        if (
            (section === "header" || section === "both")
            && window.ReportLinePageHeader
            && window.ReportLinePageHeader.replaceLayoutHtml
        ) {
            window.ReportLinePageHeader.replaceLayoutHtml(
                data.header_html || data.html,
                { preserveEditing: false }
            );
        }
        if (
            (section === "footer" || section === "both")
            && window.ReportLinePageFooter
            && window.ReportLinePageFooter.replaceLayoutHtml
        ) {
            window.ReportLinePageFooter.replaceLayoutHtml(
                data.footer_html || data.html,
                { preserveEditing: false }
            );
        }
    }

    async function restoreInstitutionalLayout(section) {
        if (!updateUrl || !isForensicReport) {
            return;
        }

        const successMessages = {
            header: "Cabeçalho institucional restaurado.",
            footer: "Rodapé institucional restaurado.",
            both: "Cabeçalho e rodapé institucionais restaurados.",
        };
        const successMessage = successMessages[section] || successMessages.both;

        const response = await fetch(updateUrl, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
            body: JSON.stringify({
                restore_institutional: true,
                restore_section: section,
            }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = (data.errors && data.errors.join(" ")) || "Falha ao restaurar layout institucional.";
            showToast(message, "danger");
            throw new Error(message);
        }

        applyLayoutResponse(data, section);
        showToast(successMessage, "success");
        return data;
    }

    function bindRestoreButtons() {
        document.querySelectorAll("[data-report-restore-institutional]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                const section = button.dataset.reportRestoreInstitutional || "both";
                closeParentModal(button);
                closeParagraphOptionsMenu();
                restoreInstitutionalLayout(section).catch(console.error);
            });
        });
    }

    function toggleForensicOnlyElements(enabled) {
        document.querySelectorAll("[data-report-forensic-only]").forEach((element) => {
            element.hidden = !enabled;
        });
    }

    function init(options) {
        updateUrl = (options && options.updateUrl) || "";
        isForensicReport = Boolean(options && options.isForensicReport);
        toggleForensicOnlyElements(isForensicReport);
        if (!isForensicReport) {
            return;
        }
        bindRestoreButtons();
    }

    window.ReportLineInstitutionalLayout = {
        init,
        restoreInstitutionalLayout,
        isForensicReport: () => isForensicReport,
    };
})();
