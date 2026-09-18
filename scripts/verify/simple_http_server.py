#!/usr/bin/env python3
import http.server
import socketserver
import sys
from pathlib import Path

PORT = 8000
DIRECTORY = Path(__file__).resolve().parent.parent.parent

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def log_message(self, format, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))
        sys.stderr.flush()

import socket

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()

if __name__ == "__main__":
    print(f"Starting dual-stack HTTP server on port {PORT} serving {DIRECTORY}...")
    sys.stdout.flush()
    with ReusableTCPServer(("::", PORT), Handler) as httpd:
        httpd.serve_forever()
