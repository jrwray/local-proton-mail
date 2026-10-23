"""A missing or locked keychain gives a clear error (e.g. Linux without a Secret Service provider)."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import keyring
import keyring.errors
import pytest
from keyring.backends import fail

from pmail import config, server
from pmail.service import Service


def _no_keyring(*args, **kwargs):
    raise keyring.errors.NoKeyringError("no backend")


@pytest.fixture
def page():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(Service(), 0))
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = server.make_handler(Service(), port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def test_save_credentials_reports_unavailable_keychain(monkeypatch):
    monkeypatch.setattr(keyring, "set_password", _no_keyring)
    with pytest.raises(config.KeychainUnavailable):
        config.save_credentials("user", "secret")


def test_load_credentials_reports_unavailable_keychain(monkeypatch):
    monkeypatch.setattr(keyring, "get_password", _no_keyring)
    with pytest.raises(config.KeychainUnavailable):
        config.load_credentials()


def test_check_keychain_flags_missing_backend(monkeypatch):
    monkeypatch.setattr(keyring, "get_keyring", lambda: fail.Keyring())
    with pytest.raises(config.KeychainUnavailable):
        config.check_keychain()


def test_linux_message_names_secret_service(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    assert "Secret Service" in config._keychain_help()


def test_message_never_suggests_a_plaintext_backend():
    assert "keyrings.alt" not in config._keychain_help()


def test_page_shows_the_keychain_message_instead_of_crashing(page, monkeypatch):
    monkeypatch.setattr(keyring, "set_password", _no_keyring)
    request = urllib.request.Request(
        f"{page}/api/credentials", method="POST",
        headers={"X-Pmail": "1", "Content-Type": "application/json"},
        data=json.dumps({"username": "user", "password": "secret"}).encode())
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(request, timeout=5)
    assert exc.value.code == 400
    assert "keychain" in json.loads(exc.value.read())["error"]
