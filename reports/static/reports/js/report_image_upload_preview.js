// reportline/reports/static/reports/js/report_image_upload_preview.js
/**
 * Padrão de projeto para preview de imagens enviadas: miniatura, checkbox
 * "Exibir no laudo" e campo de legenda proposta.
 */
(function (global) {
    "use strict";

    const DEFAULT_SHOW_IN_REPORT = true;

    /**
     * Cria item pendente a partir de um arquivo selecionado ou arrastado.
     *
     * @param {File} file
     * @returns {{ file: File, showInReport: boolean, proposedCaption: string, previewUrl: string|null, imageId: string|null }}
     */
    function createPendingItem(file) {
        return {
            file,
            showInReport: DEFAULT_SHOW_IN_REPORT,
            proposedCaption: "",
            previewUrl: null,
            imageId: null,
        };
    }

    /**
     * Revoga URLs de preview de objetos pendentes.
     *
     * @param {Array} items
     */
    function revokePreviewUrls(items) {
        (items || []).forEach((item) => {
            if (item?.previewUrl) {
                URL.revokeObjectURL(item.previewUrl);
                delete item.previewUrl;
            }
        });
    }

    /**
     * Habilita ou desabilita controles interativos do grid.
     *
     * @param {HTMLElement|null} container
     * @param {boolean} disabled
     */
    function setGridDisabled(container, disabled) {
        if (!container) {
            return;
        }
        container.querySelectorAll("input, button, textarea").forEach((control) => {
            control.disabled = disabled;
        });
    }

    /**
     * Renderiza grid de preview com miniatura, checkbox e legenda proposta.
     *
     * @param {HTMLElement|null} container
     * @param {Array} items
     * @param {{ onChange?: Function, disabled?: boolean }} [options]
     */
    function renderPreviewGrid(container, items, options) {
        const settings = options || {};
        if (!container) {
            return;
        }
        container.innerHTML = "";
        if (!items.length) {
            container.hidden = true;
            return;
        }
        container.hidden = false;

        items.forEach((item, index) => {
            const row = document.createElement("div");
            row.className = "report-image-upload-preview-item";

            const thumbWrap = document.createElement("div");
            thumbWrap.className = "report-image-upload-preview-thumb-wrap";

            const image = document.createElement("img");
            image.className = "report-image-upload-preview-thumb";
            image.alt = item.file?.name || "Imagem";
            if (!item.previewUrl && item.file) {
                item.previewUrl = URL.createObjectURL(item.file);
            }
            image.src = item.previewUrl || "";

            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.className = "btn btn-sm btn-outline-danger report-image-upload-preview-remove";
            removeButton.setAttribute("aria-label", `Remover ${item.file?.name || "imagem"}`);
            removeButton.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
            removeButton.addEventListener("click", () => {
                if (typeof settings.onRemove === "function") {
                    settings.onRemove(index);
                }
            });

            thumbWrap.appendChild(image);
            thumbWrap.appendChild(removeButton);

            const meta = document.createElement("div");
            meta.className = "report-image-upload-preview-meta";

            const checkboxId = `${container.id || "report-image-preview"}-show-${index}`;
            const checkboxWrap = document.createElement("div");
            checkboxWrap.className = "form-check mb-2";

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.className = "form-check-input";
            checkbox.id = checkboxId;
            checkbox.checked = Boolean(item.showInReport);
            checkbox.addEventListener("change", () => {
                item.showInReport = checkbox.checked;
                if (typeof settings.onChange === "function") {
                    settings.onChange();
                }
            });

            const checkboxLabel = document.createElement("label");
            checkboxLabel.className = "form-check-label";
            checkboxLabel.setAttribute("for", checkboxId);
            checkboxLabel.textContent = "Exibir no laudo";

            checkboxWrap.appendChild(checkbox);
            checkboxWrap.appendChild(checkboxLabel);

            const captionLabel = document.createElement("label");
            captionLabel.className = "form-label report-image-upload-preview-caption-label";
            captionLabel.setAttribute("for", `${checkboxId}-caption`);
            captionLabel.textContent = "Legenda proposta";

            const captionInput = document.createElement("input");
            captionInput.type = "text";
            captionInput.className = "form-control report-image-upload-preview-caption-input";
            captionInput.id = `${checkboxId}-caption`;
            captionInput.placeholder = "Descreva o que a imagem deve ilustrar no laudo…";
            captionInput.value = item.proposedCaption || "";
            captionInput.addEventListener("input", () => {
                item.proposedCaption = captionInput.value;
                if (typeof settings.onChange === "function") {
                    settings.onChange();
                }
            });

            meta.appendChild(checkboxWrap);
            meta.appendChild(captionLabel);
            meta.appendChild(captionInput);

            row.appendChild(thumbWrap);
            row.appendChild(meta);
            container.appendChild(row);
        });

        setGridDisabled(container, Boolean(settings.disabled));
    }

    /**
     * Converte itens pendentes enviados em payload da API.
     *
     * @param {Array} items — itens com ``imageId`` preenchido após upload
     * @returns {Array<{ image_id: string, show_in_report: boolean, proposed_caption: string }>}
     */
    function buildImagesPayload(items) {
        return (items || [])
            .filter((item) => item?.imageId)
            .map((item) => ({
                image_id: item.imageId,
                show_in_report: Boolean(item.showInReport),
                proposed_caption: (item.proposedCaption || "").trim(),
            }));
    }

    global.ReportLineImageUploadPreview = {
        createPendingItem,
        revokePreviewUrls,
        renderPreviewGrid,
        setGridDisabled,
        buildImagesPayload,
    };
})(window);
