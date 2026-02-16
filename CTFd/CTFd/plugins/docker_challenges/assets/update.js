CTFd.plugin.run((_CTFd) => {
    const $ = _CTFd.lib.$
    const md = _CTFd.lib.markdown()
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