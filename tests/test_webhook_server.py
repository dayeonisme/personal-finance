import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from unittest.mock import patch

import pytest

from webhook_server import HOST, _make_handler, create_app


def _start_test_server(app, port: int) -> HTTPServer:
    server = HTTPServer((HOST, port), _make_handler(app))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_server_binds_to_localhost():
    assert HOST == "127.0.0.1"


def test_post_run_returns_200_on_success():
    app = create_app()
    with patch.object(app, "handle_run_request", return_value={"exit_code": 0, "stdout": ""}):
        server = _start_test_server(app, 19001)
        try:
            req = urllib.request.Request(f"http://{HOST}:19001/run", method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                body = json.loads(resp.read())
                assert body["exit_code"] == 0
        finally:
            server.shutdown()


def test_post_run_returns_500_on_failure():
    app = create_app()
    with patch.object(app, "handle_run_request", return_value={"exit_code": 1, "stdout": ""}):
        server = _start_test_server(app, 19002)
        try:
            req = urllib.request.Request(f"http://{HOST}:19002/run", method="POST")
            try:
                urllib.request.urlopen(req, timeout=5)
                pytest.fail("Expected HTTPError 500")
            except urllib.error.HTTPError as e:
                assert e.code == 500
        finally:
            server.shutdown()


def test_post_unknown_path_returns_404():
    app = create_app()
    server = _start_test_server(app, 19003)
    try:
        req = urllib.request.Request(f"http://{HOST}:19003/unknown", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            pytest.fail("Expected HTTPError 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
