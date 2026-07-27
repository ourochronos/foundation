"""foundation CLI — ingest / ask / chain / edit / views / brief / status.

Answers are store entries with citations and honest statuses; briefs are
the G4 machinery (quote-never-reconstruct). Extraction itself is the lab
pipeline (Haiku agent fleets, docs/10); `ingest` loads its vetted output.

  python -m foundation ingest data/wiki/shards_final
  python -m foundation ask "Norbert Wiener" P69
  python -m foundation chain "Norbert Wiener" P69 P571
  python -m foundation edit "Norbert Wiener" P19 "Columbia, Missouri" \
      --source "user:correction"
  python -m foundation views "Isaac Newton" --pid P569
  python -m foundation brief "Andrey Kolmogorov"
  python -m foundation status
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _kb(args, fresh: bool = False):
    from foundation.kb import KB
    return KB(backend=os.environ.get("FOUNDATION_BACKEND", "pg"),
              dsn=os.environ.get(
                  "FOUNDATION_DSN",
                  "host=/var/run/postgresql dbname=foundation"),
              table=os.environ.get("FOUNDATION_TABLE", "poc"),
              fresh=fresh)


def _emit(obj) -> None:
    json.dump(obj, sys.stdout, indent=1, default=str)
    print()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="foundation", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="load vetted claim shards")
    p.add_argument("shard_dir")
    p.add_argument("--fresh", action="store_true",
                   help="drop and recreate the store first")
    p.add_argument("--no-embed", action="store_true",
                   help="skip gist embedding (symbolic surfaces only)")

    p = sub.add_parser("ask", help="single-hop question")
    p.add_argument("subject"); p.add_argument("pid")

    p = sub.add_parser("chain", help="multi-hop with identity hand-off")
    p.add_argument("subject"); p.add_argument("pids", nargs="+")

    p = sub.add_parser("edit", help="supersede a claim")
    p.add_argument("subject"); p.add_argument("pid")
    p.add_argument("object")
    p.add_argument("--source", default="user:edit")

    p = sub.add_parser("views", help="'according to X' per source")
    p.add_argument("subject"); p.add_argument("--pid", default=None)

    p = sub.add_parser("brief", help="grounded subject brief")
    p.add_argument("subject")

    sub.add_parser("status", help="store health")

    a = ap.parse_args(argv)
    if a.cmd == "ingest":
        kb = _kb(a, fresh=a.fresh)
        _emit(kb.ingest_shards(a.shard_dir, embed=not a.no_embed))
    elif a.cmd == "ask":
        _emit(_kb(a).ask(a.subject, a.pid))
    elif a.cmd == "chain":
        _emit(_kb(a).chain(a.subject, a.pids))
    elif a.cmd == "edit":
        _emit(_kb(a).edit(a.subject, a.pid, a.object, a.source))
    elif a.cmd == "views":
        _emit(_kb(a).views(a.subject, a.pid))
    elif a.cmd == "brief":
        b = _kb(a).brief(a.subject)
        if b["abstain"]:
            _emit(b)
        else:
            for s in b["sentences"]:
                cites = ",".join(s["citations"])
                print(f"- {s['text']}  [{cites}]")
    elif a.cmd == "status":
        _emit(_kb(a).status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
