#!/usr/bin/env python3
"""Generate a fresh FLOP testnet agent identity: an Ed25519 DID and a
Substrate (sr25519) wallet.

Outputs (in the current directory):
  did-key.json  - {"did": "did:key:z6Mk...", "seed_hex": "<64 hex chars>"}  (0600)
  wallet.json   - {"address": "5...", "mnemonic": "<12 words>"}            (0600)
  public.json   - {"did": ..., "address": ...}  (shareable, no secrets)

Only the DID and the wallet address are printed. The seed and the mnemonic
are NEVER printed. Keep did-key.json and wallet.json private and never
commit them (see .gitignore). Testnet only -- no real funds.
"""

import argparse
import base58
import json
import os
import sys

from nacl.signing import SigningKey
from substrateinterface import Keypair, KeypairType

DID_KEY_FILE = "did-key.json"
WALLET_FILE = "wallet.json"
PUBLIC_FILE = "public.json"

# multicodec varint prefix for ed25519-pub
ED25519_MULTICODEC_PREFIX = bytes([0xED, 0x01])


def make_did(public_key_bytes: bytes) -> str:
    """did:key for an Ed25519 public key (multibase base58btc)."""
    payload = ED25519_MULTICODEC_PREFIX + public_key_bytes
    return "did:key:z" + base58.b58encode(payload).decode("ascii")


def write_secret_json(path: str, data: dict) -> None:
    """Write JSON with mode 0600 (owner read/write only)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a fresh FLOP testnet agent identity.")
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing did-key.json / wallet.json "
             "(DANGEROUS: the old keys are lost).")
    args = parser.parse_args()

    for path in (DID_KEY_FILE, WALLET_FILE):
        if os.path.exists(path) and not args.force:
            print(f"Refusing to overwrite existing {path}. "
                  "Move it away or re-run with --force.", file=sys.stderr)
            return 1

    # --- DID (Ed25519) ---
    signing_key = SigningKey.generate()
    seed = bytes(signing_key)  # 32-byte seed
    did = make_did(signing_key.verify_key.encode())

    # --- Wallet (sr25519, SS58 prefix 42) ---
    mnemonic = Keypair.generate_mnemonic()
    wallet = Keypair.create_from_mnemonic(
        mnemonic, ss58_format=42, crypto_type=KeypairType.SR25519)
    address = wallet.ss58_address

    write_secret_json(DID_KEY_FILE, {"did": did, "seed_hex": seed.hex()})
    write_secret_json(WALLET_FILE, {"address": address, "mnemonic": mnemonic})
    with open(PUBLIC_FILE, "w", encoding="utf-8") as f:
        json.dump({"did": did, "address": address}, f, indent=2)
        f.write("\n")

    print(f"DID:     {did}")
    print(f"Address: {address}")
    print()
    print("Saved (mode 0600, never share): did-key.json, wallet.json")
    print("Saved (public, shareable):      public.json")
    print("The seed and mnemonic were NOT printed. Keep them private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
