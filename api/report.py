import json
from http.server import BaseHTTPRequestHandler
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
import io
import base64


def build_pdf(data):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', parent=styles['Normal'],
                                  fontSize=16, alignment=TA_CENTER,
                                  spaceAfter=6, fontName='Helvetica-Bold')
    company_style = ParagraphStyle('Company', parent=styles['Normal'],
                                    fontSize=12, alignment=TA_CENTER,
                                    spaceAfter=2, fontName='Helvetica-Bold')
    heading_style = ParagraphStyle('SectionHead', parent=styles['Normal'],
                                    fontSize=11, fontName='Helvetica-Bold',
                                    spaceBefore=16, spaceAfter=6,
                                    textColor=colors.black)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                 fontSize=10, fontName='Helvetica',
                                 spaceAfter=4, leading=14)
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'],
                                 fontSize=10, fontName='Helvetica',
                                 spaceAfter=2)

    elements = []

    # Header
    elements.append(Paragraph("Atrium Construction Corp", company_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Weekly Progress Report", title_style))
    elements.append(Spacer(1, 12))

    # Meta info
    elements.append(Paragraph(f"<b>Date:</b> {data.get('date', '')}", meta_style))
    elements.append(Paragraph(f"<b>Project:</b> {data.get('project', '')}", meta_style))
    elements.append(Paragraph(f"<b>Week of:</b> {data.get('weekOf', '')}", meta_style))
    elements.append(Spacer(1, 12))

    # Sections
    sections = [
        ("WORK PERFORMED THIS WEEK", data.get("workPerformed", [])),
        ("WORK SCHEDULED FOR NEXT WEEK", data.get("workScheduled", [])),
        ("MODIFICATIONS TO THE PROJECT", data.get("modifications", [])),
        ("APPROVALS NEEDED", data.get("approvals", [])),
        ("PRESENT AND/OR ANTICIPATED PROBLEMS", data.get("problems", [])),
        ("HOT LIST OF INFORMATION NEEDED TO STAY ON TRACK", data.get("hotList", [])),
    ]

    for title, items in sections:
        elements.append(Paragraph(title, heading_style))
        if items and len(items) > 0:
            for item in items:
                elements.append(Paragraph(f"• {item}", body_style))
        else:
            elements.append(Paragraph("N/A", body_style))

    doc.build(elements)
    return buf.getvalue()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))

            pdf_bytes = build_pdf(body)
            pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"pdf": pdf_b64}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
