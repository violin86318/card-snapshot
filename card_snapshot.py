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
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
    ".page",           # BibiGPT 等知识卡片页面
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

    # 默认输出到用户指定的工作流归档文件夹
    base_dir = "/Users/wanglingwei/Library/Mobile Documents/com~apple~CloudDocs/~Vibe-Coding/card-snapshot"
    return f"{base_dir}/outputs/cards-{name}"


def detect_selectors(target_ctx, page) -> list:
    """检测页面中可能的卡片选择器
    
    返回: [(selector, total_count, valid_count, avg_height, is_fuzzy), ...]
    优先返回精确选择器，模糊选择器作为后备
    """
    results = []

    def check_selector(selector: str, is_fuzzy: bool = False):
        try:
            elements = target_ctx.query_selector_all(selector)
            if elements and len(elements) >= 2:  # 至少有2个元素才算有效
                # 检查元素是否有合理的尺寸
                valid_count = 0
                total_height = 0
                for el in elements[:5]:  # 只检查前5个
                    try:
                        box = el.bounding_box()
                        if box and box["width"] > 50 and box["height"] > 50:
                            valid_count += 1
                            total_height += box["height"]
                    except Exception:
                        pass
                if valid_count >= 2:
                    avg_height = total_height / valid_count if valid_count > 0 else 0
                    results.append((selector, len(elements), valid_count, avg_height, is_fuzzy))
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
    # 2. 平均高度大的优先（真正的卡片通常更高）
    # 3. 总元素数量少的优先（更精确的匹配）
    results.sort(key=lambda x: (x[4], -x[3], x[1]))
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


def retry_failed_with_webkit(
    target: str,
    selector: str,
    out_dir: Path,
    failed_indices: list[int],
    args,
    frame_hint: str | None = None,
) -> tuple[int, list[int]]:
    """用 webkit 重跑到临时目录，再只拷回失败项。"""
    if not failed_indices:
        return 0, []

    temp_dir = Path(tempfile.mkdtemp(prefix="card-snapshot-webkit-"))
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        target,
        "-s",
        selector,
        "-o",
        str(temp_dir),
        "-w",
        str(args.width),
        "-H",
        str(args.height),
        "--prefix",
        args.prefix,
        "--browser",
        "webkit",
    ]

    if frame_hint:
        cmd.extend(["-f", frame_hint])
    if args.show_browser:
        cmd.append("--show-browser")

    print()
    print("🔄 使用 webkit 补拍失败卡片（导出到临时目录后合并回结果）...")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("   ❌ webkit 补拍失败")
        return 0, failed_indices

    recovered = 0
    still_failed = []
    for index in failed_indices:
        filename = f"{args.prefix}-{index:02d}.png"
        src = temp_dir / filename
        dst = out_dir / filename
        if src.exists():
            shutil.copy2(src, dst)
            recovered += 1
            print(f"   ✅ 已补回: {filename}")
        else:
            still_failed.append(index)

    if still_failed:
        print(f"   ⚠️  webkit 仍未补回: {still_failed}")
    else:
        print("   ✅ webkit 已补回全部失败卡片")

    return recovered, still_failed


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
    parser.add_argument(
        "--browser",
        choices=["chromium", "firefox", "webkit"],
        default="chromium",
        help="使用的浏览器引擎 (默认: chromium)",
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
        # Chromium 启动参数：防止大页面导致渲染进程崩溃
        chromium_args = [
            "--disable-gpu",                    # 禁用 GPU 加速（SVG filter 在 CPU 更稳定）
            "--disable-dev-shm-usage",           # 避免 /dev/shm 空间不足
            "--disable-software-rasterizer",     # 禁用软件光栅化
            "--no-sandbox",                      # 减少内存隔离开销
            "--disable-extensions",              # 不加载扩展
            "--disable-background-timer-throttling",
            "--js-flags=--max-old-space-size=4096",  # 增大 V8 堆内存
        ]

        # 选择浏览器引擎
        if args.browser == "firefox":
            browser = p.firefox.launch(headless=headless)
        elif args.browser == "webkit":
            browser = p.webkit.launch(headless=headless)
        else:
            browser = p.chromium.launch(headless=headless, args=chromium_args)
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
                is_fuzzy = detected[0][4]
                avg_h = detected[0][3]
                fuzzy_hint = " (模糊匹配)" if is_fuzzy else ""
                print(f"   找到选择器: {selector} ({detected[0][1]} 个元素, 高度 {avg_h:.0f}px){fuzzy_hint}")
                if len(detected) > 1:
                    print("   其他候选:")
                    for sel, count, valid, avg_height, fuzzy in detected[1:3]:
                        hint = " (模糊)" if fuzzy else ""
                        print(f"     - {sel} ({count} 个元素, 高度 {avg_height:.0f}px){hint}")
            else:
                print("❌ 未检测到卡片元素")
                print("请手动指定选择器: -s '.your-selector'")
                browser.close()
                sys.exit(1)

        if args.list_selectors:
            print("\n检测到的选择器:")
            detected = detect_selectors(target_ctx, page)
            for sel, count, valid, avg_height, fuzzy in detected:
                hint = " [模糊]" if fuzzy else ""
                print(f"  {sel}: {count} 个元素, 高度 {avg_height:.0f}px ({valid} 个有效){hint}")
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

        # 回到顶部（在正确的上下文中执行）
        try:
            if target_ctx != page and hasattr(target_ctx, 'evaluate'):
                target_ctx.evaluate("window.scrollTo(0, 0)")
            else:
                page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass  # 忽略滚动失败
        page.wait_for_timeout(300)

        # 第二轮: 截图（带崩溃恢复）
        print("📸 开始截图...")
        success_count = 0
        use_isolation = False  # 是否使用隔离模式（隐藏其他卡片减少内存）

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
                error_msg = str(e)
                if "Target crashed" in error_msg or "crashed" in error_msg.lower():
                    if not use_isolation:
                        print(f"   [{index}/{len(elements)}] ⚠️  渲染进程崩溃，切换到隔离模式...")
                        use_isolation = True
                    break  # 崩溃后需要重新加载页面
                else:
                    print(f"   [{index}/{len(elements)}] ❌ 失败: {e}")

        # 如果发生了崩溃，用隔离模式重试
        if use_isolation:
            print()
            print("🔄 使用隔离模式重新截图（逐张加载，减少内存压力）...")
            try:
                browser.close()
            except Exception:
                pass

            def launch_browser():
                if args.browser == "firefox":
                    return p.firefox.launch(headless=headless)
                elif args.browser == "webkit":
                    return p.webkit.launch(headless=headless)
                else:
                    return p.chromium.launch(headless=headless, args=chromium_args)

            # 用于移除导致崩溃的重型 CSS 效果的样式
            STRIP_HEAVY_CSS = """
                *::after, *::before {
                    background-image: none !important;
                    filter: none !important;
                }
                svg filter, svg feTurbulence, svg feColorMatrix {
                    display: none !important;
                }
                .noise-filter { display: none !important; }
            """

            browser = launch_browser()
            success_count = 0
            total = len(elements)
            failed_indices = []

            import tempfile
            import os

            for index in range(1, total + 1):
                ok = False
                for attempt in range(2):  # 最多重试 2 次
                    try:
                        context = browser.new_context(
                            viewport={"width": args.width, "height": args.height}
                        )
                        iso_page = context.new_page()
                        iso_page.set_default_timeout(60000)

                        temp_html_path = None
                        
                        # 动态生成每个卡片的专属 CSS：只显示当前卡片，隐藏其他所有卡片
                        CARD_ISOLATION_CSS = f"""
                            /* 隐藏所有卡片 */
                            {selector} {{ display: none !important; }}
                            /* 只显示当前目标的卡片 */
                            {selector}:nth-child({index}) {{ display: flex !important; display: block !important; }}
                            /* 抹除所有可能导致崩溃的伪元素背景和滤镜 */
                            *, *::after, *::before {{
                                filter: none !important;
                                backdrop-filter: none !important;
                            }}
                            .card::after, .card::before, body::before, body::after {{
                                background-image: none !important;
                            }}
                            svg filter, svg feTurbulence, svg feColorMatrix {{
                                display: none !important;
                            }}
                            .noise-filter {{ display: none !important; }}
                        """
                        
                        # 针对本地文件提前预处理 HTML，避免渲染引擎在加载时即崩溃
                        if not target_url:
                            try:
                                with open(html_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                
                                # 终极杀手锏：无脑替换所有的 feTurbulence 为 g（静默失效）
                                # 这比任何正则都可靠，能跨越 base64、内联 CSS、以及深层嵌套
                                content = content.replace("feTurbulence", "g")
                                
                                # 移除残余的专门滤镜外壳
                                content = re.sub(r'<svg[^>]*class="[^"]*noise-filter[^"]*"[^>]*>.*?</svg>', '', content, flags=re.DOTALL)
                                
                                # 将专属 CSS 注入到 head 头部
                                content = content.replace('</head>', f'<style>{CARD_ISOLATION_CSS}</style></head>')
                                
                                fd, temp_html_path = tempfile.mkstemp(suffix=f"_iso_card_{index}.html", dir=html_path.parent)
                                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                                    f.write(content)
                            except Exception as e:
                                print(f"   ⚠️ 预处理 HTML 失败: {e}")
                                temp_html_path = None

                        def handle_route(route):
                            if route.request.resource_type == "document":
                                try:
                                    response = route.fetch()
                                    body = response.text()
                                    body = body.replace("feTurbulence", "g")
                                    body = re.sub(r'<svg[^>]*class="[^"]*noise-filter[^"]*"[^>]*>.*?</svg>', '', body, flags=re.DOTALL)
                                    body = body.replace('</head>', f'<style>{CARD_ISOLATION_CSS}</style></head>')
                                    route.fulfill(response=response, body=body)
                                except Exception:
                                    route.continue_()
                            else:
                                route.continue_()

                        # 重新加载页面
                        if target_url:
                            iso_page.route("**/*", handle_route)
                            iso_page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                            try:
                                iso_page.wait_for_load_state("networkidle", timeout=15000)
                            except Exception:
                                pass
                        else:
                            if temp_html_path:
                                iso_page.goto(path_to_file_url(Path(temp_html_path)), wait_until="networkidle")
                            else:
                                iso_page.goto(path_to_file_url(html_path), wait_until="networkidle")

                        # 等待字体加载
                        iso_page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
                        iso_page.wait_for_timeout(500)

                        # 获取目标元素并截图
                        target_el = iso_page.query_selector(f"{selector}:nth-child({index})")
                        if not target_el:
                            # 由于我们用了 !important 隐藏其他，只需要找可见的
                            visible_els = iso_page.query_selector_all(selector)
                            visible_els = [el for el in visible_els if el.is_visible()]
                            if visible_els:
                                target_el = visible_els[0]

                        if target_el:
                            target_el.scroll_into_view_if_needed()
                            iso_page.wait_for_timeout(300)
                            filename = f"{args.prefix}-{index:02d}.png"
                            out_path = out_dir / filename
                            target_el.screenshot(path=str(out_path))
                            print(f"   [{index}/{total}] {filename}")
                            success_count += 1
                            ok = True
                        else:
                            print(f"   [{index}/{total}] ❌ 未找到元素")
                            ok = True  # 不再重试

                        context.close()
                        
                        # 清理临时文件
                        if temp_html_path and os.path.exists(temp_html_path):
                            try:
                                os.remove(temp_html_path)
                            except Exception:
                                pass
                        
                        break  # 成功，跳出重试循环

                    except Exception as e:
                        error_msg = str(e)
                        try:
                            context.close()
                        except Exception:
                            pass
                            
                        # 清理临时文件
                        if 'temp_html_path' in locals() and temp_html_path and os.path.exists(temp_html_path):
                            try:
                                os.remove(temp_html_path)
                            except Exception:
                                pass

                        if "crashed" in error_msg.lower():
                            # 浏览器崩溃了，需要完全重启
                            try:
                                browser.close()
                            except Exception:
                                pass
                            browser = launch_browser()
                            if attempt == 0:
                                print(f"   [{index}/{total}] ⚠️  崩溃，重启浏览器重试...")
                            else:
                                print(f"   [{index}/{total}] ❌ 重试后仍然崩溃")
                                failed_indices.append(index)
                        else:
                            print(f"   [{index}/{total}] ❌ 失败: {e}")
                            ok = True  # 非崩溃错误不重试
                            break

                if not ok and index not in failed_indices:
                    failed_indices.append(index)

            if failed_indices:
                print(f"\n⚠️  以下卡片因渲染过于复杂而无法截图: {failed_indices}")
                print("   提示: 可尝试 --browser webkit 或简化页面中的 SVG 滤镜")

        try:
            browser.close()
        except Exception:
            pass

    print()
    print(f"✅ 完成! 成功导出 {success_count}/{len(elements)} 张图片")
    print(f"📁 保存位置: {out_dir.absolute()}/")


if __name__ == "__main__":
    main()
