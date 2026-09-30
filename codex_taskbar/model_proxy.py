"""Process-scoped HTTPS observation proxy for Codex model response headers.

The proxy intentionally exposes only the ``OpenAI-Model`` response header to
the caller. Request and response bodies are relayed without being persisted.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import io
import queue
import select
import socket
import ssl
import tempfile
import threading
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


OBSERVED_HOSTS = frozenset({
    'chatgpt.com', 'www.chatgpt.com', 'api.openai.com', 'auth.openai.com',
})


def response_model(headers: bytes) -> str | None:
    """Return the allow-listed model response header without parsing a body."""
    try:
        message = http.client.parse_headers(io.BytesIO(headers.split(b'\r\n', 1)[1].split(b'\r\n\r\n', 1)[0] + b'\r\n'))
    except (IndexError, ValueError, UnicodeError):
        return None
    for key, value in message.items():
        if key.lower() == 'openai-model':
            value = value.strip()
            return value if value and len(value) <= 160 else None
    return None


class ModelProxy:
    """Ephemeral localhost CONNECT proxy used by a monitored Codex process."""

    def __init__(self, on_model, allowed_hosts=OBSERVED_HOSTS):
        self.on_model = on_model
        self.allowed_hosts = frozenset(allowed_hosts)
        self._server = None
        self._thread = None
        self._stop = threading.Event()
        self._cert_dir = None
        self._cert_path = None
        self._key_path = None
        self._spki = None
        self._connections = set()
        self._lock = threading.Lock()

    @property
    def address(self):
        return self._server.getsockname() if self._server else None

    @property
    def running(self):
        return self._server is not None and not self._stop.is_set()

    def start(self):
        if self.running:
            return self
        self._prepare_certificate()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 0))
        server.listen(16)
        server.settimeout(.5)
        self._server = server
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name='codex-model-proxy', daemon=True)
        self._thread.start()
        return self

    def launch_args(self):
        if not self.running:
            raise RuntimeError('model proxy is not running')
        host, port = self.address
        return [f'--proxy-server=http://{host}:{port}',
                f'--ignore-certificate-errors-spki-list={self._spki}']

    def environment(self):
        if not self.running:
            raise RuntimeError('model proxy is not running')
        host, port = self.address
        value = f'http://{host}:{port}'
        return {'HTTP_PROXY': value, 'HTTPS_PROXY': value, 'ALL_PROXY': value,
                'NO_PROXY': '127.0.0.1,localhost'}

    def close(self):
        self._stop.set()
        server, self._server = self._server, None
        if server:
            try:
                server.close()
            except OSError:
                pass
        with self._lock:
            connections = list(self._connections)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1)
        self._thread = None
        if self._cert_dir:
            self._cert_dir.cleanup()
            self._cert_dir = None
        self._cert_path = self._key_path = self._spki = None

    def _prepare_certificate(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Codex local model monitor')])
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
                .add_extension(x509.SubjectAlternativeName([
                    x509.DNSName('chatgpt.com'), x509.DNSName('*.chatgpt.com'),
                    x509.DNSName('openai.com'), x509.DNSName('*.openai.com'),
                ]), critical=False).sign(key, hashes.SHA256()))
        folder = tempfile.TemporaryDirectory(prefix='codex-taskbar-proxy-')
        cert_path, key_path = Path(folder.name) / 'proxy.crt', Path(folder.name) / 'proxy.key'
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                               serialization.PrivateFormat.TraditionalOpenSSL,
                                               serialization.NoEncryption()))
        spki = key.public_key().public_bytes(serialization.Encoding.DER,
                                             serialization.PublicFormat.SubjectPublicKeyInfo)
        self._cert_dir, self._cert_path, self._key_path = folder, cert_path, key_path
        self._spki = base64.b64encode(hashlib.sha256(spki).digest()).decode('ascii')

    def _serve(self):
        while not self._stop.is_set():
            try:
                client, _ = self._server.accept()
            except (OSError, AttributeError):
                continue
            client.settimeout(10)
            with self._lock:
                self._connections.add(client)
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client):
        upstream = None
        try:
            header = _read_headers(client)
            if not header:
                return
            first = header.split(b'\r\n', 1)[0].decode('ascii', 'ignore')
            if not first.upper().startswith('CONNECT '):
                return
            host, port = _connect_target(first[8:])
            upstream = socket.create_connection((host, port), timeout=10)
            if host.lower().rstrip('.') not in self.allowed_hosts:
                _write_connected(client)
                _relay(client, upstream)
                return
            client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            upstream_tls = ssl.create_default_context().wrap_socket(upstream, server_hostname=host)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(self._cert_path), str(self._key_path))
            downstream_tls = context.wrap_socket(client, server_side=True)
            request = _read_headers(downstream_tls)
            if request:
                upstream_tls.sendall(request)
            _relay_and_observe(downstream_tls, upstream_tls, self.on_model)
        except (OSError, ssl.SSLError, ValueError):
            pass
        finally:
            with self._lock:
                self._connections.discard(client)
            try:
                client.close()
            except OSError:
                pass
            if upstream:
                try:
                    upstream.close()
                except OSError:
                    pass


def _read_headers(sock):
    data = bytearray()
    while len(data) <= 64 * 1024:
        try:
            chunk = sock.recv(4096)
        except (OSError, ssl.SSLError):
            return b''
        if not chunk:
            return b''
        data.extend(chunk)
        if b'\r\n\r\n' in data:
            end = data.index(b'\r\n\r\n') + 4
            return bytes(data[:end])
    return b''


def _connect_target(value):
    value = value.split(b' ', 1)[0].decode('ascii')
    host, separator, port = value.rpartition(':')
    if not separator or not host or not port.isdigit() or int(port) not in (443, 80):
        raise ValueError('unsupported CONNECT target')
    return host.strip('[]').lower(), int(port)


def _write_connected(sock):
    sock.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')


def _relay(left, right):
    _relay_and_observe(left, right, None)


def _relay_and_observe(left, right, on_model):
    sockets = [left, right]
    observed = bytearray()
    try:
        while sockets:
            ready, _, _ = select.select(sockets, [], [], 1)
            for source in ready:
                target = right if source is left else left
                data = source.recv(64 * 1024)
                if not data:
                    sockets.remove(source)
                    try:
                        target.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                    continue
                target.sendall(data)
                if on_model and source is right and len(observed) < 128 * 1024:
                    observed.extend(data[:128 * 1024 - len(observed)])
                    if b'\r\n\r\n' in observed:
                        model = response_model(bytes(observed))
                        if model:
                            on_model(model, datetime.now(timezone.utc).isoformat())
                            on_model = None
    except (OSError, ssl.SSLError):
        return
