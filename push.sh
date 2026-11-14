#!/usr/bin/env bash
# Create the public GitHub repo steffanomcrey/payproof-court and push.
# Run this once GitHub auth exists on this machine (gh auth login, or a
# token in GH_TOKEN). As of 2026-11-14 the VM has no gh login and no
# readable GitHub credential, so this script is the one-step publish path.
set -euo pipefail
cd "$(dirname "$0")"

if ! gh auth status >/dev/null 2>&1 && [ -z "${GH_TOKEN:-}" ]; then
  echo "ERROR: no GitHub auth. Run: gh auth login (as steffanomcrey)" >&2
  exit 1
fi

if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin main
else
  gh repo create steffanomcrey/payproof-court --public --source . --remote origin --push \
    --description "PayProof Court: Internet Court style adjudication on GenLayer Bradbury, decided by live ZKsync settlement data"
fi
echo "Published: https://github.com/steffanomcrey/payproof-court"
