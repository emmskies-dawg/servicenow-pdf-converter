import re
import pdfplumber
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

time_pattern = r'(.*?)(\d{1,2})\s?(mo|d|h)\s?ago\s*(.*)'
printed_date_pattern = r'(\d{2}/\d{2}/\d{4}),\s*(\d{2}:\d{2})'
sas_number_pattern = r'SAS\d+'
header_pattern = re.compile(printed_date_pattern + r'.*' + sas_number_pattern)

# Anything matching these patterns is NOT a person's name
url_pattern = re.compile(r'(https?://|www\.|\.com|\.org|\.edu|\.au\b)', re.IGNORECASE)

valid_ranges = {
    "d": (1, 35),
    "mo": (1, 12),
    "h": (1, 24),
}

def is_valid_time(number_str, unit):
    number = int(number_str)
    low, high = valid_ranges[unit]
    return low <= number <= high

def clean_text(s):
    if not s:
        return s
    cleaned = ''.join(c for c in s if not (0xE000 <= ord(c) <= 0xF8FF))
    return cleaned.strip()

def calculate_date(number_str, unit, reference_date):
    number = int(number_str)
    if unit == "d":
        return reference_date - relativedelta(days=number)
    elif unit == "mo":
        return reference_date - relativedelta(months=number)
    elif unit == "h":
        return reference_date - relativedelta(hours=number)

def is_probable_name(s):
    """Heuristic check: does this line look like it could be a person's name?"""
    if not s:
        return False
    if url_pattern.search(s):
        return False
    if header_pattern.search(s):
        return False
    if re.search(r'\d', s):          # names shouldn't contain digits
        return False
    if len(s) > 40:                  # names are short; long lines are probably content/sentences
        return False
    if len(s.split()) > 5:           # more than ~5 words is probably not a name
        return False
    return True

def parse_servicenow_pdf(file_obj):
    """
    Takes an uploaded PDF file object (e.g. from request.FILES) and returns
    (dataframe, sas_number, document_printed_date) or raises ValueError if
    nothing could be parsed.
    """
    document_printed_date = None
    document_printed_date_dt = None
    sas_number = None

    records = []
    current_record = None
    recent_lines = []  # keep a short rolling history instead of just one previous_line

    with pdfplumber.open(file_obj) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue

            for line in text.split('\n'):
                stripped = clean_text(line.replace('\xa0', ' '))
                if not stripped:
                    continue

                # --- Detect and skip the repeated page header entirely ---
                if header_pattern.search(stripped):
                    if document_printed_date is None:
                        date_match = re.search(printed_date_pattern, stripped)
                        if date_match:
                            document_printed_date = date_match.group(1)
                            document_printed_date_dt = datetime.strptime(
                                f"{date_match.group(1)} {date_match.group(2)}", "%d/%m/%Y %H:%M"
                            )
                    if sas_number is None:
                        sas_match = re.search(sas_number_pattern, stripped)
                        if sas_match:
                            sas_number = sas_match.group()
                    continue  # skip entirely — don't touch recent_lines or records

                time_match = re.search(time_pattern, stripped)

                if time_match and is_valid_time(time_match.group(2), time_match.group(3)):
                    if current_record:
                        records.append(current_record)

                    before_text = time_match.group(1).strip()

                    if before_text and is_probable_name(before_text):
                        person = before_text
                    else:
                        # Walk backwards through recent lines until we find
                        # one that actually looks like a name
                        person = None
                        for candidate in reversed(recent_lines):
                            if is_probable_name(candidate):
                                person = candidate
                                break

                    number_str = time_match.group(2)
                    unit = time_match.group(3)
                    reference_date = document_printed_date_dt or datetime.now()

                    current_record = {
                        "Page number": page_num,
                        "Person from": person,
                        "Time": f"{number_str}{unit} ago",
                        "Calculated date": calculate_date(number_str, unit, reference_date).strftime("%Y-%m-%d"),
                        "Category": time_match.group(4).strip(),
                        "Text": ""
                    }
                elif current_record is not None:
                    current_record["Text"] += (stripped + " ")

                # Keep only the last few lines to search back through
                recent_lines.append(stripped)
                if len(recent_lines) > 5:
                    recent_lines.pop(0)

    if current_record:
        records.append(current_record)

    if not records:
        raise ValueError("No matching entries found in this PDF.")

    df = pd.DataFrame(records)
    df["Text"] = df["Text"].str.strip()
    df["Document printed date"] = document_printed_date
    df["SAS number"] = sas_number

    return df, sas_number, document_printed_date