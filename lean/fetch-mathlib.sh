#!/bin/sh
# Fetch the mathlib dependency and build Certkit.
# `cache get` downloads prebuilt .olean files -- without it, lake compiles
# mathlib from source (hours instead of minutes).
set -ex
export PATH="$HOME/.elan/bin:$PATH"
cd "$(dirname "$0")"
lake exe cache get
lake build Certkit
