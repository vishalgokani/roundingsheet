import re
import argparse
from pathlib import Path
from textwrap import wrap

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


SECTION_NAMES = [
    "oneliner",
    "vitals",
    "intake_output",
    "telemetry",
    "labs",
    "imaging",
    "checklist",
]


LAB_PATTERNS = {
    # CBC
    "WBC": r"^(wbc|white blood cell[s]?)\b",
    "HGB": r"^(hgb|hemoglobin|haemoglobin)\b",
    "HCT": r"^(hct|hematocrit|haematocrit)\b",
    "PLT": r"^(plt|platelet[s]?)\b",

    # BMP
    "NA": r"^(na|sodium)\b",
    "K": r"^(k|potassium)\b",
    "CL": r"^(cl|chloride)\b",
    "HCO3": r"^(hco3|bicarb|bicarbonate|co2)\b",
    "BUN": r"^(bun)\b",
    "CRET": r"^(cr|creat|creatinine)\b",
    "GLU": r"^(glu|glucose)\b",

    # Minerals
    "CA": r"^(ca|calcium)\b",
    "MG": r"^(mg|magnesium)\b",
    "PO4": r"^(po4|phos|phosphate|phosphorus)\b",

    # Coags
    "PT": r"^(pt)\b",
    "PTT": r"^(ptt|aptt)\b",
    "INR": r"^(inr)\b",

    # LFTs
    "AST": r"^(ast)\b",
    "ALT": r"^(alt)\b",
    "ALKPHOS": r"^(alk phos|alkaline phosphatase|alp)\b",
    "TBIL": r"^(t bili|t\. bili|total bili|total bilirubin|tbili|bilirubin)\b",
    "DBIL": r"^(d bili|d\. bili|direct bili|direct bilirubin|dbili)\b",
}


def parse_filename(path: Path):
    """
    m220_smith_john.txt -> M220, Smith, John
    """
    parts = path.stem.split("_")
    if len(parts) >= 3:
        room = parts[0].upper()
        last = parts[1].title()
        first = " ".join(p.title() for p in parts[2:])
        return room, f"{last}, {first}"
    return "", path.stem.replace("_", " ").title()


def parse_sections(text: str):
    sections = {name: "" for name in SECTION_NAMES}

    pattern = re.compile(
        r"(?im)^(" + "|".join(re.escape(s) for s in SECTION_NAMES) + r")\s*:\s*$"
    )

    matches = list(pattern.finditer(text))

    for i, match in enumerate(matches):
        section = match.group(1).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[section] = text[start:end].strip()

    return sections


def parse_labs(lab_text: str):
    fishbone = {}
    other_labs = []

    for raw_line in lab_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        matched = False

        for key, pattern in LAB_PATTERNS.items():
            m = re.match(pattern, line, flags=re.I)
            if m:
                value = line[m.end():].strip(" :;-–—")
                fishbone[key] = value
                matched = True
                break

        if not matched:
            other_labs.append(line)

    return fishbone, other_labs


def draw_wrapped_text(
    c,
    text,
    x,
    y_top,
    width,
    size=4.2,
    leading=4.7,
    max_lines=None,
    bold=False,
):
    if not text:
        return y_top

    c.setFont("Times-Bold" if bold else "Times-Roman", size)

    chars_per_line = max(5, int(width / (size * 0.43)))
    lines = []

    for paragraph in text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines.extend(wrap(paragraph, chars_per_line))

    if max_lines is not None:
        lines = lines[:max_lines]

    y = y_top
    for line in lines:
        c.drawString(x, y, line)
        y -= leading

    return y


def draw_value(c, value, x, y, size=5.2, max_chars=10):
    if not value:
        return
    c.setFont("Times-Bold", size)
    c.drawCentredString(x, y, str(value)[:max_chars])


def draw_value_left(c, value, x, y, size=5.0, max_chars=12):
    if not value:
        return
    c.setFont("Times-Bold", size)
    c.drawString(x, y, str(value)[:max_chars])


def draw_cbc_cell(c, x, y_top, w, h, labs):
    cx = x + w * 0.50
    cy = y_top - h * 0.52

    line_half = w * 0.12
    arm = w * 0.15
    rise = h * 0.22

    left_joint = cx - line_half
    right_joint = cx + line_half

    c.setLineWidth(0.45)

    c.line(left_joint, cy, right_joint, cy)

    c.line(left_joint, cy, left_joint - arm, cy + rise)
    c.line(left_joint, cy, left_joint - arm, cy - rise)

    c.line(right_joint, cy, right_joint + arm, cy + rise)
    c.line(right_joint, cy, right_joint + arm, cy - rise)

    draw_value(c, labs.get("WBC", ""), x + w * 0.20, cy - 2, size=5.0, max_chars=9)
    draw_value(c, labs.get("HGB", ""), cx, cy + h * 0.24, size=5.0, max_chars=9)
    draw_value(c, labs.get("HCT", ""), cx, cy - h * 0.26, size=5.0, max_chars=9)
    draw_value(c, labs.get("PLT", ""), x + w * 0.80, cy - 2, size=5.0, max_chars=9)


def draw_bmp_cell(c, x, y_top, w, h, labs):
    grid_w = w * 0.55
    cell_w = grid_w / 3
    cell_h = h * 0.21

    gx = x + w * 0.06
    gy = y_top - h * 0.28

    c.setLineWidth(0.45)

    c.line(gx + cell_w, gy, gx + cell_w, gy - 2 * cell_h)
    c.line(gx + 2 * cell_w, gy, gx + 2 * cell_w, gy - 2 * cell_h)
    c.line(gx, gy - cell_h, gx + grid_w, gy - cell_h)

    chev_x = gx + grid_w + w * 0.07
    chev_y = gy - cell_h
    arm = w * 0.08
    rise = h * 0.16

    c.line(chev_x, chev_y, chev_x + arm, chev_y + rise)
    c.line(chev_x, chev_y, chev_x + arm, chev_y - rise)

    draw_value(c, labs.get("NA", ""), gx + cell_w * 0.5, gy - cell_h * 0.72, size=5.0, max_chars=6)
    draw_value(c, labs.get("CL", ""), gx + cell_w * 1.5, gy - cell_h * 0.72, size=5.0, max_chars=6)
    draw_value(c, labs.get("BUN", ""), gx + cell_w * 2.5, gy - cell_h * 0.72, size=5.0, max_chars=6)

    draw_value(c, labs.get("K", ""), gx + cell_w * 0.5, gy - cell_h * 1.72, size=5.0, max_chars=6)
    draw_value(c, labs.get("HCO3", ""), gx + cell_w * 1.5, gy - cell_h * 1.72, size=5.0, max_chars=6)
    draw_value(c, labs.get("CRET", ""), gx + cell_w * 2.5, gy - cell_h * 1.72, size=5.0, max_chars=6)

    draw_value_left(
        c,
        labs.get("GLU", ""),
        chev_x + arm + 3,
        chev_y - 2,
        size=4.8,
        max_chars=12,
    )


def draw_lft_cell(c, x, y_top, w, h, labs):
    cx = x + w * 0.50
    cy = y_top - h * 0.52

    line_half = w * 0.12
    arm = w * 0.15
    rise = h * 0.22

    left_joint = cx - line_half
    right_joint = cx + line_half

    c.setLineWidth(0.45)

    c.line(left_joint, cy, right_joint, cy)

    c.line(left_joint, cy, left_joint - arm, cy + rise)
    c.line(left_joint, cy, left_joint - arm, cy - rise)

    c.line(right_joint, cy, right_joint + arm, cy + rise)
    c.line(right_joint, cy, right_joint + arm, cy - rise)

    draw_value(c, labs.get("AST", ""), x + w * 0.20, cy - 2, size=5.0, max_chars=8)
    draw_value(c, labs.get("ALT", ""), x + w * 0.80, cy - 2, size=5.0, max_chars=8)

    draw_value(c, labs.get("TBIL", ""), cx, cy + h * 0.25, size=5.0, max_chars=8)
    draw_value(c, labs.get("DBIL", ""), cx, cy + h * 0.08, size=5.0, max_chars=8)
    draw_value(c, labs.get("ALKPHOS", ""), cx, cy - h * 0.28, size=5.0, max_chars=8)


def draw_mineral_cell(c, x, y_top, w, h, labs):
    cx = x + w * 0.50

    stem_top = y_top - h * 0.20
    branch_y = y_top - h * 0.52

    branch_arm = w * 0.18
    branch_drop = h * 0.22

    c.setLineWidth(0.45)

    # Correct: vertical stem extends upward.
    c.line(cx, stem_top, cx, branch_y)
    c.line(cx, branch_y, cx - branch_arm, branch_y - branch_drop)
    c.line(cx, branch_y, cx + branch_arm, branch_y - branch_drop)

    draw_value(c, labs.get("CA", ""), x + w * 0.22, stem_top - 2, size=5.0, max_chars=7)
    draw_value(c, labs.get("MG", ""), x + w * 0.78, stem_top - 2, size=5.0, max_chars=7)
    draw_value(c, labs.get("PO4", ""), cx, branch_y - branch_drop - 8, size=5.0, max_chars=7)


def draw_coag_cell(c, x, y_top, w, h, labs):
    cx = x + w * 0.42
    cy = y_top - h * 0.50

    line_half = w * 0.16
    chev_x = cx + line_half + w * 0.08
    arm = w * 0.11
    rise = h * 0.18

    c.setLineWidth(0.45)

    c.line(cx - line_half, cy + 4, cx + line_half, cy + 4)

    c.line(chev_x, cy + 4, chev_x + arm, cy + 4 + rise)
    c.line(chev_x, cy + 4, chev_x + arm, cy + 4 - rise)

    draw_value(c, labs.get("PT", ""), cx, cy + h * 0.21, size=5.0, max_chars=7)
    draw_value(c, labs.get("PTT", ""), cx, cy - h * 0.22, size=5.0, max_chars=7)
    draw_value_left(c, labs.get("INR", ""), chev_x + arm + 2, cy + 1, size=5.0, max_chars=7)


def draw_other_cell(c, x, y_top, w, h, other_labs):
    draw_wrapped_text(
        c,
        "\n".join(other_labs),
        x + 2,
        y_top - 6,
        w - 4,
        size=4.2,
        leading=4.6,
        max_lines=8,
    )


def draw_header(c, y, col_x):
    headers = [
        "Room / Patient / Summary / Vitals / I&O / Tele",
        "CBC",
        "BMP",
        "LFT",
        "CaMgPhos",
        "Coags",
        "Other",
        "Imaging",
        "Checklist",
    ]

    c.setFont("Times-Bold", 5.6)
    for label, x in zip(headers, col_x):
        c.drawString(x, y, label)


def generate_pdf(input_dir: Path, output_pdf: Path):
    page_size = landscape(letter)
    page_w, page_h = page_size

    c = canvas.Canvas(str(output_pdf), pagesize=page_size)
    c.setTitle("Compact Rounding Sheet")

    margin = 0.12 * inch
    top = page_h - 0.22 * inch
    bottom = 0.12 * inch

    usable_w = page_w - 2 * margin

    # 11-inch landscape letter.
    # Sum widths intentionally kept inside printable page.
    col_w = [
        1.85 * inch,  # patient summary
        0.78 * inch,  # CBC
        1.10 * inch,  # BMP
        0.78 * inch,  # LFT
        0.72 * inch,  # Ca/Mg/Phos
        0.72 * inch,  # Coags
        1.00 * inch,  # Other labs
        1.28 * inch,  # Imaging
        usable_w - (
            1.85 * inch
            + 0.78 * inch
            + 1.10 * inch
            + 0.78 * inch
            + 0.72 * inch
            + 0.72 * inch
            + 1.00 * inch
            + 1.28 * inch
        ),  # Checklist
    ]

    col_x = [margin]
    for width in col_w[:-1]:
        col_x.append(col_x[-1] + width)

    # Approx 12 patients/page on landscape letter.
    row_h = 0.62 * inch

    patient_files = sorted(input_dir.glob("*.txt"))

    y = top
    draw_header(c, y, col_x)
    y -= 0.09 * inch

    for path in patient_files:
        if y - row_h < bottom:
            c.showPage()
            y = top
            draw_header(c, y, col_x)
            y -= 0.09 * inch

        room, patient_name = parse_filename(path)
        sections = parse_sections(path.read_text(encoding="utf-8"))
        labs, other_labs = parse_labs(sections["labs"])

        # Row boundaries.
        c.setLineWidth(0.25)
        c.line(margin, y + 2, page_w - margin, y + 2)
        c.line(margin, y - row_h, page_w - margin, y - row_h)

        # Vertical boundaries.
        for x_pos in col_x:
            c.line(x_pos, y + 2, x_pos, y - row_h)
        c.line(page_w - margin, y + 2, page_w - margin, y - row_h)

        # Patient summary.
        clinical_text = (
            f"{room}  {patient_name}\n"
            f"{sections['oneliner']}\n"
            f"V: {sections['vitals']}\n"
            f"I/O: {sections['intake_output']}  T: {sections['telemetry']}"
        )

        draw_wrapped_text(
            c,
            clinical_text,
            col_x[0] + 2,
            y - 5,
            col_w[0] - 4,
            size=4.3,
            leading=4.7,
            max_lines=8,
            bold=False,
        )

        # One fishbone per column.
        draw_cbc_cell(c, col_x[1], y, col_w[1], row_h, labs)
        draw_bmp_cell(c, col_x[2], y, col_w[2], row_h, labs)
        draw_lft_cell(c, col_x[3], y, col_w[3], row_h, labs)
        draw_mineral_cell(c, col_x[4], y, col_w[4], row_h, labs)
        draw_coag_cell(c, col_x[5], y, col_w[5], row_h, labs)
        draw_other_cell(c, col_x[6], y, col_w[6], row_h, other_labs)

        draw_wrapped_text(
            c,
            sections["imaging"],
            col_x[7] + 2,
            y - 5,
            col_w[7] - 4,
            size=4.2,
            leading=4.6,
            max_lines=8,
        )

        draw_wrapped_text(
            c,
            sections["checklist"],
            col_x[8] + 2,
            y - 5,
            col_w[8] - 4,
            size=4.2,
            leading=4.6,
            max_lines=8,
        )

        y -= row_h

    c.save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="patients")
    parser.add_argument("--output", default="rounding_sheet.pdf")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_pdf = Path(args.output)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    generate_pdf(input_dir, output_pdf)


if __name__ == "__main__":
    main()