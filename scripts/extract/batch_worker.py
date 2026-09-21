"""Single-document extraction worker for run_batch.py.

Runs one document and prints exactly one JSON result line to stdout. Isolated
in its own process so a native crash in the PDF stack (which happens: an
unrecoverable access violation with no traceback was measured on this corpus)
takes down only this document, not the whole batch.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: batch_worker.py <pdf> <out_root>"}))
        return 2
    pdf_path, out_root = sys.argv[1], sys.argv[2]
    use_layout = "--layout" in sys.argv
    import extract_all as E
    try:
        rec = E.process_one(pdf_path, out_root, gated_layout=use_layout)
    except Exception as exc:
        rec = {"error": f"{type(exc).__name__}: {exc}"[:300]}
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
