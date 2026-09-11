from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

text_lines = [
    "MEDICORE PHARMACEUTICALS PVT. LTD.",
    "Customer Quality Complaint Notification",
    "",
    "To: Quality Assurance Department, ApexPharma Manufacturing Ltd.",
    "From: Purchasing & QA, Medicore Pharmaceuticals Pvt. Ltd.",
    "Date: 03-Sep-2026",
    "Reference: MCP-QC-2026-0091",
    "",
    "Subject: Quality Complaint - Metformin Hydrochloride API",
    "",
    "Dear QA Team,",
    "",
    "We wish to formally report a quality complaint regarding a recent shipment of",
    "Metformin Hydrochloride API received from your facility.",
    "",
    "Product Name        : Metformin Hydrochloride API",
    "Product Strength/Grade : IP/BP",
    "Batch/Lot Number     : MFH26CHG2607012A",
    "Manufacturing Date   : 12-Jul-2026",
    "Expiry Date          : 11-Jul-2028",
    "Quantity Received    : 50 kg (2 HDPE drums)",
    "Reported By          : Rakesh Iyer, QC Manager, Medicore Pharmaceuticals",
    "Contact              : rakesh.iyer@medicore-pharma.example, +91-98200-11223",
    "",
    "Nature of Complaint:",
    "During incoming raw-material inspection, our QC lab observed off-white to pale",
    "yellow discoloration in a portion of the API powder, along with slightly higher",
    "than expected moisture content on Karl Fischer testing. Visual clumping was also",
    "noted in one of the two drums (Drum #2). The other drum appeared within normal",
    "visual specification.",
    "",
    "We are placing this batch on hold pending your investigation and request a formal",
    "root cause analysis, CAPA, and confirmation of whether replacement or credit note",
    "will be issued.",
    "",
    "Regards,",
    "Rakesh Iyer",
    "QC Manager, Medicore Pharmaceuticals Pvt. Ltd.",
]

c = canvas.Canvas("sample_complaint_metformin.pdf", pagesize=A4)
width, height = A4
y = height - 25*mm
c.setFont("Helvetica", 10)
for line in text_lines:
    if y < 20*mm:
        c.showPage()
        c.setFont("Helvetica", 10)
        y = height - 25*mm
    c.drawString(20*mm, y, line)
    y -= 6*mm
c.save()
print("PDF written")
