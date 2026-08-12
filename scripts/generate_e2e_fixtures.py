"""Generate synthetic scanned legal-document fixtures (no third-party content)."""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 28)
except OSError:
    FONT = ImageFont.load_default()


def page(lines, signed=False):
    image = Image.new("RGB", (1275, 1650), "white")
    draw = ImageDraw.Draw(image)
    y = 100
    for line in lines:
        draw.text((100, y), line, fill="black", font=FONT)
        y += 46
    if signed:
        y = 1280
        for offset in (0, 260):
            points = [(120 + offset, y + 25), (160 + offset, y - 20), (205 + offset, y + 30),
                      (250 + offset, y - 10), (315 + offset, y + 20)]
            draw.line(points, fill="black", width=5)
            draw.text((120 + offset, y + 45), "Authorized signature", fill="black", font=FONT)
    return image


def write_pdf(name, signed):
    first = page([
        "MASTER SERVICES AGREEMENT", "Vendor: Synthetic Acme LLC", "Effective Date: January 15, 2025",
        "This Master Services Agreement governs professional services.",
        "Expiration Date: January 15, 2027",
    ])
    second = page(["SIGNATURE PAGE", "Synthetic Acme LLC", "Example Customer Corporation"], signed=signed)
    destination = ROOT / name
    first.save(destination, "PDF", resolution=150, save_all=True, append_images=[second])
    # Pillow writes wall-clock PDF metadata; normalize it for byte-for-byte fixtures.
    content = re.sub(rb"D:\d{14}Z", b"D:20250115000000Z", destination.read_bytes())
    destination.write_bytes(content)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    write_pdf("Synthetic_Acme_LLC_scanned_signed_MSA.pdf", signed=True)
    write_pdf("Synthetic_Acme_LLC_scanned_unsigned_agreement.pdf", signed=False)
    (ROOT / "corrupt.pdf").write_bytes(b"%PDF-1.7\nsynthetic-corrupt-no-xref")


if __name__ == "__main__":
    main()
