#!/usr/bin/env python3
"""
Card Snapshot - 智能从网页中导出卡片元素为 PNG 图片

自动检测卡片选择器、iframe、并生成输出目录

使用方法:
    # 自动检测（推荐）
    python card_snapshot.py "https://example.com"
    
    # 指定选择器
    python card_snapshot.py "https://example.com" -s ".card"
    
    # 处理本地文件
    python card_snapshot.py "page.html"
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("错误: 请先安装 playwright")
    print("  pip install playwright")
    print("  python -m playwright install chromium")
    sys.exit(1)


# 常见的卡片选择器，按优先级排序
# 精确选择器在前，模糊选择器在后
COMMON_SELECTORS = [
    ".poster-card",
    ".card",
    ".post-card",
    ".article-card",
    ".item-card",
    ".grid-item",
    ".slide",
]

# 模糊选择器（作为后备）
FUZZY_SELECTORS = [
    "[class*='card']",
    "[class*='item']",
]


def path_to_file_url(path: Path) -> str:
    """将本地路径转换为 file:// URL"""
    return path.resolve().as_uri()


def is_url(s: str) -> bool:
    """判断字符串是否为 URL"""
    try:
        result = urlparse(s)
        return result.scheme in ("http", "https")
    except ValueError:
        return False


def generate_output_dir(target: str) -> str:
    """根据 URL 或文件名自动生成输出目录"""
    if is_url(target):
        parsed = urlparse(target)
        # 提取域名和路径的关键部分
        domain = parsed.netloc.replace("www.", "").split(".")[0]
        path_parts = [p for p in parsed.path.split("/") if p and len(p) < 30]
        if path_parts:
            name = f"{domain}-{path_parts[-1][:20]}"
        else:
            name = domain
    else:
        # 本地文件：使用文件名（不含扩展名）
        name = Path(target).stem

    # 清理非法字符
    name = re.sub(r"[^\w\-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")

    return f"./outputs/cards-{name}"


def detect_selectors(target_ctx, page) -> list:
    """检测页面中可能的卡片选择器
    
    返回: [(selector, total_count, valid_count, is_fuzzy), ...]
    优先返回精确选择器，模糊选择器作为后备
    """
    results = []

    def check_selector(selector: str, is_fuzzy: bool = False):
        try:
            elements = target_ctx.query_selector_all(selector)
            if elements and len(elements) >= 2:  # 至少有2个元素才算有效
                # 检查元素是否有合理的尺寸
                valid_count = 0
                for el in elements[:5]:  # 只检查前5个
                    try:
                        box = el.bounding_box()
                        if box and box["width"] > 50 and box["height"] > 50:
                            valid_count += 1
                    except Exception:
                        pass
                if valid_count >= 2:
                    results.append((selector, len(elements), valid_count, is_fuzzy))
        except Exception:
            pass

    # 先检查精确选择器
    for selector in COMMON_SELECTORS:
        check_selector(selector, is_fuzzy=False)
    
    # 再检查模糊选择器（作为后备）
    for selector in FUZZY_SELECTORS:
        check_selector(selector, is_fuzzy=True)

    # 排序优先级：
    # 1. 精确选择器优先（is_fuzzy=False 排前面）
    # 2. 有效元素数量多的优先
    # 3. 总元素数量少的优先（更精确的匹配）
    results.sort(key=lambda x: (x[3], -x[2], x[1]))
    return results


def detect_iframe(page) -> tuple:
    """检测是否有包含卡片内容的 iframe"""
    frames = page.frames
    if len(frames) <= 1:
        return None, None

    all_selectors = COMMON_SELECTORS + FUZZY_SELECTORS
    for frame in frames:
        if frame == page.main_frame:
            continue
        try:
            # 检查 iframe 中是否有卡片选择器
            for selector in all_selectors:
                elements = frame.query_selector_all(selector)
                if elements and len(elements) >= 2:
                    return frame, frame.url
        except Exception:
            pass

    return None, None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="智能从网页中导出卡片元素为 PNG 图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "https://example.com"                    # 自动检测
  %(prog)s "https://example.com" -s ".card"         # 指定选择器
  %(prog)s "page.html" -o "./my-cards"              # 自定义输出目录
  %(prog)s "https://example.com" --list-selectors   # 列出检测到的选择器
        """,
    )
    parser.add_argument(
        "target",
        help="网页 URL 或本地 HTML 文件路径",
    )
    parser.add_argument(
        "-s", "--selector",
        default="",
        help="卡片元素的 CSS 选择器（留空则自动检测）",
    )
    parser.add_argument(
        "-f", "--frame",
        default="",
        help="iframe URL 包含的字符串（留空则自动检测）",
    )
    parser.add_argument(
        "-o", "--output",
        default="",
        help="输出目录（留空则自动生成）",
    )
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=1600,
        help="浏览器视口宽度 (默认: 1600)",
    )
    parser.add_argument(
        "-H", "--height",
        type=int,
        default=1200,
        help="浏览器视口高度 (默认: 1200)",
    )
    parser.add_argument(
        "--prefix",
        default="card",
        help="输出文件名前缀 (默认: card)",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="显示浏览器窗口（调试用）",
    )
    parser.add_argument(
        "--list-selectors",
        action="store_true",
        help="只列出检测到的选择器，不导出",
    )
    args = parser.parse_args()

    # 判断是 URL 还是本地文件
    target = args.target
    if is_url(target):
        target_url = target
        html_path = None
    else:
        html_path = Path(target)
        if not html_path.exists():
            print(f"错误: 文件不存在: {html_path}")
            sys.exit(1)
        target_url = None

    # 自动生成输出目录
    out_dir = Path(args.output) if args.output else Path(generate_output_dir(target))

    headless = not args.show_browser

    print(f"🎯 目标: {target}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": args.width, "height": args.height}
        )
        page = context.new_page()

        # 加载页面
        print("📄 正在加载页面...")
        page.set_default_timeout(60000)
        if target_url:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
        else:
            page.goto(path_to_file_url(html_path), wait_until="networkidle")

        # 等待字体和内容加载
        page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
        page.wait_for_timeout(1000)

        # 检测或使用指定的 iframe
        target_ctx = page
        frame_url = None

        if args.frame:
            # 用户指定了 iframe
            for frame in page.frames:
                if args.frame in frame.url:
                    target_ctx = frame
                    frame_url = frame.url
                    break
            if target_ctx == page:
                print(f"⚠️  未找到匹配的 iframe: {args.frame}")
                print("可用的 frames:")
                for frame in page.frames:
                    print(f"  - {frame.url[:80]}")
        else:
            # 自动检测 iframe
            detected_frame, detected_url = detect_iframe(page)
            if detected_frame:
                target_ctx = detected_frame
                frame_url = detected_url
                print(f"🔍 自动检测到 iframe: {frame_url[:60]}...")

        # 检测或使用指定的选择器
        selector = args.selector
        if not selector:
            print("🔍 自动检测选择器...")
            detected = detect_selectors(target_ctx, page)
            if detected:
                selector = detected[0][0]
                is_fuzzy = detected[0][3]
                fuzzy_hint = " (模糊匹配)" if is_fuzzy else ""
                print(f"   找到选择器: {selector} ({detected[0][1]} 个元素){fuzzy_hint}")
                if len(detected) > 1:
                    print("   其他候选:")
                    for sel, count, valid, fuzzy in detected[1:3]:
                        hint = " (模糊)" if fuzzy else ""
                        print(f"     - {sel} ({count} 个元素){hint}")
            else:
                print("❌ 未检测到卡片元素")
                print("请手动指定选择器: -s '.your-selector'")
                browser.close()
                sys.exit(1)

        if args.list_selectors:
            print("\n检测到的选择器:")
            detected = detect_selectors(target_ctx, page)
            for sel, count, valid, fuzzy in detected:
                hint = " [模糊]" if fuzzy else ""
                print(f"  {sel}: {count} 个元素 ({valid} 个有效){hint}")
            browser.close()
            return

        # 查找元素
        elements = target_ctx.query_selector_all(selector)
        if not elements:
            print(f"❌ 未找到元素: {selector}")
            browser.close()
            sys.exit(1)

        print(f"📦 找到 {len(elements)} 个卡片")
        print(f"📁 输出目录: {out_dir}")
        print()

        # 创建输出目录
        out_dir.mkdir(parents=True, exist_ok=True)

        # 第一轮: 滚动触发懒加载
        print("⏳ 预加载内容...")
        for element in elements:
            try:
                element.scroll_into_view_if_needed()
                page.wait_for_timeout(100)
            except Exception:
                pass

        # 等待懒加载内容渲染
        page.wait_for_timeout(1500)

        # 回到顶部
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)

        # 第二轮: 截图
        print("📸 开始截图...")
        success_count = 0
        for index, element in enumerate(elements, start=1):
            try:
                element.scroll_into_view_if_needed()
                page.wait_for_timeout(300)

                filename = f"{args.prefix}-{index:02d}.png"
                out_path = out_dir / filename
                element.screenshot(path=str(out_path))
                print(f"   [{index}/{len(elements)}] {filename}")
                success_count += 1
            except Exception as e:
                print(f"   [{index}/{len(elements)}] ❌ 失败: {e}")

        browser.close()

    print()
    print(f"✅ 完成! 成功导出 {success_count}/{len(elements)} 张图片")
    print(f"📁 保存位置: {out_dir.absolute()}/")


if __name__ == "__main__":
    main()
