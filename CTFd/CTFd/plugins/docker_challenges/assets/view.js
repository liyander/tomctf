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

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function appendTerminalOutput(outputId, text, kind) {
    const out = document.getElementById(outputId);
    if (!out) return;
    const color = kind === 'cmd' ? '#8be9fd' : (kind === 'err' ? '#ff7777' : '#e8e8e8');
    out.innerHTML += `<span style="color:${color}">${escapeHtml(text)}</span>`;
    out.scrollTop = out.scrollHeight;
}

function ensureTerminalStyles() {
    if (document.getElementById('tom-pwnbox-styles')) return;
    const style = document.createElement('style');
    style.id = 'tom-pwnbox-styles';
    style.textContent = `
        .tom-pwnbox {
            text-align: left !important;
            margin: .9rem auto 1rem;
            max-width: 820px;
            border: 1px solid rgba(139,233,253,.22);
            border-radius: 18px;
            background:
                radial-gradient(circle at top left, rgba(139,233,253,.10), transparent 34%),
                linear-gradient(180deg, rgba(10,15,25,.98), rgba(4,7,12,.98));
            box-shadow: 0 18px 55px rgba(0,0,0,.38), inset 0 1px 0 rgba(255,255,255,.04);
            overflow: hidden;
        }
        .tom-pwnbox * { box-sizing: border-box; }
        .tom-pwnbox-titlebar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: .82rem .95rem;
            border-bottom: 1px solid rgba(139,233,253,.14);
            background: linear-gradient(90deg, rgba(139,233,253,.10), rgba(236,19,19,.07));
        }
        .tom-pwnbox-title {
            display: flex;
            align-items: center;
            gap: .7rem;
            min-width: 210px;
        }
        .tom-pwnbox-terminal-icon {
            display: grid;
            place-items: center;
            width: 34px;
            height: 34px;
            border-radius: 11px;
            color: #8be9fd;
            background: rgba(139,233,253,.10);
            border: 1px solid rgba(139,233,253,.20);
            box-shadow: 0 0 18px rgba(139,233,253,.08);
        }
        .tom-pwnbox-label {
            color: #8be9fd;
            font-size: .82rem;
            font-weight: 800;
            letter-spacing: .11em;
            text-transform: uppercase;
            line-height: 1.1;
        }
        .tom-pwnbox-meta {
            display: flex;
            align-items: center;
            gap: .45rem;
            flex-wrap: wrap;
            margin-top: .24rem;
            color: rgba(255,255,255,.58);
            font-size: .72rem;
        }
        .tom-pwnbox-chip {
            display: inline-flex;
            align-items: center;
            gap: .35rem;
            padding: .18rem .48rem;
            border-radius: 999px;
            color: rgba(255,255,255,.72);
            background: rgba(255,255,255,.055);
            border: 1px solid rgba(255,255,255,.08);
        }
        .tom-pwnbox-live-dot {
            width: 7px;
            height: 7px;
            border-radius: 999px;
            background: #00e676;
            box-shadow: 0 0 9px rgba(0,230,118,.95);
        }
        .tom-pwnbox-actions {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: .45rem;
            flex-wrap: wrap;
        }
        .tom-pwnbox-btn {
            display: inline-flex;
            align-items: center;
            gap: .38rem;
            border-radius: 999px;
            padding: .42rem .72rem;
            border: 1px solid rgba(255,255,255,.13);
            background: rgba(255,255,255,.055);
            color: rgba(255,255,255,.82);
            font-size: .76rem;
            font-weight: 700;
            line-height: 1;
            text-decoration: none !important;
            transition: transform .16s ease, border-color .16s ease, background .16s ease, color .16s ease;
        }
        .tom-pwnbox-btn:hover {
            transform: translateY(-1px);
            border-color: rgba(139,233,253,.38);
            background: rgba(139,233,253,.11);
            color: #8be9fd;
        }
        .tom-pwnbox-btn-primary {
            color: #061016;
            background: linear-gradient(135deg, #8be9fd, #64d7ff);
            border-color: rgba(139,233,253,.64);
            box-shadow: 0 8px 24px rgba(139,233,253,.14);
        }
        .tom-pwnbox-btn-primary:hover { color: #061016; }
        .tom-pwnbox-panel { padding: .82rem; }
        .tom-pwnbox-help {
            display: flex;
            align-items: flex-start;
            gap: .55rem;
            margin: 0 0 .72rem;
            padding: .62rem .75rem;
            border: 1px solid rgba(139,233,253,.12);
            border-radius: 12px;
            background: rgba(139,233,253,.055);
            color: rgba(255,255,255,.68);
            font-size: .77rem;
            line-height: 1.45;
        }
        .tom-pwnbox-output {
            height: 310px;
            overflow: auto;
            white-space: pre-wrap;
            text-align: left !important;
            margin: 0 0 .62rem;
            padding: .95rem;
            border: 1px solid rgba(139,233,253,.16);
            border-radius: 14px;
            background: #05070b;
            color: #e8e8e8;
            font-family: Consolas, Menlo, monospace;
            font-size: .86rem;
            line-height: 1.5;
            box-shadow: inset 0 0 28px rgba(0,0,0,.36);
        }
        .tom-pwnbox-inputbar {
            display: flex;
            align-items: stretch;
            overflow: hidden;
            border: 1px solid rgba(139,233,253,.18);
            border-radius: 13px;
            background: #080d15;
        }
        .tom-pwnbox-prompt {
            display: grid;
            place-items: center;
            min-width: 42px;
            color: #8be9fd;
            border-right: 1px solid rgba(139,233,253,.14);
            font-family: Consolas, Menlo, monospace;
            font-weight: 800;
        }
        .tom-pwnbox-input {
            flex: 1;
            min-width: 0;
            border: 0;
            outline: 0;
            background: transparent;
            color: #fff;
            padding: .72rem .78rem;
            font-family: Consolas, Menlo, monospace;
            font-size: .86rem;
        }
        .tom-pwnbox-run {
            border: 0;
            border-left: 1px solid rgba(139,233,253,.14);
            padding: 0 1rem;
            background: rgba(139,233,253,.12);
            color: #8be9fd;
            font-weight: 800;
        }
        .tom-pwnbox-run:disabled {
            cursor: wait;
            opacity: .65;
        }
        .tom-pwnbox-minimized .tom-pwnbox-panel { display: none; }
        .tom-pwnbox-minimized {
            max-width: 620px;
        }
        .tom-pwnbox-minimized .tom-pwnbox-titlebar {
            border-bottom: 0;
        }
        .tom-pwnbox-expanded {
            position: fixed !important;
            inset: 18px !important;
            z-index: 10050 !important;
            max-width: none !important;
            margin: 0 !important;
            border-color: rgba(139,233,253,.42);
            box-shadow: 0 28px 130px rgba(0,0,0,.86), 0 0 46px rgba(139,233,253,.18);
        }
        .tom-pwnbox-expanded .tom-pwnbox-panel {
            height: calc(100vh - 96px);
            display: flex;
            flex-direction: column;
        }
        .tom-pwnbox-expanded .tom-pwnbox-output {
            height: auto;
            flex: 1;
            min-height: 0;
        }
        @media (max-width: 640px) {
            .tom-pwnbox-titlebar {
                align-items: flex-start;
                flex-direction: column;
            }
            .tom-pwnbox-actions {
                justify-content: flex-start;
                width: 100%;
            }
            .tom-pwnbox-btn {
                flex: 1 1 auto;
                justify-content: center;
            }
            .tom-pwnbox-expanded {
                inset: 8px !important;
                border-radius: 14px;
            }
        }
    `;
    document.head.appendChild(style);
}

function setTerminalBusy(input, runButton, busy) {
    if (input) input.disabled = busy;
    if (runButton) {
        runButton.disabled = busy;
        runButton.innerHTML = busy
            ? '<i class="fas fa-circle-notch fa-spin"></i> Running'
            : '<i class="fas fa-play"></i> Run';
    }
}

function run_terminal_command(trackerId, inputId, outputId, runBtnId) {
    const input = document.getElementById(inputId);
    const runButton = runBtnId ? document.getElementById(runBtnId) : null;
    if (!input) return;
    const command = input.value;
    if (!command.trim()) return;
    input.value = '';
    appendTerminalOutput(outputId, `$ ${command}\n`, 'cmd');
    setTerminalBusy(input, runButton, true);
    CTFd.fetch("/api/v1/docker_terminal", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            tracker_id: trackerId,
            command: command,
        }),
    })
        .then(async function (response) {
            const contentType = (response.headers && response.headers.get && response.headers.get("content-type")) || "";
            const payload = contentType.includes("application/json") ? await response.json() : { success: false, message: await response.text() };
            if (!response.ok || !payload.success) {
                throw new Error(payload.message || "Terminal command failed");
            }
            appendTerminalOutput(outputId, payload.output || "\n", 'out');
        })
        .catch(function (error) {
            appendTerminalOutput(outputId, `${error.message || "Terminal command failed"}\n`, 'err');
        })
        .finally(function () {
            setTerminalBusy(input, runButton, false);
            input.focus();
        });
}

function toggle_terminal_minimized(wrapperId, inputId, btnId) {
    const wrapper = document.getElementById(wrapperId);
    const btn = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    if (!wrapper) return;
    const minimized = wrapper.classList.toggle('tom-pwnbox-minimized');
    if (btn) {
        btn.innerHTML = minimized
            ? '<i class="fas fa-chevron-up"></i> Restore'
            : '<i class="fas fa-window-minimize"></i> Minimize';
    }
    if (!minimized && input) {
        setTimeout(function () { input.focus(); }, 50);
    }
}

function toggle_terminal_expanded(wrapperId, inputId, btnId) {
    const wrapper = document.getElementById(wrapperId);
    const input = document.getElementById(inputId);
    const btn = document.getElementById(btnId);
    if (!wrapper) return;

    wrapper.classList.remove('tom-pwnbox-minimized');
    const minimizeBtn = wrapper.querySelector('[data-pwnbox-minimize]');
    if (minimizeBtn) {
        minimizeBtn.innerHTML = '<i class="fas fa-window-minimize"></i> Minimize';
    }
    const expanded = wrapper.classList.toggle('tom-pwnbox-expanded');
    if (btn) {
        btn.innerHTML = expanded
            ? '<i class="fas fa-compress-alt"></i> Exit full screen'
            : '<i class="fas fa-expand-alt"></i> Expand';
    }
    document.body.style.overflow = expanded ? 'hidden' : '';
    if (input) {
        setTimeout(function () { input.focus(); }, 50);
    }
}

document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    const expanded = document.querySelector('.tom-pwnbox-expanded');
    if (!expanded) return;
    expanded.classList.remove('tom-pwnbox-expanded');
    const expandBtn = expanded.querySelector('[data-pwnbox-expand]');
    if (expandBtn) {
        expandBtn.innerHTML = '<i class="fas fa-expand-alt"></i> Expand';
    }
    document.body.style.overflow = '';
});

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
                const isTerminalMode = item.terminal_enabled === true || item.access_mode === 'terminal';
                const isProxyMode = item.connection_mode === 'proxy' && item.connection_url;
                const hostPort = isProxyMode
                    ? String(item.connection_url || '').trim()
                    : ((host && firstPort) ? `${host}:${firstPort}` : '');
                
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
                const terminalInputId = `${instancePrefix}_terminal_input`;
                const terminalOutputId = `${instancePrefix}_terminal_output`;
                const terminalWrapperId = `${instancePrefix}_terminal_wrapper`;
                const terminalPanelId = `${instancePrefix}_terminal_panel`;
                const terminalToggleId = `${instancePrefix}_terminal_toggle`;
                const terminalExpandId = `${instancePrefix}_terminal_expand`;
                const terminalRunId = `${instancePrefix}_terminal_run`;

                const openButton = isProxyMode
                    ? `<a href="${hostPort}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="display:inline-flex;align-items:center;gap:6px;background:rgba(0,230,118,0.12);color:#00e676;border:1px solid rgba(0,230,118,0.24);border-radius:8px;padding:7px 14px;margin-bottom:.6rem;text-decoration:none">
                         <i class="fas fa-external-link-alt"></i> Open Instance
                       </a>`
                    : '';

                const hostPortField = hostPort
                    ? `${openButton}<div class="input-group input-group-sm justify-content-center" style="max-width:420px;margin:0 auto">
                         <input type="text" id="${inputId}" class="form-control text-center" value="${hostPort}" readonly onclick="this.select()" style="cursor:text;background:rgba(255,255,255,0.06);color:#e0e0e0;border-color:rgba(255,255,255,0.12);border-radius:6px 0 0 6px;font-family:monospace;letter-spacing:.5px">
                         <button type="button" class="btn btn-outline-light btn-sm" id="${copyId}" style="border-color:rgba(255,255,255,0.12);border-radius:0 6px 6px 0"><i class="fas fa-copy"></i></button>
                       </div>`
                    : `<div style="color:#aaa">Host: ${host} &middot; Port: (pending)</div>`;

                const terminalField = `
                    <div id="${terminalWrapperId}" class="tom-pwnbox">
                        <div class="tom-pwnbox-titlebar">
                            <div class="tom-pwnbox-title">
                                <span class="tom-pwnbox-terminal-icon"><i class="fas fa-terminal"></i></span>
                                <div>
                                    <div class="tom-pwnbox-label">Isolated PwnBox</div>
                                    <div class="tom-pwnbox-meta">
                                        <span class="tom-pwnbox-chip"><span class="tom-pwnbox-live-dot"></span> Live</span>
                                        <span class="tom-pwnbox-chip">${escapeHtml(item.terminal_shell || '/bin/sh')}</span>
                                        <span class="tom-pwnbox-chip">Only your instance</span>
                                    </div>
                                </div>
                            </div>
                            <div class="tom-pwnbox-actions">
                                <button id="${terminalExpandId}" type="button" class="tom-pwnbox-btn tom-pwnbox-btn-primary" title="Expand terminal full screen" data-pwnbox-expand>
                                    <i class="fas fa-expand-alt"></i> Expand
                                </button>
                                <a href="${escapeHtml(item.terminal_url || '#')}" target="_blank" rel="noopener noreferrer" class="tom-pwnbox-btn" title="Open the terminal in a new browser window">
                                    <i class="fas fa-external-link-alt"></i> Pop out
                                </a>
                                <button id="${terminalToggleId}" type="button" class="tom-pwnbox-btn" title="Minimize this terminal" data-pwnbox-minimize>
                                    <i class="fas fa-window-minimize"></i> Minimize
                                </button>
                            </div>
                        </div>
                        <div id="${terminalPanelId}" class="tom-pwnbox-panel">
                            <div class="tom-pwnbox-help">
                                <i class="fas fa-shield-alt"></i>
                                <span>Commands run inside your private Docker instance. This terminal is isolated from other players and is safe to pop out while solving.</span>
                            </div>
                            <pre id="${terminalOutputId}" class="tom-pwnbox-output">Welcome to your isolated challenge terminal.
Try: id, pwd, ls, or service-specific tools needed for this challenge.
</pre>
                            <div class="tom-pwnbox-inputbar">
                                <span class="tom-pwnbox-prompt">$</span>
                                <input id="${terminalInputId}" type="text" class="tom-pwnbox-input" placeholder="Type a command and press Enter" autocomplete="off" spellcheck="false">
                                <button id="${terminalRunId}" type="button" class="tom-pwnbox-run"><i class="fas fa-play"></i> Run</button>
                            </div>
                        </div>
                    </div>`;

                // Container info panel — admin controls the max duration
                const containerExpiry = parseInt(item.container_expiry || 300);

                CTFd.lib.$('#docker_container').html(
                    `<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:1.2rem 1rem;max-width:${isTerminalMode ? '820px' : '420px'};margin:0 auto">
                        <div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:.8rem">
                            <span style="width:8px;height:8px;border-radius:50%;background:#00e676;display:inline-block;box-shadow:0 0 6px #00e676"></span>
                            <span style="font-size:.85rem;font-weight:600;color:#e0e0e0;text-transform:uppercase;letter-spacing:1px">Instance Active</span>
                        </div>
                        <div style="margin-bottom:.8rem">${isTerminalMode ? terminalField : hostPortField}</div>
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

                if (isTerminalMode) {
                    ensureTerminalStyles();
                    const terminalInput = document.getElementById(terminalInputId);
                    const terminalRun = document.getElementById(terminalRunId);
                    const terminalToggle = document.getElementById(terminalToggleId);
                    const terminalExpand = document.getElementById(terminalExpandId);
                    const runTerminal = function () {
                        run_terminal_command(item.id, terminalInputId, terminalOutputId, terminalRunId);
                    };
                    if (terminalExpand) {
                        terminalExpand.addEventListener('click', function () {
                            toggle_terminal_expanded(terminalWrapperId, terminalInputId, terminalExpandId);
                        });
                    }
                    if (terminalToggle) {
                        terminalToggle.addEventListener('click', function () {
                            toggle_terminal_minimized(terminalWrapperId, terminalInputId, terminalToggleId);
                        });
                    }
                    if (terminalRun) {
                        terminalRun.addEventListener('click', runTerminal);
                    }
                    if (terminalInput) {
                        terminalInput.addEventListener('keydown', function (event) {
                            if (event.key === 'Enter') {
                                event.preventDefault();
                                runTerminal();
                            }
                        });
                        terminalInput.focus();
                    }
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
                if (isTerminalMode && $link.length > 0) {
                    $link.html(`<span><i class="fas fa-terminal"></i> Use the isolated terminal below for this challenge.</span>`);
                } else if (isProxyMode && $link.length > 0) {
                    $link.html(`<a href="${hostPort}" target="_blank" rel="noopener noreferrer">${hostPort}</a>`);
                } else if ($link.length > 0) {
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
