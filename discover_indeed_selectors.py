#!/usr/bin/env python3
"""Live DOM discovery for ch.indeed.com Indeed Apply anchors.

Usage:
  python discover_indeed_selectors.py

Opens Firefox, loads an Easily Apply search, pauses for manual login if needed,
then dumps interactive elements into indeed_selectors.json and .cache/indeed/.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService

CACHE_DIR = Path(".cache/indeed")
SELECTORS_PATH = Path("indeed_selectors.json")
CONFIG_PATH = Path("config.json")


def load_config():
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open() as f:
            return json.load(f)
    return {}


def describe_element(el):
    try:
        return {
            "tag": el.tag_name,
            "id": el.get_attribute("id") or "",
            "class": el.get_attribute("class") or "",
            "name": el.get_attribute("name") or "",
            "type": el.get_attribute("type") or "",
            "data_testid": el.get_attribute("data-testid") or "",
            "data_jk": el.get_attribute("data-jk") or "",
            "aria_label": el.get_attribute("aria-label") or "",
            "href": el.get_attribute("href") or "",
            "text": (el.text or "")[:200].strip(),
        }
    except Exception as exc:
        return {"error": str(exc)}


def dump_step(driver, step_name: str, snapshot: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = CACHE_DIR / f"{step_name}_{stamp}.html"
    json_path = CACHE_DIR / f"{step_name}_{stamp}.json"
    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
    except Exception:
        pass
    json_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {json_path}")
    return snapshot


def collect_interactive(driver, root=None):
    scope = root or driver
    selectors = ["button", "input", "textarea", "select", "a"]
    found = []
    for sel in selectors:
        try:
            for el in scope.find_elements(By.CSS_SELECTOR, sel):
                found.append(describe_element(el))
        except Exception:
            continue
    return found


def merge_selectors(existing: dict, discovered: dict) -> dict:
    merged = dict(existing or {})
    merged["discoveredAt"] = datetime.now().isoformat()
    merged["liveSnapshots"] = discovered
    # Prefer keeping curated seed selectors; append unique live class hints
    hints = discovered.get("classHints") or []
    if hints:
        merged.setdefault("liveClassHints", [])
        for h in hints:
            if h not in merged["liveClassHints"]:
                merged["liveClassHints"].append(h)
    return merged


def main():
    config = load_config()
    indeed_cfg = config.get("indeed") or {}
    base_url = indeed_cfg.get("baseUrl", "https://ch.indeed.com")
    location = (indeed_cfg.get("locations") or ["Zurich"])[0]
    keywords = " OR ".join(config.get("keywords") or ["typescript", "react"])
    driver_path = config.get("driver_path", "/usr/local/bin/geckodriver")

    search_url = (
        f"{base_url}/jobs?q={keywords.replace(' ', '+')}"
        f"&l={location.replace(' ', '+')}&iafilter=1"
    )

    existing = {}
    if SELECTORS_PATH.exists():
        existing = json.loads(SELECTORS_PATH.read_text(encoding="utf-8"))

    firefox_service = FirefoxService(executable_path=driver_path)
    driver = webdriver.Firefox(service=firefox_service)
    discovered = {"steps": [], "classHints": []}

    try:
        print(f"Opening {search_url}")
        driver.get(search_url)
        time.sleep(3)
        input(
            "Log in to Indeed in the browser if needed, then press Enter to capture "
            "search-page selectors..."
        )

        search_snapshot = {
            "url": driver.current_url,
            "title": driver.title,
            "elements": collect_interactive(driver),
        }
        dump_step(driver, "search", search_snapshot)
        discovered["steps"].append({"name": "search", **search_snapshot})

        # Collect class hints containing job_ / ia-
        for el in search_snapshot["elements"]:
            cls = el.get("class") or ""
            for token in cls.split():
                if token.startswith(("ia-", "job_", "css-")) and token not in discovered["classHints"]:
                    discovered["classHints"].append(token)

        print(
            "Click a job with 'Easily apply' / 'Einfach bewerben', open the apply flow, "
            "then press Enter to capture the apply wizard DOM."
        )
        input("Press Enter when the apply form/wizard is visible...")

        apply_snapshot = {
            "url": driver.current_url,
            "title": driver.title,
            "window_handles": len(driver.window_handles),
            "elements": collect_interactive(driver),
        }
        # If a new tab opened, switch and capture there too
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(1)
            apply_snapshot["apply_tab"] = {
                "url": driver.current_url,
                "elements": collect_interactive(driver),
            }
        dump_step(driver, "apply", apply_snapshot)
        discovered["steps"].append({"name": "apply", **apply_snapshot})

        for el in apply_snapshot.get("elements", []) + (
            apply_snapshot.get("apply_tab", {}).get("elements") or []
        ):
            cls = el.get("class") or ""
            for token in cls.split():
                if "ia-" in token and token not in discovered["classHints"]:
                    discovered["classHints"].append(token)

        merged = merge_selectors(existing, discovered)
        SELECTORS_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
        print(f"Updated {SELECTORS_PATH}")
        print(f"Class hints: {discovered['classHints'][:40]}")
    finally:
        input("Press Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    main()
