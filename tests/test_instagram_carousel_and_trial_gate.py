"""
Unit tests for Workstream 3 (`pipeline/studio/instagram_uploader.py`):
- `validate_instagram_carousel_slides`: `4:5` (`1080x1350`, `0.80`) passes; `3:4` (`1080x1440`, `0.75` `< 0.80`) rejected; `< 2` or `> 10` slides rejected; `.mp4` slide mixing rejected
- `publish_instagram_carousel_graph_api`: 6 child containers (`is_carousel_item=true`) -> parent `CAROUSEL` -> `FINISHED` -> `media_publish`
- `publish_instagram_reel_graph_api`: `< 1,000` follower gate (`followers_count = 42` omits `trial_params` with `trial_skipped_reason="followers_below_1000"` or raises on `require_trial=True`; `followers_count = 1500` injects `trial_params={"graduation_strategy": "SS_PERFORMANCE"}`)
"""

from __future__ import annotations

import io
import json
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

import pipeline.studio.instagram_uploader as ig_mod
from pipeline.studio.instagram_uploader import (
    publish_instagram_carousel_graph_api,
    publish_instagram_reel_graph_api,
    validate_instagram_carousel_slides,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_validate_instagram_carousel_slides_enforces_ratio_count_and_static_only(tmp_path: Path) -> None:
    slides_ok: list[Path] = []
    for idx in range(1, 7):
        sp = tmp_path / f"slide_{idx:02d}.png"
        Image.new("RGB", (1080, 1350), (16, 24, 36)).save(sp, format="PNG")
        slides_ok.append(sp)

    dims = validate_instagram_carousel_slides(slides_ok)
    assert dims == [(1080, 1350)] * 6

    # Too few slides (<2)
    with pytest.raises(ValueError, match=r"2\.\.10 slides"):
        validate_instagram_carousel_slides(slides_ok[:1])

    # Too many slides (>10)
    eleven = slides_ok + slides_ok[:5]
    with pytest.raises(ValueError, match=r"2\.\.10 slides"):
        validate_instagram_carousel_slides(eleven)

    # 3:4 portrait (1080x1440 -> aspect 0.75 < 0.80) rejected
    bad_3x4 = tmp_path / "bad_3x4.png"
    Image.new("RGB", (1080, 1440), (20, 20, 20)).save(bad_3x4, format="PNG")
    with pytest.raises(ValueError, match="aspect ratio"):
        validate_instagram_carousel_slides([slides_ok[0], bad_3x4])

    # MP4 video mixing rejected
    bad_mp4 = tmp_path / "slide_02.mp4"
    bad_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    with pytest.raises(ValueError, match="do not mix MP4 and PNG slides"):
        validate_instagram_carousel_slides([slides_ok[0], bad_mp4])


def test_publish_instagram_carousel_graph_api_mocked_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    slides: list[Path] = []
    for idx in range(1, 7):
        sp = tmp_path / f"slide_{idx:02d}.png"
        Image.new("RGB", (1080, 1350), (12, 20, 32)).save(sp, format="PNG")
        slides.append(sp)

    calls: list[tuple[str, str, dict[str, list[str]]]] = []
    child_counter = {"n": 0}

    def _fake_urlopen(req_or_url: Any, timeout: float = 30.0) -> _FakeHTTPResponse:
        if isinstance(req_or_url, str):
            url = req_or_url
            method = "GET"
            form: dict[str, list[str]] = {}
        else:
            url = req_or_url.full_url
            method = req_or_url.get_method()
            raw_body = (req_or_url.data or b"").decode("utf-8")
            form = urllib.parse.parse_qs(raw_body)
        calls.append((method, url, form))

        if method == "POST" and url.endswith("/17841400001/media"):
            if form.get("is_carousel_item") == ["true"]:
                child_counter["n"] += 1
                return _FakeHTTPResponse({"id": f"child_{child_counter['n']}"})
            assert form.get("media_type") == ["CAROUSEL"]
            assert form.get("children") == ["child_1,child_2,child_3,child_4,child_5,child_6"]
            return _FakeHTTPResponse({"id": "parent_carousel_99"})
        if method == "GET" and "/parent_carousel_99?" in url:
            return _FakeHTTPResponse({"status_code": "FINISHED"})
        if method == "POST" and url.endswith("/17841400001/media_publish"):
            assert form.get("creation_id") == ["parent_carousel_99"]
            return _FakeHTTPResponse({"id": "published_media_777"})
        if method == "GET" and "/published_media_777?" in url:
            return _FakeHTTPResponse({"permalink": "https://www.instagram.com/p/DCAPGRAS01/", "shortcode": "DCAPGRAS01"})
        raise AssertionError(f"Unexpected HTTP call: {method} {url}")

    monkeypatch.setattr(ig_mod.urllib.request, "urlopen", _fake_urlopen)

    receipt_file = tmp_path / "ig_carousel_receipt.json"
    urls = [f"https://cdn.example.com/slide_{i:02d}.png" for i in range(1, 7)]
    res = publish_instagram_carousel_graph_api(
        ig_user_id="17841400001",
        access_token="IGQW_test_token",
        image_urls=urls,
        caption="6-slide Capgras breakdown · DOI: 10.1098/rspb.1997.0092",
        slide_paths=slides,
        receipt_path=receipt_file,
        poll_interval_sec=0.01,
    )
    assert res["status"] == "published"
    assert res["kind"] == "carousel"
    assert len(res["child_creation_ids"]) == 6
    assert res["shortcode"] == "DCAPGRAS01"
    assert receipt_file.is_file()


def test_publish_instagram_reel_graph_api_trial_follower_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"followers": 42, "last_media_form": {}}

    def _fake_urlopen(req_or_url: Any, timeout: float = 30.0) -> _FakeHTTPResponse:
        if isinstance(req_or_url, str):
            url = req_or_url
            if "fields=followers_count" in url:
                return _FakeHTTPResponse({"followers_count": state["followers"]})
            if "/reel_container_1?" in url:
                return _FakeHTTPResponse({"status_code": "FINISHED"})
            if "/reel_pub_1?" in url:
                return _FakeHTTPResponse({"permalink": "https://www.instagram.com/reel/DREEL01/", "shortcode": "DREEL01"})
            raise AssertionError(f"Unexpected GET {url}")
        raw_body = (req_or_url.data or b"").decode("utf-8")
        form = urllib.parse.parse_qs(raw_body)
        if req_or_url.full_url.endswith("/media"):
            state["last_media_form"] = form
            return _FakeHTTPResponse({"id": "reel_container_1"})
        if req_or_url.full_url.endswith("/media_publish"):
            return _FakeHTTPResponse({"id": "reel_pub_1"})
        raise AssertionError(f"Unexpected POST {req_or_url.full_url}")

    monkeypatch.setattr(ig_mod.urllib.request, "urlopen", _fake_urlopen)

    # Case 1: followers=42 (<1000), require_trial=False -> falls back to standard Reel cleanly
    res_low = publish_instagram_reel_graph_api(
        ig_user_id="17841400001",
        access_token="IGQW_test",
        video_url="https://cdn.example.com/ep08.mp4",
        caption="Capgras Syndrome Reel",
        trial_graduation_strategy="SS_PERFORMANCE",
        require_trial=False,
        poll_interval_sec=0.01,
    )
    assert "trial_params" not in state["last_media_form"]
    assert res_low["trial_enabled"] is False
    assert res_low["trial_skipped_reason"] == "followers_below_1000"
    assert res_low["followers_count"] == 42

    # Case 2: followers=42 (<1000), require_trial=True -> aborts cleanly without publishing
    res_abort = publish_instagram_reel_graph_api(
        ig_user_id="17841400001",
        access_token="IGQW_test",
        video_url="https://cdn.example.com/ep08.mp4",
        caption="Capgras Syndrome Reel",
        trial_graduation_strategy="SS_PERFORMANCE",
        require_trial=True,
        poll_interval_sec=0.01,
    )
    assert res_abort["status"] == "aborted_trial_ineligible"
    assert res_abort["trial_enabled"] is False
    assert res_abort["trial_skipped_reason"] == "followers_below_1000"

    # Case 3: followers=1500 (>=1000) -> injects trial_params!
    state["followers"] = 1500
    res_high = publish_instagram_reel_graph_api(
        ig_user_id="17841400001",
        access_token="IGQW_test",
        video_url="https://cdn.example.com/ep08.mp4",
        caption="Capgras Syndrome Reel",
        trial_graduation_strategy="SS_PERFORMANCE",
        poll_interval_sec=0.01,
    )
    assert "trial_params" in state["last_media_form"]
    parsed_tp = json.loads(state["last_media_form"]["trial_params"][0])
    assert parsed_tp == {"graduation_strategy": "SS_PERFORMANCE"}
    assert res_high["trial_enabled"] is True
    assert res_high.get("trial_skipped_reason") is None
