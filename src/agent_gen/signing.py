"""Publisher signatures for Portable Units (#144), using SSH signatures (`ssh-keygen -Y`).

Why SSH: no extra dependencies, every developer already has a key, and GitHub publishes each user's public keys at
`https://github.com/<handle>.keys`. A registry unit's signature can therefore be checked against its publisher's
GitHub identity, or against a local allowed-signers file (the OpenSSH format) for private setups.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

NAMESPACE = "agentfactory-unit"  # signatures made for other purposes (git commits, files) never verify here
SIG_HEADER = "-----BEGIN SSH SIGNATURE-----"
MAX_SIGNATURE_BYTES = 8192
_HANDLE_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")


class SignatureError(Exception):
    """Signing or verification failed; the message is safe to show to the user."""


def _ssh_keygen() -> str:
    exe = shutil.which("ssh-keygen")
    if not exe:
        raise SignatureError("ssh-keygen not found: install OpenSSH (8.0+) to sign or verify units")
    return exe


def looks_like_signature(text: str) -> bool:
    return text.strip().startswith(SIG_HEADER) and len(text.encode()) <= MAX_SIGNATURE_BYTES


def sign_file(path: Path, key: Path) -> Path:
    """Write `<path>.sig` signed with the private *key*; returns the signature path."""
    if not key.is_file():
        raise SignatureError(f"signing key not found: {key}")
    sig = path.with_name(path.name + ".sig")
    sig.unlink(missing_ok=True)
    result = subprocess.run(
        [_ssh_keygen(), "-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(path)], capture_output=True, text=True
    )
    if result.returncode != 0 or not sig.is_file():
        raise SignatureError(f"ssh-keygen could not sign {path.name}: {result.stderr.strip()}")
    return sig


def github_allowed_signers(handle: str, timeout: float = 10.0) -> str:
    """Allowed-signers text for every public key GitHub lists for *handle*."""
    if not _HANDLE_RE.fullmatch(handle):
        raise SignatureError(f"invalid GitHub handle {handle!r}")
    url = f"https://github.com/{handle}.keys"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            keys = [k.strip() for k in resp.read().decode().splitlines() if k.strip()]
    except OSError as exc:
        raise SignatureError(f"could not fetch {url}: {exc}") from exc
    if not keys:
        raise SignatureError(f"GitHub user '{handle}' has no public SSH keys to verify against")
    return "".join(f'{handle} namespaces="{NAMESPACE}" {k}\n' for k in keys)


def verify_file(path: Path, signature: str, identity: str, allowed_signers: str) -> None:
    """Raise SignatureError unless *signature* over *path* was made by *identity* per *allowed_signers*."""
    if not looks_like_signature(signature):
        raise SignatureError("not an SSH signature (expected '-----BEGIN SSH SIGNATURE-----')")
    with tempfile.TemporaryDirectory(prefix="af-verify-") as tmp:
        sig_file = Path(tmp) / "unit.sig"
        sig_file.write_text(signature)
        signers = Path(tmp) / "allowed_signers"
        signers.write_text(allowed_signers)
        with path.open("rb") as data:
            result = subprocess.run(
                [
                    _ssh_keygen(),
                    "-Y",
                    "verify",
                    "-f",
                    str(signers),
                    "-I",
                    identity,
                    "-n",
                    NAMESPACE,
                    "-s",
                    str(sig_file),
                ],
                stdin=data,
                capture_output=True,
                text=True,
            )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise SignatureError(f"signature check failed for '{identity}': {detail[-1] if detail else 'invalid'}")
