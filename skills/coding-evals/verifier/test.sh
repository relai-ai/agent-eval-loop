#!/bin/bash
init=$(cat /proc/1/comm 2>/dev/null)
case "$init" in
  ""|systemd|init|launchd|upstart|openrc-init|runit)
    echo "test.sh: refusing to run: this is not a task container (PID 1 is '${init:-unknown}'), and its" \
         "cleanup stops every other process. Run the task through Harbor, or run verify.py directly." >&2
    exit 2 ;;
esac
[ -f /tests/verify.py ] || { echo "test.sh: refusing to run: /tests/verify.py is missing (not a task container)" >&2; exit 2; }
field() { sed -e 's/^.*) //' "/proc/$1/stat" 2>/dev/null | cut -d' ' -f"$2"; }
keep=" 1 $$ "
pid=$$
while [ "${pid:-1}" -gt 1 ] 2>/dev/null; do
  pid=$(field "$pid" 2)
  [ -n "$pid" ] || break
  keep="$keep$pid "
done
born=$(field 1 20)
window=$(( 2 * $(getconf CLK_TCK 2>/dev/null || echo 100) ))
for dir in /proc/[0-9]*; do
  p=${dir#/proc/}
  [ "$(field "$p" 2)" = 1 ] || continue
  started=$(field "$p" 20)
  [ -n "$started" ] && [ -n "$born" ] && [ $((started - born)) -le "$window" ] 2>/dev/null && keep="$keep$p "
done
for dir in /proc/[0-9]*; do
  p=${dir#/proc/}
  case "$keep" in *" $p "*) ;; *) kill -9 "$p" 2>/dev/null ;; esac
done
rm -f /logs/verifier/reward.json /logs/verifier/reward.txt /logs/verifier/feedback.json \
      /logs/verifier/errors.json /logs/verifier/facts.json /logs/verifier/diff.patch
exec python3 -I -S -B -c 'import runpy, sys; sys.path.append("/tests"); runpy.run_path("/tests/verify.py", run_name="__main__")'
