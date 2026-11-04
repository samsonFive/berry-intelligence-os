"""Actual catalog calculations retain human edits and publication boundaries."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import unittest
from unittest.mock import patch

from app.services.derived_model_scope import DerivedModelScope, model_scope
from app.services.presentation_memo import json_call_memo
from app.services.variety_universe import registry_import
from app.services.variety_universe.corpus_discovery import build_discovered_candidates, merge_visible_candidates
from tests.test_derived_model_scope import MemoryStore


class EarlyClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)


class LaterClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 3, 18, 0, 0, tzinfo=timezone.utc)


class CatalogIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.code = hashlib.sha256(b"catalog-integration-code").hexdigest()
        self.inputs = dict(varieties=[], entities=[], published_evidence=[], facts=[], existing_candidates=[],
            source_text_records=[{"id": "ev-cache-contract-fictional", "status": "unreviewed",
                "source_type": "company_website", "source_name": "Fictional test publisher",
                "title": "Fictional genetics portfolio", "source_url": "https://example.test/cache-contract",
                "summary": "A fictional publisher describes an unreviewed portfolio.",
                "published_date": "2021-06-14", "captured_date": "2026-11-02",
                "berry_ids": ["berry-blueberry"], "entity_ids": [],
                "article": {"full_text": "Blueberry varieties include Source Lead and Human Lead."}}])
        self.threshold = patch("app.services.presentation_memo._SNAPSHOT_MIN_BYTES", 0)
        self.threshold.start(); self.addCleanup(self.threshold.stop)

    def calculate(self, inputs, *, writer=False, clock=EarlyClock):
        scope = DerivedModelScope(self.store, self.code, writer=writer)
        # A fresh memo represents another worker; use the actual unchanged
        # catalog function rather than a fixture imitation of its behavior.
        wrapped = json_call_memo(build_discovered_candidates.__wrapped__)
        with model_scope(scope), patch.object(registry_import, "datetime", clock):
            report = wrapped(**inputs)
        return report, scope

    def test_real_corpus_reuse_preserves_materialization_and_unreviewed_source(self):
        original = deepcopy(self.inputs)
        initial, writer = self.calculate(self.inputs, writer=True)
        self.assertEqual(writer.counts["writes"], 1)
        self.assertEqual({row["candidate_name"] for row in initial["candidates"]}, {"Source Lead", "Human Lead"})
        reused, reader = self.calculate(self.inputs, clock=LaterClock)
        self.assertEqual(reader.counts["artifact_hits"], 1)
        self.assertEqual(reader.counts["writes"], 0)
        self.assertEqual(reused, initial)
        for row in reused["candidates"]:
            self.assertEqual(row["discovered_at"], "2026-11-03T12:00:00+00:00")
            self.assertFalse(row["human_gated"])
            self.assertFalse(row["auto_confirmed"])
            self.assertFalse(row["knowledge"]["source_publication_reviewed"])
        reused["candidates"][0]["candidate_name"] = "A local display mutation"
        again, _ = self.calculate(self.inputs, clock=LaterClock)
        self.assertEqual(again, initial)
        self.assertEqual(self.inputs, original)

    def test_saved_dates_notes_aliases_and_review_decisions_win_after_cache_use(self):
        initial, _ = self.calculate(self.inputs, writer=True)
        writes = self.store.writes
        human = next(row for row in initial["candidates"] if row["candidate_name"] == "Human Lead")
        for decision in ("distinct", "rejected"):
            saved = {**deepcopy(human), "human_gated": True, "identity_state": decision,
                "status": "rejected" if decision == "rejected" else "proposed",
                "discovered_at": "2020-04-01T09:30:00+00:00",
                "aliases": ["A user-maintained literal alias"],
                "user_notes": "Keep this operator note and review decision.",
                "knowledge": {"operator_note": "Do not replace this with derived provenance."}}
            before = deepcopy(saved)
            inputs = {**deepcopy(self.inputs), "existing_candidates": [saved]}
            report, reader = self.calculate(inputs, clock=LaterClock)
            self.assertEqual(reader.counts["calculations"], 1)
            self.assertEqual(reader.counts["writes"], 0)
            visible = merge_visible_candidates([saved], report["candidates"], report=report)
            current = next(row for row in visible if row["id"] == saved["id"])
            for field, value in before.items():
                self.assertEqual(current[field], value, field)
            self.assertEqual(saved, before)
            self.assertEqual(inputs["varieties"], [])
            self.assertEqual(inputs["facts"], [])
        self.assertEqual(self.store.writes, writes)

    def test_current_article_edits_review_and_deletion_do_not_reuse_old_provenance(self):
        self.calculate(self.inputs, writer=True)
        writes = self.store.writes
        edited = deepcopy(self.inputs)
        article = edited["source_text_records"][0]
        article["source_url"] = "https://example.test/changed-original"
        article["article"]["full_text"] = "Blueberry varieties include Fresh Lead and Orchard Lead. This is a fictional unreviewed source."
        report, scope = self.calculate(edited, clock=LaterClock)
        self.assertEqual(scope.counts["calculations"], 1)
        self.assertEqual({row["candidate_name"] for row in report["candidates"]}, {"Fresh Lead", "Orchard Lead"})
        self.assertTrue(all(row["source_url"] == article["source_url"] for row in report["candidates"]))
        reviewed = deepcopy(edited); reviewed["source_text_records"][0]["status"] = "published"
        report, scope = self.calculate(reviewed, clock=LaterClock)
        self.assertEqual(scope.counts["calculations"], 1)
        self.assertTrue(all(row["knowledge"]["source_publication_reviewed"] for row in report["candidates"]))
        self.assertTrue(all(not row["human_gated"] and not row["auto_confirmed"] for row in report["candidates"]))
        deleted = {**deepcopy(self.inputs), "source_text_records": []}
        report, scope = self.calculate(deleted, clock=LaterClock)
        self.assertEqual(scope.counts["calculations"], 1)
        self.assertEqual(report["candidates"], [])
        self.assertEqual(report["mentions"], [])
        self.assertEqual(self.store.writes, writes)


if __name__ == "__main__":
    unittest.main()
