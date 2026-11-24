#!/usr/bin/env python3
"""Back up the FLOP testnet agent files into a dated ZIP.

Usage:
  python3 backup.py [--out DIR]

Creates flop-testnet-backup-YYYYMMDD.zip containing:
  did-key.json, wallet.json, public.json (when present),
  gen_keys.py, tc.py, fund.py, backup.py, and a README.txt explainer.

The ZIP has NO password -- its safety comes from being stored privately,
not from encryption. NEVER upload it anywhere public and NEVER forward it
to anyone else. Only run this when the user explicitly asks for a backup.
"""

import argparse
import datetime
import os
import sys
import zipfile

SECRET_FILES = ("did-key.json", "wallet.json")
PUBLIC_FILES = ("public.json", "gen_keys.py", "tc.py", "fund.py", "backup.py")

README_TXT = """FLOP testnet agent backup
=========================

This ZIP holds the agent identity for the FLOP testnet (test tokens only,
no real funds):
  did-key.json - Ed25519 DID seed (SECRET -- whoever holds it IS the DID)
  wallet.json  - Substrate wallet mnemonic (SECRET -- whoever holds it owns
                 the wallet)
  public.json  - DID + wallet address (public, shareable)

It also holds the scripts that created and use those keys.

WARNING: this ZIP is NOT password-protected. Keep it in a private place.
Never upload it to a public site, a public repo, or a shared drive, and
never forward it to anyone else. If it leaks, generate fresh keys with
gen_keys.py and abandon the old DID and wallet.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Back up the FLOP testnet agent files into a ZIP.")
    parser.add_argument("--out", default=".",
                        help="Directory for the ZIP (default: current dir)")
    args = parser.parse_args()

    present = [name for name in SECRET_FILES + PUBLIC_FILES
               if os.path.isfile(name)]
    if not any(name in present for name in SECRET_FILES):
        print("Nothing to back up: did-key.json and wallet.json are both "
              "missing. Run gen_keys.py first.", file=sys.stderr)
        return 1

    stamp = datetime.date.today().strftime("%Y%m%d")
    zip_name = f"flop-testnet-backup-{stamp}.zip"
    zip_path = os.path.join(args.out, zip_name)
    os.makedirs(args.out, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in present:
            zf.write(name, arcname=name)
        zf.writestr("README.txt", README_TXT)

    print(f"Created {zip_path}")
    print("Files:", ", ".join(present + ["README.txt"]))
    print("WARNING: this ZIP is NOT password-protected. Keep it private --")
    print("never upload it anywhere public and never forward it to anyone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
