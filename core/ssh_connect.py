"""SSH connection helper, kept free of Qt imports so it can be tested on its own."""
import os
import sys
from typing import Any, Dict, List, Optional

import paramiko

DEFAULT_SSH_PORT = 22


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


def _existing_identity_files(host_config: Dict[str, Any]) -> List[str]:
    paths = (os.path.expanduser(p) for p in host_config.get("identityfile", []))
    return [p for p in paths if os.path.isfile(p)]


def _new_client() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client


def open_ssh_client(
    host: str, username: str, password: Optional[str], timeout: int = 30
) -> paramiko.SSHClient:
    """Open an SSH connection, trying SSH keys before the password.

    Some clusters accept the password alone on the internal network but
    require key + password from outside it. paramiko sends the password after
    a key is accepted with partial success, and falls back to the password
    when keys are refused.

    If the key-based attempt fails at the SSH level (for example the server
    drops the connection after too many rejected keys), it retries once with
    the password only, exactly how the app connected before keys were
    supported, so enabling keys can never make a working setup fail.
    """
    host_config = _ssh_config_for_host(host)
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
            password=password,
            key_filename=_existing_identity_files(host_config) or None,
            timeout=timeout,
            # paramiko's Windows OpenSSH-agent client can block forever on a
            # busy pipe, so on Windows only key files are used.
            allow_agent=sys.platform != "win32",
            look_for_keys=True,
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
