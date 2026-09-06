#!/usr/bin/env python3
"""
Upgraded EduPage Timetable Screenshot Taker for IUT.
Captures high-resolution, cleanly cropped timetable screenshots for each group.
Supports Docker/Chromium as well as standard Chrome.
"""

import argparse
import io
import os
import re
import shutil
import sys
import time
from typing import List, Optional, Tuple

try:
    from PIL import Image
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
except ImportError:
    pass

DEFAULT_URL = "https://iut.edupage.org/timetable/"


class TimetableScreenshotTaker:
    def __init__(
        self,
        url: str = DEFAULT_URL,
        output_dir: str = "screenshots",
        headless: bool = True,
        window_size: Tuple[int, int] = (1920, 1080),
    ):
        self.url = url
        self.output_dir = output_dir
        self.headless = headless
        self.window_size = window_size
        self.driver: Optional[webdriver.Chrome] = None
        os.makedirs(self.output_dir, exist_ok=True)

    def _find_chrome_binary(self) -> Optional[str]:
        candidates = [
            os.getenv("CHROME_BIN"),
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            shutil.which("google-chrome"),
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
        ]
        for c in candidates:
            if c and os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return None

    def _init_driver(self) -> webdriver.Chrome:
        options = Options()
        chrome_bin = self._find_chrome_binary()
        if chrome_bin:
            options.binary_location = chrome_bin

        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--window-size={self.window_size[0]},{self.window_size[1]}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--remote-debugging-pipe")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(options=options)
        driver.set_window_size(self.window_size[0], self.window_size[1])
        return driver

    def _accept_cookies(self) -> None:
        if not self.driver:
            return
        selectors = [
            ".eu-cookie-closeBtn",
            ".eu-cookie-panel button",
            ".eu-cookie-panel a",
            "button",
            "a",
        ]
        for sel in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    txt = (el.text or "").strip().lower()
                    if any(w in txt for w in ["accept", "agree", "ok", "close"]):
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.5)
                        return
            except Exception:
                continue

    def _open_classes_dropdown(self) -> bool:
        if not self.driver:
            return False
        try:
            elements = self.driver.find_elements(By.XPATH, "//*[@title='Classes'] | //*[contains(text(), 'Classes')]")
            for el in elements:
                if el.is_displayed() or el.get_attribute("title") == "Classes":
                    self.driver.execute_script("arguments[0].click();", el)
                    time.sleep(0.8)
                    return True
        except Exception:
            pass
        return False

    def _select_group(self, group_name: str) -> bool:
        if not self.driver:
            return False
        self._open_classes_dropdown()

        clicked = self.driver.execute_script(
            """
            const target = arguments[0];
            const items = [...document.querySelectorAll('li, a, span, div')];
            const el = items.find(node => {
                const txt = (node.textContent || '').replace(/[✓✔]/g, '').trim();
                return txt === target;
            });
            if (el) {
                el.scrollIntoView({block: 'center'});
                el.click();
                return true;
            }
            return false;
            """,
            group_name,
        )
        if clicked:
            time.sleep(1.2)
            return True
        return False

    def _get_timetable_element_id(self) -> Optional[str]:
        if not self.driver:
            return None
        return self.driver.execute_script(
            """
            const nodes = [...document.querySelectorAll("div[id^='gi'], svg, [role='grid'], div[class*='timetable'], div[class*='tt'], div[class*='grid']")];
            let bestId = null, bestArea = 0;
            for (const el of nodes) {
                const r = el.getBoundingClientRect();
                const area = r.width * r.height;
                if (area > bestArea && r.width > 250 && r.height > 250) {
                    bestArea = area;
                    bestId = el.id || ('temp_tt_' + Math.random().toString(36).substr(2, 9));
                    if (!el.id) el.id = bestId;
                }
            }
            return bestId;
            """
        )

    def capture_group_screenshot(self, group_name: str) -> Optional[str]:
        sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", group_name).strip("._") or "group"
        filename = f"{sanitized}.png"
        filepath = os.path.join(self.output_dir, filename)

        if not self._select_group(group_name):
            print(f"  [Warning] Could not find or click group '{group_name}' in dropdown.")
            return None

        # 1. Try direct element screenshot
        best_id = self._get_timetable_element_id()
        if best_id and self.driver:
            try:
                el = self.driver.find_element(By.ID, best_id)
                el.screenshot(filepath)
                return filepath
            except Exception:
                pass

        # 2. Fallback: viewport screenshot with PIL crop
        try:
            if not self.driver:
                return None
            screenshot = self.driver.get_screenshot_as_png()
            im = Image.open(io.BytesIO(screenshot)).convert("RGB")

            rect = self.driver.execute_script(
                """
                const el = document.getElementById(arguments[0]) || document.querySelector("div[id^='gi']");
                if (el) {
                    const r = el.getBoundingClientRect();
                    return {left: r.left, top: r.top, width: r.width, height: r.height};
                }
                return null;
                """,
                best_id,
            )
            if rect:
                left = max(0, int(rect["left"]))
                top = max(0, int(rect["top"]))
                right = min(im.width, left + int(rect["width"]))
                bottom = min(im.height, top + int(rect["height"]))
                if right > left and bottom > top:
                    im = im.crop((left, top, right, bottom))

            im.save(filepath, "PNG", optimize=True)
            return filepath
        except Exception as exc:
            print(f"  [Error] Screenshot capture failed for '{group_name}': {exc}")
            return None

    def capture_multiple(
        self,
        group_names: List[str],
        limit: Optional[int] = None,
        callback=None,
    ) -> dict:
        targets = group_names[:limit] if limit else group_names
        results = {}

        print(f"Starting browser session to capture {len(targets)} timetables...")
        self.driver = self._init_driver()

        try:
            self.driver.get(self.url)
            time.sleep(2.5)
            self._accept_cookies()

            for i, grp in enumerate(targets, start=1):
                print(f"  [{i}/{len(targets)}] Capturing screenshot for {grp}...")
                path = self.capture_group_screenshot(grp)
                if path:
                    results[grp] = path
                    if callback:
                        callback(grp, path)
                time.sleep(0.4)

        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

        print(f"Screenshot capture finished: {len(results)}/{len(targets)} successful.")
        return results


def main():
    parser = argparse.ArgumentParser(description="Capture EduPage Timetable Screenshots")
    parser.add_argument("--url", default=DEFAULT_URL, help="EduPage timetable URL")
    parser.add_argument("--output-dir", "-o", default="screenshots", help="Output directory for PNGs")
    parser.add_argument("--group", "-g", help="Capture for a single group (e.g. CIE26-1)")
    parser.add_argument("--limit", "-l", type=int, help="Limit number of groups to capture")
    parser.add_argument("--no-headless", action="store_true", help="Run with visible browser window")

    args = parser.parse_args()

    taker = TimetableScreenshotTaker(
        url=args.url,
        output_dir=args.output_dir,
        headless=not args.no_headless,
    )

    if args.group:
        taker.driver = taker._init_driver()
        try:
            taker.driver.get(args.url)
            time.sleep(2.5)
            taker._accept_cookies()
            res = taker.capture_group_screenshot(args.group)
            if res:
                print(f"Saved screenshot to: {res}")
            else:
                print(f"Failed to capture screenshot for {args.group}")
        finally:
            if taker.driver:
                taker.driver.quit()
    else:
        from parser import EduPageParser
        p = EduPageParser()
        p.parse()
        groups = p.get_all_groups()
        taker.capture_multiple(groups, limit=args.limit)


if __name__ == "__main__":
    main()
