import traceback
import os

from CTFd.plugins.challenges import BaseChallenge, CHALLENGE_CLASSES, get_chal_class
from CTFd.plugins.flags import get_flag_class
from CTFd.utils.user import get_ip
from CTFd.utils.uploads import delete_file
from CTFd.plugins import register_plugin_assets_directory, bypass_csrf_protection
from CTFd.schemas.tags import TagSchema
from CTFd.models import db, ma, Challenges, Teams, Users, Solves, Fails, Flags, Files, Hints, Tags, ChallengeFiles
from CTFd.utils.decorators import admins_only, authed_only, during_ctf_time_only, require_verified_emails
from CTFd.utils.decorators.visibility import check_challenge_visibility, check_score_visibility
from CTFd.utils.user import get_current_team
from CTFd.utils.user import get_current_user
from CTFd.utils.user import is_admin, authed
from CTFd.utils.config import is_teams_mode
from CTFd.api import CTFd_API_v1
from CTFd.api.v1.scoreboard import ScoreboardDetail
import CTFd.utils.scores
from CTFd.api.v1.challenges import ChallengeList, Challenge
from flask_restx import Namespace, Resource
from flask import request, Blueprint, jsonify, abort, render_template, url_for, redirect, session, Response, stream_with_context
# from flask_wtf import FlaskForm
from wtforms import (
    FileField,
    HiddenField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    TextAreaField,
    SelectMultipleField,
    BooleanField,
)
# from wtforms import TextField, SubmitField, BooleanField, HiddenField, FileField, SelectMultipleField
from wtforms.validators import DataRequired, ValidationError, InputRequired
from werkzeug.utils import secure_filename
import requests
import tempfile
import subprocess
import threading
import socket
import sys
from CTFd.utils.dates import unix_time
from datetime import datetime
import json
import hashlib
import random
import re
from urllib.parse import urlsplit, urlunsplit
from CTFd.plugins import register_admin_plugin_menu_bar

from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField
from CTFd.utils.config import get_themes

from pathlib import Path

# Auto-start WSL Docker daemon and keep WSL alive so containers don't die
if sys.platform == 'win32':
    try:
        # Start docker and keep a sleep process alive to prevent WSL idle shutdown
        subprocess.Popen(
            ['wsl', '-u', 'root', '-e', 'bash', '-c',
             'service docker start >/dev/null 2>&1; exec sleep infinity'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
    except Exception:
        pass


# ── TCP Proxy for LAN access (no admin required) ──────────────────
# WSL2 NAT auto-forwards container ports to 127.0.0.1 on Windows,
# but LAN / WiFi clients can't reach localhost.  We bind a TCP relay
# on the LAN IP (display_host) for each container port and forward
# to 127.0.0.1 where WSL2's auto-forward is listening.  This avoids
# port conflicts since WSL2 only binds 127.0.0.1, not 0.0.0.0.

_active_proxies = {}   # port (int) -> server_socket


def _relay(src, dst):
    """Copy bytes one direction; close both when done."""
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try: src.close()
        except Exception: pass
        try: dst.close()
        except Exception: pass


def _accept_loop(srv, target_port):
    """Accept connections on srv and relay to 127.0.0.1:target_port (WSL2 auto-forward)."""
    while True:
        try:
            client, _ = srv.accept()
        except Exception:
            break
        try:
            remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote.settimeout(5)
            remote.connect(('127.0.0.1', target_port))
            remote.settimeout(None)
            threading.Thread(target=_relay, args=(client, remote), daemon=True).start()
            threading.Thread(target=_relay, args=(remote, client), daemon=True).start()
        except Exception:
            try: client.close()
            except Exception: pass


def add_port_forward(port, display_host):
    """Start a TCP relay on <display_host>:<port> → 127.0.0.1:<port>."""
    if sys.platform != 'win32':
        return
    port = int(port)
    if port in _active_proxies:
        return
    bind_ip = str(display_host) if display_host else '0.0.0.0'
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((bind_ip, port))
        srv.listen(16)
        t = threading.Thread(target=_accept_loop, args=(srv, port), daemon=True)
        t.start()
        _active_proxies[port] = srv
    except OSError:
        pass


def remove_port_forward(port):
    """Stop the TCP relay for a port."""
    if sys.platform != 'win32':
        return
    port = int(port)
    srv = _active_proxies.pop(port, None)
    if srv:
        try: srv.close()
        except Exception: pass


def _config_enabled(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on", "enabled")


def docker_proxy_enabled():
    """Whether players should receive CTFd-owned proxy URLs instead of raw host ports."""
    try:
        from CTFd.utils import get_config
        return _config_enabled(get_config("docker_proxy_enabled"), default=True)
    except Exception:
        return True


def get_docker_api_host(docker):
    if not docker or not docker.hostname:
        return ""
    host = str(docker.hostname).strip()
    if "://" not in host:
        host = "tcp://" + host
    parsed = urlsplit(host)
    return parsed.hostname or str(docker.hostname).split(":")[0]


def get_proxy_upstream_host(docker, tracker=None):
    """Host CTFd should dial to reach published challenge ports."""
    try:
        from CTFd.utils import get_config
        configured = (get_config("docker_proxy_upstream_host") or "").strip()
        if configured:
            return configured
    except Exception:
        pass
    if tracker and tracker.host:
        return str(tracker.host).split(":")[0]
    if docker and docker.display_host:
        return str(docker.display_host).split(":")[0]
    return get_docker_api_host(docker)


def get_proxy_public_base():
    try:
        from CTFd.utils import get_config
        base = (get_config("docker_proxy_public_base") or "").strip()
        return base.rstrip("/")
    except Exception:
        return ""


def build_proxy_url(tracker_id, port):
    path = url_for("docker_challenge_proxy.proxy_instance", tracker_id=tracker_id, port=port, path="")
    public_base = get_proxy_public_base()
    if public_base:
        return public_base + path
    return url_for("docker_challenge_proxy.proxy_instance", tracker_id=tracker_id, port=port, path="", _external=True)


def define_challenge_proxy(app):
    challenge_proxy = Blueprint("docker_challenge_proxy", __name__)

    def _owns_tracker(tracker):
        if not authed():
            return False
        if is_teams_mode():
            team = get_current_team()
            return team is not None and str(tracker.team_id) == str(team.id)
        user = get_current_user()
        return user is not None and str(tracker.user_id) == str(user.id)

    @challenge_proxy.route("/challenge-proxy/<int:tracker_id>/<port>/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    @challenge_proxy.route("/challenge-proxy/<int:tracker_id>/<port>/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    @authed_only
    def proxy_instance(tracker_id, port, path):
        tracker = DockerChallengeTracker.query.filter_by(id=tracker_id).first_or_404()
        if not _owns_tracker(tracker):
            abort(403)

        port = str(port).split("/")[0].strip()
        allowed_ports = [p.split("/")[0].strip() for p in str(tracker.ports or "").split(",") if p.strip()]
        if port not in allowed_ports:
            abort(404)

        docker = DockerConfig.query.filter_by(id=1).first()
        upstream_host = get_proxy_upstream_host(docker, tracker)
        if not upstream_host:
            return Response("Docker proxy upstream host is not configured", status=502)

        query = request.query_string.decode("utf-8", errors="ignore")
        upstream_url = urlunsplit(("http", f"{upstream_host}:{port}", "/" + path, query, ""))

        hop_by_hop = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
            "host",
            "content-length",
        }
        headers = {
            key: value
            for key, value in request.headers
            if key.lower() not in hop_by_hop
        }
        headers["Host"] = f"{upstream_host}:{port}"
        headers["X-Forwarded-For"] = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        headers["X-Forwarded-Host"] = request.host
        headers["X-Forwarded-Proto"] = request.scheme
        headers["X-Forwarded-Prefix"] = url_for(
            "docker_challenge_proxy.proxy_instance",
            tracker_id=tracker_id,
            port=port,
            path="",
        ).rstrip("/")

        try:
            upstream = requests.request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                stream=True,
                timeout=(5, 120),
            )
        except requests.RequestException:
            return Response("Challenge instance is not reachable yet. Try again in a moment.", status=502)

        excluded = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
            "content-encoding",
        }
        response_headers = []
        proxy_prefix = url_for(
            "docker_challenge_proxy.proxy_instance",
            tracker_id=tracker_id,
            port=port,
            path="",
        )
        for key, value in upstream.headers.items():
            lower = key.lower()
            if lower in excluded:
                continue
            if lower == "location":
                parsed = urlsplit(value)
                if parsed.netloc == f"{upstream_host}:{port}":
                    value = urlunsplit(("", "", proxy_prefix.rstrip("/") + parsed.path, parsed.query, parsed.fragment))
                elif value.startswith("/"):
                    value = proxy_prefix.rstrip("/") + value
            response_headers.append((key, value))

        return Response(
            stream_with_context(upstream.iter_content(chunk_size=8192)),
            status=upstream.status_code,
            headers=response_headers,
        )

    app.register_blueprint(challenge_proxy)


class DockerConfig(db.Model):
    """
	Docker Config Model. This model stores the config for docker API connections.
	"""
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column("hostname", db.String(64), index=True)
    display_host = db.Column("display_host", db.String(128), index=True)
    tls_enabled = db.Column("tls_enabled", db.Boolean, default=False, index=True)
    ca_cert = db.Column("ca_cert", db.String(2200), index=True)
    client_cert = db.Column("client_cert", db.String(2000), index=True)
    client_key = db.Column("client_key", db.String(3300), index=True)
    repositories = db.Column("repositories", db.String(1024), index=True)
    container_expiry = db.Column("container_expiry", db.Integer, default=1200)


class DockerChallengeTracker(db.Model):
    """
	Docker Container Tracker. This model stores the users/teams active docker containers.
	"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column("team_id", db.String(64), index=True)
    user_id = db.Column("user_id", db.String(64), index=True)
    docker_image = db.Column("docker_image", db.String(64), index=True)
    timestamp = db.Column("timestamp", db.Integer, index=True)
    revert_time = db.Column("revert_time", db.Integer, index=True)
    instance_id = db.Column("instance_id", db.String(128), index=True)
    ports = db.Column('ports', db.String(128), index=True)
    host = db.Column('host', db.String(128), index=True)
    challenge = db.Column('challenge', db.String(256), index=True)

class DockerConfigForm(BaseForm):
    id = HiddenField()
    hostname = StringField(
        "Docker Hostname", description="The Hostname/IP and Port of your Docker Server"
    )
    display_host = StringField(
        "Display Host", description="IP shown to users for spawned instances (e.g. your WiFi IP). Leave blank to use Docker Hostname."
    )
    tls_enabled = RadioField('TLS Enabled?')
    ca_cert = FileField('CA Cert')
    client_cert = FileField('Client Cert')
    client_key = FileField('Client Key')
    container_expiry = SelectField(
        'Container Duration',
        choices=[('300', '5 Minutes'), ('600', '10 Minutes'), ('1200', '20 Minutes')],
        default='1200',
        description='Maximum lifetime for each spawned Docker container'
    )
    repositories = SelectMultipleField('Repositories')
    submit = SubmitField('Submit')


def define_intro_admin(app):
    admin_intro_config = Blueprint('admin_intro_config', __name__, template_folder='templates',
                                   static_folder='assets')

    @admin_intro_config.route("/admin/intro_config", methods=["GET", "POST"])
    @admins_only
    def intro_config():
        from CTFd.utils import get_config, set_config
        errors = []
        success = False

        if request.method == "POST":
            intro_enabled = request.form.get('intro_enabled', 'disabled')
            intro_file = request.form.get('intro_file', 'intro.html')
            intro_timer_mode = request.form.get('intro_timer_mode', 'none')
            intro_countdown_end = request.form.get('intro_countdown_end', '')
            intro_paused = request.form.get('intro_paused', '0')

            set_config('intro_enabled', intro_enabled)
            set_config('intro_file', intro_file)
            set_config('intro_timer_mode', intro_timer_mode)
            set_config('intro_countdown_end', intro_countdown_end)
            set_config('intro_paused', intro_paused)
            success = True

        # List HTML files from intro/ folder
        intro_dir = os.path.abspath(os.path.join(app.root_path, '../../intro'))
        intro_files = []
        if os.path.isdir(intro_dir):
            for f in os.listdir(intro_dir):
                if f.endswith('.html') or f.endswith('.htm'):
                    intro_files.append(f)
        intro_files.sort()

        return render_template('intro_config.html',
                               intro_enabled=get_config('intro_enabled') or 'disabled',
                               intro_file=get_config('intro_file') or 'intro.html',
                               intro_timer_mode=get_config('intro_timer_mode') or 'none',
                               intro_countdown_end=get_config('intro_countdown_end') or '',
                               intro_paused=get_config('intro_paused') or '0',
                               intro_files=intro_files,
                               errors=errors,
                               success=success,
                               nonce=session.get('nonce'))

    app.register_blueprint(admin_intro_config)


def define_outro_admin(app):
    admin_outro_config = Blueprint('admin_outro_config', __name__, template_folder='templates',
                                   static_folder='assets')

    @admin_outro_config.route("/admin/outro_config", methods=["GET", "POST"])
    @admins_only
    def outro_config():
        from CTFd.utils import get_config, set_config
        errors = []
        success = False

        if request.method == "POST":
            outro_enabled = request.form.get('outro_enabled', 'disabled')
            outro_file = request.form.get('outro_file', 'outro.html')
            outro_access = request.form.get('outro_access', 'authenticated')
            outro_replace_index = request.form.get('outro_replace_index', '0')
            outro_timer_enabled = request.form.get('outro_timer_enabled', '0')
            outro_timer_end = request.form.get('outro_timer_end', '')
            outro_auto_end_ctf = request.form.get('outro_auto_end_ctf', '0')

            set_config('outro_enabled', outro_enabled)
            set_config('outro_file', outro_file)
            set_config('outro_access', outro_access)
            set_config('outro_replace_index', outro_replace_index)
            set_config('outro_timer_enabled', outro_timer_enabled)
            set_config('outro_timer_end', outro_timer_end)
            set_config('outro_auto_end_ctf', outro_auto_end_ctf)

            success = True

        # List HTML files from outro/ folder
        outro_dir = os.path.abspath(os.path.join(app.root_path, '../../outro'))
        outro_files = []
        if os.path.isdir(outro_dir):
            for f in os.listdir(outro_dir):
                if f.endswith('.html') or f.endswith('.htm'):
                    outro_files.append(f)
        outro_files.sort()

        return render_template('outro_config.html',
                               outro_enabled=str(get_config('outro_enabled') or 'disabled'),
                               outro_file=str(get_config('outro_file') or 'outro.html'),
                               outro_access=str(get_config('outro_access') or 'authenticated'),
                               outro_replace_index=str(get_config('outro_replace_index') or '0'),
                               outro_timer_enabled=str(get_config('outro_timer_enabled') or '0'),
                               outro_timer_end=str(get_config('outro_timer_end') or ''),
                               outro_auto_end_ctf=str(get_config('outro_auto_end_ctf') or '0'),
                               outro_files=outro_files,
                               errors=errors,
                               success=success,
                               nonce=session.get('nonce'))

    app.register_blueprint(admin_outro_config)


def define_docker_admin(app):
    admin_docker_config = Blueprint('admin_docker_config', __name__, template_folder='templates',
                                    static_folder='assets')

    @admin_docker_config.route("/admin/docker_config", methods=["GET", "POST"])
    @admins_only
    def docker_config():
        from CTFd.utils import get_config, set_config
        docker = DockerConfig.query.filter_by(id=1).first()
        form = DockerConfigForm()
        if request.method == "POST":
            if docker:
                b = docker
            else:
                b = DockerConfig()
            ca_cert_file = request.files.get('ca_cert')
            client_cert_file = request.files.get('client_cert')
            client_key_file = request.files.get('client_key')

            ca_cert = ca_cert_file.stream.read().decode("utf-8", errors="ignore") if ca_cert_file else ""
            client_cert = client_cert_file.stream.read().decode("utf-8", errors="ignore") if client_cert_file else ""
            client_key = client_key_file.stream.read().decode("utf-8", errors="ignore") if client_key_file else ""

            if len(ca_cert) != 0:
                b.ca_cert = ca_cert
            if len(client_cert) != 0:
                b.client_cert = client_cert
            if len(client_key) != 0:
                b.client_key = client_key

            b.hostname = request.form.get('hostname', '').strip()
            b.display_host = request.form.get('display_host', '').strip()
            b.tls_enabled = request.form.get('tls_enabled') == "True"
            if not b.tls_enabled:
                b.ca_cert = None
                b.client_cert = None
                b.client_key = None
            expiry_val = request.form.get('container_expiry', '1200')
            if expiry_val in ('300', '600', '1200'):
                b.container_expiry = int(expiry_val)
            selected_repositories = request.form.getlist('repositories')
            b.repositories = ','.join(selected_repositories) if selected_repositories else None
            db.session.add(b)
            db.session.commit()
            set_config("docker_proxy_enabled", request.form.get("docker_proxy_enabled", "true"))
            set_config("docker_proxy_upstream_host", request.form.get("docker_proxy_upstream_host", "").strip())
            set_config("docker_proxy_public_base", request.form.get("docker_proxy_public_base", "").strip().rstrip("/"))
            docker = DockerConfig.query.filter_by(id=1).first()
        try:
            if docker:
                repos = get_repositories(docker)
            else:
                repos = []
        except:
            traceback.print_exc()
            repos = list()
        if len(repos) == 0:
            form.repositories.choices = [("ERROR", "Failed to Connect to Docker")]
        else:
            form.repositories.choices = [(d, d) for d in repos]
        dconfig = DockerConfig.query.first()
        if dconfig:
            try:
                selected_repos = dconfig.repositories
                if selected_repos == None:
                    selected_repos = list()
            # selected_repos = dconfig.repositories.split(',')
            except:
                traceback.print_exc()
                selected_repos = []
        else:
            selected_repos = []
        proxy_config = {
            "enabled": get_config("docker_proxy_enabled") if get_config("docker_proxy_enabled") is not None else "true",
            "upstream_host": get_config("docker_proxy_upstream_host") or "",
            "public_base": get_config("docker_proxy_public_base") or "",
        }
        return render_template("docker_config.html", config=dconfig, form=form, repos=selected_repos, proxy_config=proxy_config)

    app.register_blueprint(admin_docker_config)


def define_docker_status(app):
    admin_docker_status = Blueprint('admin_docker_status', __name__, template_folder='templates',
                                    static_folder='assets')

    @admin_docker_status.route("/admin/docker_status", methods=["GET", "POST"])
    @admins_only
    def docker_admin():
        docker_config = DockerConfig.query.filter_by(id=1).first()
        docker_tracker = DockerChallengeTracker.query.all()
        for i in docker_tracker:
            if is_teams_mode():
                name = Teams.query.filter_by(id=i.team_id).first()
                i.team_id = name.name if name else "Unknown"
            else:
                name = Users.query.filter_by(id=i.user_id).first()
                i.user_id = name.name if name else "Unknown"
        return render_template("admin_docker_status.html", dockers=docker_tracker)

    app.register_blueprint(admin_docker_status)


kill_container = Namespace("nuke", description='Endpoint to nuke containers')


@kill_container.route("", methods=['POST', 'GET'])
class KillContainerAPI(Resource):
    @admins_only
    def get(self):
        container = request.args.get('container')
        full = request.args.get('all')
        docker_config = DockerConfig.query.filter_by(id=1).first()
        docker_tracker = DockerChallengeTracker.query.all()
        if full == "true":
            for c in docker_tracker:
                delete_container(docker_config, c.instance_id, ports_str=c.ports)
                DockerChallengeTracker.query.filter_by(instance_id=c.instance_id).delete()
                db.session.commit()

        elif container != 'null' and container in [c.instance_id for c in docker_tracker]:
            tracker_entry = next((c for c in docker_tracker if c.instance_id == container), None)
            delete_container(docker_config, container, ports_str=tracker_entry.ports if tracker_entry else None)
            DockerChallengeTracker.query.filter_by(instance_id=container).delete()
            db.session.commit()

        else:
            return False
        return True
def do_request(docker, url, headers=None, method='GET'):
    if not docker:
        return None
    tls = docker.tls_enabled
    prefix = 'https' if tls else 'http'
    host = docker.hostname
    URL_TEMPLATE = '%s://%s' % (prefix, host)
    try:
        if tls:
            cert, verify = get_client_cert(docker)
            if not cert or not verify:
                return None
            if (method == 'GET'):
                r = requests.get(url=f"%s{url}" % URL_TEMPLATE, cert=cert, verify=verify, headers=headers, timeout=5)
            elif (method == 'DELETE'):
                r = requests.delete(url=f"%s{url}" % URL_TEMPLATE, cert=cert, verify=verify, headers=headers, timeout=5)
            else:
                r = None
            # Clean up the cert files:
            for file_path in [*cert, verify]:
                if file_path:
                    Path(file_path).unlink(missing_ok=True)
        else:
            if (method == 'GET'):
                r = requests.get(url=f"%s{url}" % URL_TEMPLATE, headers=headers, timeout=5)
            elif (method == 'DELETE'):
                r = requests.delete(url=f"%s{url}" % URL_TEMPLATE, headers=headers, timeout=5)
            else:
                r = None
    except:
        r = None
    return r


def docker_api_url(docker):
    if not docker:
        return None
    tls = docker.tls_enabled
    prefix = 'https' if tls else 'http'
    return '%s://%s' % (prefix, docker.hostname)


def do_post(docker, url, data=None, headers=None, timeout=20):
    if not docker:
        return None
    headers = headers or {'Content-Type': "application/json"}
    base_url = docker_api_url(docker)
    if not base_url:
        return None
    try:
        if docker.tls_enabled:
            cert, verify = get_client_cert(docker)
            if not cert or not verify:
                return None
            r = requests.post(
                url=f"{base_url}{url}",
                cert=cert,
                verify=verify,
                data=data,
                headers=headers,
                timeout=timeout,
            )
            for file_path in [*cert, verify]:
                if file_path:
                    Path(file_path).unlink(missing_ok=True)
            return r
        return requests.post(url=f"{base_url}{url}", data=data, headers=headers, timeout=timeout)
    except Exception:
        return None


def decode_docker_exec_output(content):
    """Decode Docker exec output. Non-TTY output is multiplexed with 8-byte stream headers."""
    if not content:
        return ""
    output = bytearray()
    i = 0
    while i + 8 <= len(content):
        stream_type = content[i]
        if stream_type not in (0, 1, 2):
            try:
                return content.decode("utf-8", errors="replace")
            except Exception:
                return str(content)
        size = int.from_bytes(content[i + 4:i + 8], byteorder="big")
        i += 8
        output.extend(content[i:i + size])
        i += size
    if i < len(content):
        output.extend(content[i:])
    return output.decode("utf-8", errors="replace")


def docker_exec_command(docker, instance_id, command, shell="/bin/sh", timeout=20):
    command = (command or "").strip()
    shell = (shell or "/bin/sh").strip()
    if not command:
        return ""
    if len(command) > 4000:
        return "Command is too long.\n"

    create_payload = json.dumps({
        "AttachStdout": True,
        "AttachStderr": True,
        "Tty": False,
        "Cmd": [shell, "-lc", command],
    })
    r = do_post(
        docker,
        f"/containers/{instance_id}/exec",
        data=create_payload,
        headers={'Content-Type': "application/json"},
        timeout=10,
    )
    if r is None:
        return "Could not reach Docker API.\n"
    try:
        payload = r.json()
    except Exception:
        return "Docker did not return a valid exec response.\n"
    exec_id = payload.get("Id")
    if not exec_id:
        return payload.get("message", "Could not create terminal exec session.") + "\n"

    start_payload = json.dumps({"Detach": False, "Tty": False})
    r = do_post(
        docker,
        f"/exec/{exec_id}/start",
        data=start_payload,
        headers={'Content-Type': "application/json"},
        timeout=timeout,
    )
    if r is None:
        return "Command timed out or Docker API was not reachable.\n"
    return decode_docker_exec_output(r.content)


def get_client_cert(docker):
    # this can be done more efficiently, but works for now.
    ca_file = None
    client_file = None
    key_file = None
    try:
        ca = docker.ca_cert
        client = docker.client_cert
        ckey = docker.client_key
        if not ca or not client or not ckey:
            return None, None
        ca_file = tempfile.NamedTemporaryFile(delete=False)
        ca_file.write(ca.encode())
        ca_file.seek(0)
        client_file = tempfile.NamedTemporaryFile(delete=False)
        client_file.write(client.encode())
        client_file.seek(0)
        key_file = tempfile.NamedTemporaryFile(delete=False)
        key_file.write(ckey.encode())
        key_file.seek(0)
        CERT = (client_file.name, key_file.name)
    except:
        for file_path in [
            ca_file.name if ca_file else None,
            client_file.name if client_file else None,
            key_file.name if key_file else None,
        ]:
            if file_path:
                Path(file_path).unlink(missing_ok=True)
        return None, None
    return CERT, ca_file.name


# For the Docker Config Page. Gets the Current Repositories available on the Docker Server.
def get_repositories(docker, tags=False, repos=False):
    r = do_request(docker, '/images/json?all=1')
    if r is None or isinstance(r, list):
        return []
    result = list()
    try:
        data = r.json()
    except:
        return []

    for i in data:
        if not i['RepoTags'] == []:
            if not i['RepoTags'][0].split(':')[0] == '<none>':
                if repos:
                    if not i['RepoTags'][0].split(':')[0] in repos:
                        continue
                if not tags:
                    result.append(i['RepoTags'][0].split(':')[0])
                else:
                    result.append(i['RepoTags'][0])
    return list(set(result))


def get_unavailable_ports(docker):
    r = do_request(docker, '/containers/json?all=1')
    result = list()
    if r is None or isinstance(r, list):
        return result
    for i in r.json():
        if not i['Ports'] == []:
            for p in i['Ports']:
                if 'PublicPort' in p:
                    result.append(p['PublicPort'])
    return result


def get_required_ports(docker, image):
    r = do_request(docker, f'/images/{image}/json?all=1')
    if r is None or isinstance(r, list):
        return []
    image_json = r.json()
    exposed = image_json.get('Config', {}).get('ExposedPorts', {})
    if exposed:
        return exposed.keys()

    # Fallback: try to infer a port from the image command/entrypoint
    cmd = image_json.get('Config', {}).get('Cmd') or []
    entrypoint = image_json.get('Config', {}).get('Entrypoint') or []
    cmdline = " ".join([*entrypoint, *cmd])

    # Common patterns: 0.0.0.0:4500, --bind 0.0.0.0:4500, -b 0.0.0.0:4500
    m = re.search(r"\b(?:0\.0\.0\.0|\[::\]|::|localhost)?:(\d{2,5})\b", cmdline)
    if m:
        return [f"{int(m.group(1))}/tcp"]

    return []


def create_container(docker, image, team, portbl, fallback_container_port=None):
    tls = docker.tls_enabled
    CERT = None
    if not tls:
        prefix = 'http'
    else:
        prefix = 'https'
    host = docker.hostname
    URL_TEMPLATE = '%s://%s' % (prefix, host)
    needed_ports = list(get_required_ports(docker, image) or [])
    if not needed_ports and fallback_container_port:
        needed_ports = [f"{int(fallback_container_port)}/tcp"]
    team = hashlib.md5(team.encode("utf-8")).hexdigest()[:10]
    # Use full image name (repo + tag) for unique container naming
    safe_image = re.sub(r"[^a-zA-Z0-9_.-]", "_", image)
    container_name = f"{safe_image}_{team}"

    assigned_ports = []
    for _ in needed_ports:
        while True:
            assigned_port = random.choice(range(30000, 60000))
            if assigned_port not in portbl:
                assigned_ports.append(str(assigned_port))
                break
    ports = dict()
    bindings = dict()
    tmp_ports = list(assigned_ports)
    for i in needed_ports:
        ports[i] = {}
        bindings[i] = [{"HostPort": tmp_ports.pop()}]
    headers = {'Content-Type': "application/json"}
    data = json.dumps({"Image": image, "ExposedPorts": ports, "HostConfig": {"PortBindings": bindings}})
    if tls:
        cert, verify = get_client_cert(docker)
        r = requests.post(url="%s/containers/create?name=%s" % (URL_TEMPLATE, container_name), cert=cert,
                      verify=verify, data=data, headers=headers)
        result = r.json()
        # Handle name conflict: remove stale container and retry
        if 'Id' not in result and r.status_code == 409:
            requests.delete(url="%s/containers/%s?force=true" % (URL_TEMPLATE, container_name), cert=cert, verify=verify, headers=headers)
            r = requests.post(url="%s/containers/create?name=%s" % (URL_TEMPLATE, container_name), cert=cert,
                              verify=verify, data=data, headers=headers)
            result = r.json()
        if 'Id' not in result:
            return None, data
        s = requests.post(url="%s/containers/%s/start" % (URL_TEMPLATE, result['Id']), cert=cert, verify=verify,
                          headers=headers)
        # Clean up the cert files:
        for file_path in [*cert, verify]:
            if file_path:
                Path(file_path).unlink(missing_ok=True)

    else:
        r = requests.post(url="%s/containers/create?name=%s" % (URL_TEMPLATE, container_name),
                          data=data, headers=headers)
        print(r.request.method, r.request.url, r.request.body)
        result = r.json()
        print(result)
        # Handle name conflict: remove stale container and retry
        if 'Id' not in result and r.status_code == 409:
            requests.delete(url="%s/containers/%s?force=true" % (URL_TEMPLATE, container_name), headers=headers)
            r = requests.post(url="%s/containers/create?name=%s" % (URL_TEMPLATE, container_name),
                              data=data, headers=headers)
            result = r.json()
        if 'Id' not in result:
            return None, data
        s = requests.post(url="%s/containers/%s/start" % (URL_TEMPLATE, result['Id']), headers=headers)
    return result, data


# NOTE: add_port_forward / remove_port_forward are defined near the top of
# the file as no-op stubs (mirrored networking makes them unnecessary).


def delete_container(docker, instance_id, ports_str=None):
    """Stop/remove a container and clean up port forwarding."""
    headers = {'Content-Type': "application/json"}
    # Remove port forwarding for each port
    if ports_str:
        for p in str(ports_str).split(','):
            p = p.strip()
            if p:
                remove_port_forward(p)
    do_request(docker, f'/containers/{instance_id}?force=true', headers=headers, method='DELETE')
    return True


class DockerChallengeType(BaseChallenge):
    id = "docker"
    name = "docker"
    templates = {
        'create': '/plugins/docker_challenges/assets/create.html',
        'update': '/plugins/docker_challenges/assets/update.html',
        'view': '/plugins/docker_challenges/assets/view.html',
    }
    scripts = {
        'create': '/plugins/docker_challenges/assets/create.js',
        'update': '/plugins/docker_challenges/assets/update.js',
        'view': '/plugins/docker_challenges/assets/view.js',
    }
    route = '/plugins/docker_challenges/assets'
    blueprint = Blueprint('docker_challenges', __name__, template_folder='templates', static_folder='assets')

    @staticmethod
    def update(challenge, request):
        """
		This method is used to update the information associated with a challenge. This should be kept strictly to the
		Challenges table and any child tables.

		:param challenge:
		:param request:
		:return:
		"""
        data = request.form or request.get_json()
        for attr, value in data.items():
            setattr(challenge, attr, value)

        db.session.commit()
        return challenge

    @staticmethod
    def delete(challenge):
        """
		This method is used to delete the resources used by a challenge.
		NOTE: Will need to kill all containers here

		:param challenge:
		:return:
		"""
        Fails.query.filter_by(challenge_id=challenge.id).delete()
        Solves.query.filter_by(challenge_id=challenge.id).delete()
        Flags.query.filter_by(challenge_id=challenge.id).delete()
        files = ChallengeFiles.query.filter_by(challenge_id=challenge.id).all()
        for f in files:
            delete_file(f.id)
        ChallengeFiles.query.filter_by(challenge_id=challenge.id).delete()
        Tags.query.filter_by(challenge_id=challenge.id).delete()
        Hints.query.filter_by(challenge_id=challenge.id).delete()
        DockerChallenge.query.filter_by(id=challenge.id).delete()
        Challenges.query.filter_by(id=challenge.id).delete()
        db.session.commit()

    @staticmethod
    def read(challenge):
        """
		This method is in used to access the data of a challenge in a format processable by the front end.

		:param challenge:
		:return: Challenge object, data dictionary to be returned to the user
		"""
        challenge = DockerChallenge.query.filter_by(id=challenge.id).first()
        data = {
            'id': challenge.id,
            'name': challenge.name,
            'value': challenge.value,
            'docker_image': challenge.docker_image,
            'container_expiry': challenge.container_expiry or 1200,
            'access_mode': challenge.access_mode or 'web_proxy',
            'terminal_shell': challenge.terminal_shell or '/bin/sh',
            'description': challenge.description,
            'category': challenge.category,
            'state': challenge.state,
            'max_attempts': challenge.max_attempts,
            'type': challenge.type,
            'type_data': {
                'id': DockerChallengeType.id,
                'name': DockerChallengeType.name,
                'templates': DockerChallengeType.templates,
                'scripts': DockerChallengeType.scripts,
            }
        }
        return data

    @staticmethod
    def create(request):
        """
		This method is used to process the challenge creation request.

		:param request:
		:return:
		"""
        data = request.form or request.get_json()
        challenge = DockerChallenge(**data)
        db.session.add(challenge)
        db.session.commit()
        return challenge

    @staticmethod
    def attempt(challenge, request):
        """
		This method is used to check whether a given input is right or wrong. It does not make any changes and should
		return a boolean for correctness and a string to be shown to the user. It is also in charge of parsing the
		user's input from the request itself.

		:param challenge: The Challenge object from the database
		:param request: The request the user submitted
		:return: (boolean, string)
		"""

        data = request.form or request.get_json()
        print(request.get_json())
        print(data)
        submission = data["submission"].strip()
        flags = Flags.query.filter_by(challenge_id=challenge.id).all()
        for flag in flags:
            if get_flag_class(flag.type).compare(flag, submission):
                return True, "Correct"
        return False, "Incorrect"

    @staticmethod
    def solve(user, team, challenge, request):
        """
		This method is used to insert Solves into the database in order to mark a challenge as solved.

		:param team: The Team object from the database
		:param chal: The Challenge object from the database
		:param request: The request the user submitted
		:return:
		"""
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        docker = DockerConfig.query.filter_by(id=1).first()
        try:
            if is_teams_mode():
                docker_containers = DockerChallengeTracker.query.filter_by(
                    docker_image=challenge.docker_image).filter_by(team_id=team.id).first()
            else:
                docker_containers = DockerChallengeTracker.query.filter_by(
                    docker_image=challenge.docker_image).filter_by(user_id=user.id).first()
            delete_container(docker, docker_containers.instance_id, ports_str=docker_containers.ports)
            DockerChallengeTracker.query.filter_by(instance_id=docker_containers.instance_id).delete()
        except:
            pass
        solve = Solves(
            user_id=user.id,
            team_id=team.id if team else None,
            challenge_id=challenge.id,
            ip=get_ip(req=request),
            provided=submission,
        )
        db.session.add(solve)
        db.session.commit()
        # trying if this solces the detached instance error...
        #db.session.close()

    @staticmethod
    def fail(user, team, challenge, request):
        """
		This method is used to insert Fails into the database in order to mark an answer incorrect.

		:param team: The Team object from the database
		:param chal: The Challenge object from the database
		:param request: The request the user submitted
		:return:
		"""
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        wrong = Fails(
            user_id=user.id,
            team_id=team.id if team else None,
            challenge_id=challenge.id,
            ip=get_ip(request),
            provided=submission,
        )
        db.session.add(wrong)
        db.session.commit()
        #db.session.close()


class DockerChallenge(Challenges):
    __mapper_args__ = {'polymorphic_identity': 'docker'}
    id = db.Column(None, db.ForeignKey('challenges.id'), primary_key=True)
    docker_image = db.Column(db.String(128), index=True)
    container_expiry = db.Column(db.Integer, default=1200)
    access_mode = db.Column(db.String(32), default='web_proxy')
    terminal_shell = db.Column(db.String(128), default='/bin/sh')


def get_current_docker_owner():
    """Return the account/team that owns Docker instances for this request."""
    if is_teams_mode():
        owner = get_current_team()
        if owner is None:
            return None, {
                "success": False,
                "message": "Team mode is enabled. Join or create a team before starting a challenge instance.",
                "data": [],
            }, 403
        return owner, None, None

    owner = get_current_user()
    if owner is None:
        return None, {
            "success": False,
            "message": "Authentication required",
            "data": [],
        }, 403
    return owner, None, None


# API
container_namespace = Namespace("container", description='Endpoint to interact with containers')


@container_namespace.route("", methods=['POST', 'GET'])
class ContainerAPI(Resource):
    # I wish this was Post... Issues with API/CSRF and whatnot. Open to a Issue solving this.
    def get(self):
        if not authed():
            return {"success": False, "message": "Authentication required"}, 403

        container = request.args.get('name')
        if not container:
            return {"success": False, "message": "No container specified"}, 400
        challenge = request.args.get('challenge')
        if not challenge:
            return {"success": False, "message": "No challenge name specified"}, 400
        
        docker = DockerConfig.query.filter_by(id=1).first()
        if not docker or not docker.hostname:
            return {"success": False, "message": "Docker is not configured. Ask admins to configure /admin/docker_config."}, 403

        containers = DockerChallengeTracker.query.all()
        if container not in get_repositories(docker, tags=True):
            return {"success": False, "message": f"Container {container} not present in the repository."}, 403
        session, owner_error, owner_status = get_current_docker_owner()
        if owner_error:
            return owner_error, owner_status

        if is_teams_mode():
            # First we'll delete all old docker containers (+2 hours)
            for i in containers:
                if i.team_id is not None and str(session.id) == str(i.team_id) and (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 7200:
                    delete_container(docker, i.instance_id, ports_str=i.ports)
                    DockerChallengeTracker.query.filter_by(instance_id=i.instance_id).delete()
                    db.session.commit()
            check = DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).first()
        else:
            for i in containers:
                if i.user_id is not None and str(session.id) == str(i.user_id) and (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 7200:
                    delete_container(docker, i.instance_id, ports_str=i.ports)
                    DockerChallengeTracker.query.filter_by(instance_id=i.instance_id).delete()
                    db.session.commit()
            check = DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).first()

        # Extend lifetime — resets timer to full admin-set duration from now
        if check is not None and request.args.get('extend'):
            if check.timestamp is None:
                return {"success": False, "message": "Container timestamp missing; cannot extend"}, 400

            # Look up per-challenge container_expiry
            chal_obj = DockerChallenge.query.filter_by(docker_image=container).first()
            expiry_seconds = (chal_obj.container_expiry if chal_obj and chal_obj.container_expiry else None) \
                             or (docker.container_expiry if docker and docker.container_expiry else 1200)
            new_expiry = unix_time(datetime.utcnow()) + expiry_seconds
            check.revert_time = new_expiry
            check.timestamp = unix_time(datetime.utcnow())  # reset start time
            db.session.commit()
            return {"success": True, "result": "Container extended", "revert_time": new_expiry}, 200

        # Delete when requested
        if check is not None and request.args.get('stopcontainer'):
            delete_container(docker, check.instance_id, ports_str=check.ports)
            if is_teams_mode():
                DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).delete()
            else:
                DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).delete()
            db.session.commit()
            return {"success": True, "result": "Container stopped"}, 200
        # The exception would be if we are reverting a box. So we'll delete it if it exists and has been around for more than 5 minutes.
        elif check is not None:
            delete_container(docker, check.instance_id, ports_str=check.ports)
            if is_teams_mode():
                DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).delete()
            else:
                DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).delete()
            db.session.commit()
        
        # Enforce one active container at a time across all challenge/lab types.
        MAX_CONTAINERS = 1
        containers = DockerChallengeTracker.query.all()
        if is_teams_mode():
            running_count = sum(1 for entry in containers if entry.team_id is not None and str(session.id) == str(entry.team_id))
            if running_count >= MAX_CONTAINERS:
                return {
                    "success": False,
                    "message": "Stop the running container first in order to access another lab.",
                }, 403
        else:
            running_count = sum(1 for entry in containers if entry.user_id is not None and str(session.id) == str(entry.user_id))
            if running_count >= MAX_CONTAINERS:
                return {
                    "success": False,
                    "message": "Stop the running container first in order to access another lab.",
                }, 403

        portsbl = get_unavailable_ports(docker)

        fallback_container_port = None
        try:
            challenge_obj = Challenges.query.filter_by(name=challenge).first()
            connection_info = getattr(challenge_obj, "connection_info", None) or ""
            # Extract a port number from e.g. http://host:4500 or host:4500
            match = re.search(r":(\d{2,5})\b", connection_info)
            if match:
                fallback_container_port = int(match.group(1))
        except Exception:
            fallback_container_port = None

        create = create_container(
            docker,
            container,
            session.name,
            portsbl,
            fallback_container_port=fallback_container_port,
        )
        if not create or not create[0] or 'Id' not in create[0]:
            return {"success": False, "message": "Failed to create Docker container. Check Docker host connectivity and image/tag."}, 403
        ports = json.loads(create[1])['HostConfig']['PortBindings'].values()
        host_ports = [p[0]['HostPort'] for p in ports]
        ports_str = ','.join(host_ports)
        # Set up port forwarding for each assigned port so LAN clients can reach them
        for hp in host_ports:
            add_port_forward(hp, docker.display_host)
        # Look up per-challenge container_expiry for initial timer
        chal_obj = DockerChallenge.query.filter_by(docker_image=container).first()
        initial_expiry = (chal_obj.container_expiry if chal_obj and chal_obj.container_expiry else None) \
                         or (docker.container_expiry if docker and docker.container_expiry else 1200)
        entry = DockerChallengeTracker(
            team_id=session.id if is_teams_mode() else None,
            user_id=session.id if not is_teams_mode() else None,
            docker_image=container,
            timestamp=unix_time(datetime.utcnow()),
            revert_time=unix_time(datetime.utcnow()) + initial_expiry,
            instance_id=create[0]['Id'],
            ports=ports_str,
            host=(docker.display_host or str(docker.hostname).split(':')[0]),
            challenge=challenge
        )
        db.session.add(entry)
        db.session.commit()
        #db.session.close()
        return {"success": True, "result": "Container started"}, 200


active_docker_namespace = Namespace("docker", description='Endpoint to retrieve User Docker Image Status')


@active_docker_namespace.route("", methods=['POST', 'GET'])
class DockerStatus(Resource):
    """
	The Purpose of this API is to retrieve a public JSON string of all docker containers
	in use by the current team/user.
	"""

    def get(self):
        if not authed():
            return {"success": False, "message": "Authentication required", "data": []}, 403

        docker = DockerConfig.query.filter_by(id=1).first()
        docker_host = (docker.display_host or get_docker_api_host(docker)) if docker and docker.hostname else ""
        use_proxy = docker_proxy_enabled()
        session, owner_error, owner_status = get_current_docker_owner()
        if owner_error:
            return owner_error, owner_status

        if is_teams_mode():
            tracker = DockerChallengeTracker.query.filter_by(team_id=session.id)
        else:
            tracker = DockerChallengeTracker.query.filter_by(user_id=session.id)

        # Clean up expired containers (based on revert_time)
        try:
            now = unix_time(datetime.utcnow())
            for entry in list(tracker):
                if entry.revert_time and int(entry.revert_time) <= now:
                    if docker:
                        delete_container(docker, entry.instance_id, ports_str=entry.ports)
                    DockerChallengeTracker.query.filter_by(instance_id=entry.instance_id).delete()
                    db.session.commit()
        except Exception:
            pass

        # If an older tracker entry has no ports saved, try to pull the host ports from Docker inspect
        try:
            for entry in tracker:
                if not entry.ports or not str(entry.ports).strip():
                    if not docker:
                        continue
                    r = do_request(docker, f"/containers/{entry.instance_id}/json")
                    if r is None:
                        continue
                    inspect = r.json()
                    ports = inspect.get("NetworkSettings", {}).get("Ports", {}) or {}
                    host_ports = []
                    for bindings in ports.values():
                        if not bindings:
                            continue
                        for b in bindings:
                            hp = b.get("HostPort")
                            if hp:
                                host_ports.append(str(hp))
                    if host_ports:
                        entry.ports = ",".join(sorted(set(host_ports)))
            db.session.commit()
        except Exception:
            pass

        data = list()
        for i in tracker:
            ports_value = (i.ports or "").strip()
            ports_list = [p for p in ports_value.split(',') if p] if ports_value else []
            revert_time_value = i.revert_time
            if (revert_time_value is None or revert_time_value == 0) and i.timestamp is not None:
                revert_time_value = int(i.timestamp) + 300
            # Per-challenge expiry (fallback to global config, then 1200)
            chal_obj = DockerChallenge.query.filter_by(docker_image=i.docker_image).first()
            chal_expiry = (chal_obj.container_expiry if chal_obj and chal_obj.container_expiry else None) \
                          or (docker.container_expiry if docker and docker.container_expiry else 1200)
            access_mode = (chal_obj.access_mode if chal_obj and chal_obj.access_mode else 'web_proxy')
            expose_proxy_url = use_proxy and access_mode == 'web_proxy'
            data.append({
                'id': i.id,
                'team_id': i.team_id,
                'user_id': i.user_id,
                'docker_image': i.docker_image,
                'timestamp': i.timestamp,
                'revert_time': revert_time_value,
                'instance_id': i.instance_id,
                'ports': ports_list,
                'host': docker_host,
                'access_mode': access_mode,
                'terminal_enabled': access_mode == 'terminal',
                'terminal_shell': chal_obj.terminal_shell if chal_obj and chal_obj.terminal_shell else '/bin/sh',
                'connection_mode': 'proxy' if expose_proxy_url else 'direct',
                'connection_url': build_proxy_url(i.id, ports_list[0]) if expose_proxy_url and ports_list else '',
                'container_expiry': chal_expiry
            })
        return {
            'success': True,
            'data': data
        }


terminal_namespace = Namespace("docker_terminal", description='Endpoint to run terminal commands inside owned challenge containers')


def owns_tracker_entry(tracker_entry):
    if not authed() or tracker_entry is None:
        return False
    if is_teams_mode():
        team = get_current_team()
        return team is not None and str(tracker_entry.team_id) == str(team.id)
    user = get_current_user()
    return user is not None and str(tracker_entry.user_id) == str(user.id)


@terminal_namespace.route("", methods=['POST'])
class DockerTerminalAPI(Resource):
    @authed_only
    def post(self):
        data = request.get_json(silent=True) or request.form or {}
        tracker_id = data.get("tracker_id")
        command = data.get("command", "")
        if not tracker_id:
            return {"success": False, "message": "Missing terminal instance id"}, 400

        tracker_entry = DockerChallengeTracker.query.filter_by(id=tracker_id).first()
        if not owns_tracker_entry(tracker_entry):
            return {"success": False, "message": "Terminal not found or not owned by this account"}, 403

        chal_obj = DockerChallenge.query.filter_by(docker_image=tracker_entry.docker_image).first()
        if not chal_obj or (chal_obj.access_mode or "web_proxy") != "terminal":
            return {"success": False, "message": "This challenge is not configured for terminal access"}, 403

        docker = DockerConfig.query.filter_by(id=1).first()
        if not docker or not docker.hostname:
            return {"success": False, "message": "Docker is not configured"}, 403

        now = unix_time(datetime.utcnow())
        if tracker_entry.revert_time and int(tracker_entry.revert_time) <= now:
            delete_container(docker, tracker_entry.instance_id, ports_str=tracker_entry.ports)
            DockerChallengeTracker.query.filter_by(instance_id=tracker_entry.instance_id).delete()
            db.session.commit()
            return {"success": False, "message": "This terminal instance has expired"}, 410

        output = docker_exec_command(
            docker,
            tracker_entry.instance_id,
            command,
            shell=chal_obj.terminal_shell or "/bin/sh",
        )
        return {"success": True, "output": output}


docker_namespace = Namespace("docker", description='Endpoint to retrieve dockerstuff')


@docker_namespace.route("", methods=['POST', 'GET'])
class DockerAPI(Resource):
    """
	This is for creating Docker Challenges. The purpose of this API is to populate the Docker Image Select form
	object in the Challenge Creation Screen.
	"""

    @admins_only
    def get(self):
        docker = DockerConfig.query.filter_by(id=1).first()
        if not docker or not docker.hostname:
            return {
                'success': False,
                'data': []
            }

        selected_repositories = []
        if docker.repositories:
            selected_repositories = [repo.strip() for repo in docker.repositories.split(',') if repo.strip()]

        images = get_repositories(docker, tags=True, repos=selected_repositories)
        if images:
            data = list()
            for i in images:
                data.append({'name': i})
            return {
                'success': True,
                'data': data
            }
        else:
            return {
                       'success': False,
                       'data': [
                           {
                               'name': 'Error in Docker Config!'
                           }
                       ]
                   }, 400



def load(app):
    app.db.create_all()
    # Auto-migrate: add missing columns to existing tables
    with app.app_context():
        from sqlalchemy import inspect as sa_inspect, text
        insp = sa_inspect(app.db.engine)
        migrations = []
        # docker_config.display_host
        if 'docker_config' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('docker_config')]
            if 'display_host' not in cols:
                migrations.append('ALTER TABLE docker_config ADD COLUMN display_host VARCHAR(128)')
            if 'container_expiry' not in cols:
                migrations.append('ALTER TABLE docker_config ADD COLUMN container_expiry INTEGER DEFAULT 1200')
            else:
                # Update old default (300) or NULL to new default (1200)
                migrations.append('UPDATE docker_config SET container_expiry = 1200 WHERE container_expiry IS NULL OR container_expiry = 300')
        # docker_challenge_tracker columns
        if 'docker_challenge_tracker' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('docker_challenge_tracker')]
            if 'host' not in cols:
                migrations.append('ALTER TABLE docker_challenge_tracker ADD COLUMN host VARCHAR(128)')
            if 'challenge' not in cols:
                migrations.append('ALTER TABLE docker_challenge_tracker ADD COLUMN challenge VARCHAR(256)')
        # docker_challenge (challenges child table) columns
        if 'docker_challenge' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('docker_challenge')]
            if 'container_expiry' not in cols:
                migrations.append('ALTER TABLE docker_challenge ADD COLUMN container_expiry INTEGER DEFAULT 1200')
            if 'access_mode' not in cols:
                migrations.append("ALTER TABLE docker_challenge ADD COLUMN access_mode VARCHAR(32) DEFAULT 'web_proxy'")
            if 'terminal_shell' not in cols:
                migrations.append("ALTER TABLE docker_challenge ADD COLUMN terminal_shell VARCHAR(128) DEFAULT '/bin/sh'")
        if migrations:
            with app.db.engine.connect() as conn:
                for sql in migrations:
                    conn.execute(text(sql))
                try:
                    conn.commit()
                except Exception:
                    pass  # autocommit mode on older SA
    CHALLENGE_CLASSES['docker'] = DockerChallengeType
    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
        return datetime.fromtimestamp(value).strftime(format)
    register_plugin_assets_directory(app, base_path='/plugins/docker_challenges/assets')
    define_docker_admin(app)
    define_intro_admin(app)
    register_admin_plugin_menu_bar('Intro', '/admin/intro_config')
    define_outro_admin(app)
    register_admin_plugin_menu_bar('Outro', '/admin/outro_config')
    define_docker_status(app)
    define_challenge_proxy(app)
    CTFd_API_v1.add_namespace(docker_namespace, '/docker')
    CTFd_API_v1.add_namespace(container_namespace, '/container')
    CTFd_API_v1.add_namespace(active_docker_namespace, '/docker_status')
    CTFd_API_v1.add_namespace(terminal_namespace, '/docker_terminal')
    CTFd_API_v1.add_namespace(kill_container, '/nuke')
