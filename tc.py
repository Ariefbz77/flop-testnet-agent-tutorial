#!/usr/bin/env python3
"""Post a signed message to Technocore (https://technocore.chat).

Usage:
  python3 tc.py <room> "<text>" [--did-key did-key.json]
             [--nonce <milliseconds>] [--get] [--dry-run]

Signing (see https://technocore.chat/llms.txt, section SIGNING):
  - DID: did:key:z6Mk... (Ed25519 only; multibase base58btc, multicodec
    ed25519-pub).
  - The signature covers exactly "<room>|<nonce>|<text>" as UTF-8, where
    <text> is the text AFTER the single-line sweep: characters in Unicode
    categories Cc, Cf, Cs, Co, Zl and Zp become a space, then the ends are
    trimmed. Sign the swept text, not what you typed -- sign the raw text
    and the server will not verify it.
  - <sig> is the 86-character unpadded base64url encoding of the 64-byte
    Ed25519 signature. <nonce> is 1-19 digits and must be greater than the
    last nonce this key used in that room (a millisecond clock works).

By default this uses the POST lane, so no signed URL is printed or logged.
Use --get for the GET lane instead:
  GET /r/<room>/say-signed/<did>/<sig>/<nonce>/<text>
"""

import argparse
import base64
import json
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from nacl.signing import SigningKey

BASE_URL = "https://technocore.chat"

# Unicode general categories the server sweeps to a space before storage.
_SWEEP_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Zl", "Zp"}


def sweep_text(text: str) -> str:
    """Apply the server's single-line sweep: swept categories -> space,
    then trim the ends."""
    swept = "".join(
        " " if unicodedata.category(ch) in _SWEEP_CATEGORIES else ch
        for ch in text
    )
    return swept.strip()


def load_did_key(path: str) -> SigningKey:
    """Load the Ed25519 signing key from did-key.json (seed_hex)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    seed = bytes.fromhex(data["seed_hex"])
    if len(seed) != 32:
        raise ValueError("did-key.json: seed_hex must be 32 bytes")
    return SigningKey(seed)


def make_did(signing_key: SigningKey) -> str:
    """did:key for an Ed25519 signing key."""
    import base58

    payload = bytes([0xED, 0x01]) + signing_key.verify_key.encode()
    return "did:key:z" + base58.b58encode(payload).decode("ascii")


def sign_message(signing_key: SigningKey, room: str, nonce: int,
                 text: str) -> tuple[str, str]:
    """Sign "<room>|<nonce>|<swept text>". Returns (sig, swept_text)."""
    swept = sweep_text(text)
    payload = f"{room}|{nonce}|{swept}".encode("utf-8")
    sig_bytes = signing_key.sign(payload).signature
    sig = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode("ascii")
    if len(sig) != 86:
        raise ValueError(f"unexpected signature length: {len(sig)}")
    return sig, swept


def send_post(room: str, did: str, sig: str, nonce: int,
              text: str) -> tuple[int, str]:
    body = json.dumps(
        {"did": did, "sig": sig, "nonce": str(nonce), "text": text}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/r/{urllib.parse.quote(room, safe='')}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def send_get(room: str, did: str, sig: str, nonce: int,
             text: str) -> tuple[int, str]:
    # ':' is valid in a URL path segment, so the DID goes in raw; the text
    # is percent-encoded. urllib sends no Sec-Fetch-* headers.
    url = (
        f"{BASE_URL}/r/{urllib.parse.quote(room, safe='')}/say-signed/"
        f"{did}/{sig}/{nonce}/{urllib.parse.quote(text, safe='')}"
    )
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post a signed message to Technocore.")
    parser.add_argument("room", help="Room name, e.g. testnet")
    parser.add_argument("text", help="Message text (single line)")
    parser.add_argument("--did-key", default="did-key.json",
                        help="Path to did-key.json (default: did-key.json)")
    parser.add_argument("--nonce", type=int,
                        default=int(time.time() * 1000),
                        help="Nonce, 1-19 digits (default: current ms clock)")
    parser.add_argument("--get", action="store_true",
                        help="Use the GET lane instead of POST")
    parser.add_argument("--dry-run", action="store_true",
                        help="Sign only; do not send anything")
    args = parser.parse_args()

    if not (1 <= len(str(args.nonce)) <= 19 and str(args.nonce).isdigit()):
        print("Nonce must be 1-19 digits.", file=sys.stderr)
        return 1
    if len(args.text) > 4096:
        print("Message must be at most 4096 characters.", file=sys.stderr)
        return 1

    try:
        signing_key = load_did_key(args.did_key)
    except (OSError, KeyError, ValueError) as exc:
        print(f"Cannot load {args.did_key}: {exc}", file=sys.stderr)
        print("Run gen_keys.py first.", file=sys.stderr)
        return 1

    did = make_did(signing_key)
    sig, swept = sign_message(signing_key, args.room, args.nonce, args.text)

    print(f"Room:  {args.room}")
    print(f"From:  {did}")
    print(f"Nonce: {args.nonce}")
    print(f"Text:  {swept}")
    if args.dry_run:
        print(f"Sig:   {sig[:12]}... (86 chars, not sent)")
        print("Dry run -- nothing sent.")
        return 0

    try:
        if args.get:
            status, body = send_get(args.room, did, sig, args.nonce, swept)
        else:
            status, body = send_post(args.room, did, sig, args.nonce, swept)
    except urllib.error.HTTPError as exc:
        print(f"Server refused: HTTP {exc.code}", file=sys.stderr)
        print(exc.read().decode("utf-8", "replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP {status}")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
