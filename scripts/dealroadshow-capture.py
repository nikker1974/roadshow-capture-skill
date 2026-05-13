#!/usr/bin/env python3
"""
DealRoadShow 自动化捕获脚本 — Playwright 版

已验证流程（2026-05-13，ArcelorMittal USD Bond issuance，32 slides）：

  1. 导航到 deal URL → 填邮箱 → Launch Deal Roadshow
  2. 进入 disclaimer 页 → I Agree
  3. 进入幻灯片页 → ArrowRight 逐页翻 → 截图 → Pillow 合成 PDF

与 NetRoadShow 的区别：
  ✓ 不需要弹窗处理（没有 expect_popup）
  ✓ URL 基于页码：.../e/MTNA2026/1, /2, /3...
  ✓ 免责声明按钮是标准 button 元素，非 div
  ✓ 翻页后 URL 会变化，可直接检测

依赖：
  pip install playwright pillow
  playwright install chromium

用法：
  python dealroadshow-capture.py --url "https://dealroadshow.com/e/MTNA2026"
  python dealroadshow-capture.py --url "..." --email "your@email.com"
"""

import argparse
import os
import re
import time
from pathlib import Path
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(description="DealRoadShow page capture (Playwright)")
    parser.add_argument("--url", required=True, help="路演 URL（如 https://dealroadshow.com/e/XXXX）")
    parser.add_argument("--email", default=None, help="查看人邮箱（默认取 NRS_EMAIL 环境变量）")
    parser.add_argument("--output", "-o", default="/tmp/dealroadshow_output", help="输出目录")
    parser.add_argument("--wait", type=float, default=2.0, help="翻页后等待秒数")
    parser.add_argument("--max-pages", type=int, default=50, help="最大页数限制")
    parser.add_argument("--pdf-only", action="store_true", help="仅合成 PDF，跳过截屏")
    return parser.parse_args()


def capture_pages(args):
    from playwright.sync_api import sync_playwright

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve email
    email = args.email or os.environ.get("NRS_EMAIL")
    assert email, "NRS_EMAIL 未设置。请通过 --email 参数或 export NRS_EMAIL=your-email@company.com 设置邮箱。"

    UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, user_agent=UA)
        page = ctx.new_page()

        # ---- Step 1: Navigate to the deal URL ----
        print(f"1. Navigating to: {args.url}")
        page.goto(args.url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # ---- Step 1b: Accept cookies if banner present ----
        try:
            cookie_btn = page.get_by_role("button", name="Ok").first
            if cookie_btn.is_visible(timeout=3000):
                cookie_btn.click()
                print("   Cookies accepted")
                time.sleep(1)
        except Exception:
            pass

        # ---- Step 2: Fill email and launch ----
        print(f"2. Filling email: {email}")
        email_input = page.locator("input[type='text']").first
        email_input.fill(email)
        time.sleep(0.5)

        launch_btn = page.get_by_text("Launch Deal Roadshow")
        launch_btn.click()
        print("   Launch clicked, waiting for redirect...")
        time.sleep(3)
        page.wait_for_load_state("networkidle")
        print(f"   URL: {page.url}")

        # ---- Step 3: Accept disclaimer / I Agree ----
        print(f"3. Accepting disclaimer...")
        try:
            agree_btn = page.get_by_text("I Agree").first
            agree_btn.click(timeout=5000)
            print("   I Agree clicked")
        except Exception:
            # Maybe already past disclaimer, or button is different
            print("   No I Agree button found, may already be on slides")
        time.sleep(3)
        page.wait_for_load_state("networkidle")
        print(f"   URL after agree: {page.url}")

        # ---- Step 4: Detect total pages from URL pattern or page text ----
        # URL after agree should be like .../e/MTNA2026/1
        # Extract current page from URL
        url_match = re.search(r'/(\d+)$', page.url)
        current_page = int(url_match.group(1)) if url_match else 1
        print(f"4. Starting from page {current_page}")

        # Try to detect total pages from the "X of Y" text
        total = args.max_pages
        try:
            body_text = page.inner_text("body")
            of_match = re.search(r'of\s*(\d+)', body_text, re.I)
            if of_match:
                total = int(of_match.group(1))
                print(f"   Detected {total} total pages from page text")
        except Exception:
            pass

        # If URL shows a number pattern like /e/MTNA2026/{page}, navigate to detect total
        if "/e/" in page.url:
            base_url = re.sub(r'/\d+$', '', page.url)
        else:
            base_url = page.url.rstrip('/')

        # ---- Step 5: Screenshot current page and navigate through ----
        print(f"5. Capturing up to {total} pages starting from page {current_page}...")

        screenshots = []
        for i in range(current_page, current_page + total):
            time.sleep(args.wait)
            page.wait_for_load_state("networkidle")

            path = str(output_dir / f"slide_{i:03d}.png")
            page.screenshot(path=path, full_page=False)
            screenshots.append(path)
            print(f"   Slide {i} captured")

            # Check if we've reached the last page (try to go next)
            current_url_before = page.url
            page.keyboard.press("ArrowRight")
            time.sleep(0.5)
            page.wait_for_load_state("networkidle")

            # If URL didn't change after pressing ArrowRight, we're at the last page
            if page.url == current_url_before:
                print(f"   Last page detected (page {i})")
                break

            # Also check if we went back to start (sometimes wraps around)
            next_url_match = re.search(r'/(\d+)$', page.url)
            if next_url_match and int(next_url_match.group(1)) <= current_page:
                print(f"   Cycle detected, stopping at page {i}")
                break

        browser.close()
        return sorted(output_dir.glob("slide_*.png"))


def images_to_pdf(image_paths, output_path, resolution=150):
    imgs = [Image.open(f).convert("RGB") for f in image_paths]
    if not imgs:
        print("❌ No images to convert")
        return False
    imgs[0].save(
        output_path,
        save_all=True,
        append_images=imgs[1:],
        format="PDF",
        resolution=resolution,
    )
    print(f"✅ PDF: {output_path} ({len(imgs)} pages, {Path(output_path).stat().st_size / 1024 / 1024:.1f} MB)")
    return True


def main():
    args = parse_args()

    # Resolve email: CLI arg → env var → agent prompt
    email = args.email or os.environ.get("NRS_EMAIL")
    assert email, "NRS_EMAIL 未设置。请通过 --email 参数或 export NRS_EMAIL=your-email@company.com 设置邮箱。"
    args.email = email

    if args.pdf_only:
        images = sorted(Path(args.output).glob("slide_*.png"))
        if images:
            images_to_pdf(images, str(Path(args.output) / "dealroadshow.pdf"))
        return

    screenshots = capture_pages(args)
    if screenshots:
        pdf_path = Path(args.output) / "dealroadshow.pdf"
        images_to_pdf(screenshots, str(pdf_path))


if __name__ == "__main__":
    main()
