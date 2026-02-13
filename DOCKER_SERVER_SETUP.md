# Setting Up a Remote Linux Docker Server for T0MCTF

This guide covers configuring a **separate Linux server** to host Docker challenge containers, with CTFd connecting to it remotely via the Docker API.

---

## Architecture

```
┌──────────────────┐         Docker API (TCP)        ┌──────────────────────┐
│   CTFd Server    │ ──────────────────────────────►  │   Linux Docker Host  │
│  (Windows/Any)   │       http://<IP>:2375           │  Runs all challenge  │
│  Port 4000       │   or  https://<IP>:2376 (TLS)    │  containers          │
└──────────────────┘                                  └──────────────────────┘
                                                        Players connect here
                                                        http://<IP>:30000-60000
```

- **CTFd** manages challenges, users, scoreboards — runs anywhere.
- **Docker Host** runs the actual challenge containers — must be a Linux server.
- Players access containers directly at `<Docker Server IP>:<assigned_port>`.

---

## Part 1: Linux Server Setup

### 1.1 Install Docker

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sudo sh

# Add your user to the docker group (avoid needing sudo)
sudo usermod -aG docker $USER

# Start and enable Docker
sudo systemctl enable docker
sudo systemctl start docker

# Verify
docker --version
docker run hello-world
```

### 1.2 Expose Docker API over TCP

The CTFd Docker plugin communicates with Docker via its HTTP API. You need to expose it on a TCP port.

#### Option A: Without TLS (Simple — LAN/trusted network only)

> ⚠️ **WARNING**: This exposes full Docker control with NO authentication. Only use on a private/trusted network (e.g., LAN for your CTF event). Never expose port 2375 to the internet.

```bash
# Create override directory
sudo mkdir -p /etc/systemd/system/docker.service.d

# Create override config
sudo tee /etc/systemd/system/docker.service.d/override.conf > /dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd -H unix:///var/run/docker.sock -H tcp://0.0.0.0:2375
EOF

# Reload and restart Docker
sudo systemctl daemon-reload
sudo systemctl restart docker

# Verify it's listening
ss -tlnp | grep 2375
# Should show: 0.0.0.0:2375
```

**Test from CTFd machine:**
```bash
curl http://<DOCKER_SERVER_IP>:2375/version
```
You should get a JSON response with Docker version info.

#### Option B: With TLS (Recommended for production / untrusted networks)

Generate certificates on the Docker server:

```bash
# Create a directory for certs
mkdir -p ~/docker-certs && cd ~/docker-certs

# Set your Docker server's IP or hostname
export DOCKER_HOST_IP="<YOUR_DOCKER_SERVER_IP>"

# Generate CA key and cert
openssl genrsa -aes256 -out ca-key.pem 4096
openssl req -new -x509 -days 365 -key ca-key.pem -sha256 -out ca.pem \
  -subj "/CN=DockerCA"

# Generate server key and CSR
openssl genrsa -out server-key.pem 4096
openssl req -new -key server-key.pem -out server.csr \
  -subj "/CN=$DOCKER_HOST_IP"

# Create extensions file for SAN
echo "subjectAltName = IP:$DOCKER_HOST_IP,IP:127.0.0.1" > extfile.cnf
echo "extendedKeyUsage = serverAuth" >> extfile.cnf

# Sign the server cert
openssl x509 -req -days 365 -sha256 \
  -in server.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial \
  -out server-cert.pem -extfile extfile.cnf

# Generate client key and CSR
openssl genrsa -out client-key.pem 4096
openssl req -new -key client-key.pem -out client.csr \
  -subj "/CN=client"

# Create client extensions
echo "extendedKeyUsage = clientAuth" > client-extfile.cnf

# Sign the client cert
openssl x509 -req -days 365 -sha256 \
  -in client.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial \
  -out client-cert.pem -extfile client-extfile.cnf

# Set permissions
chmod 0400 ca-key.pem server-key.pem client-key.pem
chmod 0444 ca.pem server-cert.pem client-cert.pem
```

Configure Docker to use TLS:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d

sudo tee /etc/systemd/system/docker.service.d/override.conf > /dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd \
  -H unix:///var/run/docker.sock \
  -H tcp://0.0.0.0:2376 \
  --tlsverify \
  --tlscacert=$HOME/docker-certs/ca.pem \
  --tlscert=$HOME/docker-certs/server-cert.pem \
  --tlskey=$HOME/docker-certs/server-key.pem
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker
```

**Copy these 3 files to your CTFd machine** (you'll upload them in the admin panel):
- `ca.pem` — CA Certificate
- `client-cert.pem` — Client Certificate
- `client-key.pem` — Client Key

### 1.3 Firewall Configuration

Open the required ports:

```bash
# Docker API
sudo ufw allow 2375/tcp    # Without TLS
# OR
sudo ufw allow 2376/tcp    # With TLS

# Challenge container port range
sudo ufw allow 30000:60000/tcp

# Apply
sudo ufw enable
```

If using `iptables` instead of `ufw`:

```bash
sudo iptables -A INPUT -p tcp --dport 2375 -j ACCEPT
sudo iptables -A INPUT -p tcp --match multiport --dports 30000:60000 -j ACCEPT
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

### 1.4 Load Challenge Docker Images

Transfer your challenge images to the Linux server. You have two options:

#### Option A: Build from Dockerfiles on the server

```bash
# Copy your challenge source to the server, then build
cd /path/to/challenge-source
docker build -t shield-omega:latest .
docker build -t linkedin-ctf:latest .
docker build -t shield-ctf:latest .
```

#### Option B: Export from current machine, import on server

On your **current machine** (WSL/Windows):

```bash
# Save images to tar files
docker save shield-omega:latest -o shield-omega.tar
docker save linkedin-ctf:latest -o linkedin-ctf.tar
docker save shield-ctf:latest -o shield-ctf.tar
```

Transfer the `.tar` files to the Linux server (via `scp`, USB, etc.):

```bash
scp shield-omega.tar shield-ctf.tar linkedin-ctf.tar user@<SERVER_IP>:/tmp/
```

On the **Linux server**:

```bash
docker load -i /tmp/shield-omega.tar
docker load -i /tmp/linkedin-ctf.tar
docker load -i /tmp/shield-ctf.tar

# Verify
docker images
```

### 1.5 Test Containers Manually

```bash
# Test that a container runs and is accessible
docker run -d --name test -p 45000:4500 shield-omega:latest
curl http://localhost:45000
# Should return HTML — the challenge is working

# Clean up
docker rm -f test
```

---

## Part 2: CTFd Configuration

### 2.1 Configure Docker Host in CTFd Admin Panel

1. Open CTFd → **Admin Panel** → **Docker Config** (`/admin/docker_config`)

2. Fill in the fields:

   | Field | Without TLS | With TLS |
   |-------|-------------|----------|
   | **Docker Hostname** | `<SERVER_IP>:2375` | `<SERVER_IP>:2376` |
   | **Display Host** | `<SERVER_IP>` | `<SERVER_IP>` |
   | **TLS Enabled** | `False` | `True` |
   | **CA Cert** | _(leave empty)_ | Upload `ca.pem` |
   | **Client Cert** | _(leave empty)_ | Upload `client-cert.pem` |
   | **Client Key** | _(leave empty)_ | Upload `client-key.pem` |

3. Click **Submit**.

4. Your Docker images should appear in the **Repositories** list. Select the ones you want to use and click **Submit** again.

> **Display Host** is the IP shown to players. Set it to the Docker server's IP so players connect directly to the server where containers run. No port forwarding or proxying needed!

### 2.2 Verify Connection

After saving the config:
- The Repositories dropdown should list your images (e.g., `shield-omega:latest`, `linkedin-ctf:latest`).
- If it shows **"Failed to Connect to Docker"**, check:
  - Server IP and port are correct
  - Docker is running on the server (`sudo systemctl status docker`)
  - Firewall allows the connection
  - TLS certs are correct (if using TLS)

### 2.3 Test a Challenge

1. Go to **Challenges** → pick a Docker challenge → click **Start Instance**.
2. CTFd should spawn a container on the remote server.
3. The challenge URL shown to players will be `http://<Display_Host>:<port>`.
4. Open that URL — it should load the challenge.

---

## Part 3: Production Hardening (Optional but Recommended)

### 3.1 Limit Container Resources

Prevent challenge containers from consuming all server resources. Edit the `create_container` function in the plugin or add Docker daemon defaults:

```bash
# /etc/docker/daemon.json
{
  "default-runtime": "runc",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### 3.2 Network Isolation

Create a dedicated Docker network for challenges:

```bash
docker network create --driver bridge ctf-challenges
```

### 3.3 Auto-Cleanup Cron

CTFd has a 2-hour stale container nuke, but as a safety net:

```bash
# Add to crontab (sudo crontab -e)
# Kill containers running longer than 3 hours
0 * * * * docker ps --filter "status=running" --format '{{.ID}} {{.RunningFor}}' | awk '/hours/ && $2 > 3 {print $1}' | xargs -r docker rm -f
```

### 3.4 Monitor Server

```bash
# Watch running containers
watch docker ps

# Check resource usage
docker stats

# Check Docker logs
sudo journalctl -u docker -f
```

---

## Quick Reference

| Item | Value |
|------|-------|
| Docker API (no TLS) | `http://<SERVER_IP>:2375` |
| Docker API (TLS) | `https://<SERVER_IP>:2376` |
| Container port range | `30000–60000` |
| CTFd Docker Config page | `/admin/docker_config` |
| CTFd Docker Status page | `/admin/docker_status` |
| Display Host | Set to Docker server's IP |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Failed to Connect to Docker" | Check firewall, Docker service status, hostname:port |
| Containers spawn but unreachable | Open ports 30000-60000 in firewall |
| TLS handshake fails | Verify SAN in server cert matches the IP you're connecting to |
| Images not showing | Make sure images are loaded (`docker images`) and repos are selected in config |
| Container exits immediately | Check image works locally: `docker run -it <image> /bin/sh` |
| Port conflicts | The plugin picks random ports 30000-60000; ensure nothing else uses that range |

---

## Summary

The key difference from the WSL2 setup: **no port forwarding or TCP proxy needed**. Since Docker runs natively on Linux and binds `0.0.0.0`, containers are directly accessible from any machine on the network. Just point CTFd's Docker Hostname to `<SERVER_IP>:2375` and set Display Host to `<SERVER_IP>`.
