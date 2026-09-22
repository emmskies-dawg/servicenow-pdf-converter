import pdfplumber

with pdfplumber.open("doc_4_activity.pdf") as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        print(f"--- Page {page_num} ---")

        text = page.extract_text()

        if text:
            for line in text.split('\n'):
                print(repr(line))
        else:
            print("(no text extracted)")