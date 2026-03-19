"""Convert Chinese markdown whitepaper to PDF with CJK font support using fpdf2."""

import re
from fpdf import FPDF

INPUT = "whitepaper_cn.md"
OUTPUT = "whitepaper_cn.pdf"

# Chinese font path on macOS
FONT_PATH = "/System/Library/Fonts/PingFang.ttc"
FONT_BOLD_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"
MONO_FONT_PATH = "/System/Library/Fonts/Menlo.ttc"


class WhitepaperPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Register CJK fonts
        self.add_font("PingFang", "", FONT_PATH, uni=True)
        self.add_font("PingFang", "B", FONT_BOLD_PATH, uni=True)
        self.add_font("Mono", "", MONO_FONT_PATH, uni=True)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("PingFang", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"- {self.page_no()} -", align="C")

    def write_title(self, text):
        self.set_font("PingFang", "B", 20)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 12, text, align="C")
        self.ln(4)

    def write_h2(self, text):
        self.ln(6)
        self.set_font("PingFang", "B", 15)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 10, text)
        # Underline
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def write_h3(self, text):
        self.ln(4)
        self.set_font("PingFang", "B", 12)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 8, text)
        self.ln(2)

    def write_paragraph(self, text):
        self.set_font("PingFang", "", 10)
        self.set_text_color(30, 30, 30)
        # Handle inline bold
        self.write_rich_text(text)
        self.ln(4)

    def write_rich_text(self, text):
        """Write text with **bold** support."""
        parts = re.split(r'(\*\*.*?\*\*)', text)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                self.set_font("PingFang", "B", 10)
                self.write(6, part[2:-2])
                self.set_font("PingFang", "", 10)
            else:
                # Strip remaining markdown formatting
                clean = part.replace('`', '')
                self.write(6, clean)
        self.ln()

    def write_bullet(self, text, indent=1):
        self.set_font("PingFang", "", 10)
        self.set_text_color(30, 30, 30)
        x = self.l_margin + indent * 6
        self.set_x(x)
        self.write(6, "  " + text.lstrip("- ").lstrip("0123456789. "))
        self.ln(5)

    def write_code_block(self, text):
        self.ln(2)
        self.set_fill_color(245, 245, 245)
        self.set_font("PingFang", "", 8)
        self.set_text_color(50, 50, 50)
        lines = text.split("\n")
        for line in lines:
            self.set_x(self.l_margin + 4)
            self.cell(0, 5, line, fill=True)
            self.ln()
        self.ln(3)
        self.set_text_color(30, 30, 30)

    def write_table(self, headers, rows):
        self.ln(2)
        n_cols = len(headers)
        usable_w = self.w - self.l_margin - self.r_margin
        col_w = usable_w / n_cols

        # Header
        self.set_font("PingFang", "B", 9)
        self.set_fill_color(240, 240, 240)
        for h in headers:
            self.cell(col_w, 7, h.strip(), border=1, fill=True, align="C")
        self.ln()

        # Rows
        self.set_font("PingFang", "", 9)
        self.set_fill_color(255, 255, 255)
        for row in rows:
            max_h = 7
            # Calculate needed height
            for cell_text in row:
                clean = cell_text.strip().replace('**', '')
                lines_needed = max(1, len(clean) * 0.35 / col_w + 1)
                max_h = max(max_h, int(lines_needed) * 6)
            max_h = min(max_h, 20)

            for cell_text in row:
                clean = cell_text.strip().replace('**', '')
                self.cell(col_w, max_h, clean, border=1, align="L")
            self.ln()
        self.ln(3)

    def write_blockquote(self, text):
        self.ln(2)
        self.set_draw_color(180, 180, 180)
        self.set_fill_color(250, 250, 250)
        x = self.l_margin
        y = self.get_y()
        self.set_x(x + 6)
        self.set_font("PingFang", "", 9)
        self.set_text_color(80, 80, 80)
        clean = text.replace("> ", "").replace("**", "").strip()
        self.multi_cell(self.w - self.l_margin - self.r_margin - 12, 6, clean, fill=True)
        y2 = self.get_y()
        self.line(x + 2, y, x + 2, y2)
        self.ln(3)
        self.set_text_color(30, 30, 30)

    def write_hr(self):
        self.ln(4)
        self.set_draw_color(220, 220, 220)
        y = self.get_y()
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(4)

    def write_subtitle(self, text):
        self.set_font("PingFang", "B", 10)
        self.set_text_color(100, 100, 100)
        self.multi_cell(0, 7, text, align="C")
        self.ln(6)


def parse_and_render(pdf, md_text):
    lines = md_text.split("\n")
    i = 0
    in_code = False
    code_buf = []
    in_table = False
    table_headers = []
    table_rows = []
    in_blockquote = False
    bq_buf = []

    while i < len(lines):
        line = lines[i]

        # Code block toggle
        if line.strip().startswith("```"):
            if in_code:
                pdf.write_code_block("\n".join(code_buf))
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # Table
        if "|" in line and not line.strip().startswith("```"):
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]
            # Check if separator row
            if all(re.match(r'^[-:]+$', c) for c in cells):
                i += 1
                continue
            if not in_table:
                in_table = True
                table_headers = cells
            else:
                table_rows.append(cells)
            i += 1
            # Check if next line is still table
            if i < len(lines) and "|" in lines[i]:
                continue
            else:
                # Flush table
                if table_headers:
                    pdf.write_table(table_headers, table_rows)
                in_table = False
                table_headers = []
                table_rows = []
                continue

        # Blockquote
        if line.strip().startswith(">"):
            bq_buf.append(line.strip())
            i += 1
            while i < len(lines) and lines[i].strip().startswith(">"):
                bq_buf.append(lines[i].strip())
                i += 1
            pdf.write_blockquote("\n".join(bq_buf))
            bq_buf = []
            continue

        stripped = line.strip()

        # Headings
        if stripped.startswith("# ") and not stripped.startswith("## "):
            pdf.write_title(stripped[2:])
            i += 1
            continue
        if stripped.startswith("## "):
            pdf.write_h2(stripped[3:])
            i += 1
            continue
        if stripped.startswith("### "):
            pdf.write_h3(stripped[4:])
            i += 1
            continue
        if stripped.startswith("#### "):
            pdf.write_h3(stripped[5:])
            i += 1
            continue

        # HR
        if stripped == "---":
            pdf.write_hr()
            i += 1
            continue

        # Bullet / numbered list
        if re.match(r'^[-*]\s', stripped) or re.match(r'^\d+\.\s', stripped):
            pdf.write_bullet(stripped)
            i += 1
            continue

        # Empty line
        if not stripped:
            i += 1
            continue

        # Regular paragraph — collect consecutive non-empty lines
        para_lines = [stripped]
        i += 1
        while i < len(lines):
            next_stripped = lines[i].strip()
            if (not next_stripped or next_stripped.startswith("#") or
                next_stripped.startswith("```") or next_stripped.startswith("|") or
                next_stripped.startswith(">") or next_stripped == "---" or
                re.match(r'^[-*]\s', next_stripped) or re.match(r'^\d+\.\s', next_stripped)):
                break
            para_lines.append(next_stripped)
            i += 1
        pdf.write_paragraph(" ".join(para_lines))


def main():
    with open(INPUT, "r", encoding="utf-8") as f:
        md_text = f.read()

    pdf = WhitepaperPDF()
    pdf.add_page()

    parse_and_render(pdf, md_text)

    pdf.output(OUTPUT)
    print(f"Done: {OUTPUT}")


if __name__ == "__main__":
    main()
