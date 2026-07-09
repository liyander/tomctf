# Docker challenge proxy setup

This plugin can now publish player instances through CTFd instead of exposing every dynamic challenge port to players.

## What changes

- Players receive a URL like `/challenge-proxy/<instance>/<port>/`.
- CTFd verifies the logged-in user or team owns that Docker instance.
- CTFd forwards the request to the private Docker host/port.
- Other players cannot access another instance through the proxy because ownership is checked before forwarding.

## Recommended network layout

```text
Players
  |
  | HTTPS/HTTP to CTFd only
  v
CTFd server
  |
  | private/admin network to Docker host challenge ports
  v
Docker challenge host
```

Only CTFd needs to reach the Docker host's published container ports. Those ports do not need to be public to players.

If Docker is on another server, set this in `/admin/docker_config`:

- Proxy Mode: `Enabled`
- Proxy Upstream Host: private IP/DNS that the CTFd server can reach, for example `10.0.0.20`
- Public CTFd Base URL: your public CTFd URL, for example `https://ctf.example.com`

## Important notes

- This is an HTTP/HTTPS reverse proxy for web challenge apps.
- Raw TCP services such as SSH, nc, custom binary protocols, and game servers cannot be safely multiplexed through this HTTP path. For those, keep direct port access or add a protocol-specific gateway.
- Challenge apps work best when they use relative links. Apps that hard-code absolute `/static/...` paths may need to respect `X-Forwarded-Prefix` or be adjusted to serve under a path prefix.
- Do not expose the Docker API publicly. If Docker runs remotely, restrict Docker API access to the CTFd server only and use TLS where possible.
