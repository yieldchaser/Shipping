import http.server
import socket
import threading
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="session")
def web_server():
    """Starts a local HTTP server serving the repo root on an ephemeral port."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port),
        lambda *args: QuietHandler(*args, directory=str(REPO_ROOT))
    )
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    httpd.shutdown()
