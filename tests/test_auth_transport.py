import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import httpx
import pytest
from conftest import response_for
from nacl.signing import VerifyKey
from test_contracts import verify

from dmarket_client import ClientConfig, CreateTarget, DMarketClient, Game, Money
from dmarket_client._internal.auth import Signer
from dmarket_client.exceptions import ConfigurationError
from dmarket_client.rate_limits import RateLimiter, retry_after


@pytest.mark.parametrize(
    "title", ["AK-47 | Redline (Field-Tested)", "★ ™ Україна", "100% + # ? /", "literal%20name"]
)
def test_encoded_path_and_signature(title, keys):
    def handler(request):
        verify(request, keys[0])
        assert request.url.path.endswith("/" + title)
        assert request.url.query == b""
        return httpx.Response(200, json={"orders": []})

    with DMarketClient(*keys, transport=httpx.MockTransport(handler), rate_limiter=False) as client:
        client.market.get_targets_by_title(game=Game.CS2, title=title)


def test_key_validation_and_explicit_seed(keys):
    for public, secret in [("bad", keys[1]), (keys[0], "bad"), (keys[0], "00" * 64)]:
        with pytest.raises(ConfigurationError):
            Signer.from_hex(public, secret)
    with pytest.raises(ConfigurationError):
        Signer.from_hex(keys[0], keys[1][:64])
    signer = Signer.from_hex(keys[0].upper(), keys[1][:64], secret_key_is_seed=True)
    assert signer.public_key == keys[0]
    assert keys[1] not in repr(signer)


def test_signing_occurs_after_limiter_wait_and_each_retry(keys, monkeypatch):
    wall = [1700000000.0]
    captured = []

    class Limiter:
        calls = 0

        def reserve(self, group):
            self.calls += 1
            return 3.0 if self.calls % 2 else 0.0

        def observe(self, group, headers):
            pass

    def sleep(seconds):
        wall[0] += seconds

    def handler(request):
        captured.append(request)
        return (
            httpx.Response(503)
            if len(captured) == 1
            else httpx.Response(200, json=response_for("balance"))
        )

    monkeypatch.setattr("dmarket_client.client.time.sleep", sleep)
    with DMarketClient(
        *keys,
        transport=httpx.MockTransport(handler),
        rate_limiter=Limiter(),
        config=ClientConfig(retry_base_delay=0),
    ) as client:
        client._signer = replace(client._signer, clock=lambda: wall[0])
        client.account.get_balance()
    assert [r.headers["x-sign-date"] for r in captured] == ["1700000003", "1700000006"]
    for request in captured:
        verify(request, keys[0])


def test_rate_limiter_shared_budget_and_server_headers():
    clock = [100.0]
    limiter = RateLimiter(clock=lambda: clock[0])
    assert limiter.reserve("market") == 0
    assert limiter.reserve("other") == pytest.approx(0.2)
    limiter.observe(
        "other",
        {
            "x-ratelimit-limit-second": "2",
            "x-ratelimit-remaining-second": "0",
            "ratelimit-reset": "1",
        },
    )
    assert limiter.reserve("sales") >= 1
    limiter.observe("sales", {"x-ratelimit-limit-second": "100"})
    clock[0] = 101.0
    assert limiter.reserve("other") == 0
    assert limiter.reserve("other") == pytest.approx(0.5)
    assert retry_after({"retry-after": "3"}) == 3
    assert retry_after({"retry-after": "nan"}) is None
    assert retry_after({"retry-after": "Thu, 01 Jan 1970 00:00:10 GMT"}, wall_time=1) == 9


def test_signature_verified_over_real_http_bytes(keys):
    """Loopback only: independent server verifies URL/body received over a socket."""
    received, errors = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_api(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            try:
                parsed = urlsplit(self.path)
                message = (
                    (
                        self.command
                        + unquote(parsed.path)
                        + ("?" + parsed.query if parsed.query else "")
                    ).encode()
                    + body
                    + self.headers["X-Sign-Date"].encode()
                )
                signature = bytes.fromhex(
                    self.headers["X-Request-Sign"].removeprefix("dmar ed25519 ")
                )
                VerifyKey(bytes.fromhex(keys[0])).verify(message, signature)
                received.append((self.path, body))
            except Exception as exc:
                errors.append(type(exc).__name__)
            response = b'{"Result":[]}' if self.command == "POST" else b'{"orders":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        do_GET = handle_api
        do_POST = handle_api

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = ClientConfig(base_url=f"http://127.0.0.1:{server.server_port}")
        with DMarketClient(*keys, config=config, rate_limiter=False) as client:
            client.market.get_targets_by_title(game=Game.CS2, title="★ AK-47 | Україна 100% ? +")
            client.targets.create(
                game=Game.CS2, targets=[CreateTarget(title="★ ™", price=Money.usd("1.50"))]
            )
        assert errors == []
        assert len(received) == 2
        assert b'"Amount":1.50' in received[1][1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
