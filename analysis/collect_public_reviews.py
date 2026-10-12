"""Collect the public review records exposed for MoveInSync on both stores.

The storefront headline totals include rating-only events. Public endpoints do
not expose those events as review rows, so this collector records both the
retrievable written-review population and the storefront totals separately.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from google_play_scraper import Sort, reviews_all


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
AUDIT_PATH = ROOT / "data" / "collection_audit.json"

GOOGLE_APP_ID = "com.moveinsync.ets"
APPLE_APP_ID = "962949521"

# Google Play separates review feeds by requested language. These are the
# currently supported public Play language parameters, including major Indian
# languages. Country does not change the English newest feed for this app, so
# India is used consistently and review IDs are deduplicated across languages.
GOOGLE_LANGUAGES = [
    "af", "am", "ar", "az", "bg", "bn", "ca", "cs", "da", "de", "el",
    "en", "es", "et", "eu", "fa", "fi", "fil", "fr", "gl", "gu", "he",
    "hi", "hr", "hu", "hy", "id", "is", "it", "ja", "ka", "kk", "km",
    "kn", "ko", "ky", "lo", "lt", "lv", "mk", "ml", "mn", "mr", "ms",
    "my", "ne", "nl", "no", "pa", "pl", "pt", "ro", "ru", "si", "sk",
    "sl", "sr", "sv", "sw", "ta", "te", "th", "tr", "uk", "ur", "uz",
    "vi", "zh", "zu",
]

# ISO alpha-2 storefront candidates. Apple returns a normal page only where
# the app is available. Unavailable storefronts are logged and skipped.
APPLE_STOREFRONTS = """
ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be bf bg bh bi bj bl
bm bn bo bq br bs bt bv bw by bz ca cc cd cf cg ch ci ck cl cm cn co cr cu cv
cw cx cy cz de dj dk dm do dz ec ee eg eh er es et fi fj fk fm fo fr ga gb gd
ge gf gg gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il im
in io iq ir is it je jm jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk
lr ls lt lu lv ly ma mc md me mf mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw
mx my mz na nc ne nf ng ni nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr
ps pt pw py qa re ro rs ru rw sa sb sc sd se sg sh si sj sk sl sm sn so sr ss
st sv sx sy sz tc td tf tg th tj tk tl tm tn to tr tt tv tw tz ua ug um us uy
uz va vc ve vg vi vn vu wf ws ye yt za zm zw
""".split()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


def clean_mojibake(value: str) -> str:
    """Repair UTF-8 text decoded as Windows-1252 when Apple emits it that way."""
    if not value:
        return value
    if "â" not in value and "Ã" not in value and "ð" not in value:
        return value.strip()
    try:
        return value.encode("latin1").decode("utf-8").strip()
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value.strip()


def collect_google() -> tuple[pd.DataFrame, list[dict]]:
    rows_by_id: dict[str, dict] = {}
    query_audit: list[dict] = []

    for position, lang in enumerate(GOOGLE_LANGUAGES, start=1):
        started = time.time()
        error = None
        items: list[dict] = []
        for attempt in range(1, 4):
            try:
                items = reviews_all(
                    GOOGLE_APP_ID,
                    sleep_milliseconds=300,
                    lang=lang,
                    country="in",
                    sort=Sort.NEWEST,
                )
                break
            except Exception as exc:  # pragma: no cover - network dependent
                error = f"{type(exc).__name__}: {exc}"
                time.sleep(attempt * 2)

        new_ids = 0
        for item in items:
            review_id = str(item.get("reviewId", "")).strip()
            if not review_id:
                continue
            if review_id not in rows_by_id:
                row = dict(item)
                row["store"] = "Google Play"
                row["sourceCountry"] = "in"
                row["sourceLanguages"] = lang
                rows_by_id[review_id] = row
                new_ids += 1
            else:
                langs = set(rows_by_id[review_id]["sourceLanguages"].split(","))
                langs.add(lang)
                rows_by_id[review_id]["sourceLanguages"] = ",".join(sorted(langs))

        query_audit.append(
            {
                "language": lang,
                "country": "in",
                "records_returned": len(items),
                "new_unique_records": new_ids,
                "elapsed_seconds": round(time.time() - started, 2),
                "error": error,
            }
        )
        print(
            f"Google {position:02d}/{len(GOOGLE_LANGUAGES)} lang={lang}: "
            f"{len(items):,} returned, {new_ids:,} new, {len(rows_by_id):,} total",
            flush=True,
        )

    frame = pd.DataFrame(rows_by_id.values())
    if not frame.empty:
        frame["at"] = pd.to_datetime(frame["at"], errors="coerce", utc=True)
        frame["repliedAt"] = pd.to_datetime(frame["repliedAt"], errors="coerce", utc=True)
        frame = frame.sort_values("at", ascending=False)
    return frame, query_audit


def parse_apple_storefront(country: str, html: str) -> tuple[list[dict], dict]:
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.select_one('link[rel="canonical"]')
    canonical_url = canonical.get("href", "") if canonical else ""
    canonical_match = re.search(r"apps\.apple\.com/([a-z]{2})/app/", canonical_url.lower())
    canonical_country = canonical_match.group(1) if canonical_match else ""
    available = canonical_country == country

    rating_text = ""
    rating_node = soup.find(string=re.compile(r"Ratings$"))
    if rating_node:
        rating_text = rating_node.strip()

    average = None
    average_node = soup.find(string=lambda value: value and "out of 5" in value)
    if average_node:
        parent_text = average_node.parent.parent.get_text(" ", strip=True)
        match = re.search(r"([0-5](?:\.\d+)?)\s*out of 5", parent_text)
        if match:
            average = float(match.group(1))

    reviews = []
    for card in soup.select('#allProductReviews div.container[aria-labelledby^="review-"]'):
        label = card.get("aria-labelledby", "")
        id_match = re.search(r"review-(\d+)-title", label)
        if not id_match:
            continue
        rating_el = card.select_one("ol.stars[aria-label]")
        rating_match = re.search(r"(\d+)\s+Stars?", rating_el.get("aria-label", "")) if rating_el else None
        rating_value = int(rating_match.group(1)) if rating_match else (len(rating_el.find_all("li", recursive=False)) if rating_el else None)
        time_el = card.select_one("time[datetime]")
        reviews.append(
            {
                "reviewId": id_match.group(1),
                "userName": clean_mojibake(card.select_one(".author").get_text(" ", strip=True)) if card.select_one(".author") else "",
                "title": clean_mojibake(card.select_one("h3.title").get_text(" ", strip=True)) if card.select_one("h3.title") else "",
                "content": clean_mojibake(card.select_one('p[data-testid="truncate-text"]').get_text(" ", strip=True)) if card.select_one('p[data-testid="truncate-text"]') else "",
                "score": rating_value,
                "at": time_el.get("datetime") if time_el else None,
                "reviewCreatedVersion": None,
                "thumbsUpCount": None,
                "replyContent": None,
                "repliedAt": None,
                "appVersion": None,
                "store": "Apple App Store",
                "sourceCountry": canonical_country or country,
                "sourceLanguages": None,
            }
        )

    summary = {
        "country": country,
        "canonical_country": canonical_country,
        "available": available,
        "visible_reviews": len(reviews),
        "displayed_rating_text": rating_text,
        "displayed_average": average,
        "canonical_url": canonical_url,
    }
    return reviews, summary


def collect_apple() -> tuple[pd.DataFrame, list[dict]]:
    rows_by_id: dict[str, dict] = {}
    storefront_audit: list[dict] = []

    def fetch_storefront(country: str) -> tuple[str, list[dict], dict]:
        url = f"https://apps.apple.com/{country}/app/moveinsync/id{APPLE_APP_ID}?see-all=reviews"
        error = None
        status = None
        html = ""
        session = requests.Session()
        session.headers.update(HEADERS)
        for attempt in range(1, 4):
            try:
                response = session.get(url, timeout=30)
                status = response.status_code
                if status == 200:
                    html = response.text
                    break
                if status in {404, 410}:
                    break
                time.sleep(attempt * 2)
            except requests.RequestException as exc:  # pragma: no cover
                error = f"{type(exc).__name__}: {exc}"
                time.sleep(attempt * 2)

        if html:
            reviews, summary = parse_apple_storefront(country, html)
        else:
            reviews, summary = [], {
                "country": country,
                "available": False,
                "visible_reviews": 0,
                "displayed_rating_text": "",
                "displayed_average": None,
                "canonical_url": "",
            }
        summary.update({"http_status": status, "error": error})
        return country, reviews, summary

    completed = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_storefront, country): country for country in APPLE_STOREFRONTS}
        for future in as_completed(futures):
            country, reviews, summary = future.result()
            storefront_audit.append(summary)
            completed += 1
            new_ids = 0
            for row in reviews:
                review_id = row["reviewId"]
                if review_id not in rows_by_id:
                    rows_by_id[review_id] = row
                    new_ids += 1
                else:
                    countries = set(rows_by_id[review_id]["sourceCountry"].split(","))
                    countries.add(country)
                    rows_by_id[review_id]["sourceCountry"] = ",".join(sorted(countries))

            print(
                f"Apple {completed:03d}/{len(APPLE_STOREFRONTS)} {country}: "
                f"{len(reviews)} visible, {new_ids} new, {len(rows_by_id)} total",
                flush=True,
            )

    storefront_audit.sort(key=lambda row: row["country"])

    frame = pd.DataFrame(rows_by_id.values())
    if not frame.empty:
        frame["at"] = pd.to_datetime(frame["at"], errors="coerce", utc=True)
        frame = frame.sort_values("at", ascending=False)
    return frame, storefront_audit


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(timezone.utc).isoformat()

    google_path = RAW_DIR / "google_play_public_reviews.csv"
    if "--apple-only" in sys.argv and google_path.exists():
        google = pd.read_csv(google_path)
        prior_audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else {}
        google_audit = prior_audit.get("google", {}).get("queries", [])
    else:
        google, google_audit = collect_google()
        google.to_csv(google_path, index=False, encoding="utf-8-sig")
        print(f"Saved {len(google):,} Google review records to {google_path}", flush=True)

    apple_path = RAW_DIR / "apple_app_store_public_reviews.csv"
    if "--google-only" in sys.argv and apple_path.exists():
        apple = pd.read_csv(apple_path)
        apple_audit = []
    else:
        apple, apple_audit = collect_apple()
        apple.to_csv(apple_path, index=False, encoding="utf-8-sig")
        print(f"Saved {len(apple):,} Apple review records to {apple_path}", flush=True)

    combined = pd.concat([google, apple], ignore_index=True, sort=False)
    combined_path = RAW_DIR / "moveinsync_public_reviews_combined.csv"
    combined.to_csv(combined_path, index=False, encoding="utf-8-sig")

    audit = {
        "collected_at_utc": collected_at,
        "scope_note": (
            "Counts are written review records exposed by public storefronts. "
            "They cannot equal rating headline totals because rating-only events "
            "and older/filtered reviews are not publicly enumerable."
        ),
        "google": {
            "unique_reviews": int(len(google)),
            "languages_queried": len(GOOGLE_LANGUAGES),
            "queries": google_audit,
        },
        "apple": {
            "unique_reviews": int(len(apple)),
            "storefronts_queried": len(APPLE_STOREFRONTS),
            "storefronts_with_visible_reviews": sum(x["visible_reviews"] > 0 for x in apple_audit),
            "public_page_limit": (
                "Apple currently embeds up to 20 visible reviews per storefront. "
                "The legacy RSS feed returned no entries during this run."
            ),
            "storefronts": apple_audit,
        },
        "combined_unique_store_review_records": int(len(combined)),
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved combined dataset and audit: {combined_path}, {AUDIT_PATH}", flush=True)


if __name__ == "__main__":
    main()
