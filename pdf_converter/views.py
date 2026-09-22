import io
from django.shortcuts import render
from django.http import HttpResponse
from .forms import PDFUploadForm
from .parser import parse_servicenow_pdf

def upload_pdf(request):
    if request.method == "POST":
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES["pdf_file"]

            try:
                df, sas_number, printed_date = parse_servicenow_pdf(pdf_file)
            except ValueError as e:
                return render(request, "pdf_converter/upload.html", {
                    "form": form,
                    "error": str(e),
                })

            # Write the Excel file to an in-memory buffer instead of disk
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)

            filename = f"{sas_number}.xlsx" if sas_number else "activity_export.xlsx"

            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
    else:
        form = PDFUploadForm()

    return render(request, "pdf_converter/upload.html", {"form": form})