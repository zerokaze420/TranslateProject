#!/usr/bin/env python3
import sys
import json
import os
import argparse
import requests
from typing import List, Dict, Any, Callable, Set
from dotenv import load_dotenv

# ========================
# 🔐 环境变量加载（静默模式）
# ========================
if not os.getenv("FEISHU_WEBHOOK_URL"):
    load_dotenv()  # 不输出 verbose

FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")

if not FEISHU_WEBHOOK_URL:
    print("❌ FEISHU_WEBHOOK_URL 未设置", file=sys.stderr)
    sys.exit(1)

# ========================
# 🎨 配置
# ========================
COLORS = [
    'carmine', 'orange', 'wathet', 'turquoise', 'green',
    'yellow', 'red', 'violet', 'purple', 'indigo',
    'grey', 'default', 'blue'
]

DEFAULT_LINK_FIELDS = {'url', 'link', 'href', 'website', 'page'}


# ========================
# 🧱 构造卡片
# ========================
def create_feishu_list_card(
    title: str = "系统通知",
    list_items: List[Dict[str, Any]] = None,
    render_item: Callable = None,
    header_text: str = "**数据列表报告**",
    color: str = "blue",
    wide_screen: bool = True,
    link_fields: Set[str] = None,
) -> Dict[str, Any]:
    if list_items is None:
        list_items = []
    if link_fields is None:
        link_fields = DEFAULT_LINK_FIELDS

    if render_item is None:
        def default_render(item: Dict[str, Any], index: int, _list: List[Dict[str, Any]]) -> str:
            lines = [f"**项 {index + 1}**"]
            for k, v in item.items():
                if k in link_fields and isinstance(v, str) and v.startswith(('http://', 'https://')):
                    display_text = v if len(v) < 30 else v[:27] + "..."
                    lines.append(f"{k}: [{display_text}]({v})")
                else:
                    lines.append(f"{k}: {v}")
            return "\n".join(lines)
        render_item = default_render

    list_elements = []
    for index, item in enumerate(list_items):
        content = render_item(item, index, list_items)
        list_elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": content
            }
        })

    return {
        "config": {"wide_screen_mode": wide_screen},
        "header": {
            "template": color,
            "title": {"content": title, "tag": "plain_text"}
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": header_text}},
            *list_elements,
        ]
    }


# ========================
# 📤 发送卡片（静默成功，简洁失败）
# ========================
def send_feishu_card(card: Dict[str, Any]) -> bool:
    try:
        payload = {"msg_type": "interactive", "card": card}
        response = requests.post(FEISHU_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("code") == 0:
            print("✅", end="", file=sys.stderr)  # 可选：成功只打一个 ✅
            return True
        else:
            print(f"❌ 发送失败 (code {result.get('code')})", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ 请求异常: {type(e).__name__}", file=sys.stderr)
        return False


# ========================
# 🚀 主函数（静默处理输入）
# ========================
def main():
    parser = argparse.ArgumentParser(add_help=False)  # 静默模式可选关闭 help
    parser.add_argument('-t', '--title', default="系统通知")
    parser.add_argument('-H', '--header-text', default="**数据列表报告**")
    parser.add_argument('-c', '--color', default="blue", choices=COLORS)
    parser.add_argument('--narrow', action='store_true')
    parser.add_argument('-f', '--file', type=str)
    parser.add_argument('--link-fields', type=str, default="url,link,href")

    args = parser.parse_args()
    link_fields = set(field.strip() for field in args.link_fields.split(',') if field.strip())

    try:
        raw_data = open(args.file, encoding='utf-8').read() if args.file else sys.stdin.read()
        list_items = json.loads(raw_data)
        if not isinstance(list_items, list):
            raise ValueError("非数组")
    except Exception:
        print("❌ JSON 输入错误", file=sys.stderr)
        sys.exit(1)

    card = create_feishu_list_card(
        title=args.title,
        list_items=list_items,
        header_text=args.header_text,
        color=args.color,
        wide_screen=not args.narrow,
        link_fields=link_fields
    )

    if not send_feishu_card(card):
        sys.exit(1)


if __name__ == "__main__":
    main()