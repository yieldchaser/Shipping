#!/usr/bin/env python
"""Launch run_batch.py detached from the calling agent session (Windows).

WHY THIS EXISTS
---------------
The hourly orchestrator restarts a dead batch with the tool's background
terminal session, as docs/EXTRACTION_RUNBOOK.md prescribes. Measured on
2026-09-22 IST that restart did not survive the agent run that made it:

  * batch restarted 05:37:03 (hourly run)
  * last checkpoint row written 05:48:59.579
  * the launching agent run was recorded finished 05:49:00.462
  * no run_batch / batch_worker process existed by 06:02
  * the Windows Application log has NO python.exe crash record (event 1000)
    in that window, while other applications on this box DO produce those
    records (PhoneExperienceHost 05:40:44, Hermes.exe 21-09 12:04). The driver
    was therefore terminated, not crashed. It exited with no traceback and no
    stdout anywhere, which is why it took a forensic pass to explain.

Hermes attaches its own process to a Windows job object with
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (hermes-agent/hermes_cli/process_identity.py
layer 3, ~line 425). A child that does not explicitly break away stays in that
job and is killed when the agent process exits. BREAKAWAY_OK is set on the job,
so requesting CREATE_BREAKAWAY_FROM_JOB is permitted.

WHAT THIS DOES
--------------
Spawns exactly the prescribed run_batch command with
CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, so the
extraction outlives the agent session, and redirects stdout+stderr to
data/extracted/batch_run.log. That log is the missing forensic record: the
05:48 death left no driver output at all.

usage:
    python scripts/extract/launch_detached.py            # prescribed command
    python scripts/extract/launch_detached.py --dry-run  # print, do not start
    python scripts/extract/launch_detached.py -- <extra run_batch args>

It does not bypass run_batch's own single-instance lock: if a batch is already
running, run_batch refuses to start and this launcher reports that.
"""
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, 'data', 'extracted', 'corpus')
CHECKPOINT = os.path.join(REPO, 'data', 'extracted', 'corpus_checkpoint.jsonl')
STATE = os.path.join(REPO, 'data', 'extracted', 'corpus_state.json')
LOG = os.path.join(REPO, 'data', 'extracted', 'batch_run.log')


def build_cmd(extra=None):
    cmd = [sys.executable, os.path.join(REPO, 'scripts', 'extract', 'run_batch.py'),
           '--all', '--workers', '2', '--timeout', '900', '--resume',
           '--out', OUT, '--checkpoint', CHECKPOINT, '--state', STATE]
    if extra:
        cmd += list(extra)
    return cmd


def spawn(cmd, flags):
    log = open(LOG, 'a', encoding='utf-8', errors='replace')
    log.write('\n===== launch %s | pid(shell)=%s =====\n' %
              (time.strftime('%Y-%m-%dT%H:%M:%S'), os.getpid()))
    log.write('cmd: %s\n' % ' '.join(cmd))
    log.flush()
    return subprocess.Popen(
        cmd, cwd=REPO, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        creationflags=flags, close_fds=True)


def main(argv):
    if argv and argv[0] == '--dry-run':
        print('would run: %s' % ' '.join(build_cmd()))
        return 0
    extra = argv[1:] if argv and argv[0] == '--' else argv
    cmd = build_cmd(extra)

    breakaway = getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0x01000000)
    detached = getattr(subprocess, 'DETACHED_PROCESS', 0x00000008)
    newgroup = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200)

    try:
        proc = spawn(cmd, breakaway | detached | newgroup)
        mode = 'breakaway+detached'
    except OSError as exc:
        # ERROR_ACCESS_DENIED: the parent job object forbids breakaway.
        print('breakaway spawn refused (%s); retrying detached only' % exc)
        proc = spawn(cmd, detached | newgroup)
        mode = 'detached-only'

    time.sleep(3.0)
    alive = proc.poll() is None
    print('mode=%s pid=%s alive_after_3s=%s log=%s' % (mode, proc.pid, alive, LOG))
    if not alive:
        print('FAILED: driver exited rc=%s within 3 s; tail of log:' % proc.returncode)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
