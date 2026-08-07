// reportline/reports/static/reports/js/report_image_client.js
/**
 * Preparação leve de imagem no cliente e upload compartilhado.
 *
 * Reduz bytes antes do envio quando Canvas está disponível; em falha ou
 * navegador antigo, repassa o arquivo original para o servidor processar.
 */
(function () {
    "use strict";

    var DEFAULT_JPEG_QUALITY = 0.85;
    var DEFAULT_SKIP_BELOW_BYTES = 250000;
    var DEFAULT_MAX_SIDE_PX = 529;
    var IMAGE_LOAD_TIMEOUT_MS = 20000;

    function getCsrfToken() {
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function resolveMaxSidePx(options) {
        if (options && options.maxSidePx) {
            return Number(options.maxSidePx);
        }
        if (window.REPORT_EDITOR_IMAGES && window.REPORT_EDITOR_IMAGES.maxSidePx) {
            return Number(window.REPORT_EDITOR_IMAGES.maxSidePx);
        }
        return DEFAULT_MAX_SIDE_PX;
    }

    function extensionFromMime(mime) {
        if (mime === "image/png") {
            return "png";
        }
        if (mime === "image/jpeg") {
            return "jpg";
        }
        if (mime === "image/webp") {
            return "webp";
        }
        if (mime === "image/gif") {
            return "gif";
        }
        return "jpg";
    }

    function buildPreparedFilename(originalName, mime) {
        var base = (originalName || "imagem").replace(/\.[^.]+$/, "");
        return base + "." + extensionFromMime(mime);
    }

    function canvasToBlob(canvas, mime, quality) {
        return new Promise(function (resolve) {
            if (!canvas.toBlob) {
                resolve(null);
                return;
            }
            canvas.toBlob(function (blob) {
                resolve(blob);
            }, mime, quality);
        });
    }

    function loadImageElement(file) {
        return new Promise(function (resolve, reject) {
            var url = URL.createObjectURL(file);
            var img = new Image();
            var settled = false;

            function finish(callback, value) {
                if (settled) {
                    return;
                }
                settled = true;
                URL.revokeObjectURL(url);
                callback(value);
            }

            var timer = window.setTimeout(function () {
                finish(reject, new Error("timeout"));
            }, IMAGE_LOAD_TIMEOUT_MS);

            img.onload = function () {
                window.clearTimeout(timer);
                finish(resolve, img);
            };
            img.onerror = function () {
                window.clearTimeout(timer);
                finish(reject, new Error("load-error"));
            };
            img.src = url;
        });
    }

    function canPrepareImages() {
        if (!window.HTMLCanvasElement || !window.URL || !URL.createObjectURL) {
            return false;
        }
        var canvas = document.createElement("canvas");
        return Boolean(canvas.getContext && canvas.getContext("2d"));
    }

    function shouldSkipProcessing(file, width, height, maxSidePx, skipBelowBytes) {
        var longest = Math.max(width, height);
        if (longest > maxSidePx) {
            return false;
        }
        return file.size <= skipBelowBytes;
    }

    function chooseOutputMime(sourceType) {
        if (
            sourceType === "image/png"
            || sourceType === "image/gif"
            || sourceType === "image/webp"
        ) {
            return "image/png";
        }
        return "image/jpeg";
    }

    function buildUploadFile(blob, preparedName) {
        try {
            return new File([blob], preparedName, {
                type: blob.type,
                lastModified: Date.now(),
            });
        } catch (error) {
            blob.name = preparedName;
            return blob;
        }
    }

    async function prepareForUpload(file, options) {
        options = options || {};
        var maxSidePx = resolveMaxSidePx(options);
        var jpegQuality = options.jpegQuality != null
            ? options.jpegQuality
            : DEFAULT_JPEG_QUALITY;
        var skipBelowBytes = options.skipBelowBytes != null
            ? options.skipBelowBytes
            : DEFAULT_SKIP_BELOW_BYTES;

        if (!file || !canPrepareImages()) {
            return file;
        }

        try {
            var img = await loadImageElement(file);
            var width = img.naturalWidth || img.width;
            var height = img.naturalHeight || img.height;
            if (!width || !height) {
                return file;
            }

            if (shouldSkipProcessing(file, width, height, maxSidePx, skipBelowBytes)) {
                return file;
            }

            var longest = Math.max(width, height);
            var scale = longest > maxSidePx ? maxSidePx / longest : 1;
            var targetWidth = Math.max(1, Math.round(width * scale));
            var targetHeight = Math.max(1, Math.round(height * scale));

            var canvas = document.createElement("canvas");
            canvas.width = targetWidth;
            canvas.height = targetHeight;
            var ctx = canvas.getContext("2d");
            if (!ctx) {
                return file;
            }
            ctx.drawImage(img, 0, 0, targetWidth, targetHeight);

            var mime = chooseOutputMime(file.type || "");
            var quality = mime === "image/jpeg" ? jpegQuality : undefined;
            var blob = await canvasToBlob(canvas, mime, quality);
            if (!blob || blob.size <= 0) {
                return file;
            }
            if (blob.size >= file.size && scale >= 1) {
                return file;
            }

            return buildUploadFile(blob, buildPreparedFilename(file.name, mime));
        } catch (error) {
            return file;
        }
    }

    async function uploadReportImage(file, options) {
        options = options || {};
        var uploadUrl = options.uploadUrl || "";
        if (!uploadUrl) {
            throw new Error("URL de upload não configurada.");
        }

        var prepared = await prepareForUpload(file, options);
        var formData = new FormData();
        formData.append("image", prepared, prepared.name || file.name);

        var response = await fetch(uploadUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
            body: formData,
        });

        var data = await response.json().catch(function () {
            return {};
        });
        if (!response.ok) {
            var message = (data.errors && data.errors.join(" ")) || "Falha ao enviar imagem.";
            throw new Error(message);
        }
        return data;
    }

    window.ReportLineImageClient = {
        prepareForUpload: prepareForUpload,
        uploadReportImage: uploadReportImage,
        getCsrfToken: getCsrfToken,
    };
})();
