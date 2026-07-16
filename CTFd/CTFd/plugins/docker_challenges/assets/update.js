CTFd.plugin.run((_CTFd) => {
    const $ = _CTFd.lib.$
    const md = _CTFd.lib.markdown()
    function syncTerminalShellField() {
        const enabled = $("#access_mode").val() === "terminal";
        $("#terminal-shell-group").toggle(enabled);
    }
    $("#access_mode").on("change", syncTerminalShellField);
    syncTerminalShellField();
    CTFd.fetch("/api/v1/docker", { method: "GET" })
        .then(function (response) { return response.json(); })
        .then(function (result) {
            if (result && result.data) {
                $.each(result.data, function (i, item) {
                    $("#dockerimage_select").append($("<option />").val(item.name).text(item.name));
                });
            }
            $("#dockerimage_select").val(DOCKER_IMAGE).change();
        })
        .catch(function (err) {
            console.error("Failed to load Docker images:", err);
            $("#dockerimage_select").prop('disabled', true);
        });
});
