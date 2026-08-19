import re
import urllib.request
from datetime import date, timedelta
from bs4 import BeautifulSoup

PAGES = {
    2026: "https://www.scotborders.gov.uk/schools-learning/term-holiday-closure-dates/2",
    2027: "https://www.scotborders.gov.uk/schools-learning/term-holiday-closure-dates/3",
    2028: "https://www.scotborders.gov.uk/schools-learning/term-holiday-closure-dates/4",
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}

def get_page(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")

def clean(text):
    return re.sub(r"\s+", " ", text).strip()

def parse_date(day, month, year):
    return date(
        int(year),
        MONTHS[month.lower()],
        int(day)
    )

def extract_date_range(text):
    text = clean(text)

    # Same-month range:
    # Monday 12 to Friday 16 October 2026
    m = re.search(
        r"(\d{1,2})\s+to\s+(?:\w+\s+)?(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})",
        text,
        re.I
    )

    if m:
        start = parse_date(m.group(1), m.group(3), m.group(4))
        end = parse_date(m.group(2), m.group(3), m.group(4))
        return start, end

    # Cross-year range:
    # Wednesday 23 December 2026 - Tuesday 5 January 2027
    m = re.search(
        r"(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})\s*(?:to|-)\s*"
        r"(?:\w+\s+)?(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})",
        text,
        re.I
    )

    if m:
        start = parse_date(m.group(1), m.group(2), m.group(3))
        end = parse_date(m.group(4), m.group(5), m.group(6))
        return start, end

    # Single date:
    # Monday 30 November 2026
    m = re.search(
        r"(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})",
        text,
        re.I
    )

    if m:
        d = parse_date(m.group(1), m.group(2), m.group(3))
        return d, d

    return None


def extract_year(html):
    soup = BeautifulSoup(html, "html.parser")

    # Find the main page content rather than every date appearing
    # anywhere on the council website.
    main = soup.find("main")

    if main is None:
        main = soup

    lines = [
        clean(x)
        for x in main.get_text("\n").splitlines()
        if clean(x)
    ]

    events = []

    for i, line in enumerate(lines):
        lower = line.lower()

        # Ignore navigation and unrelated content.
        if any(x in lower for x in [
            "school term dates for",
            "contents",
            "contact hq operations",
            "address",
            "telephone",
            "next school term dates",
            "previous school term dates",
        ]):
            continue

        # General term/holiday/in-service dates.
        if any(x in lower for x in [
            "staff resume",
            "in service",
            "pupils resume",
            "last day of term",
            "all resume",
            "schools closed",
            "school closed",
            "holiday",
            "easter holidays",
            "christmas holidays",
        ]):
            parsed = extract_date_range(line)

            if parsed:
                start, end = parsed
                events.append((start, end, line))

        # Galashiels-specific casual holiday.
        if lower == "galashiels":
            for following in lines[i + 1:i + 5]:
                parsed = extract_date_range(following)

                if parsed:
                    start, end = parsed
                    events.append(
                        (
                            start,
                            end,
                            "Galashiels casual holiday"
                        )
                    )
                    break

    return events


all_events = []

for year, url in PAGES.items():
    print(f"Checking {url}")

    try:
        html = get_page(url)
        year_events = extract_year(html)

        print(f"Found {len(year_events)} relevant events")

        all_events.extend(year_events)

    except Exception as error:
        print(f"ERROR reading {url}: {error}")


# Remove duplicates using date + description.
unique = {}

for start, end, summary in all_events:
    key = (
        start.isoformat(),
        end.isoformat(),
        summary
    )

    unique[key] = (
        start,
        end,
        summary
    )

events = sorted(
    unique.values(),
    key=lambda x: (x[0], x[1], x[2])
)


def escape(value):
    return (
        value
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Scottish Borders Council//Galashiels School Dates//EN",
    "CALSCALE:GREGORIAN",
    "X-WR-CALNAME:Galashiels School Dates",
]

for number, (start, end, summary) in enumerate(events, 1):

    ics.extend([
        "BEGIN:VEVENT",
        f"UID:galashiels-{start.isoformat()}-{number}@github.com",
        "DTSTAMP:20260819T000000Z",
        f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
        f"DTEND;VALUE=DATE:{(end + timedelta(days=1)):%Y%m%d}",
        f"SUMMARY:{escape(summary)}",
        "END:VEVENT",
    ])

ics.append("END:VCALENDAR")

with open(
    "galashiels-school-dates.ics",
    "w",
    encoding="utf-8"
) as file:
    file.write("\r\n".join(ics) + "\r\n")

print(f"Generated {len(events)} calendar events.")