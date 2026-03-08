# nintendo.py
# Combined NAS + Conntest handler for DSi connectivity
# Always returns 200 OK so the DSi believes the internet + NAS login succeeded

from http.server import BaseHTTPRequestHandler, HTTPServer

class NintendoHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        host = (self.headers.get("Host") or "").lower()
        path = self.path

        # Log incoming request
        print(f"[Nintendo] {host}{path}")

        # ------------------------------
        # 1. Fake Conntest (internet test)
        # ------------------------------
        if "conntest" in host or path.startswith("/conntest"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # ------------------------------
        # 2. Fake NAS (authentication)
        # ------------------------------
        if "nas" in host or path.startswith("/ac") or path.startswith("/nas"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # ------------------------------
        # 3. Fallback for any Nintendo domain
        # ------------------------------
        if "nintendowifi" in host or "nintendo" in host:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # ------------------------------
        # 4. If it's not Nintendo, return 404
        # ------------------------------
        self.send_response(404)
        self.end_headers()


def run_server(port=80):
    print(f"[Nintendo] Fake NAS + Conntest server running on port {port}")
    server = HTTPServer(("", port), NintendoHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
