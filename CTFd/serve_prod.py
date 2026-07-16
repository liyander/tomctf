"""Production server for CTFd.

Run with:  python serve_prod.py [--port 8000] [--workers auto]

Uses gevent's WSGI server (already a CTFd dependency) instead of the Flask
debug server that serve.py starts. Differences that matter for performance:

- Templates are compiled once and cached (debug mode recompiles per request)
- Static/theme assets are served with cache headers instead of no-cache
- Thousands of concurrent connections are handled via greenlets

For events (notifications) CTFd needs an async-capable server, which gevent
provides. Do NOT use serve.py (debug=True) with real players.
"""
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
parser.add_argument("--host", default="0.0.0.0", help="Address to bind")
args = parser.parse_args()

from gevent import monkey

monkey.patch_all()

from gevent.pywsgi import WSGIServer

# Import after monkey patching
from CTFd import create_app

app = create_app()

# Make sure nothing left us in debug/auto-reload mode
app.debug = False
app.config["DEBUG"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = False
app.jinja_env.auto_reload = False
# Cache static assets in the browser for a year; CTFd cache-busts theme
# assets per server restart via the ?d= query parameter.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000

if __name__ == "__main__":
    print(f" * CTFd production server on http://{args.host}:{args.port}")
    http_server = WSGIServer((args.host, args.port), app, log=None)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.stop()
