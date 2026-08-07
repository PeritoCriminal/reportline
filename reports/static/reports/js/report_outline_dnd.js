// reportline/reports/static/reports/js/report_outline_dnd.js
/**
 * Reordenação por arrastar e soltar no sumário do editor de relatórios.
 */
(function () {
    "use strict";

    var sortableGroupSeq = 0;

    function getConfig() {
        return window.REPORT_EDITOR_OUTLINE || null;
    }

    function getCsrfToken() {
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function nextIsolatedGroupName() {
        sortableGroupSeq += 1;
        return "report-outline-isolated-" + sortableGroupSeq;
    }

    function parentAttrFromNodeId(parentNodeId) {
        return parentNodeId === null || parentNodeId === "" ? "" : String(parentNodeId);
    }

    function parentNodeIdFromList(listElement) {
        var parentRaw = listElement.getAttribute("data-node-parent-id");
        return parentRaw === null || parentRaw === "" ? null : parentRaw;
    }

    function itemMatchesParent(itemElement, parentNodeId) {
        var parentAttr = parentAttrFromNodeId(parentNodeId);
        return (itemElement.getAttribute("data-report-parent-id") || "") === parentAttr;
    }

    function collectSectionHeadingIds(itemElement, parentNodeId) {
        var ids = [];
        if (itemMatchesParent(itemElement, parentNodeId)) {
            ids.push(itemElement.getAttribute("data-outline-node-id"));
        }
        var childList = itemElement.querySelector(
            ":scope > .report-editor-outline-accordion-body > .report-editor-outline-children"
        );
        if (childList) {
            Array.prototype.forEach.call(
                childList.querySelectorAll(":scope > .report-editor-outline-dnd-item"),
                function (childItem) {
                    ids = ids.concat(collectSectionHeadingIds(childItem, parentNodeId));
                }
            );
        }
        return ids;
    }

    function buildReorderSections(listElement, parentNodeId) {
        return Array.prototype.map.call(
            listElement.querySelectorAll(":scope > .report-editor-outline-dnd-item"),
            function (item) {
                return collectSectionHeadingIds(item, parentNodeId);
            }
        );
    }

    function flattenSections(sections) {
        var flat = [];
        sections.forEach(function (sectionIds) {
            flat = flat.concat(sectionIds);
        });
        return flat;
    }

    function findSubsequenceStart(fullOrder, subsequence) {
        if (!subsequence.length) {
            return -1;
        }
        for (var start = 0; start <= fullOrder.length - subsequence.length; start++) {
            var matches = true;
            for (var index = 0; index < subsequence.length; index++) {
                if (fullOrder[start + index] !== subsequence[index]) {
                    matches = false;
                    break;
                }
            }
            if (matches) {
                return start;
            }
        }
        return -1;
    }

    function applySectionReorder(fullOrder, sectionsBefore, sectionsAfter) {
        var flatBefore = flattenSections(sectionsBefore);
        var flatAfter = flattenSections(sectionsAfter);
        if (!flatBefore.length) {
            return flatAfter;
        }
        var start = findSubsequenceStart(fullOrder, flatBefore);
        if (start === -1) {
            return flatAfter;
        }
        return fullOrder.slice(0, start).concat(flatAfter, fullOrder.slice(start + flatBefore.length));
    }

    function getAllHeadingIdsForParent(parentNodeId) {
        var root = document.getElementById("report-editor-outline-root");
        if (!root) {
            return [];
        }
        var parentAttr = parentAttrFromNodeId(parentNodeId);
        var ids = [];

        function walkList(listElement) {
            Array.prototype.forEach.call(
                listElement.querySelectorAll(":scope > .report-editor-outline-dnd-item"),
                function (item) {
                    if ((item.getAttribute("data-report-parent-id") || "") === parentAttr) {
                        ids.push(item.getAttribute("data-outline-node-id"));
                    }
                    var childList = item.querySelector(
                        ":scope > .report-editor-outline-accordion-body > .report-editor-outline-children"
                    );
                    if (childList) {
                        walkList(childList);
                    }
                }
            );
        }

        var rootList = root.querySelector(".report-editor-outline");
        if (rootList) {
            walkList(rootList);
        }
        return ids;
    }

    function postJson(url, body) {
        return fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify(body),
            credentials: "same-origin",
        });
    }

    function showReorderError(message) {
        var container = document.querySelector(".toast-container");
        if (!container) {
            container = document.createElement("div");
            container.className = "toast-container position-fixed top-0 end-0 p-3";
            container.style.zIndex = "1080";
            container.setAttribute("aria-live", "polite");
            container.setAttribute("aria-atomic", "true");
            document.body.appendChild(container);
        }

        var toastElement = document.createElement("div");
        toastElement.className = "toast align-items-center text-bg-danger border-0 mb-2";
        toastElement.setAttribute("role", "alert");
        toastElement.innerHTML = [
            '<div class="d-flex">',
            '<div class="toast-body">',
            '<i class="bi bi-exclamation-triangle-fill me-2" aria-hidden="true"></i>',
            message,
            "</div>",
            '<button type="button" class="btn-close btn-close-white me-2 m-auto" ',
            'data-bs-dismiss="toast" aria-label="Fechar"></button>',
            "</div>",
        ].join("");
        container.appendChild(toastElement);
        bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 4000 }).show();
        toastElement.addEventListener("hidden.bs.toast", function () {
            toastElement.remove();
        });
    }

    function validateSiblingList(listElement) {
        var parentRaw = listElement.getAttribute("data-node-parent-id") || "";
        var items = listElement.querySelectorAll(":scope > .report-editor-outline-dnd-item");
        for (var i = 0; i < items.length; i++) {
            var itemParent = items[i].getAttribute("data-report-parent-id") || "";
            if (itemParent !== parentRaw) {
                return false;
            }
        }
        return true;
    }

    async function applyReorderResponse(data) {
        if (window.ReportLineOutline && window.ReportLineOutline.applyReorderPayload) {
            await window.ReportLineOutline.applyReorderPayload(data);
            return;
        }
        if (data && data.body_node_ids && window.ReportLineOutline.applyBodyNodeOrder) {
            window.ReportLineOutline.applyBodyNodeOrder(data.body_node_ids);
        }
    }

    async function persistOutlineReorder(cfg, parentNodeId, orderedHeadingIds) {
        var response = await postJson(cfg.reorderNodesUrl, {
            parent_node_id: parentNodeId,
            ordered_node_ids: orderedHeadingIds,
        });
        var data = await response.json().catch(function () {
            return {};
        });
        if (!response.ok || !data.ok) {
            var errors = data.errors;
            var message = Array.isArray(errors) && errors.length
                ? errors.join(" ")
                : "Falha ao reordenar sumário.";
            throw new Error(message);
        }
        await applyReorderResponse(data);
        return data;
    }

    async function revertOutlineList(listElement) {
        if (window.ReportLineOutline && window.ReportLineOutline.refresh) {
            await window.ReportLineOutline.refresh();
        }
    }

    function recordOutlineReorderHistory(cfg, parentNodeId, beforeIds, afterIds) {
        if (!window.ReportLineUndo || window.ReportLineUndo.isApplying()) {
            return;
        }
        window.ReportLineUndo.recordCommand({
            label: "Reordenar sumário",
            undo: function () {
                return persistOutlineReorder(cfg, parentNodeId, beforeIds);
            },
            redo: function () {
                return persistOutlineReorder(cfg, parentNodeId, afterIds);
            },
        });
    }

    async function handleReorderEnd(listElement, cfg, reorderState) {
        if (!validateSiblingList(listElement)) {
            await revertOutlineList(listElement);
            showReorderError("Não foi possível reordenar itens de níveis diferentes.");
            return;
        }

        var parentNodeId = reorderState.parentNodeId !== undefined
            ? reorderState.parentNodeId
            : parentNodeIdFromList(listElement);
        var fullOrderBefore = reorderState.fullOrder || getAllHeadingIdsForParent(parentNodeId);
        var sectionsBefore = reorderState.sectionsBefore
            || buildReorderSections(listElement, parentNodeId);
        var sectionsAfter = buildReorderSections(listElement, parentNodeId);
        var beforeIds = applySectionReorder(fullOrderBefore, sectionsBefore, sectionsBefore);
        var afterIds = applySectionReorder(fullOrderBefore, sectionsBefore, sectionsAfter);

        if (beforeIds.join(",") === afterIds.join(",")) {
            return;
        }

        try {
            await persistOutlineReorder(cfg, parentNodeId, afterIds);
            recordOutlineReorderHistory(cfg, parentNodeId, beforeIds, afterIds);
        } catch (error) {
            await revertOutlineList(listElement);
            showReorderError(error.message || "Falha ao reordenar sumário.");
        }
    }

    function blockCrossParentMove(event) {
        return event.from === event.to;
    }

    function initSortable(listElement, cfg) {
        if (typeof Sortable === "undefined") {
            return;
        }
        if (listElement.dataset.reportOutlineSortableBound === "1") {
            return;
        }
        listElement.dataset.reportOutlineSortableBound = "1";
        Sortable.create(listElement, {
            group: { name: nextIsolatedGroupName(), pull: false, put: false },
            draggable: "> .report-editor-outline-dnd-item",
            handle: ".report-editor-outline-drag-handle",
            animation: 150,
            revertOnSpill: true,
            ghostClass: "report-editor-outline-dnd-ghost",
            dragClass: "report-editor-outline-dnd-drag",
            onMove: blockCrossParentMove,
            onStart: function (event) {
                var parentNodeId = parentNodeIdFromList(event.from);
                event.from.dataset.outlineReorderState = JSON.stringify({
                    parentNodeId: parentNodeId,
                    fullOrder: getAllHeadingIdsForParent(parentNodeId),
                    sectionsBefore: buildReorderSections(event.from, parentNodeId),
                });
            },
            onEnd: function (event) {
                if (event.from !== event.to) {
                    return;
                }
                if (event.oldIndex === event.newIndex) {
                    return;
                }
                var reorderState = {};
                try {
                    reorderState = JSON.parse(event.from.dataset.outlineReorderState || "{}");
                } catch (parseError) {
                    reorderState = {};
                }
                handleReorderEnd(listElement, cfg, reorderState).catch(console.error);
            },
        });
    }

    function mount(container) {
        var cfg = getConfig();
        if (!cfg || !cfg.reorderNodesUrl) {
            return;
        }
        container.querySelectorAll(".report-editor-outline-siblings").forEach(function (listElement) {
            initSortable(listElement, cfg);
        });
    }

    window.ReportLineOutlineDnD = { mount: mount };

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("#report-editor-outline-root").forEach(mount);
    });
})();
