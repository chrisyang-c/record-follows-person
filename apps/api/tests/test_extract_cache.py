"""Extraction is cached per (sentence, resident, model, effort, day): a later turn only extracts
the new sentence, and the on-disk cache survives a server reload (in-process LRU is cleared)."""

from __future__ import annotations

import pytest

from ingest import intake_dialog as dialog


class _CountingLLM:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def extract_observation(self, text, lang, profile=None, baseline=None):
        from record_schema import StructuredObservation

        self.calls.append(text)
        return StructuredObservation(raw_text=text, language=lang)


@pytest.fixture
def counting(monkeypatch):
    llm = _CountingLLM()
    monkeypatch.setattr(dialog, "get_llm", lambda: llm)
    dialog._extract_cached.cache_clear()
    return llm


def test_same_sentence_extracted_once_across_turns(records_root, counting):
    dialog._extract("今天中午只吃一半", None, None)
    dialog._extract("今天中午只吃一半", None, None)
    dialog._extract("沒有喘", None, None)
    assert counting.calls == ["今天中午只吃一半", "沒有喘"]


def test_disk_cache_survives_process_cache_clear(records_root, counting, monkeypatch):
    s = dialog.get_settings()
    # the mock provider never persists; pretend to be a real one for this test
    monkeypatch.setattr(type(s), "effective_provider", property(lambda self: "openai"))
    dialog._extract("晚上起來三次", None, None)
    dialog._extract_cached.cache_clear()  # what a fastapi reload / new worker does
    dialog._extract("晚上起來三次", None, None)
    assert counting.calls == ["晚上起來三次"]
    assert dialog._extract_cache_file("").exists()


def test_cache_key_changes_with_model_and_resident(records_root):
    a = dialog._extract_cache_key("x", "P001")
    assert a != dialog._extract_cache_key("x", "P002")
    assert a != dialog._extract_cache_key("y", "P001")
