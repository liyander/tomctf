from CTFd import create_app
from CTFd.models import db
from CTFd.plugins.docker_challenges import DockerConfig
import os


def main():
    hostname = os.environ.get("DOCKER_PLUGIN_HOSTNAME", "").strip()
    repositories = os.environ.get("DOCKER_PLUGIN_REPOSITORIES", "").strip()
    if not hostname:
        raise SystemExit("DOCKER_PLUGIN_HOSTNAME is required")

    app = create_app()
    with app.app_context():
        cfg = DockerConfig.query.filter_by(id=1).first()
        if not cfg:
            cfg = DockerConfig(id=1)

        cfg.hostname = hostname
        cfg.tls_enabled = False
        cfg.ca_cert = None
        cfg.client_cert = None
        cfg.client_key = None
        cfg.repositories = repositories or None

        db.session.add(cfg)
        db.session.commit()
        print(f"Configured docker_challenges: host={cfg.hostname}, repos={cfg.repositories}")


if __name__ == "__main__":
    main()
