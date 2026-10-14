"""High-Quality Vector PDF Invoice Generator (Pure Python Standard Library)
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)

Generates professional, print-ready vector PDF invoices conforming to the
ISO 32000-1 (PDF 1.4) standard. Operates with zero third-party dependencies,
ensuring 100% offline portability and universal rendering across Acrobat,
Chrome, Edge, Firefox, and macOS/Linux viewers.
"""

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional


def _escape_pdf_str(text: str) -> str:
    """Escape special characters for PDF text string literals."""
    if text is None:
        return ""
    # Replace unicode rupee symbol or non-ascii with standard ASCII equivalent
    text = (
        str(text)
        .replace("₹", "INR ")
        .replace("•", "*")
        .replace("—", "-")
        .replace("–", "-")
    )
    # Filter to printable ASCII / Latin-1 range for Type 1 fonts
    clean = []
    for ch in text:
        code = ord(ch)
        if 32 <= code <= 126 or 160 <= code <= 255:
            clean.append(ch)
        elif ch in "\r\n\t":
            clean.append(" ")
        else:
            clean.append("?")
    text = "".join(clean)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class PDFCanvas:
    """Lightweight 2D vector graphic canvas for assembling PDF page streams."""

    def __init__(self, width: float = 595.28, height: float = 841.89):
        # A4 Page Size: 595.28 x 841.89 points (210 x 297 mm)
        self.width = width
        self.height = height
        self.stream = []

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill_color: Optional[tuple] = None,
        stroke_color: Optional[tuple] = None,
        line_width: float = 1.0,
    ):
        """Draw a rectangle with optional fill and stroke."""
        self.stream.append("q")
        if fill_color:
            r, g, b = fill_color
            self.stream.append(f"{r:.3f} {g:.3f} {b:.3f} rg")
        if stroke_color:
            r, g, b = stroke_color
            self.stream.append(f"{r:.3f} {g:.3f} {b:.3f} RG")
            self.stream.append(f"{line_width:.2f} w")
        self.stream.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill_color and stroke_color:
            self.stream.append("B")
        elif fill_color:
            self.stream.append("f")
        elif stroke_color:
            self.stream.append("s")
        self.stream.append("Q")

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: tuple = (0.8, 0.8, 0.8),
        width: float = 1.0,
    ):
        """Draw a 1-pixel or custom vector line divider."""
        r, g, b = color
        self.stream.append(
            f"q {width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l s Q"
        )

    def text(
        self,
        text: str,
        x: float,
        y: float,
        font: str = "/F1",
        size: float = 10,
        color: tuple = (0.1, 0.1, 0.1),
        align: str = "left",
        width: float = 0,
    ):
        """Draw single line of text with alignment support."""
        escaped = _escape_pdf_str(text)
        r, g, b = color

        # Compute estimated character width for Helvetica
        # Average character width ratio is ~0.55 of font size
        char_ratio = 0.58 if "Bold" in font or font == "/F2" else 0.52
        if font == "/F3":  # Monospaced Courier
            char_ratio = 0.60
        est_len = len(text) * size * char_ratio

        actual_x = x
        if align == "right":
            actual_x = x + (width - est_len) if width > 0 else x - est_len
        elif align == "center":
            actual_x = x + (width - est_len) / 2.0 if width > 0 else x - (est_len / 2.0)

        self.stream.append("q")
        self.stream.append(f"{r:.3f} {g:.3f} {b:.3f} rg")
        self.stream.append("BT")
        self.stream.append(f"{font} {size:.2f} Tf")
        self.stream.append(f"{actual_x:.2f} {y:.2f} Td")
        self.stream.append(f"({escaped}) Tj")
        self.stream.append("ET")
        self.stream.append("Q")

    def render_content_stream(self) -> bytes:
        """Join commands into byte stream."""
        return "\n".join(self.stream).encode("latin-1")


class PDFDocument:
    """Standard ISO 32000-1 PDF document builder."""

    def __init__(self):
        self.objects: List[bytes] = []

    def add_object(self, data: bytes) -> int:
        """Add object and return 1-based object number."""
        self.objects.append(data)
        return len(self.objects)

    def build(self, canvas_or_canvases: Any) -> bytes:
        """Compile complete vector PDF with catalog, pages, fonts, and xref table.

        Supports single canvas (1 page) or multiple canvases (multi-page PDF report).
        """
        if isinstance(canvas_or_canvases, PDFCanvas):
            canvases = [canvas_or_canvases]
        elif isinstance(canvas_or_canvases, (list, tuple)):
            canvases = list(canvas_or_canvases)
        else:
            raise TypeError("canvas_or_canvases must be a PDFCanvas or a sequence of PDFCanvas instances.")

        if not canvases:
            raise ValueError("At least one canvas is required to build a PDF document.")

        n_pages = len(canvases)

        # Structure of PDF objects:
        # 1: Catalog
        # 2: Pages root
        # 3: Font F1 (Helvetica)
        # 4: Font F2 (Helvetica-Bold)
        # 5: Font F3 (Courier)
        # 6: Font F4 (Courier-Bold)
        # For each page index i (0 <= i < n_pages):
        #   page_obj_num = 7 + 2 * i
        #   stream_obj_num = 8 + 2 * i

        kids_refs = " ".join(f"{7 + 2 * i} 0 R" for i in range(n_pages))
        obj_1 = b"<< /Type /Catalog /Pages 2 0 R >>"
        obj_2 = f"<< /Type /Pages /Kids [{kids_refs}] /Count {n_pages} >>".encode("latin-1")
        obj_3 = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        obj_4 = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        obj_5 = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"
        obj_6 = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>"

        all_objs = [obj_1, obj_2, obj_3, obj_4, obj_5, obj_6]

        for i, canvas in enumerate(canvases):
            stream_obj_num = 8 + 2 * i
            content_stream = canvas.render_content_stream()
            stream_len = len(content_stream)

            page_obj = (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {canvas.width:.2f} {canvas.height:.2f}] "
                f"/Contents {stream_obj_num} 0 R "
                f"/Resources << "
                f"/Font << "
                f"/F1 3 0 R "
                f"/F2 4 0 R "
                f"/F3 5 0 R "
                f"/F4 6 0 R "
                f">> >> >>"
            ).encode("latin-1")

            stream_obj = (
                f"<< /Length {stream_len} >>\r\nstream\r\n".encode("latin-1")
                + content_stream
                + b"\r\nendstream"
            )
            all_objs.append(page_obj)
            all_objs.append(stream_obj)

        out = BytesIO()
        out.write(b"%PDF-1.4\r\n%\xe2\xe3\xcf\xd3\r\n")

        offsets = []
        for idx, obj in enumerate(all_objs, start=1):
            offset = out.tell()
            offsets.append(offset)
            out.write(f"{idx} 0 obj\r\n".encode("latin-1"))
            out.write(obj)
            out.write(b"\r\nendobj\r\n")

        xref_pos = out.tell()
        out.write(b"xref\r\n")
        out.write(f"0 {len(all_objs) + 1}\r\n".encode("latin-1"))
        out.write(b"0000000000 65535 f \r\n")
        for off in offsets:
            out.write(f"{off:010d} 00000 n \r\n".encode("latin-1"))

        out.write(b"trailer\r\n")
        out.write(f"<< /Size {len(all_objs) + 1} /Root 1 0 R >>\r\n".encode("latin-1"))
        out.write(b"startxref\r\n")
        out.write(f"{xref_pos}\r\n".encode("latin-1"))
        out.write(b"%%EOF\r\n")

        return out.getvalue()


def render_invoice_canvas(bill_details: Dict[str, Any], restaurant_name: str = "Amrapali Campus Diner") -> PDFCanvas:
    """Render a single invoice receipt onto a dedicated A4 vector PDFCanvas."""
    canvas = PDFCanvas(width=595.28, height=841.89)

    # ------------------------------------------------------------------
    # 1. Colors Setup
    # ------------------------------------------------------------------
    EMERALD_DARK = (0.016, 0.471, 0.341)   # #047857
    EMERALD_LIGHT = (0.925, 0.992, 0.961) # #ECFDF5
    SLATE_900 = (0.059, 0.090, 0.165)     # #0F172A (Text main)
    SLATE_600 = (0.278, 0.333, 0.412)     # #475569 (Text muted)
    SLATE_200 = (0.894, 0.914, 0.941)     # #E2E8F0 (Borders)
    SLATE_100 = (0.945, 0.957, 0.973)     # #F1F5F9 (Background)
    WHITE = (1.0, 1.0, 1.0)
    DANGER = (0.863, 0.149, 0.149)        # #DC2626 (Void/Red)

    is_void = (bill_details.get("status") == "VOID")

    # ------------------------------------------------------------------
    # 2. Header Brand Banner
    # ------------------------------------------------------------------
    # Top banner background
    banner_color = DANGER if is_void else EMERALD_DARK
    canvas.rect(36, 742, 523.28, 64, fill_color=banner_color)

    # Restaurant Title
    disp_name = restaurant_name.upper()
    canvas.text(disp_name, 56, 780, font="/F2", size=18, color=WHITE)
    canvas.text(
        "Total Quality Management POS  |  Haldwani Campus Diner",
        56,
        762,
        font="/F1",
        size=10,
        color=WHITE,
    )
    canvas.text("OFFICIAL TAX INVOICE", 400, 778, font="/F2", size=12, color=WHITE, align="right", width=140)
    canvas.text("GSTIN: 05AABCA1234D1Z5", 400, 762, font="/F1", size=9, color=WHITE, align="right", width=140)

    # ------------------------------------------------------------------
    # 3. Invoice Metadata Card
    # ------------------------------------------------------------------
    canvas.rect(36, 664, 523.28, 68, fill_color=WHITE, stroke_color=SLATE_200, line_width=1.0)

    # Column 1: Invoice & Date
    canvas.text("INVOICE NUMBER:", 50, 712, font="/F2", size=9, color=SLATE_600)
    canvas.text(bill_details.get("bill_number", "N/A"), 145, 712, font="/F4", size=10, color=SLATE_900)

    canvas.text("DATE & TIME:", 50, 694, font="/F2", size=9, color=SLATE_600)
    canvas.text(str(bill_details.get("created_at", ""))[:19], 145, 694, font="/F1", size=9, color=SLATE_900)

    cust_phone = bill_details.get("customer_phone")
    if cust_phone and cust_phone != "[Encrypted at Rest]":
        canvas.text("CUSTOMER PHONE:", 50, 676, font="/F2", size=9, color=SLATE_600)
        canvas.text(cust_phone, 145, 676, font="/F1", size=9, color=SLATE_900)
    else:
        canvas.text("CUSTOMER:", 50, 676, font="/F2", size=9, color=SLATE_600)
        canvas.text("Counter Walk-in Guest", 145, 676, font="/F1", size=9, color=SLATE_600)

    # Column 2: Cashier & Payment Status
    canvas.text("BILLED BY:", 340, 712, font="/F2", size=9, color=SLATE_600)
    canvas.text(str(bill_details.get("cashier_name", "Cashier")), 430, 712, font="/F1", size=9, color=SLATE_900)

    canvas.text("PAYMENT MODE:", 340, 694, font="/F2", size=9, color=SLATE_600)
    canvas.text(str(bill_details.get("payment_mode", "Cash")), 430, 694, font="/F2", size=9, color=SLATE_900)

    canvas.text("STATUS:", 340, 676, font="/F2", size=9, color=SLATE_600)
    status_str = bill_details.get("status", "COMPLETED")
    status_clr = DANGER if is_void else EMERALD_DARK
    canvas.text(status_str, 430, 676, font="/F2", size=9, color=status_clr)

    # ------------------------------------------------------------------
    # 4. Itemized Table
    # ------------------------------------------------------------------
    table_top = 644
    row_height = 20

    # Table Header Bar
    canvas.rect(36, table_top - row_height, 523.28, row_height, fill_color=SLATE_100, stroke_color=SLATE_200, line_width=1.0)
    canvas.text("#", 48, table_top - 14, font="/F2", size=9, color=SLATE_600)
    canvas.text("ITEM DESCRIPTION", 78, table_top - 14, font="/F2", size=9, color=SLATE_600)
    canvas.text("QTY", 320, table_top - 14, font="/F2", size=9, color=SLATE_600, align="right", width=35)
    canvas.text("UNIT RATE", 390, table_top - 14, font="/F2", size=9, color=SLATE_600, align="right", width=65)
    canvas.text("TOTAL (INR)", 480, table_top - 14, font="/F2", size=9, color=SLATE_600, align="right", width=65)

    curr_y = table_top - row_height

    items = bill_details.get("items", [])
    for idx, itm in enumerate(items, start=1):
        curr_y -= row_height
        bg = WHITE if idx % 2 != 0 else (0.98, 0.98, 0.99)
        canvas.rect(36, curr_y, 523.28, row_height, fill_color=bg)
        canvas.line(36, curr_y, 559.28, curr_y, color=SLATE_200, width=0.5)

        name = itm.get("item_name_snapshot", itm.get("name", "Item"))
        qty = itm.get("quantity", itm.get("qty", 1))
        rate = float(itm.get("unit_price_snapshot", itm.get("rate", 0.0)))
        total = float(itm.get("line_total", itm.get("total", 0.0)))

        canvas.text(str(idx), 48, curr_y + 6, font="/F1", size=9, color=SLATE_600)
        canvas.text(name[:36], 78, curr_y + 6, font="/F1", size=9, color=SLATE_900)
        canvas.text(str(qty), 320, curr_y + 6, font="/F1", size=9, color=SLATE_900, align="right", width=35)
        canvas.text(f"{rate:.2f}", 390, curr_y + 6, font="/F1", size=9, color=SLATE_900, align="right", width=65)
        canvas.text(f"{total:.2f}", 480, curr_y + 6, font="/F2", size=9, color=SLATE_900, align="right", width=65)

    # ------------------------------------------------------------------
    # 5. Financial Summary Calculation Box
    # ------------------------------------------------------------------
    subtotal = float(bill_details.get("subtotal", 0.0))
    discount = float(bill_details.get("discount_amount", 0.0))
    tax_amount = float(bill_details.get("tax_amount", 0.0))
    final_total = float(bill_details.get("final_total", 0.0))

    summary_y = curr_y - 20
    box_w = 230
    box_x = 559.28 - box_w

    # Subtotal line
    canvas.text("Items Subtotal:", box_x, summary_y, font="/F1", size=10, color=SLATE_600)
    canvas.text(f"INR {subtotal:.2f}", box_x + 110, summary_y, font="/F2", size=10, color=SLATE_900, align="right", width=110)
    summary_y -= 16

    # Discount line if present
    if discount > 0:
        disc_pct = (discount / subtotal * 100.0) if subtotal > 0 else 0.0
        canvas.text(f"Discount ({disc_pct:.0f}%):", box_x, summary_y, font="/F1", size=10, color=SLATE_600)
        canvas.text(f"-INR {discount:.2f}", box_x + 110, summary_y, font="/F2", size=10, color=DANGER, align="right", width=110)
        summary_y -= 16

    # GST Inclusive Breakdown
    tax_rate = float(bill_details.get("tax_rate", 0.05))
    gst_pct = int(tax_rate * 100)
    canvas.text(f"GST ({gst_pct}% Included):", box_x, summary_y, font="/F1", size=10, color=SLATE_600)
    canvas.text(f"INR {tax_amount:.2f}", box_x + 110, summary_y, font="/F1", size=10, color=SLATE_600, align="right", width=110)
    summary_y -= 22

    # Grand Total Banner Card
    total_card_h = 32
    summary_y -= total_card_h
    canvas.rect(box_x - 10, summary_y, box_w + 10, total_card_h, fill_color=EMERALD_LIGHT, stroke_color=EMERALD_DARK, line_width=1.2)
    canvas.text("GRAND TOTAL:", box_x, summary_y + 10, font="/F2", size=11, color=EMERALD_DARK)
    canvas.text(f"INR {final_total:.2f}", box_x + 90, summary_y + 8, font="/F2", size=15, color=EMERALD_DARK, align="right", width=130)

    # ------------------------------------------------------------------
    # 6. Void / Cancellation Stamp (if applicable)
    # ------------------------------------------------------------------
    if is_void:
        void_y = summary_y + 10
        canvas.rect(40, void_y - 20, 240, 50, fill_color=(1.0, 0.94, 0.94), stroke_color=DANGER, line_width=1.5)
        canvas.text("** INVOICE CANCELLED / VOID **", 50, void_y + 12, font="/F2", size=11, color=DANGER)
        reason = bill_details.get("void_reason") or "Administrative cancellation"
        canvas.text(f"Reason: {reason[:36]}", 50, void_y - 4, font="/F1", size=8, color=DANGER)

    # ------------------------------------------------------------------
    # 7. Security Checksum & Legal Footer
    # ------------------------------------------------------------------
    footer_y = 70
    canvas.line(36, footer_y + 30, 559.28, footer_y + 30, color=SLATE_200, width=0.8)

    rec_hash = str(bill_details.get("receipt_hash", "N/A"))
    canvas.text("Digital Tamper-Detection Hash (HMAC-SHA256):", 36, footer_y + 16, font="/F2", size=8, color=SLATE_600)
    canvas.text(rec_hash[:58] + ("..." if len(rec_hash) > 58 else ""), 36, footer_y + 5, font="/F3", size=8, color=SLATE_900)

    canvas.text(
        "Prices are inclusive of 5% Goods and Services Tax (GST). Computer generated tax invoice.",
        36,
        footer_y - 12,
        font="/F1",
        size=8,
        color=SLATE_600,
        align="center",
        width=523.28,
    )
    canvas.text(
        "Thank You for Dining With Us! Please Visit Again.",
        36,
        footer_y - 24,
        font="/F2",
        size=9,
        color=EMERALD_DARK,
        align="center",
        width=523.28,
    )

    return canvas


def generate_invoice_pdf(bill_details: Dict[str, Any], restaurant_name: str = "Amrapali Campus Diner") -> bytes:
    """Generate professional, print-ready PDF invoice bytes from bill details dictionary."""
    canvas = render_invoice_canvas(bill_details, restaurant_name=restaurant_name)
    return PDFDocument().build(canvas)


def generate_all_invoices_pdf(bills_details: List[Dict[str, Any]], restaurant_name: str = "Amrapali Campus Diner") -> bytes:
    """Generate a consolidated multi-page vector PDF containing all customer invoice receipts."""
    if not bills_details:
        raise ValueError("No invoice records provided to generate PDF.")
    canvases = [render_invoice_canvas(b, restaurant_name=restaurant_name) for b in bills_details]
    return PDFDocument().build(canvases)
