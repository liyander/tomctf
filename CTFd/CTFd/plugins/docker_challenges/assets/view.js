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

function copyFromInput(inputId, btnEl) {
    var inp = document.getElementById(inputId);
    if (!inp) return;
    inp.focus();
    inp.select();
    inp.setSelectionRange(0, inp.value.length);
    var ok = false;
    try { ok = document.execCommand('copy'); } catch(e) {}
    if (!ok && window.isSecureContext && navigator.clipboard) {
        navigator.clipboard.writeText(inp.value).catch(function(){});
        ok = true;
    }
    if (btnEl) {
        var old = btnEl.innerHTML;
        btnEl.innerHTML = '<i class="fas fa-check"></i> Copied!';
        setTimeout(function(){ btnEl.innerHTML = old; }, 1200);
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
        <div style="max-width:420px;margin:0 auto;text-align:center;padding:1rem 0">
            <button onclick="start_container('${CTFd._internal.challenge.data.docker_image}');" class='btn' style='background:rgba(0,230,118,0.12);color:#00e676;border:1px solid rgba(0,230,118,0.25);border-radius:10px;padding:12px 32px;font-size:.9rem;cursor:pointer;transition:all .2s'>
                <i class="fas fa-play" style="margin-right:6px"></i> Start Instance
            </button>
        </div>`;

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

                const inputId = `${instancePrefix}_hostport_input`;

                const hostPortField = hostPort
                    ? `<div class="input-group input-group-sm justify-content-center" style="max-width:340px;margin:0 auto">
                         <input type="text" id="${inputId}" class="form-control text-center" value="${hostPort}" readonly onclick="this.select()" style="cursor:text;background:rgba(255,255,255,0.06);color:#e0e0e0;border-color:rgba(255,255,255,0.12);border-radius:6px 0 0 6px;font-family:monospace;letter-spacing:.5px">
                         <button type="button" class="btn btn-outline-light btn-sm" id="${copyId}" style="border-color:rgba(255,255,255,0.12);border-radius:0 6px 6px 0"><i class="fas fa-copy"></i></button>
                       </div>`
                    : `<div style="color:#aaa">Host: ${host} &middot; Port: (pending)</div>`;

                // Container info panel — admin controls the max duration
                const containerExpiry = parseInt(item.container_expiry || 300);

                CTFd.lib.$('#docker_container').html(
                    `<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:1.2rem 1rem;max-width:420px;margin:0 auto">
                        <div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:.8rem">
                            <span style="width:8px;height:8px;border-radius:50%;background:#00e676;display:inline-block;box-shadow:0 0 6px #00e676"></span>
                            <span style="font-size:.85rem;font-weight:600;color:#e0e0e0;text-transform:uppercase;letter-spacing:1px">Instance Active</span>
                        </div>
                        <div style="margin-bottom:.8rem">${hostPortField}</div>
                        <div id="${timerId}" style="font-size:.8rem;color:#aaa;margin-bottom:.8rem"></div>
                        <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
                            <button id="${revertId}" onclick="start_container('${item.docker_image}');" class="btn btn-sm" style="background:rgba(255,255,255,0.07);color:#e0e0e0;border:1px solid rgba(255,255,255,0.12);border-radius:8px;padding:6px 16px;font-size:.8rem;transition:all .2s">
                                <i class="fas fa-redo" style="margin-right:4px"></i>Revert
                            </button>
                            <button id="${stopId}" onclick="stop_container('${item.docker_image}');" class="btn btn-sm" style="background:rgba(255,82,82,0.15);color:#ff5252;border:1px solid rgba(255,82,82,0.25);border-radius:8px;padding:6px 16px;font-size:.8rem;transition:all .2s">
                                <i class="fas fa-stop" style="margin-right:4px"></i>Stop
                            </button>
                            <button id="${instancePrefix}_extend_btn" class="btn btn-sm" style="background:rgba(0,230,118,0.1);color:#00e676;border:1px solid rgba(0,230,118,0.2);border-radius:8px;padding:6px 16px;font-size:.8rem;transition:all .2s">
                                <i class="fas fa-clock" style="margin-right:4px"></i>Extend
                            </button>
                        </div>
                    </div>`
                );

                const copyEl = document.getElementById(copyId);
                if (copyEl) {
                    copyEl.addEventListener('click', function () {
                        copyFromInput(inputId, copyEl);
                    });
                }

                const timerEl = document.getElementById(timerId);
                const extendEl = document.getElementById(`${instancePrefix}_extend_btn`);

                if (extendEl) {
                    extendEl.addEventListener('click', function () {
                        extend_container(item.docker_image);
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
                const expiresAtSeconds = (parseInt(item.revert_time || 0) || 0) || (startedAtSeconds ? startedAtSeconds + containerExpiry : 0);

                // Show extend button only when timer is low (under 5 min left)
                if (extendEl) {
                    const now = Math.floor(Date.now() / 1000);
                    if (!expiresAtSeconds || (expiresAtSeconds - now) > 300) {
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
                        if (timerEl) timerEl.innerHTML = '<i class="fas fa-exclamation-triangle" style="margin-right:4px"></i>Timer unavailable';
                        return;
                    }
                    var color = distance < 60000 ? '#ff5252' : (distance < 120000 ? '#ffab40' : '#aaa');
                    if (timerEl) timerEl.innerHTML = '<i class="fas fa-hourglass-half" style="margin-right:4px;color:' + color + '"></i><span style="color:' + color + '">Expires in ' + minutes + ':' + seconds + '</span>';

                    // Show extend button when under 5 min left
                    if (extendEl && distance <= 300000 && distance > 0) {
                        extendEl.style.display = '';
                    }

                    // Auto-stop when the countdown is finished
                    if (distance < 0) {
                        clearInterval(x);
                        if (timerEl) timerEl.innerHTML = '<i class="fas fa-times-circle" style="margin-right:4px;color:#ff5252"></i><span style="color:#ff5252">Instance expired</span>';
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

function extend_container(container) {
    return CTFd.fetch(
        "/api/v1/container?name=" +
            encodeURIComponent(container) +
            "&challenge=" +
            encodeURIComponent(CTFd._internal.challenge.data.name) +
            "&extend=1",
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
                warningText: "A Docker container is started for you.<br>This instance will stop automatically when the timer ends. You can Stop, Revert, or Extend when time is running low.",
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
