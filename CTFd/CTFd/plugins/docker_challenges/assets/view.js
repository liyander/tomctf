CTFd._internal.challenge.data = undefined

CTFd._internal.challenge.renderer = CTFd._internal.markdown;


CTFd._internal.challenge.preRender = function() {}

CTFd._internal.challenge.render = function(markdown) {

    return CTFd._internal.challenge.renderer.parse(markdown)
}


CTFd._internal.challenge.postRender = function() {
    const containername = CTFd._internal.challenge.data.docker_image;
    get_docker_status(containername);
    createWarningModalBody();
}

function copyText(text) {
    if (!text) {
        return;
    }

    if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text);
        return;
    }

    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.left = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        document.execCommand('copy');
    } finally {
        document.body.removeChild(ta);
    }
}

function createWarningModalBody(){
    // Creates the Warning Modal placeholder, that will be updated when stuff happens.
    if (CTFd.lib.$('#warningModalBody').length === 0) {
        CTFd.lib.$('body').append('<div id="warningModalBody"></div>');
    }
}

function get_docker_status(container) {
    const NormalStartButtonHTML=`
        <span>
            <a onclick="start_container('${CTFd._internal.challenge.data.docker_image}');" class='btn btn-dark'>
                <small style='color:white;'><i class="fas fa-play"></i>  Start Docker Instance for challenge</small>
            </a>
        </span>`;

    // Default UI: show the start button; if a running container exists we'll replace it.
    CTFd.lib.$('#docker_container').html(NormalStartButtonHTML);

    // Use CTFd.fetch to call the API
    CTFd.fetch("/api/v1/docker_status")
    .then(async (response) => {
        const contentType = (response.headers && response.headers.get && response.headers.get('content-type')) || '';
        if (contentType.includes('application/json')) {
            return response.json();
        }
        const text = await response.text();
        throw new Error(text || 'Non-JSON response from docker_status');
    })
    .then(result => {
        if (!result || !Array.isArray(result.data)) {
            return;
        }

        for (const item of result.data) {
            if (item.docker_image == container) {
                // Split the ports and create the data string
                var ports = Array.isArray(item.ports)
                    ? item.ports
                    : String(item.ports).split(',');
                ports = ports.map(p => String(p || '').trim()).filter(p => p && p.toLowerCase() !== 'none');
                var data = '';

                const host = String(item.host || '').trim();
                const firstPort = ports.length > 0 ? String(ports[0]).split('/')[0] : '';
                const hostPort = (host && firstPort) ? `${host}:${firstPort}` : '';
                
                ports.forEach(port => {
                    port = String(port);
                    data = data + 'Host: ' + item.host + ' Port: ' + port + '<br />';
                });

                // Update the DOM with the docker container information
                const instancePrefix = String(item.instance_id || '').substring(0, 10);
                const timerId = `${instancePrefix}_revert_container`;
                const copyId = `${instancePrefix}_copy_hostport`;
                const stopId = `${instancePrefix}_stop_btn`;
                const revertId = `${instancePrefix}_revert_btn`;

                const hostPortLine = hostPort
                    ? `Host: ${host} Port: ${firstPort}`
                    : `Host: ${host} Port: (pending)`;

                const copyBtn = hostPort
                    ? `<button type="button" class="btn btn-sm btn-dark" id="${copyId}">Copy ${hostPort}</button>`
                    : '';

                // Always show timer + buttons; Stop/Revert should work immediately after start.
                CTFd.lib.$('#docker_container').html(
                    `<div class="text-center">
                        <div><strong>Docker Container Information:</strong></div>
                        <div class="mt-1">${hostPortLine}</div>
                        ${copyBtn ? `<div class="mt-2">${copyBtn}</div>` : ``}
                        <div class="mt-2" id="${timerId}"></div>
                        <div class="mt-2">
                            <a id="${revertId}" onclick="start_container('${item.docker_image}');" class="btn btn-dark">
                                <small style="color:white;"><i class="fas fa-redo"></i> Revert</small>
                            </a>
                            <a id="${stopId}" onclick="stop_container('${item.docker_image}');" class="btn btn-dark">
                                <small style="color:white;"><i class="fas fa-stop"></i> Stop</small>
                            </a>
                            <a id="${instancePrefix}_extend_btn" class="btn btn-dark">
                                <small style="color:white;"><i class="fas fa-clock"></i> Extend to 10 min</small>
                            </a>
                        </div>
                    </div>`
                );

                const copyEl = document.getElementById(copyId);
                if (copyEl) {
                    copyEl.addEventListener('click', function () {
                        copyText(hostPort);
                        const oldText = copyEl.textContent;
                        copyEl.textContent = 'Copied!';
                        setTimeout(() => (copyEl.textContent = oldText), 1200);
                    });
                }

                const timerEl = document.getElementById(timerId);
                const extendEl = document.getElementById(`${instancePrefix}_extend_btn`);

                if (extendEl) {
                    extendEl.addEventListener('click', function () {
                        extend_container_to_10min(item.docker_image);
                    });
                }

                // Update the DOM with connection info information (if present).
                // Some themes/challenge templates may not render `.challenge-connection-info`.
                var $link = CTFd.lib.$('.challenge-connection-info');
                if ($link.length > 0) {
                    const currentHtml = $link.html();
                    if (typeof currentHtml === 'string') {
                        $link.html(currentHtml.replace(/host/gi, item.host));
                        if (ports.length > 0) {
                            const updatedHtml = $link.html();
                            if (typeof updatedHtml === 'string') {
                                $link.html(updatedHtml.replace(/port|\b\d{5}\b/gi, ports[0].split("/")[0]));
                            }
                        }
                    }
                }

                // Check if there are links in there, if not and we use a http[s] address, make it a link
                CTFd.lib.$(".challenge-connection-info").each(function () {
                    const $span = CTFd.lib.$(this);
                    const html = $span.html();
                
                    // Skip if already has a link
                    if (html.includes("<a")) {
                        return;
                    }
                
                    // If it contains "http", try to extract and wrap it
                    const urlMatch = html.match(/(http[s]?:\/\/[^\s<]+)/);
                
                    if (urlMatch) {
                        const url = urlMatch[0];
                        const linked = html.replace(url, `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
                        $span.html(linked);
                    }
                });

                // Set up the expiry countdown timer. When it hits 0, the container should stop.
                const startedAtSeconds = parseInt(item.timestamp || 0) || 0;
                const expiresAtSeconds = (parseInt(item.revert_time || 0) || 0) || (startedAtSeconds ? startedAtSeconds + 300 : 0);
                const maxExpiresAtSeconds = startedAtSeconds ? (startedAtSeconds + 600) : 0;

                if (extendEl) {
                    if (!startedAtSeconds || !expiresAtSeconds || (maxExpiresAtSeconds && expiresAtSeconds >= maxExpiresAtSeconds)) {
                        extendEl.style.display = 'none';
                    }
                }

                var countDownDate = new Date(expiresAtSeconds * 1000).getTime();
                let didAutoStop = false;
                var x = setInterval(function() {
                    var now = new Date().getTime();
                    var distance = countDownDate - now;
                    var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                    var seconds = Math.floor((distance % (1000 * 60)) / 1000);
                    if (seconds < 10) {
                        seconds = "0" + seconds;
                    }

                    // Update the countdown display
                    if (isNaN(countDownDate) || !expiresAtSeconds) {
                        if (timerEl) timerEl.textContent = 'Instance timer unavailable';
                        return;
                    }
                    if (timerEl) timerEl.textContent = 'Instance stops in ' + minutes + ':' + seconds;

                    // Auto-stop when the countdown is finished
                    if (distance < 0) {
                        clearInterval(x);
                        if (timerEl) timerEl.textContent = 'Instance expired. Stopping...';
                        if (!didAutoStop) {
                            didAutoStop = true;
                            stop_container_api(item.docker_image, { silent: true });
                        }
                    }
                }, 1000);

                return; // Stop once the correct container is found
            }
        }
    })
    .catch(error => {
        console.error('Error fetching docker status:', error);
    });
}

function stop_container(container) {
    if (confirm("Are you sure you want to stop the container for: \n" + CTFd._internal.challenge.data.name)) {
        stop_container_api(container, { silent: false });
    }
}

function stop_container_api(container, { silent } = {}) {
    return CTFd.fetch(
        "/api/v1/container?name=" +
            encodeURIComponent(container) +
            "&challenge=" +
            encodeURIComponent(CTFd._internal.challenge.data.name) +
            "&stopcontainer=True",
        {
            method: "GET",
        }
    )
        .then(async function (response) {
            const contentType =
                (response.headers && response.headers.get && response.headers.get("content-type")) || "";
            const payload = contentType.includes("application/json")
                ? await response.json()
                : await response.text();
            if (response.ok) {
                if (!silent) {
                    updateWarningModal({
                        title: "Attention!",
                        warningText:
                            "The Docker container for <br><strong>" +
                            CTFd._internal.challenge.data.name +
                            "</strong><br> was stopped successfully.",
                        buttonText: "Close",
                        onClose: function () {
                            get_docker_status(container);
                        },
                    });
                } else {
                    get_docker_status(container);
                }
                return;
            }
            const msg = payload && payload.message ? payload.message : String(payload || "Failed to stop container");
            throw new Error(msg);
        })
        .catch(function (error) {
            if (!silent) {
                updateWarningModal({
                    title: "Error",
                    warningText: error.message || "An unknown error occurred while stopping the container.",
                    buttonText: "Close",
                    onClose: function () {
                        get_docker_status(container);
                    },
                });
            } else {
                console.warn("[Docker] Auto-stop failed:", error);
            }
        });
}

function extend_container_to_10min(container) {
    return CTFd.fetch(
        "/api/v1/container?name=" +
            encodeURIComponent(container) +
            "&challenge=" +
            encodeURIComponent(CTFd._internal.challenge.data.name) +
            "&extend=10",
        {
            method: "GET",
        }
    )
        .then(async function (response) {
            const contentType =
                (response.headers && response.headers.get && response.headers.get("content-type")) || "";
            const payload = contentType.includes("application/json")
                ? await response.json()
                : await response.text();
            if (response.ok) {
                get_docker_status(container);
                return;
            }
            const msg = payload && payload.message ? payload.message : String(payload || "Failed to extend container");
            throw new Error(msg);
        })
        .catch(function (error) {
            updateWarningModal({
                title: "Error!",
                warningText: error.message || "An unknown error occurred when extending your Docker container.",
                buttonText: "Got it!",
            });
        });
}

function start_container(container) {
    CTFd.lib.$('#docker_container').html('<div class="text-center"><i class="fas fa-circle-notch fa-spin fa-1x"></i></div>');
    CTFd.fetch("/api/v1/container?name=" + encodeURIComponent(container) + "&challenge=" + encodeURIComponent(CTFd._internal.challenge.data.name), {
        method: "GET"
    }).then(async function (response) {
        const contentType = (response.headers && response.headers.get && response.headers.get('content-type')) || '';
        const payload = contentType.includes('application/json') ? await response.json() : await response.text();
        if (response.ok) {
            get_docker_status(container);
            updateWarningModal({
                title: "Attention!",
                warningText: "A Docker container is started for you.<br>This instance will stop automatically when the timer ends. You can Stop/Revert any time, and you can extend up to 10 minutes.",
                buttonText: "Got it!"
            });
            return;
        }

        const msg = (payload && payload.message) ? payload.message : String(payload || 'Failed to start container');
        throw new Error(msg);
    }).catch(function (error) {
        // Handle error and notify the user
        updateWarningModal({
            title: "Error!",
            warningText: error.message || "An unknown error occurred when starting your Docker container.",
            buttonText: "Got it!",
            onClose: function () {
                get_docker_status(container);  // ← Will be called when modal is closed
            }
        });
    });
}

// WE NEED TO CREATE THE MODAL FIRST, and this should be only used to fill it.

function updateWarningModal({
    title, warningText = '', buttonText, onClose } = {}) {
    const modalHTML = `
        <div id="warningModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; z-index:9999; background-color:rgba(0,0,0,0.5);">
          <div style="position:relative; margin:10% auto; width:400px; background:white; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.3); overflow:hidden;">
            <div class="modal-header bg-warning text-dark" style="padding:1rem; display:flex; justify-content:space-between; align-items:center;">
              <h5 class="modal-title" style="margin:0;">${title}</h5>
              <button type="button" id="warningCloseBtn" style="border:none; background:none; font-size:1.5rem; line-height:1; cursor:pointer;">&times;</button>
            </div>
                        <div class="modal-body text-dark" style="padding:1rem;">
              ${warningText}
            </div>
            <div class="modal-footer" style="padding:1rem; text-align:right; border-top:1px solid #dee2e6;">
              <button type="button" class="btn btn-secondary" id="warningOkBtn">${buttonText}</button>
            </div>
          </div>
        </div>
    `;
    CTFd.lib.$("#warningModalBody").html(modalHTML);

    // Show the modal
    CTFd.lib.$("#warningModal").show();

    // Close logic with callback
    const closeModal = () => {
        CTFd.lib.$("#warningModal").hide();
        if (typeof onClose === 'function') {
            onClose();  
        }
    };

    CTFd.lib.$("#warningCloseBtn").on("click", closeModal);
    CTFd.lib.$("#warningOkBtn").on("click", closeModal);
}

// In order to capture the flag submission, and remove the "Revert" and "Stop" buttons after solving a challenge
// We need to hook that call, and do this manually.
function checkForCorrectFlag() {
    const challengeWindow = document.querySelector('#challenge-window');
    if (!challengeWindow || getComputedStyle(challengeWindow).display === 'none') {
        // console.log("❌ Challenge window hidden or closed, stopping check.");
        clearInterval(checkInterval);
        checkInterval = null;
        return;
    }

    const notification = document.querySelector('.notification-row .alert');
    if (!notification) return;

    const strong = notification.querySelector('strong');
    if (!strong) return;

    const message = strong.textContent.trim();

    if (message.includes("Correct")) {
        // console.log("✅ Correct flag detected:", message);
        get_docker_status(CTFd._internal.challenge.data.docker_image);
        clearInterval(checkInterval);
        checkInterval = null;
    }
}

if (!checkInterval) {
    var checkInterval = setInterval(checkForCorrectFlag, 1500);
}
