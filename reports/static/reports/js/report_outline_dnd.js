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

    function orderedNodeIdsFromList(listElement) {
        return Array.prototype.map.call(
            listElement.querySelectorAll(":scope > .report-editor-outline-dnd-item"),
            function (item) {
                return item.getAttribute("data-outline-node-id");
            }
        );
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

    function handleReorderResponse(response) {
        if (!response.ok) {
            window.location.reload();
            return Promise.reject(new Error("http"));
        }
        return response.json().then(function (data) {
            if (!data || !data.ok) {
                window.location.reload();
                return Promise.reject(new Error("payload"));
            }
            window.location.reload();
        });
    }

    function persistSiblingOrder(listElement, cfg) {
        var parentRaw = listElement.getAttribute("data-node-parent-id");
        var parentNodeId = parentRaw === null || parentRaw === "" ? null : parentRaw;
        var items = listElement.querySelectorAll(":scope > .report-editor-outline-dnd-item");
        for (var i = 0; i < items.length; i++) {
            var itemParent = items[i].getAttribute("data-report-parent-id") || "";
            if (itemParent !== (parentRaw || "")) {
                window.location.reload();
                return;
            }
        }
        postJson(cfg.reorderNodesUrl, {
            parent_node_id: parentNodeId,
            ordered_node_ids: orderedNodeIdsFromList(listElement),
        })
            .then(handleReorderResponse)
            .catch(function () {
                window.location.reload();
            });
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
            onEnd: function (event) {
                if (event.from !== event.to) {
                    return;
                }
                if (event.oldIndex === event.newIndex) {
                    return;
                }
                persistSiblingOrder(listElement, cfg);
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
