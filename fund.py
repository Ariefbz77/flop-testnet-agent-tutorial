#!/usr/bin/env python3
"""Claim FLOP from the Technocore faucet lane (private GET, no browser).

Usage:
  python3 fund.py <nonce> [--wallet wallet.json] [--dry-run]

Flow (see https://faucet.flop.network/llms.txt, section 4):
  1. The faucet bot (or the docs) gives a challenge:
       fund|<ss58>|<nonce>
  2. Sign those exact bytes with the wallet's sr25519 key.
  3. Fetch, privately -- never post the signature in a room:
       https://faucet.technocore.chat/faucet/fund/<ss58>/<nonce>/<0x-hex-sig>
  4. The answer is one text line, e.g. "funded 2 devnet FLOP ... tx 0x...".
     A refusal code comes in the X-Flop-Refusal-Reason header.

The nonce must be a canonical decimal of 1-19 digits, greater than your
previous grant's nonce (a millisecond clock works). A repeat grant also
needs on-chain use of the previous one and a 24 h cooldown.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from substrateinterface import Keypair, KeypairType

FAUCET_BASE = "https://faucet.technocore.chat"


def load_wallet(path: str) -> Keypair:
    """Load the sr25519 wallet from wallet.json (mnemonic + address)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    keypair = Keypair.create_from_mnemonic(
        data["mnemonic"], ss58_format=42, crypto_type=KeypairType.SR25519)
    if keypair.ss58_address != data["address"]:
        raise ValueError(
            "wallet.json: mnemonic does not match the stored address")
    return keypair


def build_challenge(address: str, nonce: int) -> str:
    return f"fund|{address}|{nonce}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Claim FLOP from the Technocore faucet lane.")
    parser.add_argument("nonce", help="Nonce, 1-19 digits, above your last grant")
    parser.add_argument("--wallet", default="wallet.json",
                        help="Path to wallet.json (default: wallet.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Sign only; do not fetch the faucet")
    args = parser.parse_args()

    if not (args.nonce.isdigit() and 1 <= len(args.nonce) <= 19):
        print("Nonce must be 1-19 digits.", file=sys.stderr)
        return 1
    nonce = int(args.nonce)

    try:
        keypair = load_wallet(args.wallet)
    except (OSError, KeyError, ValueError) as exc:
        print(f"Cannot load {args.wallet}: {exc}", file=sys.stderr)
        print("Run gen_keys.py first.", file=sys.stderr)
        return 1

    address = keypair.ss58_address
    challenge = build_challenge(address, nonce)
    signature = keypair.sign(challenge)
    # substrate-interface returns raw bytes on this version (older
    # versions returned a "0x..." hex string); normalize to "0x" hex,
    # which is what the faucet URL carries.
    if isinstance(signature, bytes):
        signature = "0x" + signature.hex()
    elif not signature.startswith("0x"):
        signature = "0x" + signature

    print(f"Address:   {address}")
    print(f"Challenge: {challenge}")
    if args.dry_run:
        print(f"Signature: {signature[:12]}... ({len(signature)} hex chars, not sent)")
        print("Dry run -- nothing fetched.")
        return 0

    url = (f"{FAUCET_BASE}/faucet/fund/{address}/{nonce}/{signature}")
    # urllib sends no Sec-Fetch-* headers (browsers and Node fetch do,
    # and the faucet refuses those).
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"HTTP {resp.status}")
            print(resp.read().decode("utf-8", "replace"))
            refusal = resp.headers.get("X-Flop-Refusal-Reason")
            if refusal:
                print(f"Refusal reason: {refusal}")
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}", file=sys.stderr)
        print(exc.read().decode("utf-8", "replace"), file=sys.stderr)
        refusal = exc.headers.get("X-Flop-Refusal-Reason") if exc.headers else None
        if refusal:
            print(f"Refusal reason: {refusal}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
