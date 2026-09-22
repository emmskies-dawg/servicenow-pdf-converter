import re
import pdfplumber
import pandas as pd
import openpyxl
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- Matches a number + unit + "ago" anywhere in the line, e.g. "5d ago", "2mo ago", "14h ago" ---
time_pattern = r'(.*?)(\d{1,2})\s?(mo|d|h)\s?ago\s*(.*)'

# --- Matches "01/09/2026, 11:23" (the document printed/saved date+time) ---
printed_date_pattern = r'(\d{2}/\d{2}/\d{4}),\s*(\d{2}:\d{2})'

# --- Matches "SAS2671161" (SAS followed by digits) ---
sas_number_pattern = r'SAS\d+'

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
    """Strip Private Use Area icon glyphs (e.g. \\ue023, \\uf111) and extra whitespace."""
    if not s:
        return s
    cleaned = ''.join(c for c in s if not (0xE000 <= ord(c) <= 0xF8FF))
    return cleaned.strip()

def calculate_date(number_str, unit, reference_date):
    """Subtract the parsed relative time from a reference date."""
    number = int(number_str)
    if unit == "d":
        return reference_date - relativedelta(days=number)
    elif unit == "mo":
        return reference_date - relativedelta(months=number)
    elif unit == "h":
        return reference_date - relativedelta(hours=number)

document_printed_date = None       # string, e.g. "01/09/2026"
document_printed_date_dt = None    # datetime object, used as the reference for calculations
sas_number = None                  # string, e.g. "SAS2671161"

records = []
current_record = None
previous_line = None

with pdfplumber.open("doc_4_activity.pdf") as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()
        if not text:
            continue

        lines = text.split('\n')

        for line in lines:
            stripped = clean_text(line.replace('\xa0', ' '))

            if not stripped:
                continue

            # --- Check for the document printed date (only needs to be found once) ---
            if document_printed_date is None:
                date_match = re.search(printed_date_pattern, stripped)
                if date_match:
                    document_printed_date = date_match.group(1)
                    document_printed_date_dt = datetime.strptime(
                        f"{date_match.group(1)} {date_match.group(2)}", "%d/%m/%Y %H:%M"
                    )

            # --- Check for the SAS number (only needs to be found once) ---
            if sas_number is None:
                sas_match = re.search(sas_number_pattern, stripped)
                if sas_match:
                    sas_number = sas_match.group()

            # --- Check for a "X ago" time entry ---
            time_match = re.search(time_pattern, stripped)

            if time_match and is_valid_time(time_match.group(2), time_match.group(3)):
                if current_record:
                    records.append(current_record)

                before_text = time_match.group(1).strip()
                person = before_text if before_text else previous_line

                number_str = time_match.group(2)
                unit = time_match.group(3)

                # Use the printed date as the reference; fall back to now() if it wasn't found yet
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

            previous_line = stripped

if current_record:
    records.append(current_record)

if not records:
    print("No records matched — check your time_pattern against the actual PDF text.")
else:
    df = pd.DataFrame(records)
    df["Text"] = df["Text"].str.strip()

    # Add document-level fields as their own columns on every row
    df["Document printed date"] = document_printed_date
    df["SAS number"] = sas_number

    print(f"Document printed date: {document_printed_date}")
    print(f"SAS number: {sas_number}")
    print(df)

    filename = f"{sas_number}.xlsx" if sas_number else "activity_export.xlsx"
    df.to_excel(filename, index=False)
    print(f"Exported to {filename}")