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
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12
}

def get_page(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Galashiels-School-Calendar/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")

def clean(text):
    return re.sub(r"\s+", " ", text).strip()

def parse_single(day, month, year):
    return date(year, MONTHS[month], int(day))

def parse_date_text(text, default_year):
    text = clean(text)

    # Range:
    # Monday 12 to Friday 16 October 2026
    m = re.search(
        r"\b(\d{1,2})\s+(?:to|-)\s+(?:\w+\s+)?(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})",
        text,
        re.I
    )
    if m:
        d1 = int(m.group(1))
        d2 = int(m.group(2))
        month = MONTHS[m.group(3).capitalize()]
        year = int(m.group(4))
        return date(year, month, d1), date(year, month, d2)

    # Range:
    # Wednesday 23 December 2026 - Tuesday 5 January 2027
    m = re.search(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})\s*(?:to|-)\s*(?:\w+\s+)?(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})",
        text,
        re.I
    )
    if m:
        start = parse_single(m.group(1), m.group(2).capitalize(), int(m.group(3)))
        end = parse_single(m.group(4), m.group(5).capitalize(), int(m.group(6)))
        return start, end

    # Single date:
    # Monday 30 November 2026
    m = re.search(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})",
        text,
        re.I
    )
    if m:
        d = parse_single(m.group(1), m.group(2).capitalize(), int(m.group(3)))
        return d, d

    # Casual holiday may be written:
    # Tuesday 1 December 2026
    return None

def extract_events(html, academic_year):
    soup = BeautifulSoup(html, "html.parser")

    # Get the visible text as individual lines.
    text = soup.get_text("\n")
    lines = [clean(x) for x in text.splitlines() if clean(x)]

    events = []

    for i, line in enumerate(lines):
        lower = line.lower()

        # Only take the general term/holiday material.
        interesting = any(word in lower for word in [
            "staff resume",
            "in service",
            "pupils resume",
            "holiday",
            "last day of term",
            "term starts",
            "all resume",
            "schools closed",
            "school closed",
            "easter",
            "christmas"
        ])

        if interesting:
            parsed = parse_date_text(line, academic_year)
            if parsed:
                start, end = parsed
                events.append((start, end, line))

        # Galashiels-specific casual holiday.
        if lower == "galashiels":
            for following in lines[i + 1:i + 4]:
                parsed = parse_date_text(following, academic_year)
                if parsed:
                    start, end = parsed
                    events.append(
                        (start, end, "Galashiels casual holiday - " + following)
                    )
                    break

    return events

def escape(value):
    return (
        value.replace("\\", "\\\\")
             .replace(",", "\\,")
             .replace(";", "\\;")
             .replace("\n", "\\n")
    )

all_events = []

for year, url in PAGES.items():
    try:
        html = get_page(url)
        all_events.extend(extract_events(html, year))
    except Exception as e:
        print(f"Could not read {url}: {e}")

# Remove duplicates.
unique = {}
for start, end, summary in all_events:
    key = (start, end, summary)
    unique[key] = (start, end, summary)

events = sorted(unique.values(), key=lambda x: (x[0], x[1], x[2]))

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

with open("galashiels-school-dates.ics", "w", encoding="utf-8") as f:
    f.write("\r\n".join(ics) + "\r\n")

print(f"Generated {len(events)} calendar events.")
