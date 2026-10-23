"""Settings. Credentials live in the OS keychain (Windows Credential Manager / macOS Keychain / Linux Secret Service), never in files."""

import os
import sys
from pathlib import Path

import keyring
from keyring.backends import fail
from keyring.errors import KeyringError

KEYRING_SERVICE = "local-proton-mail"

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = Path(os.environ.get("PMAIL_ARCHIVE", REPO_ROOT / "archive"))
DATA_DIR = Path(os.environ.get("PMAIL_DATA", REPO_ROOT / "data"))

BRIDGE_HOST = os.environ.get("PMAIL_BRIDGE_HOST", "127.0.0.1")
BRIDGE_IMAP_PORT = int(os.environ.get("PMAIL_BRIDGE_IMAP_PORT", "1143"))


class KeychainUnavailable(SystemExit):
    """The OS keychain can't be used (missing, locked or unreachable).

    A SystemExit, like the "no credentials" error below, so the command line, the local
    page and the background sync already show its message instead of a traceback.
    """


def _keychain_help() -> str:
    msg = "The Bridge password is only ever stored in the system keychain, and it can't be reached."
    if sys.platform.startswith("linux"):
        msg += (
            " On Linux, install and unlock a Secret Service provider "
            "(for example gnome-keyring or KeePassXC) and make sure a D-Bus session is running."
        )
    return msg


def check_keychain() -> None:
    """Fail early, with a clear message, when no usable keychain exists."""
    if isinstance(keyring.get_keyring(), fail.Keyring):
        raise KeychainUnavailable(_keychain_help())


def _keychain(call, *args):
    try:
        return call(*args)
    except KeyringError as err:
        raise KeychainUnavailable(_keychain_help()) from err


def save_credentials(username: str, password: str) -> None:
    _keychain(keyring.set_password, KEYRING_SERVICE, "username", username)
    _keychain(keyring.set_password, KEYRING_SERVICE, "password", password)


def load_credentials() -> tuple[str, str]:
    username = _keychain(keyring.get_password, KEYRING_SERVICE, "username")
    password = _keychain(keyring.get_password, KEYRING_SERVICE, "password")
    if not username or not password:
        raise SystemExit("No Bridge credentials saved on this device. Run: python -m pmail setup")
    return username, password
