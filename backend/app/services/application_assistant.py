"""Application Assistant (spec §9) — Playwright auto-fill with human-in-the-loop.

Flow:
  1. Open the application URL in a headless Chromium.
  2. Scan the form (labels + placeholders + aria-labels + names).
  3. Match known profile fields against detected form fields.
  4. Fill non-sensitive fields from the master profile + the application's CV/letter.
  5. Hard-block sensitive attestations (criminal record, ID/visa, legal
     declarations, salary, diversity, disability, TSC number, CAPTCHA…).
  6. Save draft if the site offers a Save Draft button.
  7. Close the browser and return the APPLICATION REVIEW card.

The review card is displayed in the dashboard. The user reviews filled answers,
types blocked ones, and SUBMITS manually on the target site (the assistant
NEVER clicks final submit — spec §9).
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.core.crypto import decrypt_text
from app.models import MasterProfile

logger = logging.getLogger("careerpilot.assistant")

# ── sensitive field patterns (spec §10) ─────────────────────────
_SENSITIVE_PATTERNS = (
    r"\bcriminal\b", r"\bconvict", r"\boffense\b|offence", r"\bbackground\s*check\b",
    r"\bcrb\b", r"\bpolice\s*clearance\b", r"\bid\s*number\b", r"\bpassport\b",
    r"\bnational\s*id\b", r"\bidentity\b", r"\bvisa\b", r"\bimmigration\b",
    r"\blegal\b", r"\bdeclar", r"\battest", r"\bswear", r"\bcertify\b", r"\bconfirm\b",
    r"\bsalary\s*(expectation|requirement|desired)\b",
    r"\bdiversity\b", r"\bethnic", r"\bdisability\b", r"\bgender\b",
    r"\btsc\s*(number|registration|reference)\b",
    r"\binformation\s*(true|correct|accurate)\b",
    r"\bcaptcha", r"\brecaptcha",
)

_FIELD_MAP: dict[str, str] = {
    "full_name": "name",
    "name": "name",
    "email": "email",
    "phone": "phone",
    "telephone": "phone",
    "mobile": "phone",
    "cv": "cv_file",
    "resume": "cv_file",
    "cover letter": "cover_letter_file",
    "location": "location",
    "city": "location",
    "address": "location",
}


def _is_sensitive(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in _SENSITIVE_PATTERNS)


def _map_field(label: str) -> str | None:
    low = label.lower().strip().rstrip(":*")
    for key, val in _FIELD_MAP.items():
        if key in low:
            return val if val else None
    return None


async def _fill_value(page, selector: str, value: str) -> bool:
    try:
        el = await page.query_selector(selector)
        if el is None:
            return False
        tag = (await el.get_attribute("type") or "").lower()
        if tag == "file":
            await el.set_input_files(value)
        else:
            await el.fill(value)
        return True
    except Exception:
        logger.exception("Failed to fill %s", selector)
        return False


async def scan_and_fill(page: Any, profile: MasterProfile, user_email: str,
                        cv_path: str | None, letter_path: str | None) -> list[dict]:
    results: list[dict] = []
    phone = decrypt_text(profile.phone_encrypted) or ""

    inputs = await page.query_selector_all("input:not([type=hidden]), textarea, select")
    label_map: dict[str, str] = {}
    for label_el in await page.query_selector_all("label"):
        text = (await label_el.inner_text()).strip()
        for_id = await label_el.get_attribute("for")
        if for_id and text:
            label_map[for_id] = text

    for inp in inputs:
        inp_id = (await inp.get_attribute("id")) or ""
        inp_name = (await inp.get_attribute("name")) or ""
        placeholder = (await inp.get_attribute("placeholder")) or ""
        aria_label = (await inp.get_attribute("aria-label")) or ""
        combined = f"{inp_name} {placeholder} {aria_label} {label_map.get(inp_id, '')}"

        selector = None
        if inp_id:
            selector = f"#{inp_id}"
        elif inp_name:
            selector = f"[name='{inp_name}']"
        else:
            continue

        question = label_map.get(inp_id) or placeholder or aria_label or inp_name
        sensitive = _is_sensitive(combined)

        field: dict = {
            "name": inp_name or inp_id,
            "question": question,
            "value": None,
            "filled": False,
            "requires_approval": sensitive,
            "selector": selector,
        }

        if not sensitive:
            mapped = _map_field(combined)
            if mapped == "name":
                field["value"] = profile.full_name
            elif mapped == "email":
                field["value"] = user_email
            elif mapped == "phone":
                field["value"] = phone
            elif mapped == "location":
                field["value"] = f"{profile.location or ''}"
            elif mapped == "cv_file" and cv_path:
                field["value"] = cv_path
                await _fill_value(page, selector, cv_path)
                field["filled"] = True
            elif mapped == "cover_letter_file" and letter_path:
                field["value"] = letter_path
                await _fill_value(page, selector, letter_path)
                field["filled"] = True

            if field["value"] and not field["filled"]:
                ok = await _fill_value(page, selector, field["value"])
                field["filled"] = ok

        results.append(field)
    return results


async def assist_application(profile: MasterProfile, user_email: str, app_url: str,
                             cv_path: str | None, letter_path: str | None) -> dict:
    """Run the assistant on an application form URL."""
    if not app_url or not app_url.startswith("http"):
        return {"url": app_url or "", "status": "NO_URL", "fields": [], "blocked": [], "captcha": False}

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"url": app_url, "status": "PLAYWRIGHT_MISSING", "fields": [], "blocked": [],
                "captcha": False, "note": "Install playwright: pip install playwright && playwright install chromium"}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(app_url, wait_until="networkidle", timeout=30000)
            fields = await scan_and_fill(page, profile, user_email, cv_path, letter_path)

            draft_saved = False
            try:
                draft_btn = await page.query_selector(
                    "button:has-text('Save'), button:has-text('Draft'), "
                    "button:has-text('Save Draft'), input[value*='Save']"
                )
                if draft_btn:
                    await draft_btn.click()
                    draft_saved = True
            except Exception:
                pass

            captcha = await page.query_selector(
                "[src*='captcha'], [title*='captcha'], #recaptcha, iframe[src*='recaptcha']"
            )

            blocked = [f for f in fields if f.get("requires_approval")]
            return {
                "url": app_url,
                "status": "NEEDS_REVIEW" if blocked else "FILLED",
                "fields": fields,
                "blocked": blocked,
                "captcha": bool(captcha),
                "draft_saved": draft_saved,
            }
        finally:
            await browser.close()