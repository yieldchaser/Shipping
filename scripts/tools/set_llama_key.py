"""Set or rotate the LlamaParse key in the Hermes secrets file.

Built for repeated use: the user rotates across several free-tier accounts, so this
must be safe to run many times, idempotent, and must never print or log the value.

Design notes:
  * The Hermes .env is the canonical secrets location, but it is NOT exported into
    terminal subprocesses - consumers must read the file directly.
  * The file uses CRLF. A naive rewrite (or `sed -i`) silently converts to LF and
    shrinks it one byte per line; we preserve the original convention.
  * Writes are atomic (temp + os.replace) so an interrupted run cannot corrupt a
    file that holds the user's live credentials.

Usage:
    python3 scripts/tools/set_llama_key.py --check
    python3 scripts/tools/set_llama_key.py --key llx-...        # add/replace
    python3 scripts/tools/set_llama_key.py --clear              # remove
"""
import argparse, os, sys
from pathlib import Path

KEY_NAME = 'LLAMA_CLOUD_API_KEY'


def env_paths():
    out = []
    hh = os.environ.get('HERMES_HOME')
    if hh:
        out.append(Path(hh) / '.env')
    out.append(Path.home() / '.hermes' / '.env')
    if os.name == 'nt':
        la = os.environ.get('LOCALAPPDATA')
        if la:
            out.append(Path(la) / 'hermes' / '.env')
    return out


def target_file():
    for p in env_paths():
        if p.exists():
            return p
    return env_paths()[-1]


def read_lines(p):
    raw = p.read_bytes() if p.exists() else b''
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n') - crlf
    text = raw.decode('utf-8', errors='replace')
    # split without losing the trailing-newline information
    lines = text.replace('\r\n', '\n').split('\n')
    return lines, ('crlf' if crlf >= lf else 'lf'), raw


def write_lines(p, lines, style):
    nl = '\r\n' if style == 'crlf' else '\n'
    body = nl.join(lines)
    if body.endswith(nl):
        body = body[:-len(nl)]
    data = body.encode('utf-8')
    if not data.endswith(b'\n'):
        data += nl.encode('ascii') if style == 'crlf' else b'\n'
    tmp = str(p) + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, p)
    return len(data)


def current_value(lines):
    for ln in lines:
        s = ln.strip()
        if s.startswith(KEY_NAME + '='):
            return s.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--key', help='the key value to store (or rotate to)')
    g.add_argument('--clear', action='store_true', help='remove the key')
    g.add_argument('--check', action='store_true', help='report presence only')
    a = ap.parse_args()

    p = target_file()
    lines, style, raw = read_lines(p)

    if a.check:
        v = current_value(lines)
        print(f'file      : {p}')
        print(f'line ends : {style}   ({raw.count(bytes([13, 10]))} CRLF)')
        print(f'bytes     : {len(raw)}')
        if v:
            print(f'{KEY_NAME}: PRESENT  (len {len(v)}, prefix {v[:8]}..., tail ...{v[-4:]})')
        else:
            print(f'{KEY_NAME}: ABSENT')
        return

    if a.clear:
        new = [ln for ln in lines if not ln.strip().startswith(KEY_NAME + '=')]
        n = write_lines(p, new, style)
        print(f'removed {KEY_NAME}; file now {n} bytes ({style})')
        return

    key = (a.key or '').strip()
    if not key:
        print('refusing to store an empty key'); sys.exit(2)
    if not key.startswith('llx-'):
        print(f'warning: value does not start with "llx-" (starts {key[:4]!r}) - continuing')

    replaced = False
    new = []
    for ln in lines:
        if ln.strip().startswith(KEY_NAME + '='):
            if not replaced:
                new.append(f'{KEY_NAME}={key}')
                replaced = True
            # drop any duplicate lines for the same key
        else:
            new.append(ln)
    if not replaced:
        while new and new[-1].strip() == '':
            new.pop()
        new.append(f'{KEY_NAME}={key}')

    n = write_lines(p, new, style)
    print(f'{"replaced" if replaced else "added"} {KEY_NAME}')
    print(f'file : {p}')
    print(f'bytes: {n}  (line ends preserved as {style})')
    print(f'value: len {len(key)}, prefix {key[:8]}..., tail ...{key[-4:]}  [not stored anywhere else]')


if __name__ == '__main__':
    main()
