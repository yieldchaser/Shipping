import http.server
import socket
import sys
import threading
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))


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


# ---------------------------------------------------------------------------
# Leave the working tree as the run found it.
#
# Several tests run the real builders on the real data (build_bunker_cache.py,
# build_comment_chunks.py, build_desk_caches.py, compute_port_stress_matrix.py,
# ...) and then check what they wrote. That is the point of those tests, but it
# rewrote about a dozen tracked files under data/ with fresh content on every
# local run and left them showing as modified. At session start this records
# which tracked files under data/ are already modified and which untracked files
# exist; at the end it restores every tracked file the run changed and removes
# every file the run created. Files you had already edited are never touched.
# ---------------------------------------------------------------------------
import subprocess as _subprocess

_REPO = Path(__file__).resolve().parent.parent
_GUARDED = ["data"]


def _git_lines(*args):
    r = _subprocess.run(["git", *args], cwd=_REPO, capture_output=True, text=True)
    return set(r.stdout.splitlines()) if r.returncode == 0 else None


def pytest_sessionstart(session):
    session.config._data_dirty_before = _git_lines("diff", "--name-only", "--", *_GUARDED)
    session.config._data_untracked_before = _git_lines(
        "ls-files", "--others", "--exclude-standard", "--", *_GUARDED)


def pytest_sessionfinish(session, exitstatus):
    before_dirty = getattr(session.config, "_data_dirty_before", None)
    before_new = getattr(session.config, "_data_untracked_before", None)
    if before_dirty is None or before_new is None:
        return  # not a git checkout
    changed = sorted((_git_lines("diff", "--name-only", "--", *_GUARDED) or set()) - before_dirty)
    created = sorted((_git_lines("ls-files", "--others", "--exclude-standard", "--", *_GUARDED) or set()) - before_new)
    if changed:
        _subprocess.run(["git", "checkout", "--", *changed], cwd=_REPO, capture_output=True)
    for rel in created:
        try:
            (_REPO / rel).unlink()
        except OSError:
            pass
    if changed or created:
        print(f"\n[conftest] restored {len(changed)} data file(s) and removed {len(created)} created by tests")
