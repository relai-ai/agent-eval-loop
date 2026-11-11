#!/bin/bash
# Runs after the agent is done, in its container. The agent could have left processes running and
# written to /logs/verifier and /tests, so first:
#  1. stop every process except PID 1 and this script's own ancestors (Harbor's exec);
#  2. remove score files planted in /logs/verifier (Harbor scores reward.json if it exists);
#  3. run verify.py isolated: -I -S (no PYTHON* variables, user or site packages), /tests last on
#     the path, so nothing planted there stands in for a standard module.
# Scores go in /logs/verifier/reward.json; a low score is not a failed script.
keep=" 1 $$ "
pid=$$
while [ "${pid:-1}" -gt 1 ] 2>/dev/null; do
  pid=$(sed -e 's/^.*) //' "/proc/$pid/stat" 2>/dev/null | cut -d' ' -f2)
  [ -n "$pid" ] || break
  keep="$keep$pid "
done
for dir in /proc/[0-9]*; do
  p=${dir#/proc/}
  case "$keep" in *" $p "*) ;; *) kill -9 "$p" 2>/dev/null ;; esac
done
rm -f /logs/verifier/reward.json /logs/verifier/reward.txt /logs/verifier/feedback.json \
      /logs/verifier/errors.json /logs/verifier/facts.json /logs/verifier/diff.patch
exec python3 -I -S -B -c 'import runpy, sys; sys.path.append("/tests"); runpy.run_path("/tests/verify.py", run_name="__main__")'
