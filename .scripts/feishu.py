#!/usr/bin/env python3
import sys
import json
import os
import argparse
import requests
from typing import List, Dict, Any, Callable, Set, Optional
from urllib.parse import urljoin
from dotenv import load_dotenv

# ========================
# 🔐 环境变量加载（静默模式）
# ========================
if not os.getenv("FEISHU_WEBHOOK_URL"):
    load_dotenv()

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
DEFAULT_EMOJI_MAP = {
    "success": "✅",
    "fail": "❌",
    "error": "❌",
    "done": "✅",
    "completed": "✅",
    "running": "🔄",
    "pending": "⏳",
    "warning": "⚠️",
}

# ========================
# 🧩 工具函数
# ========================
def is_url(text: str) -> bool:
    if not isinstance(text, str):
        return False
    text = text.strip()
    return text.startswith(('http://', 'https://'))

def ensure_url(text: str, base_url: Optional[str] = None) -> Optional[str]:
    if not isinstance(text, str):
        return None
    text = text.strip()
    if text.startswith(('http://', 'https://')):
        return text
    if base_url:
        return urljoin(base_url.rstrip('/') + '/', text.lstrip('/'))
    return None

# ========================
# 🧱 构造卡片
# ========================
def create_feishu_list_card(
    title: str = "系统通知",
    list_items: List[Dict[str, Any]] = None,
    render_item: Optional[Callable] = None,
    header_text: str = "**数据列表报告**",
    color: str = "blue",
    wide_screen: bool = True,
    link_fields: Set[str] = None,
    link_prefix: Optional[str] = None,
    emoji_fields: Optional[Dict[str, str]] = None,
    compact: bool = False,
) -> Dict[str, Any]:
    if list_items is None:
        list_items = []
    if link_fields is None:
        link_fields = DEFAULT_LINK_FIELDS
    if emoji_fields is None:
        emoji_fields = DEFAULT_EMOJI_MAP

    if render_item is None:
        def default_render(item: Dict[str, Any], index: int, _list: List[Dict[str, Any]]) -> str:
            lines = []
            for k, v in item.items():
                # 处理链接字段
                if k in link_fields:
                    url = ensure_url(v, link_prefix)
                    if url:
                        display_text = "🔗 查看详情"
                        lines.append(f"{k}: [{display_text}]({url})")
                        continue

                # 处理状态字段 → emoji
                if isinstance(v, str) and k in emoji_fields:
                    emoji = emoji_fields.get(v.lower(), None)
                    if emoji:
                        lines.append(f"{k}: {emoji} {v}")
                        continue

                # 默认显示
                display_value = str(v) if v is not None else "—"
                lines.append(f"{k}: {display_value}")

            if compact:
                return " | ".join(lines)
            return "\n".join(lines)

        render_item = default_render

    list_elements = []
    for index, item in enumerate(list_items):
        try:
            content = render_item(item, index, list_items)
        except Exception as e:
            content = f"⚠️ 渲染错误: {type(e).__name__}"
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
            print("✅", end="", file=sys.stderr)
            return True
        else:
            print(f"❌ 发送失败 (code {result.get('code', 'unknown')})", file=sys.stderr)
            return False
    except requests.exceptions.Timeout:
        print("❌ 请求超时", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络错误: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ 未知异常: {type(e).__name__}", file=sys.stderr)
        return False


# ========================
# 🚀 主函数
# ========================
def main():
    parser = argparse.ArgumentParser(
        description="🚀 将 JSON 数据发送为飞书富文本列表卡片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  echo '[{"name":"项目A","url":"https://xxx.com","status":"success"}]' | python3 feishu_card.py -t "部署通知"
  python3 feishu_card.py -f data.json --compact --color green
        """
    )
    parser.add_argument('-t', '--title', default="系统通知", help="卡片标题")
    parser.add_argument('-H', '--header-text', default="**数据列表报告**", help="卡片头部说明文字（支持 Markdown）")
    parser.add_argument('-c', '--color', default="blue", choices=COLORS, help="卡片颜色")
    parser.add_argument('--narrow', action='store_true', help="使用窄屏模式")
    parser.add_argument('-f', '--file', type=str, help="从文件读取 JSON 数据")
    parser.add_argument('--link-fields', type=str, default="url,link,href", help="逗号分隔的链接字段名")
    parser.add_argument('--link-prefix', type=str, help="为非完整 URL 添加前缀（如 https://example.com/#/item/）")
    parser.add_argument('--compact', action='store_true', help="紧凑模式：字段用 | 分隔")
    parser.add_argument('-v', '--verbose', action='store_true', help="显示详细日志")

    args = parser.parse_args()

    # 解析 link_fields
    link_fields = set(field.strip() for field in args.link_fields.split(',') if field.strip())

    # 读取数据
    try:
        raw_data = open(args.file, encoding='utf-8').read() if args.file else sys.stdin.read()
        if args.verbose:
            print("📄 读取数据完成", file=sys.stderr)

        list_items = json.loads(raw_data)
        if not isinstance(list_items, list):
            raise ValueError("输入数据必须是 JSON 数组")

        if args.verbose:
            print(f"✅ 解析 {len(list_items)} 条记录", file=sys.stderr)

    except FileNotFoundError:
        print(f"❌ 文件未找到: {args.file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 数据读取错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 创建卡片
    card = create_feishu_list_card(
        title=args.title,
        list_items=list_items,
        header_text=args.header_text,
        color=args.color,
        wide_screen=not args.narrow,
        link_fields=link_fields,
        link_prefix=args.link_prefix,
        compact=args.compact,
    )

    # 发送
    if send_feishu_card(card):
        if args.verbose:
            print("\n🎉 卡片发送成功！", file=sys.stderr)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()