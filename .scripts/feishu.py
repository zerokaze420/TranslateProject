#!/usr/bin/env python3
import sys
import json
import os
import argparse
import requests
from typing import List, Dict, Any, Callable, Set
from dotenv import load_dotenv

# ========================
# 环境变量加载（安全兼容模式）
# ========================
# 仅当环境变量未设置时，才尝试加载 .env 文件（本地开发友好）
if not os.getenv("FEISHU_WEBHOOK_URL"):
    load_dotenv(verbose=True)  # verbose=True 会在控制台提示是否加载成功

FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")

if not FEISHU_WEBHOOK_URL:
    raise SystemExit(
        "❌ 请设置环境变量 FEISHU_WEBHOOK_URL\n"
        "   • 本地开发：创建 .env 文件并写入 FEISHU_WEBHOOK_URL=your_url\n"
        "   • GitHub Actions：在 Settings > Secrets 中设置，并在 workflow 中通过 env 注入"
    )

# ========================
# 配置常量
# ========================
# 支持的颜色模板
COLORS = [
    'carmine', 'orange', 'wathet', 'turquoise', 'green',
    'yellow', 'red', 'violet', 'purple', 'indigo',
    'grey', 'default', 'blue'
]

# 默认识别为链接的字段名（可自定义）
DEFAULT_LINK_FIELDS = {'url', 'link', 'href', 'website', 'page'}


# ========================
# 核心函数：构造飞书列表卡片
# ========================
def create_feishu_list_card(
    title: str = "系统通知",
    list_items: List[Dict[str, Any]] = None,
    render_item: Callable[[Dict[str, Any], int, List[Dict[str, Any]]], str] = None,
    header_text: str = "**数据列表报告**",
    color: str = "blue",
    wide_screen: bool = True,
    link_fields: Set[str] = None,
) -> Dict[str, Any]:
    """
    构造飞书列表卡片（支持超链接）
    """
    if list_items is None:
        list_items = []
    if link_fields is None:
        link_fields = DEFAULT_LINK_FIELDS

    if render_item is None:
        def default_render(item: Dict[str, Any], index: int, _list: List[Dict[str, Any]]) -> str:
            lines = [f"**项 {index + 1}**"]
            for k, v in item.items():
                if k in link_fields and isinstance(v, str) and v.startswith(('http://', 'https://')):
                    # 渲染为 [显示文字](链接)
                    display_text = v if len(v) < 30 else v[:27] + "..."
                    lines.append(f"{k}: [{display_text}]({v})")
                else:
                    lines.append(f"{k}: {v}")
            return "\n".join(lines)
        render_item = default_render

    # 渲染每一项为 div 元素
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

    # 构建完整卡片（无 note 提醒）
    card = {
        "config": {
            "wide_screen_mode": wide_screen
        },
        "header": {
            "template": color,
            "title": {
                "content": title,
                "tag": "plain_text"
            }
        },
        "elements": [
            # 头部说明文字
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": header_text
                }
            },
            # 列表内容
            *list_elements,
        ]
    }

    return card


# ========================
# 发送卡片到飞书
# ========================
def send_feishu_card(card: Dict[str, Any]) -> bool:
    """
    发送飞书卡片
    """
    try:
        payload = {
            "msg_type": "interactive",
            "card": card
        }
        response = requests.post(FEISHU_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("code") == 0:
            print("✅ 飞书卡片发送成功", file=sys.stderr)
            return True
        else:
            print(f"❌ 发送失败: {result}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}", file=sys.stderr)
        return False


# ========================
# 主函数
# ========================
def main():
    parser = argparse.ArgumentParser(
        description="发送 JSON 数据列表到飞书群聊（支持超链接）",
        epilog="""示例：
echo '[{"name":"GitHub","url":"https://github.com"}]' | ./feishu-send.py -t "链接列表"
"""
    )
    parser.add_argument(
        '-t', '--title',
        default="系统通知",
        help="卡片标题 (默认: 系统通知)"
    )
    parser.add_argument(
        '-H', '--header-text',
        default="**数据列表报告**",
        help="卡片头部说明文字 (默认: **数据列表报告**)"
    )
    parser.add_argument(
        '-c', '--color',
        default="blue",
        choices=COLORS,
        help="卡片颜色模板 (默认: blue)"
    )
    parser.add_argument(
        '--narrow',
        action='store_true',
        help="禁用宽屏模式（默认启用宽屏）"
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        help="从文件读取 JSON 数据（若未指定，则从 stdin 读取）"
    )
    parser.add_argument(
        '--link-fields',
        type=str,
        default="url,link,href",
        help="指定哪些字段应被识别为超链接，逗号分隔 (默认: url,link,href)"
    )

    args = parser.parse_args()

    # 解析 link-fields
    link_fields = set(field.strip() for field in args.link_fields.split(',') if field.strip())

    # 读取数据
    try:
        if args.file:
            with open(args.file, 'r', encoding='utf-8') as f:
                raw_data = f.read()
        else:
            raw_data = sys.stdin.read()

        list_items = json.loads(raw_data)
        if not isinstance(list_items, list):
            raise ValueError("输入数据必须是 JSON 数组")

    except Exception as e:
        print(f"❌ 数据读取失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 构造卡片
    card = create_feishu_list_card(
        title=args.title,
        list_items=list_items,
        header_text=args.header_text,
        color=args.color,
        wide_screen=not args.narrow,
        link_fields=link_fields
    )

    # 发送
    if not send_feishu_card(card):
        sys.exit(1)


# ========================
# 入口
# ========================
if __name__ == "__main__":
    main()