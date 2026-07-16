CTFd.plugin.run((_CTFd) => {
    const $ = _CTFd.lib.$
    const md = _CTFd.lib.markdown()
    $('a[href="#new-desc-preview"]').on('shown.bs.tab', function (event) {
        if (event.target.hash == '#new-desc-preview') {
            var editor_value = $('#new-desc-editor').val();
            $(event.target.hash).html(
                md.render(editor_value)
            );
        }
    });
    $('[data-toggle="tooltip"]').tooltip();
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
                    if (item.name === 'Error in Docker Config!') {
                        $("#dockerimage_select").prop('disabled', true);
                        $("label[for='DockerImage']").text('Docker Image: ' + item.name);
                    } else {
                        $("#dockerimage_select").append($("<option />").val(item.name).text(item.name));
                    }
                });
            }
        })
        .catch(function (err) {
            console.error("Failed to load Docker images:", err);
            $("#dockerimage_select").prop('disabled', true);
            $("label[for='DockerImage']").text('Docker Image: Failed to load');
        });
});
