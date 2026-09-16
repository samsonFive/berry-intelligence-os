window.PUBLICATION_REVIEW_FIXTURES = {
  "meta": {
    "label": "SYNTHETIC PUBLICATION-REVIEW FIXTURES \u2014 NOT PRODUCTION / NOT CANONICAL",
    "live_mutation": false,
    "trusted_publications_created": 0,
    "trusted_evidence_created": 0,
    "bulk_approval_available": false,
    "actor": {
      "actor_id": "operator.prototype.demo",
      "display_name": "Prototype Operator"
    }
  },
  "filters": [
    {
      "id": "all",
      "label": "All pending"
    },
    {
      "id": "readable",
      "label": "Readable body"
    },
    {
      "id": "transcript",
      "label": "Transcript"
    },
    {
      "id": "limited",
      "label": "Limited content"
    },
    {
      "id": "problem",
      "label": "Problem states"
    }
  ],
  "rejection_reasons": [
    {
      "id": "not_relevant",
      "label": "Not relevant to scope"
    },
    {
      "id": "duplicate",
      "label": "Duplicate of trusted item"
    },
    {
      "id": "weak_source",
      "label": "Weak / unverifiable source"
    },
    {
      "id": "unreadable",
      "label": "Unreadable / unusable body"
    },
    {
      "id": "other",
      "label": "Other"
    }
  ],
  "correction_reasons": [
    {
      "id": "bad_extraction",
      "label": "Extraction needs correction"
    },
    {
      "id": "wrong_entity",
      "label": "Entity match incorrect"
    },
    {
      "id": "date_issue",
      "label": "Publication date needs review"
    },
    {
      "id": "provenance_gap",
      "label": "Provenance incomplete"
    },
    {
      "id": "other",
      "label": "Other"
    }
  ],
  "drafts": [
    {
      "draft_id": "pub-readable-ok",
      "fixture_state": "readable_body",
      "headline": "Chilean packer commissions incremental cold rooms in Biob\u00edo",
      "source_name": "Fresh Produce News (synthetic)",
      "source_url": "https://example.test/synthetic/biobio-cold-rooms",
      "source_type": "trade_press",
      "publication_date": "2026-09-14",
      "publication_date_confidence": "high",
      "discovered_at": "2026-09-14T18:22:00Z",
      "captured_at": "2026-09-15T07:10:00Z",
      "content_quality": "readable",
      "content_quality_label": "Readable body",
      "acquisition_outcome": "full_article_capture",
      "body_kind": "readable",
      "body_text": "Agrofruta Sur commissioned two additional cold rooms at its Biob\u00edo packing site, citing peak-export volume pressure for the 2026 season. Capacity is described as incremental, not a new facility. Managers did not disclose capital expenditure.",
      "limited_explanation": null,
      "entity_match": {
        "status": "matched",
        "entities": [
          {
            "id": "company-agrofruta-sur",
            "name": "Agrofruta Sur",
            "type": "company"
          }
        ]
      },
      "duplicate": null,
      "provenance_warnings": [],
      "blocking_warnings": [],
      "needs_attention_rank": 3,
      "attention_reasons": [],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-14T18:22:00Z",
          "detail": "RSS discovery"
        },
        {
          "step": "captured",
          "at": "2026-09-15T07:10:00Z",
          "detail": "Full article body stored"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-15T07:11:00Z",
          "detail": "Publication draft created for review"
        }
      ],
      "review_history": [],
      "queue_state": "pending",
      "version": 1
    },
    {
      "draft_id": "pub-transcript",
      "fixture_state": "transcript",
      "headline": "Podcast: Peruvian highbush outlook \u2014 Lambayeque growers roundtable",
      "source_name": "Andean Berry Audio (synthetic)",
      "source_url": "https://example.test/synthetic/lambayeque-podcast",
      "source_type": "podcast",
      "publication_date": "2026-09-12",
      "publication_date_confidence": "medium",
      "discovered_at": "2026-09-12T21:00:00Z",
      "captured_at": "2026-09-13T09:40:00Z",
      "content_quality": "transcript",
      "content_quality_label": "Supported transcript",
      "acquisition_outcome": "transcript_capture",
      "body_kind": "transcript",
      "body_text": "[00:04:12] Host: Acreage guidance for Lambayeque highbush was revised upward.\n[00:04:40] Grower: Figures remain draft pending association sign-off.\n[00:05:05] Host: No export volumes were confirmed on air.",
      "limited_explanation": null,
      "entity_match": {
        "status": "matched",
        "entities": [
          {
            "id": "company-valle-azul",
            "name": "Valle Azul Growers",
            "type": "company"
          }
        ]
      },
      "duplicate": null,
      "provenance_warnings": [
        {
          "code": "audio_source",
          "level": "info",
          "message": "Transcript derived from audio; verify speaker attribution if promoting claims."
        }
      ],
      "blocking_warnings": [],
      "needs_attention_rank": 4,
      "attention_reasons": [],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-12T21:00:00Z",
          "detail": "Podcast feed"
        },
        {
          "step": "captured",
          "at": "2026-09-13T09:40:00Z",
          "detail": "Transcript extracted"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-13T09:41:00Z",
          "detail": "Publication draft staged"
        }
      ],
      "review_history": [],
      "queue_state": "pending",
      "version": 1
    },
    {
      "draft_id": "pub-metadata-only",
      "fixture_state": "metadata_only",
      "headline": "Industry note listed without usable body",
      "source_name": "Softfruit Index Desk (synthetic)",
      "source_url": "https://example.test/synthetic/metadata-only",
      "source_type": "aggregator",
      "publication_date": "2026-09-10",
      "publication_date_confidence": "medium",
      "discovered_at": "2026-09-10T12:00:00Z",
      "captured_at": "2026-09-10T12:05:00Z",
      "content_quality": "limited",
      "content_quality_label": "Metadata only",
      "acquisition_outcome": "metadata_only",
      "body_kind": "limited",
      "body_text": null,
      "limited_explanation": "Capture stored title, source, and dates only. No readable article body or transcript is available in-app.",
      "entity_match": {
        "status": "matched",
        "entities": [
          {
            "id": "company-costa-roja",
            "name": "Costa Roja Berries",
            "type": "company"
          }
        ]
      },
      "duplicate": null,
      "provenance_warnings": [
        {
          "code": "no_body",
          "level": "warn",
          "message": "No readable body \u2014 publication approval still possible but Evidence richness will be limited."
        }
      ],
      "blocking_warnings": [],
      "needs_attention_rank": 2,
      "attention_reasons": [
        "limited_content"
      ],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-10T12:00:00Z",
          "detail": "Index listing"
        },
        {
          "step": "captured",
          "at": "2026-09-10T12:05:00Z",
          "detail": "Metadata-only acquisition"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-10T12:06:00Z",
          "detail": "Staged for review"
        }
      ],
      "review_history": [],
      "queue_state": "pending",
      "version": 1
    },
    {
      "draft_id": "pub-nav-shell",
      "fixture_state": "navigation_only_shell",
      "headline": "Navigation shell capture \u2014 cookie / menu frame",
      "source_name": "Consent Gate Capture (synthetic)",
      "source_url": "https://example.test/synthetic/nav-shell",
      "source_type": "unknown",
      "publication_date": null,
      "publication_date_confidence": "none",
      "discovered_at": "2026-09-15T08:00:00Z",
      "captured_at": "2026-09-15T08:01:00Z",
      "content_quality": "problem",
      "content_quality_label": "Navigation-only shell",
      "acquisition_outcome": "navigation_shell",
      "body_kind": "problem",
      "body_text": null,
      "limited_explanation": "Captured page is a navigation/cookie shell. It is not article content. Do not invent a summary.",
      "entity_match": {
        "status": "missing",
        "entities": []
      },
      "duplicate": null,
      "provenance_warnings": [
        {
          "code": "nav_shell",
          "level": "warn",
          "message": "Navigation-only shell \u2014 not usable as publication body."
        },
        {
          "code": "no_entity",
          "level": "warn",
          "message": "No entity match proposed."
        }
      ],
      "blocking_warnings": [],
      "needs_attention_rank": 1,
      "attention_reasons": [
        "navigation_shell",
        "missing_entity",
        "uncertain_date"
      ],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-15T08:00:00Z",
          "detail": "URL fetch"
        },
        {
          "step": "captured",
          "at": "2026-09-15T08:01:00Z",
          "detail": "Shell HTML only"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-15T08:02:00Z",
          "detail": "Staged with problem state"
        }
      ],
      "review_history": [],
      "queue_state": "pending",
      "version": 1
    },
    {
      "draft_id": "pub-probable-duplicate",
      "fixture_state": "probable_duplicate",
      "headline": "Duplicate wire: Chilean packer cold-chain note (same event)",
      "source_name": "Wire Mirror (synthetic)",
      "source_url": "https://example.test/synthetic/dup-cold-chain",
      "source_type": "wire",
      "publication_date": "2026-09-14",
      "publication_date_confidence": "high",
      "discovered_at": "2026-09-15T10:00:00Z",
      "captured_at": "2026-09-15T10:05:00Z",
      "content_quality": "readable",
      "content_quality_label": "Readable body",
      "acquisition_outcome": "full_article_capture",
      "body_kind": "readable",
      "body_text": "Near-identical recount of the Biob\u00edo cold-room expansion already covered by another synthetic draft (pub-readable-ok).",
      "limited_explanation": null,
      "entity_match": {
        "status": "matched",
        "entities": [
          {
            "id": "company-agrofruta-sur",
            "name": "Agrofruta Sur",
            "type": "company"
          }
        ]
      },
      "duplicate": {
        "status": "probable",
        "candidate_id": "pub-readable-ok",
        "candidate_title": "Chilean packer commissions incremental cold rooms in Biob\u00edo",
        "similarity": 0.91
      },
      "provenance_warnings": [
        {
          "code": "probable_duplicate",
          "level": "warn",
          "message": "Probable duplicate of another pending draft \u2014 warning, not an automatic blocker."
        }
      ],
      "blocking_warnings": [],
      "needs_attention_rank": 1,
      "attention_reasons": [
        "probable_duplicate"
      ],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-15T10:00:00Z",
          "detail": "Wire ingest"
        },
        {
          "step": "captured",
          "at": "2026-09-15T10:05:00Z",
          "detail": "Full body"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-15T10:06:00Z",
          "detail": "Duplicate detector flagged"
        }
      ],
      "review_history": [],
      "queue_state": "pending",
      "version": 1
    },
    {
      "draft_id": "pub-uncertain-date",
      "fixture_state": "uncertain_date",
      "headline": "Undated industry PDF on Dutch greenhouse strawberries",
      "source_name": "Undated Industry PDF (synthetic)",
      "source_url": "https://example.test/synthetic/undated-pdf",
      "source_type": "pdf",
      "publication_date": null,
      "publication_date_confidence": "low",
      "discovered_at": "2026-09-11T15:00:00Z",
      "captured_at": "2026-09-11T15:20:00Z",
      "content_quality": "readable",
      "content_quality_label": "Readable body",
      "acquisition_outcome": "pdf_extract",
      "body_kind": "readable",
      "body_text": "Readable PDF excerpt without a reliable publisher date. Unknown-date limitation must be retained even if publication is approved.",
      "limited_explanation": null,
      "entity_match": {
        "status": "matched",
        "entities": [
          {
            "id": "company-westland",
            "name": "Westland Greenhouse Group",
            "type": "company"
          }
        ]
      },
      "duplicate": null,
      "provenance_warnings": [
        {
          "code": "uncertain_date",
          "level": "warn",
          "message": "Publication date uncertain \u2014 not an automatic approval blocker."
        }
      ],
      "blocking_warnings": [],
      "needs_attention_rank": 2,
      "attention_reasons": [
        "uncertain_date"
      ],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-11T15:00:00Z",
          "detail": "PDF crawl"
        },
        {
          "step": "captured",
          "at": "2026-09-11T15:20:00Z",
          "detail": "Text extracted"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-11T15:21:00Z",
          "detail": "Date confidence low"
        }
      ],
      "review_history": [],
      "queue_state": "pending",
      "version": 1
    },
    {
      "draft_id": "pub-missing-entity",
      "fixture_state": "missing_entity_match",
      "headline": "Softfruit tray pricing note with unresolved subject",
      "source_name": "Entity Noise Desk (synthetic)",
      "source_url": "https://example.test/synthetic/missing-entity",
      "source_type": "trade_press",
      "publication_date": "2026-09-09",
      "publication_date_confidence": "high",
      "discovered_at": "2026-09-09T16:00:00Z",
      "captured_at": "2026-09-09T16:10:00Z",
      "content_quality": "readable",
      "content_quality_label": "Readable body",
      "acquisition_outcome": "full_article_capture",
      "body_kind": "readable",
      "body_text": "Body discusses strawberry tray pricing in California but entity resolution proposed no confident company match.",
      "limited_explanation": null,
      "entity_match": {
        "status": "missing",
        "entities": []
      },
      "duplicate": null,
      "provenance_warnings": [
        {
          "code": "missing_entity",
          "level": "warn",
          "message": "No entity match \u2014 operator should confirm before approval."
        }
      ],
      "blocking_warnings": [],
      "needs_attention_rank": 2,
      "attention_reasons": [
        "missing_entity"
      ],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-09T16:00:00Z",
          "detail": "Trade RSS"
        },
        {
          "step": "captured",
          "at": "2026-09-09T16:10:00Z",
          "detail": "Full body"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-09T16:11:00Z",
          "detail": "Entity unresolved"
        }
      ],
      "review_history": [],
      "queue_state": "pending",
      "version": 1
    },
    {
      "draft_id": "pub-upgraded",
      "fixture_state": "upgraded_acquisition",
      "headline": "Spanish raspberry programme note \u2014 body upgraded after reacquisition",
      "source_name": "Iberia Softfruit Digest (synthetic)",
      "source_url": "https://example.test/synthetic/upgraded-body",
      "source_type": "trade_press",
      "publication_date": "2026-09-08",
      "publication_date_confidence": "high",
      "discovered_at": "2026-09-08T11:00:00Z",
      "captured_at": "2026-09-15T11:30:00Z",
      "content_quality": "readable",
      "content_quality_label": "Readable body (upgraded)",
      "acquisition_outcome": "reacquisition_upgrade",
      "body_kind": "readable",
      "body_text": "Originally metadata-only; reacquisition retrieved a full readable body describing a UK retailer programme citation for Costa Roja Berries.",
      "limited_explanation": null,
      "entity_match": {
        "status": "matched",
        "entities": [
          {
            "id": "company-costa-roja",
            "name": "Costa Roja Berries",
            "type": "company"
          }
        ]
      },
      "duplicate": null,
      "provenance_warnings": [
        {
          "code": "upgraded",
          "level": "info",
          "message": "Acquisition upgraded from metadata-only to full body on 2026-09-15."
        }
      ],
      "blocking_warnings": [],
      "needs_attention_rank": 3,
      "attention_reasons": [],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-08T11:00:00Z",
          "detail": "Initial listing"
        },
        {
          "step": "captured",
          "at": "2026-09-08T11:05:00Z",
          "detail": "Metadata only"
        },
        {
          "step": "reacquired",
          "at": "2026-09-15T11:30:00Z",
          "detail": "Full body upgrade"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-15T11:31:00Z",
          "detail": "Restaged after upgrade"
        }
      ],
      "review_history": [
        {
          "at": "2026-09-08T12:00:00Z",
          "actor": "operator.alex",
          "action": "defer",
          "note": "Deferred pending better capture"
        }
      ],
      "queue_state": "pending",
      "version": 2
    },
    {
      "draft_id": "pub-concurrent",
      "fixture_state": "already_handled_by_another_reviewer",
      "headline": "Polish cooperatives autumn marketing window (already decided elsewhere)",
      "source_name": "Central Europe Berry Wire (synthetic)",
      "source_url": "https://example.test/synthetic/concurrent",
      "source_type": "trade_press",
      "publication_date": "2026-09-07",
      "publication_date_confidence": "high",
      "discovered_at": "2026-09-07T09:00:00Z",
      "captured_at": "2026-09-07T09:20:00Z",
      "content_quality": "readable",
      "content_quality_label": "Readable body",
      "acquisition_outcome": "full_article_capture",
      "body_kind": "readable",
      "body_text": "Cooperatives in Pomerania aligned on a late-season blueberry promotional calendar.",
      "limited_explanation": null,
      "entity_match": {
        "status": "matched",
        "entities": [
          {
            "id": "company-pomorskie",
            "name": "Pomorskie Berry Coop",
            "type": "company"
          }
        ]
      },
      "duplicate": null,
      "provenance_warnings": [],
      "blocking_warnings": [
        {
          "code": "concurrent_decision",
          "level": "block",
          "message": "Another reviewer already recorded a publication decision for this draft."
        }
      ],
      "needs_attention_rank": 0,
      "attention_reasons": [
        "concurrent_review"
      ],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-07T09:00:00Z",
          "detail": "Wire"
        },
        {
          "step": "captured",
          "at": "2026-09-07T09:20:00Z",
          "detail": "Full body"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-07T09:21:00Z",
          "detail": "Staged"
        },
        {
          "step": "decided",
          "at": "2026-09-15T12:00:00Z",
          "detail": "Approved by operator.jordan"
        }
      ],
      "review_history": [
        {
          "at": "2026-09-15T12:00:00Z",
          "actor": "operator.jordan",
          "action": "approve_publication",
          "note": "Approved while this session was open",
          "resulting_publication_id": "pub-out-seed-001"
        }
      ],
      "queue_state": "approved",
      "version": 2,
      "expected_version_conflict_if_acted": true
    },
    {
      "draft_id": "pub-validation-fail",
      "fixture_state": "validation_failure",
      "headline": "Draft missing required source URL (validation failure)",
      "source_name": "Broken Staging Desk (synthetic)",
      "source_url": null,
      "source_type": "unknown",
      "publication_date": "2026-09-06",
      "publication_date_confidence": "medium",
      "discovered_at": "2026-09-06T14:00:00Z",
      "captured_at": "2026-09-06T14:10:00Z",
      "content_quality": "problem",
      "content_quality_label": "Validation failure",
      "acquisition_outcome": "invalid_draft",
      "body_kind": "problem",
      "body_text": "Body text exists in fixture memory, but draft fails publication validation because source URL is missing.",
      "limited_explanation": "Contractual validation failure: source URL required before publication approval.",
      "entity_match": {
        "status": "matched",
        "entities": [
          {
            "id": "company-valley-soft",
            "name": "Valley Softfruit",
            "type": "company"
          }
        ]
      },
      "duplicate": null,
      "provenance_warnings": [
        {
          "code": "missing_source_url",
          "level": "block",
          "message": "Source URL missing \u2014 contractual blocker for approval."
        }
      ],
      "blocking_warnings": [
        {
          "code": "missing_source_url",
          "level": "block",
          "message": "Cannot approve publication without a source URL."
        }
      ],
      "needs_attention_rank": 1,
      "attention_reasons": [
        "validation_failure"
      ],
      "provenance_chain": [
        {
          "step": "discovered",
          "at": "2026-09-06T14:00:00Z",
          "detail": "Manual stage"
        },
        {
          "step": "captured",
          "at": "2026-09-06T14:10:00Z",
          "detail": "Partial record"
        },
        {
          "step": "draft_staged",
          "at": "2026-09-06T14:11:00Z",
          "detail": "Failed validation"
        }
      ],
      "review_history": [],
      "queue_state": "pending",
      "version": 1
    }
  ]
};
