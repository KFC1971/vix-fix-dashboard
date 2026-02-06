from pypdf import PdfReader
import os

pdf_path = "S&P 500 Vix Fix Strategy Scanner.pdf"
if not os.path.exists(pdf_path):
    print(f"File not found: {pdf_path}")
    exit(1)

try:
    reader = PdfReader(pdf_path)
    text = ""
    for i, page in enumerate(reader.pages):
        text += f"--- Page {i+1} ---\n"
        text += page.extract_text() + "\n"
    with open("pdf_content.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("PDF content written to pdf_content.txt")
except Exception as e:
    print(f"Error reading PDF: {e}")
