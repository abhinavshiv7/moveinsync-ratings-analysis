import re
import json
import datetime
from pathlib import Path

import pandas as pd


SOURCE = Path(__file__).resolve().parents[1] / "data" / "raw" / "google_play_public_reviews.csv"
APPLE_SOURCE = Path(__file__).resolve().parents[1] / "data" / "raw" / "apple_app_store_public_reviews.csv"
BUILD_DIR = Path(__file__).resolve().parent / "build"


THEMES = {
    "App stability and loading": [
        r"\bcrash(?:es|ed|ing)?\b", r"\bhang(?:s|ing)?\b", r"\bfroze\b|\bfrozen\b|\bfreez(?:e|es|ing)\b",
        r"\bstuck\b", r"keeps? stopp(?:ing|ed)", r"not (?:open|opening|start|starting|launch|launching)",
        r"won['’]?t (?:open|start|launch)", r"blank screen", r"splash screen", r"not load(?:ing)?",
        r"unable to (?:open|start|launch)", r"app (?:is )?not working", r"application (?:is )?not working",
        r"doesn['’]?t work", r"not working (?:properly|and opening)", r"open and close automatically",
        r"can(?:not|'t) (?:open|be opened)", r"(?:app|application) error", r"functions? don['’]?t .*work",
    ],
    "Performance and responsiveness": [
        r"\bslow\b", r"\bslowness\b", r"\blag(?:s|ging|gy)?\b", r"takes? (?:too |so )?(?:long|much time)",
        r"loading (?:forever|continuously|constantly)", r"keeps? loading", r"not respons(?:ive|ing)", r"\btimeout\b",
    ],
    "Login, registration and OTP": [
        r"\blog[ -]?in\b", r"\blog(?:s|ged|ging)? out\b", r"\bsign[ -]?in\b", r"\bregister(?:ed|ing|ation)?\b", r"\botp\b",
        r"verification code", r"authenticate", r"password", r"mobile number", r"employee id",
    ],
    "Booking, scheduling and cancellation": [
        r"\bbook(?:ing|ed|s)?\b", r"\bschedul(?:e|ed|ing)\b", r"\broster\b", r"\bshift\b",
        r"\bcancel(?:lation|led|ing|s)?\b", r"\breschedul", r"\bad[ -]?hoc\b", r"no slots?",
        r"logins? and logouts?", r"login and logout", r"logout and login",
    ],
    "Live tracking, map and ETA": [
        r"\btrack(?:ing|ed)?\b", r"real[ -]?time", r"live location", r"cab location", r"vehicle location",
        r"wrong location", r"exact location", r"\bgps\b", r"\bmap\b", r"\beta\b", r"estimated time",
        r"zoom(?:ing|ed)? (?:in|out)", r"location (?:is )?not (?:accurate|correct|updated|updating)",
    ],
    "Driver details and contact": [
        r"call (?:the )?(?:cab )?driver", r"contact (?:the )?driver", r"driver (?:contact|number|details)",
        r"driver['’]?s (?:contact|number|details)", r"connect(?:ing)? (?:to|with) (?:the )?driver",
        r"unable to (?:call|contact).*driver", r"driver.*(?:not reachable|unreachable)",
    ],
    "Notifications and reminders": [
        r"\bnotification(?:s)?\b", r"\balert(?:s)?\b", r"\bremind(?:er|ers|ing)?\b", r"push notification",
        r"(?:sms|message) (?:not|doesn['’]?t|didn['’]?t|never) (?:come|receive|arrive)",
    ],
    "Route, pickup and drop planning": [
        r"\broute(?:s|d|ing)?\b", r"pick[ -]?up (?:point|location|time|sequence|route)",
        r"drop (?:point|location|time|sequence|route)", r"long(?:er)? route", r"wrong route",
        r"opposite route", r"multiple pickup", r"detour", r"travel time", r"distance", r"\brouting\b", r"\bmapping\b",
    ],
    "Cab allocation and punctuality": [
        r"cab (?:is )?not (?:assigned|allotted|allocated)", r"cab (?:was )?(?:late|delayed)",
        r"late cab", r"not (?:arrive|arrived|coming|come)", r"didn['’]?t (?:arrive|come|show)",
        r"no cab", r"miss(?:ed|ing) (?:the )?cab", r"left without", r"no show", r"pickup.*late",
    ],
    "UI and usability": [
        r"not user[ -]?friendly", r"user unfriendly", r"\bconfus(?:e|ed|ing)\b", r"\bcomplicated\b",
        r"\bdifficult\b", r"\binterface\b", r"\bui\b", r"\bux\b", r"hard to (?:use|understand|find|know)",
        r"poor design", r"bad design", r"unintuitive", r"not intuitive", r"\bnavigation\b",
        r"drop[ -]?downs?", r"too many (?:selection|click|step)", r"no edit option", r"edit options?",
    ],
    "Support and complaint resolution": [
        r"\bsupport\b", r"help[ -]?desk", r"customer care", r"transport (?:desk|team|department)",
        r"\bcomplain(?:t|ts|ed|ing)?\b", r"no response", r"not respond", r"unhelpful", r"not resolv",
        r"issue.*(?:not|never) (?:resolved|fixed)",
    ],
    "Driver conduct and safety": [
        r"driver.*\brude\b", r"driver.*\barrogant\b", r"driver.*\bbehavio", r"rash driv",
        r"unsafe", r"safety", r"harass", r"threat", r"driver.*(?:refus|deny)", r"driver.*left",
    ],
    "Privacy, permissions and battery": [
        r"\bprivacy\b", r"\bpermission(?:s)?\b", r"battery", r"background", r"personal data",
        r"data privacy", r"tracking me", r"track.*background",
    ],
    "Feedback and rating prompts": [
        r"rate (?:the |your )?trip", r"rate every trip", r"rating (?:popup|after every|every)", r"mandatory (?:rating|review)",
        r"forc(?:e|ed|ing).*rat(?:e|ing)", r"feedback (?:notification|popup|option)",
        r"give feedback", r"provide feedback", r"submit feedback", r"feedback.*(?:not|doesn['’]?t|unable)",
        r"no option to skip.*feedback", r"feedback.*no skip", r"can['’]?t use.*(?:rate|rating)",
    ],
    "Update regression": [
        r"after (?:the |latest |recent |new )?update", r"since (?:the |latest |recent |new )?update",
        r"latest update", r"recent update", r"new update", r"previous version", r"older version",
        r"update.*(?:worse|worst|issue|problem|not working|crash|stuck)",
    ],
}


def normalize_text(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).lower()).strip()


def load_reviews():
    reviews = pd.read_csv(SOURCE)
    reviews["at"] = pd.to_datetime(reviews["at"], errors="coerce")
    reviews["text_normalized"] = reviews["content"].map(normalize_text)
    return reviews


def load_apple_reviews():
    reviews = pd.read_csv(APPLE_SOURCE)
    reviews["at"] = pd.to_datetime(reviews["at"], errors="coerce")
    reviews["text_normalized"] = reviews["content"].map(normalize_text)
    return reviews


def label_reviews(reviews):
    compiled = {theme: re.compile("|".join(f"(?:{p})" for p in patterns), re.I) for theme, patterns in THEMES.items()}
    for theme, pattern in compiled.items():
        reviews[theme] = reviews["text_normalized"].str.contains(pattern, na=False)
    reviews["theme_count"] = reviews[list(THEMES)].sum(axis=1)
    return reviews


def theme_summary(reviews, start=None):
    frame = reviews[(reviews["score"] <= 2) & reviews["text_normalized"].ne("")].copy()
    if start is not None:
        frame = frame[frame["at"] >= start]
    rows = []
    for theme in THEMES:
        hit = frame[frame[theme]]
        rows.append({
            "theme": theme,
            "reviews": len(hit),
            "share_low_text": len(hit) / len(frame) if len(frame) else 0,
            "one_star_share": hit["score"].eq(1).mean() if len(hit) else 0,
            "avg_score": hit["score"].mean() if len(hit) else None,
            "thumbs_up": hit["thumbsUpCount"].sum() if len(hit) else 0,
        })
    return pd.DataFrame(rows).sort_values("reviews", ascending=False), frame


def main():
    reviews = label_reviews(load_reviews())
    end = reviews["at"].max()
    lifetime, low = theme_summary(reviews)
    recent, recent_low = theme_summary(reviews, end - pd.Timedelta(days=365))
    print("LIFETIME LOW-TEXT REVIEW COVERAGE", len(low), (low.theme_count > 0).mean(), "MULTI-LABEL", (low.theme_count > 1).mean())
    print(lifetime.to_string(index=False, formatters={"share_low_text": "{:.1%}".format, "one_star_share": "{:.1%}".format, "avg_score": "{:.2f}".format}))
    print("\nRECENT 365-DAY LOW-TEXT REVIEW COVERAGE", len(recent_low), (recent_low.theme_count > 0).mean(), "MULTI-LABEL", (recent_low.theme_count > 1).mean())
    print(recent.to_string(index=False, formatters={"share_low_text": "{:.1%}".format, "one_star_share": "{:.1%}".format, "avg_score": "{:.2f}".format}))
    print("\nRECENT UNCLASSIFIED EXAMPLES")
    cols = ["at", "score", "thumbsUpCount", "content"]
    print(recent_low[recent_low.theme_count.eq(0)].sort_values(["thumbsUpCount", "at"], ascending=False)[cols].head(30).to_string(index=False, max_colwidth=240))


def export_build_data():
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    reviews = label_reviews(load_reviews())
    end = reviews["at"].max()
    reviews["month"] = reviews["at"].dt.to_period("M").astype(str)
    reviews["has_reply"] = reviews["replyContent"].fillna("").astype(str).str.strip().ne("")
    reviews["repliedAt"] = pd.to_datetime(reviews["repliedAt"], errors="coerce")
    reviews["reply_hours"] = (reviews["repliedAt"] - reviews["at"]).dt.total_seconds() / 3600

    monthly = reviews.groupby("month").agg(
        reviews=("score", "size"),
        average_score=("score", "mean"),
        one_star_share=("score", lambda s: s.eq(1).mean()),
        low_score_share=("score", lambda s: s.le(2).mean()),
        positive_share=("score", lambda s: s.ge(4).mean()),
    ).reset_index()

    lifetime, _ = theme_summary(reviews)
    recent, _ = theme_summary(reviews, end - pd.Timedelta(days=365))
    previous, _ = theme_summary(reviews[(reviews["at"] <= end - pd.Timedelta(days=365))], end - pd.Timedelta(days=730))
    themes = recent.merge(
        lifetime[["theme", "reviews", "share_low_text"]].rename(columns={"reviews": "lifetime_reviews", "share_low_text": "lifetime_share"}),
        on="theme",
    ).merge(
        previous[["theme", "share_low_text"]].rename(columns={"share_low_text": "previous_year_share"}),
        on="theme",
    )
    themes["year_change_pp"] = 100 * (themes["share_low_text"] - themes["previous_year_share"])

    versions = reviews[reviews["reviewCreatedVersion"].notna()].groupby("reviewCreatedVersion").agg(
        reviews=("score", "size"),
        average_score=("score", "mean"),
        one_star_share=("score", lambda s: s.eq(1).mean()),
        low_score_share=("score", lambda s: s.le(2).mean()),
        first_review=("at", "min"),
        last_review=("at", "max"),
    ).reset_index().sort_values("last_review", ascending=False)

    response_rows = []
    for score, group in reviews.groupby("score"):
        valid = group.loc[group["reply_hours"].between(0, 24 * 365), "reply_hours"]
        response_rows.append({
            "score": int(score),
            "reviews": len(group),
            "reply_rate": group["has_reply"].mean(),
            "valid_latency_records": len(valid),
            "median_reply_hours": valid.median(),
            "p90_reply_hours": valid.quantile(.9),
        })
    response = pd.DataFrame(response_rows)

    recent_low = reviews[(reviews["score"] <= 2) & (reviews["at"] >= end - pd.Timedelta(days=365))]
    evidence_rows = []
    for theme in THEMES:
        sample = recent_low[recent_low[theme]].sort_values(["thumbsUpCount", "at"], ascending=False).head(8)
        for _, row in sample.iterrows():
            evidence_rows.append({
                "theme": theme,
                "reviewId": row["reviewId"],
                "date": row["at"],
                "score": int(row["score"]),
                "thumbsUpCount": int(row["thumbsUpCount"]),
                "version": row["reviewCreatedVersion"] if pd.notna(row["reviewCreatedVersion"]) else "",
                "content": row["content"] if pd.notna(row["content"]) else "",
            })
    evidence = pd.DataFrame(evidence_rows)

    apple = label_reviews(load_apple_reviews())
    apple_low = apple[(apple["score"] <= 2) & apple["text_normalized"].ne("")].copy()
    cross_rows = []
    for theme in THEMES:
        google_hit = recent_low[recent_low[theme]]
        apple_hit = apple_low[apple_low[theme]]
        cross_rows.append({
            "theme": theme,
            "google_recent_low_reviews": len(google_hit),
            "google_recent_share": len(google_hit) / len(recent_low) if len(recent_low) else 0,
            "apple_low_reviews": len(apple_hit),
            "apple_low_share": len(apple_hit) / len(apple_low) if len(apple_low) else 0,
            "cross_platform": len(google_hit) > 0 and len(apple_hit) > 0,
        })
    cross_platform = pd.DataFrame(cross_rows).sort_values(
        ["cross_platform", "apple_low_reviews", "google_recent_low_reviews"], ascending=False
    )

    apple_evidence_rows = []
    for theme in THEMES:
        sample = apple_low[apple_low[theme]].sort_values(["at"], ascending=False).head(5)
        for _, row in sample.iterrows():
            apple_evidence_rows.append({
                "theme": theme,
                "reviewId": row["reviewId"],
                "country": row["sourceCountry"],
                "date": row["at"],
                "score": int(row["score"]),
                "title": row["title"] if pd.notna(row["title"]) else "",
                "content": row["content"] if pd.notna(row["content"]) else "",
            })
    apple_evidence = pd.DataFrame(apple_evidence_rows)

    store_summary = pd.DataFrame([
        {
            "store": "Google Play",
            "retrieved_reviews": len(reviews),
            "average_score": reviews["score"].mean(),
            "low_score_share": reviews["score"].le(2).mean(),
            "one_star_share": reviews["score"].eq(1).mean(),
            "first_review": reviews["at"].min(),
            "last_review": reviews["at"].max(),
            "interpretation": "Primary dataset. All written reviews exposed across 69 queried language feeds.",
        },
        {
            "store": "Apple App Store",
            "retrieved_reviews": len(apple),
            "average_score": apple["score"].mean(),
            "low_score_share": apple["score"].le(2).mean(),
            "one_star_share": apple["score"].eq(1).mean(),
            "first_review": apple["at"].min(),
            "last_review": apple["at"].max(),
            "interpretation": "Validation sample. Apple publicly embedded up to 20 visible reviews per storefront.",
        },
    ])

    audit = {
        "as_of": end.isoformat(),
        "rows": len(reviews),
        "unique_review_ids": int(reviews["reviewId"].nunique()),
        "blank_content": int(reviews["text_normalized"].eq("").sum()),
        "sample_average_score": reviews["score"].mean(),
        "sample_low_score_share": reviews["score"].le(2).mean(),
        "sample_one_star_share": reviews["score"].eq(1).mean(),
        "sample_positive_share": reviews["score"].ge(4).mean(),
        "latest_90_average": reviews.loc[reviews["at"] > end - pd.Timedelta(days=90), "score"].mean(),
        "previous_90_average": reviews.loc[(reviews["at"] <= end - pd.Timedelta(days=90)) & (reviews["at"] > end - pd.Timedelta(days=180)), "score"].mean(),
        "latest_90_low_share": reviews.loc[reviews["at"] > end - pd.Timedelta(days=90), "score"].le(2).mean(),
        "previous_90_low_share": reviews.loc[(reviews["at"] <= end - pd.Timedelta(days=90)) & (reviews["at"] > end - pd.Timedelta(days=180)), "score"].le(2).mean(),
        "reply_rate_lifetime": reviews["has_reply"].mean(),
        "reply_rate_latest_90": reviews.loc[reviews["at"] > end - pd.Timedelta(days=90), "has_reply"].mean(),
        "negative_reply_latency_rows": int(reviews["reply_hours"].lt(0).sum()),
        "version_missing": int(reviews["reviewCreatedVersion"].isna().sum()),
        "distinct_versions": int(reviews["reviewCreatedVersion"].nunique()),
        "google_languages_represented": int(reviews["sourceLanguages"].nunique()),
        "apple_rows": int(len(apple)),
        "apple_low_text_rows": int(len(apple_low)),
        "apple_sample_average": apple["score"].mean(),
        "apple_first_review": apple["at"].min().isoformat(),
        "apple_last_review": apple["at"].max().isoformat(),
        "cross_platform_theme_count": int(cross_platform["cross_platform"].sum()),
    }

    def records(frame):
        clean = frame.copy()
        for col in clean.columns:
            clean[col] = clean[col].map(
                lambda value: value.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(value, (pd.Timestamp, datetime.datetime)) else value
            )
        clean = clean.where(pd.notna(clean), None)
        return clean.to_dict(orient="records")

    payloads = {
        "audit.json": audit,
        "monthly.json": records(monthly),
        "themes.json": records(themes),
        "versions.json": records(versions),
        "response.json": records(response),
        "evidence.json": records(evidence),
        "cross_platform.json": records(cross_platform),
        "apple_evidence.json": records(apple_evidence),
        "store_summary.json": records(store_summary),
    }
    for name, payload in payloads.items():
        (BUILD_DIR / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported build data to {BUILD_DIR}")


if __name__ == "__main__":
    if "--export" in __import__("sys").argv:
        export_build_data()
    else:
        main()
