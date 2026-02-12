import os
import sqlite3

DB_PATH = r"c:/Users/Liyander/Downloads/TomCTF/CTFd/CTFd/ctfd.db"


def main():
    hostname = os.environ.get("DOCKER_PLUGIN_HOSTNAME", "").strip()
    repositories = os.environ.get("DOCKER_PLUGIN_REPOSITORIES", "").strip() or None
    if not hostname:
        raise SystemExit("DOCKER_PLUGIN_HOSTNAME is required")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS docker_config (
            id INTEGER PRIMARY KEY,
            hostname VARCHAR(64),
            tls_enabled BOOLEAN,
            ca_cert VARCHAR(2200),
            client_cert VARCHAR(2000),
            client_key VARCHAR(3300),
            repositories VARCHAR(1024)
        )
        """
    )

    cur.execute("SELECT id FROM docker_config WHERE id = 1")
    exists = cur.fetchone() is not None

    if exists:
        cur.execute(
            """
            UPDATE docker_config
            SET hostname = ?, tls_enabled = ?, ca_cert = NULL, client_cert = NULL, client_key = NULL, repositories = ?
            WHERE id = 1
            """,
            (hostname, 0, repositories),
        )
    else:
        cur.execute(
            """
            INSERT INTO docker_config (id, hostname, tls_enabled, ca_cert, client_cert, client_key, repositories)
            VALUES (1, ?, ?, NULL, NULL, NULL, ?)
            """,
            (hostname, 0, repositories),
        )

    conn.commit()

    row = cur.execute("SELECT id, hostname, tls_enabled, repositories FROM docker_config WHERE id = 1").fetchone()
    print(f"docker_config saved: {row}")

    conn.close()


if __name__ == "__main__":
    main()
