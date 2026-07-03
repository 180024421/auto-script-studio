"""vision_pc 识字过滤测试。"""

from __future__ import annotations

from studio.services.vision_pc import TextHit, filter_text_hits


def test_filter_text_hits_contains():
    hits = [
        TextHit("确定", 10, 20, 0.9),
        TextHit("取消", 30, 40, 0.8),
    ]
    out = filter_text_hits(hits, "定", match_mode="contains")
    assert len(out) == 1
    assert out[0].text == "确定"


def test_filter_text_hits_exact():
    hits = [TextHit("确定", 10, 20, 0.9), TextHit("确定吧", 30, 40, 0.8)]
    out = filter_text_hits(hits, "确定", match_mode="exact")
    assert len(out) == 1
    assert out[0].text == "确定"
