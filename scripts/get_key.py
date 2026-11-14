#!/usr/bin/env python3
"""Print the farming EVM private key as hex to stdout.

Only ever invoked by the Node deploy scripts in this workspace, which
capture stdout into an in-process variable. Never run this interactively
and never redirect its output to a file or a log.
"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "onchain", "/home/hatch/workspace/airdrop-daily/runner/onchain.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
address, priv = mod.unlock_vault()
assert address.lower() == "0x00000c2be4edf75d0f292153cc27230891dc67a5"
sys.stdout.write("0x%064x" % priv)
