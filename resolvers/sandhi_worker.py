"""
sandhi_worker.py
────────────────
Disposable subprocess for sanskrit_parser compound splitting.

Stdin  : one IAST word per line (UTF-8)
Stdout : one JSON line per word:
           {"iast": "...", "status": "ok|no_split|timeout|oom|error",
            "candidates": [["seg1","seg2"], ...] }
Stderr : silenced (sanskrit_parser DEBUG flood)

Memory and time are hard-capped before sanskrit_parser is imported:
  - RLIMIT_AS  = $PARSER_MEM_CAP_MB MiB (default 1500)
  - SIGALRM    = 8 s per word
A breach turns into a MemoryError / TimeoutError, NOT an OOM kill.

This worker is stateless: segments come back as IAST strings only; the
parent process owns Monier-Williams and validates each candidate.
"""
import json
import logging
import os
import resource
import signal
import sys
import warnings

# 1. Silence library noise BEFORE imports.
logging.disable(logging.CRITICAL)
warnings.filterwarnings("ignore")
sys.stderr = open(os.devnull, "w")  # sanskrit_parser DEBUG goes to stderr

# 2. Hard memory cap BEFORE importing sanskrit_parser (so even import is bounded).
MEM_CAP_MB = int(os.environ.get("PARSER_MEM_CAP_MB", "1500"))
_cap = MEM_CAP_MB * 1024 * 1024
try:
    resource.setrlimit(resource.RLIMIT_AS, (_cap, _cap))
except (ValueError, OSError):
    pass  # if current usage already exceeds cap, skip — parent will catch the OOM

# 3. ast.Str shim for Python 3.12+ (aksharamukha not used here, but harmless).
import ast as _ast
if not hasattr(_ast, "Str"):
    _ast.Str = str

# 4. Import the heavy stuff under the cap.
try:
    from sanskrit_parser import Parser
    from indic_transliteration import sanscript
except MemoryError:
    sys.stderr = sys.__stderr__
    print(json.dumps({"_fatal": "MemoryError during import"}), flush=True)
    sys.exit(3)
except Exception as e:
    sys.stderr = sys.__stderr__
    print(json.dumps({"_fatal": f"import failed: {type(e).__name__}: {e}"[:200]}),
          flush=True)
    sys.exit(2)

try:
    P = Parser()
except MemoryError:
    print(json.dumps({"_fatal": "MemoryError during Parser()"}), flush=True)
    sys.exit(3)

# Restore stderr so any fatal traceback isn't swallowed (debug aid for parent).
sys.stderr = sys.__stderr__

# 5. Per-word timeout.
class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


signal.signal(signal.SIGALRM, _alarm)

MIN_SEG_LEN = 3
MAX_CANDIDATES = 3
SPLIT_LIMIT = 3
ALARM_SECONDS = 8


def split_one(iast):
    rec = {"iast": iast, "status": None, "candidates": []}
    signal.alarm(ALARM_SECONDS)
    try:
        splits = list(P.split(iast, limit=SPLIT_LIMIT))
        cands = []
        # prefer fewest-segment splits
        for sp in sorted(splits, key=lambda s: len(s.split)):
            segs = sp.split
            if len(segs) < 2:
                continue
            try:
                seg_iast = [x.transcoded(sanscript.IAST) for x in segs]
            except Exception:
                continue
            if any(len(s) < MIN_SEG_LEN for s in seg_iast):
                continue
            cands.append(seg_iast)
            if len(cands) >= MAX_CANDIDATES:
                break
        rec["candidates"] = cands
        rec["status"] = "ok" if cands else "no_split"
    except _Timeout:
        rec["status"] = "timeout"
    except MemoryError:
        rec["status"] = "oom"
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        sys.exit(3)  # bail; parent will reap and respawn for next batch
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = f"{type(e).__name__}: {e}"[:120]
    finally:
        signal.alarm(0)
    return rec


def main():
    for line in sys.stdin:
        w = line.strip()
        if not w:
            continue
        rec = split_one(w)
        print(json.dumps(rec, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
