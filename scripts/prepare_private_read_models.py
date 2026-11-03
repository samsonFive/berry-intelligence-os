"""Explicit offline preparation of private derived catalog calculations.

No collection/provider request, startup hook, source edit or review decision.
Only the owned derived-read-models-v1 leaf can be written or expired.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import socket
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@contextmanager
def offline_preparation():
    def deny(*args, **kwargs):
        raise RuntimeError("Private model preparation cannot open network connections")
    targets = [(socket.socket, "connect"), (socket.socket, "connect_ex"),
               (socket, "create_connection"), (socket, "getaddrinfo")]
    originals = [(owner, name, getattr(owner, name)) for owner, name in targets]
    try:
        for owner, name, _ in originals:
            setattr(owner, name, deny)
        yield
    finally:
        for owner, name, value in originals:
            setattr(owner, name, value)


def _prepare(parser, start):
    from app import main as app
    from app.services.derived_model_scope import configured_scope, model_scope
    from app.services.identity_read_model import identity_read_model_scope
    from app.services.request_corpus import RequestCorpus, bind_request_corpus, reset_request_corpus
    if not app.AUTHORING_MODE:
        parser.error("Preparation requires the private authoring runtime.")
    scope = configured_scope(repo_root=app.BASE_DIR, data_dir=app.DATA_DIR,
        schemas_dir=app.SCHEMAS_DIR, inbox_dir=app.INBOX_DIR, preparation=True)
    if scope is None:
        parser.error("Preparation requires POSIX and configured private signing material.")
    token = bind_request_corpus(RequestCorpus(app.DATA_DIR, app.SCHEMAS_DIR, app.INBOX_DIR))
    try:
        with model_scope(scope), identity_read_model_scope():
            app.variety_candidate_universe()
    finally:
        reset_request_corpus(token)
    complete = scope.counts["writes"] + scope.counts["artifact_hits"] >= 2
    print(json.dumps({"prepared": complete, "seconds": time.perf_counter() - start,
        "counts": scope.counts, "source_or_review_writes": False, "provider_requests": 0}))
    return 0 if complete else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", required=True,
                        help="Explicitly create/expire bounded derived artifacts; source data stays unchanged.")
    parser.parse_args(argv)
    start = time.perf_counter()
    with offline_preparation():
        return _prepare(parser, start)


if __name__ == "__main__":
    raise SystemExit(main())
