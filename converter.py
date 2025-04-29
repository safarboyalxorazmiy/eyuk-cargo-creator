import fitz  # PyMuPDF

# Path to your PDF
pdf_path = "view.pdf"
doc = fitz.open(pdf_path)

# Loop through each page and save as SVG
for i, page in enumerate(doc):
    svg = page.get_svg_image()
    with open(f"page_{i+1}.svg", "w", encoding="utf-8") as f:
        f.write(svg)
