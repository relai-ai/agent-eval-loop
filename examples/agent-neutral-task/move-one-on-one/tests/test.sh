#!/bin/bash
set -u
rm -rf /logs/verifier
mkdir -p /logs/verifier
python3 -I -S -c "import runpy, sys; sys.path.append('/tests'); runpy.run_path('/tests/verify.py', run_name='__main__')"
