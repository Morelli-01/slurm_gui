"""SSH connection helper, kept free of Qt imports so it can be tested on its own."""
import copy
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import paramiko

DEFAULT_SSH_PORT = 22
# The default identities the ssh command tries, in its order
DEFAULT_KEY_NAMES = ("id_rsa", "id_ecdsa", "id_ed25519")


class KeyFileError(Exception):
    """A key file that cannot be used, with a message meant for the user."""


def _ssh_config_for_host(host: str) -> Dict[str, Any]:
    """Return the ~/.ssh/config entry for host, like the ssh command would use."""
    config_path = os.path.expanduser(os.path.join("~", ".ssh", "config"))
    if not os.path.isfile(config_path):
        return {}
    try:
        return paramiko.SSHConfig.from_path(config_path).lookup(host)
    except Exception as e:
        print(f"Could not read {config_path}: {e}")
        return {}


def _candidate_key_files(key_file: Optional[str], host_config: Dict[str, Any]) -> List[str]:
    """Key file chosen in the settings, then ~/.ssh/config, then the defaults."""
    ssh_dir = os.path.join("~", ".ssh")
    paths = [key_file] if key_file else []
    paths += host_config.get("identityfile", [])
    paths += [os.path.join(ssh_dir, name) for name in DEFAULT_KEY_NAMES]
    existing = []
    for path in (os.path.normpath(os.path.expanduser(p)) for p in paths):
        if os.path.isfile(path) and path not in existing:
            existing.append(path)
    return existing


def _load_key(path: str, passphrase: Optional[str]) -> paramiko.PKey:
    """Load a private key of any type (and its -cert.pub certificate, if any).

    The type comes from the file content, not its name: OpenSSH keeps whatever
    key is in id_rsa, while paramiko's own key discovery reads it as RSA only.
    """
    try:
        return paramiko.PKey.from_path(path)
    except TypeError:
        # Raised by cryptography for a passphrase-protected key
        if not passphrase:
            raise KeyFileError(f"key {path} is protected by a passphrase, set it in Settings") from None
    except Exception as e:
        raise KeyFileError(f"key {path} could not be read ({e})") from None
    try:
        return paramiko.PKey.from_path(path, password=passphrase.encode())
    except Exception:
        raise KeyFileError(
            f"key {path} is protected by a passphrase that was not accepted, check it in Settings"
        ) from None


def _load_keys(paths: List[str], passphrase: Optional[str]) -> Tuple[List[paramiko.PKey], List[str]]:
    """Load the key files, returning the keys and why the others are unusable.

    paramiko silently skips keys it cannot decrypt and then reports only the
    password error, so the reasons are collected here to explain a failure.
    """
    keys, problems = [], []
    for path in paths:
        try:
            keys.append(_load_key(path, passphrase))
        except KeyFileError as e:
            problems.append(str(e))
    return keys, problems


def check_key_files(host: str, key_file: Optional[str], passphrase: Optional[str]) -> List[Tuple[str, Optional[str]]]:
    """Return each key file a connection to host would try, with why it is unusable (None if usable)."""
    results = []
    for path in _candidate_key_files(key_file, _ssh_config_for_host(host) if host else {}):
        try:
            _load_key(path, passphrase)
            results.append((path, None))
        except KeyFileError as e:
            results.append((path, str(e)))
    return results


def _offered_keys(keys: List[paramiko.PKey]) -> List[paramiko.PKey]:
    """Each key with its certificate, then without, as OpenSSH offers them.

    paramiko offers only the certificate when one sits next to the key, which
    servers that do not trust its CA reject even though they accept the key.
    """
    offered = []
    for key in keys:
        offered.append(key)
        if key.public_blob is not None:
            plain = copy.copy(key)
            plain.public_blob = None
            offered.append(plain)
    return offered


class _KeysThenPassword(paramiko.AuthStrategy):
    """The login order of paramiko's own connect, with keys of our choosing.

    Keys are tried first; the password is sent when they are all refused, or
    after one is accepted with partial success (clusters asking for key +
    password). paramiko's stock AuthStrategy stops at partial success instead.
    """

    def __init__(self, username: str, password: Optional[str], keys: List[paramiko.PKey]):
        super().__init__(ssh_config=None)
        self.username = username
        self.password = password
        self.keys = keys

    def authenticate(self, transport):
        error = None
        for key in self.keys:
            try:
                remaining_types = transport.auth_publickey(self.username, key)
            except paramiko.SSHException as e:
                error = e
                continue
            if not remaining_types:
                return
            break  # partial success: the server wants the password as well
        if self.password:
            transport.auth_password(self.username, self.password)
            return
        raise error or paramiko.SSHException("No authentication methods available")


def _agent_keys() -> List[paramiko.PKey]:
    # paramiko's Windows OpenSSH-agent client can block forever on a busy pipe,
    # so on Windows only key files are used.
    if sys.platform == "win32":
        return []
    try:
        return list(paramiko.Agent().get_keys())
    except Exception as e:
        print(f"Could not read keys from the SSH agent: {e}")
        return []


def _new_client() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client


def open_ssh_client(
    host: str,
    username: str,
    password: Optional[str],
    timeout: int = 30,
    key_file: Optional[str] = None,
    key_passphrase: Optional[str] = None,
) -> paramiko.SSHClient:
    """Open an SSH connection, trying SSH keys before the password.

    Some clusters accept the password alone on the internal network but
    require key + password from outside it. The password is sent after a key
    is accepted with partial success, and as a fallback when keys are refused.

    If the key-based attempt fails at the SSH level (for example the server
    drops the connection after too many rejected keys), it retries once with
    the password only, exactly how the app connected before keys were
    supported, so enabling keys can never make a working setup fail.

    Encrypted keys are unlocked with key_passphrase, or with the password when
    no passphrase is set (like paramiko does).
    """
    host_config = _ssh_config_for_host(host)
    keys, key_problems = _load_keys(
        _candidate_key_files(key_file, host_config), key_passphrase or password
    )
    try:
        return _connect(host, username, password, _offered_keys(keys) + _agent_keys(), host_config, timeout)
    except paramiko.SSHException as e:
        if not key_problems:
            raise
        raise paramiko.SSHException(f"{e}; {'; '.join(key_problems)}") from e


def _connect(
    host: str,
    username: str,
    password: Optional[str],
    keys: List[paramiko.PKey],
    host_config: Dict[str, Any],
    timeout: int,
) -> paramiko.SSHClient:
    hostname = host_config.get("hostname", host)
    try:
        port = int(host_config.get("port", DEFAULT_SSH_PORT))
    except ValueError:
        port = DEFAULT_SSH_PORT
    uses_ssh_config_target = (hostname, port) != (host, DEFAULT_SSH_PORT)

    client = _new_client()
    try:
        client.connect(
            hostname,
            port=port,
            username=username,
            timeout=timeout,
            auth_strategy=_KeysThenPassword(username, password, keys),
        )
        return client
    except (paramiko.SSHException, OSError) as key_error:
        client.close()
        # Network errors only warrant a retry when ~/.ssh/config redirected us
        # to a different host or port than the legacy connection would use.
        is_ssh_error = isinstance(key_error, paramiko.SSHException)
        # A plain AuthenticationException means the password itself was
        # rejected: retrying would only send it again (and could trip
        # fail2ban-style lockouts), so report it right away.
        password_rejected = type(key_error) is paramiko.AuthenticationException
        if (
            not password
            or password_rejected
            or not (is_ssh_error or uses_ssh_config_target)
        ):
            raise
        print(f"SSH login with keys failed ({key_error}); retrying with password only")
        first_error = key_error  # the "as" name is unbound after this block

    client = _new_client()
    try:
        client.connect(
            host,
            port=DEFAULT_SSH_PORT,
            username=username,
            password=password,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as fallback_error:
        client.close()
        print(f"Password-only retry failed too ({fallback_error})")
        # The key-based attempt is the more complete one, so its error is the
        # one that explains what went wrong (e.g. "publickey required").
        raise first_error from None
    return client
