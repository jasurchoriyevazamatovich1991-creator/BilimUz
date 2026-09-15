"""
Sprint 43 — Certificate PDF generation.

Isolated from the HTTP router and from CertificateService's own
persistence concerns (per this sprint's "generator must be isolated"
requirement): this module has ONE job — given already-loaded data, it
returns PDF bytes. It never touches the database, storage, or HTTP
layer itself.

Library: reportlab (pure-Python, no system-level font/rendering
dependency — matches this sprint's "no system-level dependencies"
constraint; WeasyPrint was explicitly excluded for this reason).
"""
import io

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def generate_certificate_pdf(
    *,
    certificate_number: str,
    student_full_name: str,
    test_title: str,
    subject_name: str | None,
    score: float | None,
    percentage: float | None,
    issue_date: str,
    verification_code: str,
    verification_url: str,
) -> bytes:
    """
    Renders a single-page, landscape A4 certificate as PDF bytes.

    Every field the certificate DISPLAYS is optional-safe: subject_name/
    score/percentage can be None (certificates.result_id is mandatory,
    but a defensive caller — or a future relationship change — should
    never crash PDF generation), and simply aren't printed when absent
    rather than showing a placeholder like "None" or "N/A" pretending to
    be real data.
    """
    buffer = io.BytesIO()
    page_size = landscape(A4)
    width, height = page_size
    c = canvas.Canvas(buffer, pagesize=page_size)

    # --- Border ---------------------------------------------------------
    c.setStrokeColor(colors.HexColor("#4F46E5"))  # indigo — matches the project's own design system (Sprint 24)
    c.setLineWidth(3)
    c.rect(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm)
    c.setLineWidth(0.75)
    c.rect(18 * mm, 18 * mm, width - 36 * mm, height - 36 * mm)

    # --- Branding ---------------------------------------------------------
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.HexColor("#4F46E5"))
    c.drawCentredString(width / 2, height - 35 * mm, "BilimUz")

    # --- Title ---------------------------------------------------------
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawCentredString(width / 2, height - 55 * mm, "SERTIFIKAT")

    # --- Student name ---------------------------------------------------------
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#374151"))
    c.drawCentredString(width / 2, height - 72 * mm, "ushbu sertifikat quyidagi shaxsga topshiriladi:")

    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawCentredString(width / 2, height - 85 * mm, student_full_name)

    # --- Achievement line ---------------------------------------------------------
    achievement = f'"{test_title}"'
    if subject_name:
        achievement += f" ({subject_name})"
    c.setFont("Helvetica", 13)
    c.setFillColor(colors.HexColor("#374151"))
    c.drawCentredString(width / 2, height - 100 * mm, "testini muvaffaqiyatli yakunladi.")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 108 * mm, achievement)

    # --- Score line (only if both values are actually present) ---------
    if score is not None and percentage is not None:
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.HexColor("#4B5563"))
        c.drawCentredString(width / 2, height - 118 * mm, f"Natija: {score:g} ball ({percentage:g}%)")

    # --- Footer: certificate number, date, verification code ------------
    footer_y = 30 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(25 * mm, footer_y + 10 * mm, f"Sertifikat raqami: {certificate_number}")
    c.drawString(25 * mm, footer_y + 5 * mm, f"Berilgan sana: {issue_date}")
    c.drawString(25 * mm, footer_y, f"Tekshiruv kodi: {verification_code}")

    # --- QR code (verification URL) ---------------------------------
    qr_img = qrcode.make(verification_url)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_size = 28 * mm
    c.drawImage(
        ImageReader(qr_buffer), width - 25 * mm - qr_size, footer_y - 2 * mm,
        width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto",
    )
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.drawCentredString(width - 25 * mm - qr_size / 2, footer_y - 5 * mm, "Tekshirish uchun skanerlang")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
