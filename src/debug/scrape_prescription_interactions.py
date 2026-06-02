"""Scrape the IU Flockhart Table into an offline prescription interaction snapshot."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

SOURCE_URL = "https://drug-interactions.medicine.iu.edu/main-table"
OUTPUT_FILE = Path("data/prescription_interactions.json")
STRENGTHS = {"S": "strong", "M": "moderate", "W": "weak", "I": "in-vitro", "T": "tbd"}


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).casefold()


def add_relationship(drugs, name, enzyme, role, strength=None, references=None):
    key = normalize(name)
    if not key:
        return
    drug = drugs.setdefault(key, {"name": name.strip(), "relationships": []})
    relationship = {
        "enzyme": enzyme,
        "role": role,
        "strength": strength,
        "references": references or [],
    }
    if relationship not in drug["relationships"]:
        drug["relationships"].append(relationship)


def scrape():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(SOURCE_URL, wait_until="networkidle", timeout=60_000)
        page.wait_for_selector("[data-rvt-dialog-trigger]", timeout=30_000)
        payload = {}
        extract_visible = """() => {
                const dialogs = new Map(
                    [...document.querySelectorAll("[data-rvt-dialog]")]
                        .map(dialog => [dialog.dataset.rvtDialog, dialog])
                );
                return [...document.querySelectorAll("[data-rvt-dialog-trigger]")]
                    .map(trigger => {
                        const id = trigger.dataset.rvtDialogTrigger;
                        const dialog = dialogs.get(id);
                        if (!dialog) return null;
                        const [, role, enzyme] = id.match(/^\\S+\\s+(\\S+)\\s+(.+)$/) || [];
                        const columns = [...dialog.querySelectorAll(".rvt-cols-6")];
                        const list = heading => {
                            const column = columns.find(col =>
                                col.querySelector("h2")?.textContent.trim() === heading
                            );
                            return column
                                ? [...column.querySelectorAll("li")].map(li => li.textContent.trim())
                                : [];
                        };
                        return {
                            name: trigger.textContent.trim(),
                            role: role?.toLowerCase(),
                            enzyme,
                            strength: trigger.parentElement.querySelector("img")?.alt || null,
                            references: [...dialog.querySelectorAll("a.pub")]
                                .map(link => link.href),
                            inhibitors: list("Inhibitors"),
                            inducers: list("Inducers"),
                        };
                    })
                    .filter(Boolean);
            }"""
        height = page.evaluate("document.documentElement.scrollHeight")
        for offset in range(0, height + 1000, 500):
            page.evaluate("(offset) => window.scrollTo(0, offset)", offset)
            page.wait_for_timeout(100)
            for entry in page.locator("body").evaluate(extract_visible):
                key = (entry["name"], entry["role"], entry["enzyme"])
                payload[key] = entry
        browser.close()
    return payload.values()


def build_snapshot(entries):
    drugs = {}
    for entry in entries:
        references = sorted(set(entry["references"]))
        add_relationship(
            drugs,
            entry["name"],
            entry["enzyme"],
            entry["role"],
            STRENGTHS.get(entry["strength"], entry["strength"]),
            references,
        )
        for inhibitor in entry["inhibitors"]:
            add_relationship(drugs, inhibitor, entry["enzyme"], "inhibitor")
        for inducer in entry["inducers"]:
            add_relationship(drugs, inducer, entry["enzyme"], "inducer")
    for drug in drugs.values():
        drug["relationships"].sort(key=lambda item: (item["enzyme"], item["role"]))
    return {
        "metadata": {
            "source_url": SOURCE_URL,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
        "drugs": dict(sorted(drugs.items())),
    }


def main():
    snapshot = build_snapshot(scrape())
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)
    print(f"Saved {len(snapshot['drugs'])} drugs to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
