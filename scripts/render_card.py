#!/usr/bin/env python3
"""把测试结果 JSON 渲染成可分享的 HTML 卡片。

用法: python3 render_card.py result.json out.html

result.json 格式:
{
  "name": "项目名",
  "dims": [                       # 固定顺序: EI, SN, TF, JP
    {"pct": 68, "evidence": ["证据1", "证据2"]},   # 偏前者(E/S/T/J)的百分比，0~100，不能是 50
    ...
  ],
  "strength": "优势，一两句",
  "weakness": "待改进，一两句",
  "summary": "总评，一整段，轻松有趣"
}
类型、称号、吐槽由脚本根据百分比和 types.json 自动补全。
"""
import html
import json
import sys
from pathlib import Path

PAIRS = [("E", "I", "对外开放", "对内聚焦"), ("S", "N", "务实具体", "前瞻抽象"),
         ("T", "F", "严谨验证", "体验导向"), ("J", "P", "规范有序", "灵活迭代")]


def main():
    if len(sys.argv) < 3:
        sys.exit("用法: render_card.py result.json out.html")
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    types = json.loads((Path(__file__).parent.parent / "references" / "types.json")
                       .read_text(encoding="utf-8"))
    dims = data["dims"]
    if len(dims) != 4:
        sys.exit("dims 必须有 4 项")

    letters, rows = "", ""
    for (a, b, na, nb), d in zip(PAIRS, dims):
        p = d["pct"]
        if not 0 <= p <= 100 or p == 50:
            sys.exit("pct 必须在 0~100 之间且不能为 50")
        first = p > 50
        letters += a if first else b
        width = abs(p - 50)  # 条形从中线向一侧延伸，最多 50%
        # 左端是前者，偏前者时条形向左延伸；右端是后者，条形向右延伸
        pos = "right:50%" if first else "left:50%"
        tag = '<span class="wobble">摇摆中</span>' if width <= 5 else ""
        ev = "".join(f"<li>{html.escape(e)}</li>" for e in d.get("evidence", []))
        rows += f"""
    <div class="dim">
      <div class="labels"><span class="{'on' if first else ''}">{a} {na} {p:g}%</span>{tag}
        <span class="{'' if first else 'on'}">{100 - p:g}% {nb} {b}</span></div>
      <div class="track"><div class="mid"></div>
        <div class="fill" style="{pos};width:{width}%"></div></div>
      <ul>{ev}</ul>
    </div>"""

    info = types.get(letters, {"title": "神秘类型", "roast": ""})
    page = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(data['name'])} 的 MBTI</title>
<style>
body{{margin:0;padding:24px 16px;background:#f4f1ec;font-family:-apple-system,"PingFang SC",sans-serif;color:#2a2a2a}}
.card{{max-width:460px;margin:auto;background:#fff;border-radius:20px;padding:28px 24px;box-shadow:0 6px 24px rgba(0,0,0,.08)}}
.name{{font-size:14px;color:#888}}
.type{{font-size:56px;font-weight:800;letter-spacing:4px;margin:4px 0}}
.title{{font-size:18px;font-weight:600}}
.roast{{margin:8px 0 22px;color:#666;font-size:14px}}
.dim{{margin-bottom:18px}}
.labels{{display:flex;justify-content:space-between;font-size:13px;color:#aaa}}
.labels .on{{color:#2a2a2a;font-weight:700}}
.track{{position:relative;height:10px;background:#eee;border-radius:5px;margin:6px 0}}
.mid{{position:absolute;left:50%;top:-2px;width:2px;height:14px;background:#ccc}}
.fill{{position:absolute;top:0;height:10px;background:#4a6cf7;border-radius:5px}}
ul{{margin:6px 0 0;padding-left:18px;font-size:12px;color:#777}}
.sum{{font-size:14px;line-height:1.6;border-top:1px solid #eee;padding-top:14px}}
.wrap{{margin-top:14px;padding:14px;background:#f7f8ff;border-radius:12px;font-size:14px}}
.wrap p{{margin:6px 0 0;line-height:1.8;color:#444}}
.wobble{{font-size:11px;color:#c77700;background:#fff1d6;border-radius:8px;padding:1px 8px}}
.foot{{margin-top:14px;font-size:11px;color:#bbb;text-align:center}}
</style></head><body><div class="card">
<div class="name">{html.escape(data['name'])} 的 MBTI</div>
<div class="type">{letters}</div>
<div class="title">{html.escape(info['title'])}</div>
<div class="roast">{html.escape(info['roast'])}</div>{rows}
<div class="sum"><b>优势</b>：{html.escape(data.get('strength', ''))}<br>
<b>待改进</b>：{html.escape(data.get('weakness', ''))}</div>
<div class="wrap"><b>总评</b><p>{html.escape(data.get('summary', ''))}</p></div>
<div class="foot">Project MBTI</div>
</div></body></html>"""
    Path(sys.argv[2]).write_text(page, encoding="utf-8")
    print(f"{letters} {info['title']} -> {sys.argv[2]}")


if __name__ == "__main__":
    main()
