/**
 * Continuação de exame de local no editor após análise documental.
 *
 * Exibe modais de escolha de tipo ou coleta de características do local
 * e persiste dados no bootstrap antes de retomar a montagem do laudo.
 */
(function () {
    "use strict";

    const CATEGORY_PROPERTY_SCENE = "property_scene";
    const CATEGORY_TRAFFIC = "traffic_accident";
    const CATEGORY_WORK = "work_accident";
    const CATEGORY_UNKNOWN = "unknown";
    const DEFERRED_CATEGORIES = new Set([CATEGORY_TRAFFIC, CATEGORY_WORK]);

    let typeModal = null;
    let characteristicsModal = null;
    let typeModalElement = null;
    let characteristicsModalElement = null;
    let dropzone = null;
    let fileInput = null;
    let previewGrid = null;
    let promptInput = null;
    let errorBox = null;
    let submitButton = null;
    let toastContainer = null;
    let locationKindAddress = null;
    let locationKindCoordinates = null;
    let addressFields = null;
    let coordinatesFields = null;
    let addressInput = null;
    let latitudeInput = null;
    let longitudeInput = null;
    let pendingFiles = [];
    let uploadedImageIds = [];
    let isSubmitting = false;
    let domInitialized = false;

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function showToast(message, variant) {
        if (!toastContainer) {
            toastContainer = document.querySelector(".toast-container");
        }
        if (!toastContainer) {
            toastContainer = document.createElement("div");
            toastContainer.className = "toast-container position-fixed top-0 end-0 p-3";
            toastContainer.style.zIndex = "1080";
            document.body.appendChild(toastContainer);
        }
        if (!window.bootstrap?.Toast) {
            return;
        }
        const tone = variant || "info";
        const toastElement = document.createElement("div");
        toastElement.className = `toast align-items-center text-bg-${tone} border-0`;
        toastElement.setAttribute("role", "alert");
        toastElement.setAttribute("aria-live", "assertive");
        toastElement.setAttribute("aria-atomic", "true");
        toastElement.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button"
                        class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"
                        aria-label="Fechar"></button>
            </div>`;
        toastContainer.appendChild(toastElement);
        const toast = window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 6000 });
        toastElement.addEventListener("hidden.bs.toast", () => toastElement.remove());
        toast.show();
    }

    function setError(message) {
        if (!errorBox) {
            return;
        }
        errorBox.textContent = message || "";
        errorBox.hidden = !message;
    }

    function normalizeCategory(value) {
        const cleaned = String(value || "").trim().toLowerCase();
        if (
            cleaned === CATEGORY_PROPERTY_SCENE ||
            cleaned === CATEGORY_TRAFFIC ||
            cleaned === CATEGORY_WORK
        ) {
            return cleaned;
        }
        return CATEGORY_UNKNOWN;
    }

    async function postJson(url, body) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body || {}),
        });
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

    async function uploadImage(imageUploadUrl, file) {
        const formData = new FormData();
        formData.append("image", file);
        const response = await fetch(imageUploadUrl, {
            method: "POST",
            headers: { "X-CSRFToken": getCsrfToken() },
            body: formData,
        });
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
                : errors || "Falha ao enviar imagem.";
            throw new Error(message);
        }
        return payload.image_id;
    }

    function revokePendingPreviewUrls() {
        pendingFiles.forEach((file) => {
            if (file.previewUrl) {
                URL.revokeObjectURL(file.previewUrl);
                delete file.previewUrl;
            }
        });
    }

    function resetCharacteristicsForm() {
        revokePendingPreviewUrls();
        pendingFiles = [];
        uploadedImageIds = [];
        if (promptInput) {
            promptInput.value = "";
        }
        if (addressInput) {
            addressInput.value = "";
        }
        if (latitudeInput) {
            latitudeInput.value = "";
        }
        if (longitudeInput) {
            longitudeInput.value = "";
        }
        if (locationKindAddress) {
            locationKindAddress.checked = true;
        }
        toggleLocationFields();
        setError("");
        renderPreviewGrid();
    }

    function toggleLocationFields() {
        const useCoordinates = locationKindCoordinates?.checked;
        if (addressFields) {
            addressFields.hidden = Boolean(useCoordinates);
        }
        if (coordinatesFields) {
            coordinatesFields.hidden = !useCoordinates;
        }
    }

    function readLocationPayload() {
        if (locationKindCoordinates?.checked) {
            return {
                kind: "coordinates",
                address: "",
                latitude: (latitudeInput?.value || "").trim(),
                longitude: (longitudeInput?.value || "").trim(),
            };
        }
        return {
            kind: "address",
            address: (addressInput?.value || "").trim(),
            latitude: "",
            longitude: "",
        };
    }

    function hasLocationInput(location) {
        if (!location) {
            return false;
        }
        if (location.kind === "coordinates") {
            return Boolean(location.latitude && location.longitude);
        }
        return Boolean(location.address);
    }

    function renderPreviewGrid() {
        if (!previewGrid) {
            return;
        }
        previewGrid.innerHTML = "";
        if (!pendingFiles.length) {
            previewGrid.hidden = true;
            return;
        }
        previewGrid.hidden = false;
        pendingFiles.forEach((file, index) => {
            const item = document.createElement("div");
            item.className = "scene-location-preview-item";
            const image = document.createElement("img");
            image.alt = file.name;
            if (!file.previewUrl) {
                file.previewUrl = URL.createObjectURL(file);
            }
            image.src = file.previewUrl;
            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.className = "btn btn-sm btn-outline-danger scene-location-preview-remove";
            removeButton.setAttribute("aria-label", `Remover ${file.name}`);
            removeButton.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
            removeButton.addEventListener("click", () => {
                const removed = pendingFiles.splice(index, 1)[0];
                if (removed?.previewUrl) {
                    URL.revokeObjectURL(removed.previewUrl);
                    delete removed.previewUrl;
                }
                renderPreviewGrid();
            });
            item.appendChild(image);
            item.appendChild(removeButton);
            previewGrid.appendChild(item);
        });
    }

    function addFiles(fileList) {
        const incoming = Array.from(fileList || []).filter((file) => file.type.startsWith("image/"));
        if (!incoming.length) {
            setError("Selecione arquivos de imagem válidos.");
            return;
        }
        setError("");
        pendingFiles = pendingFiles.concat(incoming);
        renderPreviewGrid();
    }

    function bindDropzoneEvents() {
        if (!dropzone || !fileInput || dropzone.dataset.eventsBound === "true") {
            return;
        }
        dropzone.dataset.eventsBound = "true";
        dropzone.addEventListener("click", () => fileInput.click());
        dropzone.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                fileInput.click();
            }
        });
        fileInput.addEventListener("change", () => {
            addFiles(fileInput.files);
            fileInput.value = "";
        });
        dropzone.addEventListener("dragover", (event) => {
            event.preventDefault();
            dropzone.classList.add("is-dragover");
        });
        dropzone.addEventListener("dragleave", () => {
            dropzone.classList.remove("is-dragover");
        });
        dropzone.addEventListener("drop", (event) => {
            event.preventDefault();
            event.stopPropagation();
            dropzone.classList.remove("is-dragover");
            addFiles(event.dataTransfer?.files);
        });
    }

    function showModal(modalInstance) {
        return new Promise((resolve) => {
            const element = modalInstance._element;
            const handleHidden = () => {
                element.removeEventListener("hidden.bs.modal", handleHidden);
                resolve();
            };
            element.addEventListener("hidden.bs.modal", handleHidden);
            modalInstance.show();
        });
    }

    function hideModal(modalInstance) {
        if (modalInstance) {
            modalInstance.hide();
        }
    }

    function waitForTypeSelection() {
        return new Promise((resolve) => {
            const options = typeModalElement.querySelectorAll(".scene-exam-type-option");
            options.forEach((button) => {
                button.addEventListener(
                    "click",
                    () => {
                        resolve(normalizeCategory(button.dataset.examCategory));
                    },
                    { once: true }
                );
            });
            showModal(typeModal);
        });
    }

    function waitForCharacteristicsSubmission() {
        return new Promise((resolve, reject) => {
            const handleSubmit = async () => {
                if (isSubmitting) {
                    return;
                }
                const prompt = (promptInput?.value || "").trim();
                const location = readLocationPayload();
                if (!prompt && !pendingFiles.length && !hasLocationInput(location)) {
                    setError("Informe localização, imagens ou orientações sobre o local.");
                    return;
                }
                if (location.kind === "coordinates" && (location.latitude || location.longitude)) {
                    if (!location.latitude || !location.longitude) {
                        setError("Informe latitude e longitude.");
                        return;
                    }
                }
                isSubmitting = true;
                if (submitButton) {
                    submitButton.disabled = true;
                }
                setError("");
                try {
                    resolve({
                        prompt,
                        location,
                        imageIds: [],
                        pendingUploads: pendingFiles.slice(),
                    });
                } catch (error) {
                    isSubmitting = false;
                    if (submitButton) {
                        submitButton.disabled = false;
                    }
                    reject(error);
                }
            };
            submitButton?.addEventListener("click", handleSubmit, { once: true });
            showModal(characteristicsModal);
        });
    }

    async function resolveExamCategory(initialCategory) {
        const category = normalizeCategory(initialCategory);
        if (category === CATEGORY_PROPERTY_SCENE) {
            return category;
        }
        if (DEFERRED_CATEGORIES.has(category)) {
            return category;
        }
        return waitForTypeSelection();
    }

    async function collectPropertySceneData(config) {
        resetCharacteristicsForm();
        const draft = await waitForCharacteristicsSubmission();
        hideModal(characteristicsModal);

        const imageIds = [];
        for (const file of draft.pendingUploads) {
            const imageId = await uploadImage(config.imageUploadUrl, file);
            imageIds.push(imageId);
        }
        return {
            prompt: draft.prompt,
            location: draft.location,
            imageIds,
        };
    }

    async function persistContinuation(config, examCategory, sceneData) {
        const payload = {
            exam_category: examCategory,
            prompt: sceneData?.prompt || "",
            image_ids: sceneData?.imageIds || [],
        };
        if (sceneData?.location && hasLocationInput(sceneData.location)) {
            payload.location = sceneData.location;
        }
        return postJson(config.sceneContinuationUrl, payload);
    }

    /**
     * Executa fluxo de continuação de exame de local e retorna novo estado.
     *
     * @param {object} config
     * @returns {Promise<object>}
     */
    async function run(config) {
        if (!config?.sceneContinuationUrl) {
            throw new Error("Continuação de exame indisponível nesta tela.");
        }

        const initialCategory = config.examCategory || config.metadata?.exam_category;
        const examCategory = await resolveExamCategory(initialCategory);

        if (DEFERRED_CATEGORIES.has(examCategory)) {
            hideModal(typeModal);
            const response = await persistContinuation(config, examCategory, null);
            if (response.todo_message) {
                showToast(response.todo_message, "info");
            }
            return response;
        }

        let sceneData = null;
        if (examCategory === CATEGORY_PROPERTY_SCENE) {
            hideModal(typeModal);
            sceneData = await collectPropertySceneData(config);
        }

        const response = await persistContinuation(config, examCategory, sceneData);
        isSubmitting = false;
        if (submitButton) {
            submitButton.disabled = false;
        }
        return response;
    }

    function initDomReferences() {
        if (domInitialized) {
            return true;
        }

        typeModalElement = document.getElementById("sceneExamTypeModal");
        characteristicsModalElement = document.getElementById("sceneLocationCharacteristicsModal");
        dropzone = document.getElementById("scene-location-dropzone");
        fileInput = document.getElementById("scene-location-file-input");
        previewGrid = document.getElementById("scene-location-preview-grid");
        promptInput = document.getElementById("scene-location-prompt-input");
        errorBox = document.getElementById("scene-location-error");
        submitButton = document.getElementById("scene-location-submit");
        locationKindAddress = document.getElementById("scene-location-kind-address");
        locationKindCoordinates = document.getElementById("scene-location-kind-coordinates");
        addressFields = document.getElementById("scene-location-address-fields");
        coordinatesFields = document.getElementById("scene-location-coordinates-fields");
        addressInput = document.getElementById("scene-location-address-input");
        latitudeInput = document.getElementById("scene-location-latitude-input");
        longitudeInput = document.getElementById("scene-location-longitude-input");

        locationKindAddress?.addEventListener("change", toggleLocationFields);
        locationKindCoordinates?.addEventListener("change", toggleLocationFields);
        toggleLocationFields();

        if (!typeModalElement || !characteristicsModalElement || !window.bootstrap?.Modal) {
            return false;
        }

        typeModal = window.bootstrap.Modal.getOrCreateInstance(typeModalElement, {
            backdrop: "static",
            keyboard: false,
        });
        characteristicsModal = window.bootstrap.Modal.getOrCreateInstance(
            characteristicsModalElement,
            {
                backdrop: "static",
                keyboard: false,
            }
        );
        bindDropzoneEvents();
        domInitialized = true;
        return true;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initDomReferences);
    } else {
        initDomReferences();
    }

    window.ReportLineSceneExaminationContinuation = {
        run,
        initDomReferences,
    };
})();
