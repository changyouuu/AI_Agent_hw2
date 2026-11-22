from io import BytesIO

from PIL import Image
from reportlab.pdfgen import canvas

from formulas import inspect_page, page_count


def sample():
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(55, 760, "A synthetic page for checking formula geometry.")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 700, "x")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(106, 695, "i")
    pdf.drawString(109, 705, "2")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(117, 700, "= 9")
    pdf.drawString(300, 700, "(1)")
    pdf.drawString(115, 637, "a+b")
    pdf.line(111, 632, 141, 632)
    pdf.drawString(120, 618, "c")
    pdf.showPage()
    pdf.drawString(50, 760, "A page with regular prose only.")
    pdf.showPage()
    pdf.save()
    return stream.getvalue()


def run():
    raw = sample()
    assert page_count(raw) == 2
    regions = inspect_page(raw, 1)
    print([region["text"] for region in regions])
    assert any("_{i}^{2}" in region["text"] and region["number"] == "(1)"
               for region in regions), regions
    assert any(region["text"] == "(a+b)/(c)" for region in regions), regions
    assert inspect_page(raw, 2) == []
    page = Image.open(BytesIO(inspect_page(raw, 1, render=True)))
    crop = Image.open(BytesIO(inspect_page(raw, 1, regions[0]["box"], render=True)))
    assert 0 < crop.width < page.width and 0 < crop.height < page.height
    print("PASS: scripts, fraction, full page fallback, and region rendering")


if __name__ == "__main__":
    run()
