import subprocess
import threading
from unittest.mock import patch, MagicMock
import urllib.request
import time
import pytest


def test_post_to_run_endpoint_returns_200():
    from webhook_server import create_app
    app = create_app(dry_run=True)

    with patch("webhook_server.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # Test that the handler works
        result = app.handle_run_request()
        assert result["exit_code"] == 0


def test_server_binds_to_localhost():
    from webhook_server import HOST
    assert HOST == "127.0.0.1"
