from __future__ import annotations
from datetime import date, datetime

from todo_cli.parse_text import parse_input

REF = datetime(2026, 5, 8)  # Friday


def test_plain_text_no_extraction():
    r = parse_input("buy milk", ref=REF)
    assert r.text == "buy milk"
    assert r.due is None
    assert r.priority is None
    assert r.tags == []
    assert r.project is None


def test_trailing_date_extracted():
    r = parse_input("buy milk tomorrow", ref=REF)
    assert r.text == "buy milk"
    assert r.due == date(2026, 5, 9)


def test_due_trigger_strips_trigger_word():
    r = parse_input("project review due today", ref=REF)
    assert r.text == "project review"
    assert r.due == date(2026, 5, 8)


def test_by_trigger():
    r = parse_input("finish report by friday", ref=REF)
    assert r.text == "finish report"
    assert r.due == date(2026, 5, 15)


def test_on_trigger():
    r = parse_input("meeting on may 15", ref=REF)
    assert r.text == "meeting"
    assert r.due == date(2026, 5, 15)


def test_iso_date_at_end():
    r = parse_input("review pr 2026-06-01", ref=REF)
    assert r.text == "review pr"
    assert r.due == date(2026, 6, 1)


def test_mid_string_date_not_stripped():
    r = parse_input("remember tomorrow's meeting", ref=REF)
    assert r.text == "remember tomorrow's meeting"
    assert r.due is None


def test_due_phrase_not_a_date():
    r = parse_input("fix bug due to error", ref=REF)
    assert r.text == "fix bug due to error"
    assert r.due is None


def test_time_only_ignored():
    r = parse_input("meeting at 3pm", ref=REF)
    assert r.due is None


def test_tag_extracted():
    r = parse_input("buy milk #shopping", ref=REF)
    assert r.text == "buy milk"
    assert r.tags == ["shopping"]


def test_multiple_tags():
    r = parse_input("buy milk #shop #urgent", ref=REF)
    assert r.text == "buy milk"
    assert r.tags == ["shop", "urgent"]


def test_project_extracted():
    r = parse_input("buy milk @groceries", ref=REF)
    assert r.text == "buy milk"
    assert r.project == "groceries"


def test_high_priority_words():
    for phrase in ["urgent", "p1", "high priority"]:
        r = parse_input(f"task {phrase}", ref=REF)
        assert r.priority == "high", phrase
        assert "task" in r.text


def test_low_priority_words():
    for phrase in ["p3", "low priority"]:
        r = parse_input(f"task {phrase}", ref=REF)
        assert r.priority == "low", phrase


def test_med_priority_words():
    for phrase in ["p2", "medium priority", "med priority"]:
        r = parse_input(f"task {phrase}", ref=REF)
        assert r.priority == "med", phrase


def test_combined_extraction():
    r = parse_input("fix critical bug by friday p1 #work @backend", ref=REF)
    assert r.text == "fix critical bug"
    assert r.due == date(2026, 5, 15)
    assert r.priority == "high"
    assert "work" in r.tags
    assert r.project == "backend"


def test_empty_title_after_strip_keeps_original():
    # "due tomorrow" alone would empty the title; should fall back to no extraction
    r = parse_input("due tomorrow", ref=REF)
    assert "tomorrow" in r.text
    assert r.due is None


def test_whitespace_collapsed():
    r = parse_input("  buy   milk   #urgent  ", ref=REF)
    assert r.text == "buy milk"


def test_in_n_days():
    r = parse_input("ship release in 3 days", ref=REF)
    assert r.text == "ship release"
    assert r.due == date(2026, 5, 11)
