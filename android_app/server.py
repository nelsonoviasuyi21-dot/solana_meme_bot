from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess, json

PREFIX = "/data/data/com.termux/files/usr"
SERVICE = "solana-bot"

class Handler(BaseHTTPRequestHandler):
    def send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/status":
            p = subprocess.run(
                ["sv", "status", SERVICE],
                env={**__import__("os").environ, "SVDIR": f"{PREFIX}/var/service"},
                capture_output=True,
                text=True
            )
            self.send_json({
                "running": p.stdout.startswith("run:"),
                "status": p.stdout.strip()
            })
        else:
            self.send_json({"error": "not found"})

    def do_POST(self):
        actions = {
            "/start": ["up"],
            "/stop": ["down"],
            "/restart": ["restart"],
        }

        if self.path not in actions:
            self.send_json({"error": "unknown action"})
            return

        subprocess.run(
            ["sv", actions[self.path][0], SERVICE],
            env={**__import__("os").environ, "SVDIR": f"{PREFIX}/var/service"},
            capture_output=True,
            text=True
        )
        self.send_json({"ok": True, "action": self.path[1:]})

    def log_message(self, *args):
        pass

HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
