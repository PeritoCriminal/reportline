/**
 * Armazenamento temporário de documentos do intake rápido (IndexedDB).
 *
 * Permite redirecionar ao editor antes da análise e recuperar os arquivos
 * selecionados na mesma origem.
 */
(function () {
    "use strict";

    const DB_NAME = "reportline-forensic-bootstrap";
    const STORE_NAME = "pending-documents";
    const DB_VERSION = 1;

    function openDatabase() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = () => {
                const db = request.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    db.createObjectStore(STORE_NAME);
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    function filesFromRecords(records) {
        return (records || []).map((record) => {
            return new File([record.buffer], record.name, {
                type: record.type || "application/octet-stream",
                lastModified: record.lastModified || Date.now(),
            });
        });
    }

    async function storePendingDocuments(reportId, files) {
        if (!reportId || !files || !files.length) {
            return;
        }

        const records = await Promise.all(
            Array.from(files).map(async (file) => ({
                name: file.name,
                type: file.type,
                lastModified: file.lastModified,
                buffer: await file.arrayBuffer(),
            }))
        );

        const db = await openDatabase();
        await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, "readwrite");
            tx.objectStore(STORE_NAME).put({ records }, String(reportId));
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
        db.close();
    }

    async function takePendingDocuments(reportId) {
        if (!reportId) {
            return [];
        }

        const db = await openDatabase();
        const payload = await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, "readonly");
            const request = tx.objectStore(STORE_NAME).get(String(reportId));
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });

        await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, "readwrite");
            tx.objectStore(STORE_NAME).delete(String(reportId));
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
        db.close();

        return filesFromRecords(payload ? payload.records : []);
    }

    async function hasPendingDocuments(reportId) {
        if (!reportId) {
            return false;
        }

        const db = await openDatabase();
        const payload = await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, "readonly");
            const request = tx.objectStore(STORE_NAME).get(String(reportId));
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
        db.close();

        return Boolean(payload && Array.isArray(payload.records) && payload.records.length);
    }

    window.ReportLineForensicBootstrapDocuments = {
        storePendingDocuments,
        takePendingDocuments,
        hasPendingDocuments,
    };
})();
