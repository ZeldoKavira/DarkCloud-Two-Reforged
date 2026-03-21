"""PINE relay server — exposes the mod's PINE connection over TCP.

External tools can connect to the relay port and send standard PINE
protocol messages.  The relay forwards them to PCSX2 and returns the
response.  Controlled by the ``pine_relay`` / ``pine_relay_port`` settings.
"""

import logging
import selectors
import socket
import struct
import threading

log = logging.getLogger(__name__)

_DEFAULT_PORT = 28012


class PineRelay:
    """TCP relay that forwards PINE IPC messages through an existing PineIPC."""

    def __init__(self, ipc, port=None):
        self.ipc = ipc
        self.port = port or _DEFAULT_PORT
        self._sel = selectors.DefaultSelector()
        self._server = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.port))
        srv.listen(4)
        srv.setblocking(False)
        self._server = srv
        self._sel.register(srv, selectors.EVENT_READ, data=None)
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pine-relay")
        self._thread.start()
        log.info("PINE relay listening on 127.0.0.1:%d", self.port)

    def stop(self):
        self._stop.set()
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=2)
        self._sel.close()
        log.info("PINE relay stopped")

    # ── internals ──

    def _loop(self):
        while not self._stop.is_set():
            try:
                events = self._sel.select(timeout=0.25)
            except (OSError, ValueError):
                break
            for key, _ in events:
                if key.data is None:
                    self._accept(key.fileobj)
                else:
                    self._handle(key)

    def _accept(self, srv):
        try:
            conn, addr = srv.accept()
        except OSError:
            return
        conn.setblocking(True)
        conn.settimeout(5)
        self._sel.register(conn, selectors.EVENT_READ, data="client")

    def _handle(self, key):
        conn = key.fileobj
        try:
            hdr = self._recv_exact(conn, 4)
            if not hdr:
                raise ConnectionError
            size = struct.unpack("<I", hdr)[0]
            payload = self._recv_exact(conn, size - 4)
            if not payload:
                raise ConnectionError
            resp_body = self.ipc._send_recv(payload)
            # _send_recv returns (body, ) tuple — unpack
            if isinstance(resp_body, tuple):
                resp_body = resp_body[0]
            resp = struct.pack("<I", len(resp_body) + 4) + resp_body
            conn.sendall(resp)
        except Exception:
            self._sel.unregister(conn)
            try:
                conn.close()
            except OSError:
                pass

    @staticmethod
    def _recv_exact(sock, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)
