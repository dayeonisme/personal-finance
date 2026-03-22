import json
import logging
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORT = 9000


_PROJECT_ROOT = Path(__file__).parent


class _App:
    def handle_run_request(self) -> dict:
        result = subprocess.run(
            [sys.executable, "run.py"],
            capture_output=True,
            text=True,
            cwd=str(_PROJECT_ROOT),
        )
        logger.info("run.py exited with code %d", result.returncode)
        if result.stderr:
            logger.error(result.stderr)
        return {"exit_code": result.returncode, "stdout": result.stdout}


def create_app() -> _App:
    return _App()


def _make_handler(app: _App):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/run":
                result = app.handle_run_request()
                body = json.dumps(result).encode()
                status = 200 if result["exit_code"] == 0 else 500
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            logger.info(format, *args)

    return Handler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    app = create_app()
    server = HTTPServer((HOST, PORT), _make_handler(app))
    logger.info("Webhook server running at http://%s:%d", HOST, PORT)
    server.serve_forever()
