(function () {
    "use strict";

    function readConfig() {
        var configNode = document.getElementById("forensic-examiner-admin-config");
        if (!configNode) {
            return null;
        }
        try {
            return JSON.parse(configNode.textContent);
        } catch (error) {
            return null;
        }
    }

    function resetTeamSelect(teamSelect, disabled) {
        teamSelect.innerHTML = "";
        var emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "---------";
        teamSelect.appendChild(emptyOption);
        teamSelect.disabled = disabled;
    }

    function loadTeams(config, nucleusId, selectedTeamId) {
        var teamSelect = document.getElementById("id_forensic_team");
        if (!teamSelect) {
            return;
        }

        if (!nucleusId) {
            resetTeamSelect(teamSelect, true);
            return;
        }

        resetTeamSelect(teamSelect, true);

        fetch(config.teamsUrl + "?nucleus_id=" + encodeURIComponent(nucleusId), {
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Falha ao carregar equipes.");
                }
                return response.json();
            })
            .then(function (payload) {
                resetTeamSelect(teamSelect, false);
                payload.teams.forEach(function (team) {
                    var option = document.createElement("option");
                    option.value = team.id;
                    option.textContent = team.label;
                    if (selectedTeamId && team.id === selectedTeamId) {
                        option.selected = true;
                    }
                    teamSelect.appendChild(option);
                });
            })
            .catch(function () {
                resetTeamSelect(teamSelect, true);
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var config = readConfig();
        var nucleusSelect = document.getElementById("id_lotacao_nucleus");
        var teamSelect = document.getElementById("id_forensic_team");

        if (!config || !nucleusSelect || !teamSelect) {
            return;
        }

        var initialTeamId = teamSelect.value || "";

        nucleusSelect.addEventListener("change", function () {
            loadTeams(config, nucleusSelect.value, "");
        });

        if (nucleusSelect.value) {
            loadTeams(config, nucleusSelect.value, initialTeamId);
        } else {
            resetTeamSelect(teamSelect, true);
        }
    });
})();
