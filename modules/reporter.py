from fpdf import FPDF
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_PATH = os.path.join(BASE_DIR, 'fonts', 'NanumGothic.ttf')

class PDFReport(FPDF):
    def header(self):
        if os.path.exists(FONT_PATH):
            self.add_font('Nanum', '', FONT_PATH)
            self.add_font('Nanum', 'B', FONT_PATH)
            self.set_font('Nanum', 'B', 16)
        else:
            self.set_font('Arial', 'B', 16)
            
        self.cell(0, 10, 'Data Cleaning Report', ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        if os.path.exists(FONT_PATH): self.set_font('Nanum', '', 8)
        else: self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def create_pdf_report(stats, cleaned_data):
    pdf = PDFReport()
    pdf.add_page()
    
    body_font = 'Nanum' if os.path.exists(FONT_PATH) else 'Arial'
    
    pdf.set_font(body_font, 'B', 14)
    pdf.cell(0, 10, '1. Summary Statistics', ln=True)
    pdf.set_font(body_font, '', 12)
    pdf.cell(0, 8, f"- Total Rows Processed: {stats['total_rows']}", ln=True)
    pdf.cell(0, 8, f"- Valid Data: {stats['total_rows'] - stats['removed_rows']}", ln=True)
    pdf.cell(0, 8, f"- Duplicates Removed: {stats['removed_rows']}", ln=True)
    pdf.cell(0, 8, f"- Rows with Missing Info: {stats['missing_info_rows']}", ln=True)
    pdf.ln(10)

    pdf.set_font(body_font, 'B', 14)
    pdf.cell(0, 10, '2. Sheet Details', ln=True)
    pdf.set_font(body_font, '', 11)
    for name, df in cleaned_data.items():
        pdf.cell(0, 8, f"[{name}] : {len(df)} rows", ln=True)
    
    # [핵심 수정] encode 제거하고 bytes()로 변환
    return bytes(pdf.output())