import traceback

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
from flask import request, Blueprint, jsonify, abort, render_template, url_for, redirect, session
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
    repositories = SelectMultipleField('Repositories')
    submit = SubmitField('Submit')


def define_docker_admin(app):
    admin_docker_config = Blueprint('admin_docker_config', __name__, template_folder='templates',
                                    static_folder='assets')

    @admin_docker_config.route("/admin/docker_config", methods=["GET", "POST"])
    @admins_only
    def docker_config():
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
            selected_repositories = request.form.getlist('repositories')
            b.repositories = ','.join(selected_repositories) if selected_repositories else None
            db.session.add(b)
            db.session.commit()
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
        return render_template("docker_config.html", config=dconfig, form=form, repos=selected_repos)

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
    tag = image.split(":", 1)[1] if ":" in image else "latest"
    safe_tag = re.sub(r"[^a-zA-Z0-9_.-]", "_", tag)
    container_name = f"{safe_tag}_{team}"

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
        if is_teams_mode():
            session = get_current_team()
            # First we'll delete all old docker containers (+2 hours)
            for i in containers:
                if int(session.id) == int(i.team_id) and (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 7200:
                    delete_container(docker, i.instance_id, ports_str=i.ports)
                    DockerChallengeTracker.query.filter_by(instance_id=i.instance_id).delete()
                    db.session.commit()
            check = DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).first()
        else:
            session = get_current_user()
            for i in containers:
                if int(session.id) == int(i.user_id) and (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 7200:
                    delete_container(docker, i.instance_id, ports_str=i.ports)
                    DockerChallengeTracker.query.filter_by(instance_id=i.instance_id).delete()
                    db.session.commit()
            check = DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).first()

        # Extend lifetime to at most 10 minutes total (from creation timestamp)
        if check is not None and request.args.get('extend'):
            extend_value = str(request.args.get('extend')).strip()
            if extend_value != '10':
                return {"success": False, "message": "Unsupported extend value"}, 400
            if check.timestamp is None:
                return {"success": False, "message": "Container timestamp missing; cannot extend"}, 400

            max_expiry = int(check.timestamp) + 600
            # Cap expiry strictly to 10 minutes total from start
            check.revert_time = max_expiry
            db.session.commit()
            return {"success": True, "result": "Container extended", "revert_time": max_expiry}, 200

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
        
        # Check if too many containers are already running for this team/user.
        MAX_CONTAINERS = 3
        containers = DockerChallengeTracker.query.all()
        if is_teams_mode():
            running_count = sum(1 for entry in containers if entry.team_id is not None and str(session.id) == str(entry.team_id))
            if running_count >= MAX_CONTAINERS:
                return {
                    "success": False,
                    "message": f"You already have {running_count} containers running. Please stop one first. Maximum allowed: {MAX_CONTAINERS}.",
                }, 403
        else:
            running_count = sum(1 for entry in containers if entry.user_id is not None and str(session.id) == str(entry.user_id))
            if running_count >= MAX_CONTAINERS:
                return {
                    "success": False,
                    "message": f"You already have {running_count} containers running. Please stop one first. Maximum allowed: {MAX_CONTAINERS}.",
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
        entry = DockerChallengeTracker(
            team_id=session.id if is_teams_mode() else None,
            user_id=session.id if not is_teams_mode() else None,
            docker_image=container,
            timestamp=unix_time(datetime.utcnow()),
            revert_time=unix_time(datetime.utcnow()) + 300,
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
        docker_host = (docker.display_host or str(docker.hostname).split(':')[0]) if docker and docker.hostname else ""
        if is_teams_mode():
            session = get_current_team()
            tracker = DockerChallengeTracker.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
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
            data.append({
                'id': i.id,
                'team_id': i.team_id,
                'user_id': i.user_id,
                'docker_image': i.docker_image,
                'timestamp': i.timestamp,
                'revert_time': revert_time_value,
                'instance_id': i.instance_id,
                'ports': ports_list,
                'host': docker_host
            })
        return {
            'success': True,
            'data': data
        }


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
        # docker_challenge_tracker columns
        if 'docker_challenge_tracker' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('docker_challenge_tracker')]
            if 'host' not in cols:
                migrations.append('ALTER TABLE docker_challenge_tracker ADD COLUMN host VARCHAR(128)')
            if 'challenge' not in cols:
                migrations.append('ALTER TABLE docker_challenge_tracker ADD COLUMN challenge VARCHAR(256)')
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
    define_docker_status(app)
    CTFd_API_v1.add_namespace(docker_namespace, '/docker')
    CTFd_API_v1.add_namespace(container_namespace, '/container')
    CTFd_API_v1.add_namespace(active_docker_namespace, '/docker_status')
    CTFd_API_v1.add_namespace(kill_container, '/nuke')
