from dataclasses import dataclass, field
from pathlib import Path
from textwrap import wrap

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


FONT_SCALES = {
    "extra-small": 0.85,
    "small": 0.95,
    "medium": 1.0,
    "large": 1.15,
}


@dataclass
class PatientRecord:
    room: str = ""
    patient_name: str = ""
    oneliner: str = ""
    vitals_summary: str = ""
    io_summary: str = ""
    labs: dict = field(default_factory=dict)
    imaging_summary: str = ""
    notes: str = ""


def coerce_patient_record(record) -> PatientRecord:
    if isinstance(record, PatientRecord):
        return record

    labs = dict(record.get("labs", {}))
    for section in ("cbc", "bmp", "lft", "ca_mg_phos", "coags"):
        value = record.get(section)
        if isinstance(value, dict):
            labs.update(value)

    return PatientRecord(
        room=record.get("room", ""),
        patient_name=record.get("patient_name", ""),
        oneliner=record.get("oneliner", ""),
        vitals_summary=record.get("vitals_summary", record.get("vitals", "")),
        io_summary=record.get("io_summary", ""),
        labs=labs,
        imaging_summary=record.get("imaging_summary", record.get("imaging", "")),
        notes=record.get("notes", ""),
    )


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


def draw_room_text(c, text, x, y_top, width, font_scale=1.0):
    if not text:
        return

    size = 6.8 * font_scale
    min_size = 5.0 * font_scale
    while size > min_size and c.stringWidth(text, "Times-Bold", size) > width:
        size -= 0.2
    size = max(size, min_size)

    c.setFont("Times-Bold", size)
    c.drawString(x, y_top, text)


def draw_cbc_cell(c, x, y_top, w, h, labs, font_scale=1.0):
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

    lab_size = 5.0 * font_scale
    draw_value(c, labs.get("WBC", ""), x + w * 0.20, cy - 2, size=lab_size, max_chars=9)
    draw_value(c, labs.get("HGB", ""), cx, cy + h * 0.24, size=lab_size, max_chars=9)
    draw_value(c, labs.get("HCT", ""), cx, cy - h * 0.26, size=lab_size, max_chars=9)
    draw_value(c, labs.get("PLT", ""), x + w * 0.80, cy - 2, size=lab_size, max_chars=9)


def draw_bmp_cell(c, x, y_top, w, h, labs, font_scale=1.0):
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

    lab_size = 5.0 * font_scale
    draw_value(c, labs.get("NA", ""), gx + cell_w * 0.5, gy - cell_h * 0.72, size=lab_size, max_chars=8)
    draw_value(c, labs.get("CL", ""), gx + cell_w * 1.5, gy - cell_h * 0.72, size=lab_size, max_chars=8)
    draw_value(c, labs.get("BUN", ""), gx + cell_w * 2.5, gy - cell_h * 0.72, size=lab_size, max_chars=8)

    draw_value(c, labs.get("K", ""), gx + cell_w * 0.5, gy - cell_h * 1.72, size=lab_size, max_chars=8)
    draw_value(c, labs.get("HCO3", ""), gx + cell_w * 1.5, gy - cell_h * 1.72, size=lab_size, max_chars=8)
    draw_value(c, labs.get("CRET", ""), gx + cell_w * 2.5, gy - cell_h * 1.72, size=lab_size, max_chars=8)

    draw_value_left(c, labs.get("GLU", ""), chev_x + arm + 3, chev_y - 2, size=4.8 * font_scale, max_chars=12)


def draw_lft_cell(c, x, y_top, w, h, labs, font_scale=1.0):
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

    lab_size = 5.0 * font_scale
    draw_value(c, labs.get("AST", ""), x + w * 0.20, cy - 2, size=lab_size, max_chars=8)
    draw_value(c, labs.get("ALT", ""), x + w * 0.80, cy - 2, size=lab_size, max_chars=8)

    draw_value(c, labs.get("TBIL", ""), cx, cy + h * 0.25, size=lab_size, max_chars=8)
    draw_value(c, labs.get("DBIL", ""), cx, cy + h * 0.08, size=lab_size, max_chars=8)
    draw_value(c, labs.get("ALKPHOS", ""), cx, cy - h * 0.28, size=lab_size, max_chars=8)


def draw_mineral_cell(c, x, y_top, w, h, labs, font_scale=1.0):
    cx = x + w * 0.50

    stem_top = y_top - h * 0.20
    branch_y = y_top - h * 0.52

    branch_arm = w * 0.18
    branch_drop = h * 0.22

    c.setLineWidth(0.45)

    c.line(cx, stem_top, cx, branch_y)
    c.line(cx, branch_y, cx - branch_arm, branch_y - branch_drop)
    c.line(cx, branch_y, cx + branch_arm, branch_y - branch_drop)

    lab_size = 5.0 * font_scale
    draw_value(c, labs.get("CA", ""), x + w * 0.22, stem_top - 2, size=lab_size, max_chars=8)
    draw_value(c, labs.get("MG", ""), x + w * 0.78, stem_top - 2, size=lab_size, max_chars=8)
    draw_value(c, labs.get("PO4", ""), cx, branch_y - branch_drop - 8, size=lab_size, max_chars=8)


def draw_coag_cell(c, x, y_top, w, h, labs, font_scale=1.0):
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

    lab_size = 5.0 * font_scale
    draw_value(c, labs.get("PT", ""), cx, cy + h * 0.21, size=lab_size, max_chars=7)
    draw_value(c, labs.get("PTT", ""), cx, cy - h * 0.22, size=lab_size, max_chars=7)
    draw_value_left(c, labs.get("INR", ""), chev_x + arm + 2, cy + 1, size=lab_size, max_chars=7)


def draw_header(c, y, col_x, include_imaging=True, font_scale=1.0):
    headers = [
        "Room",
        "Patient / One-liner",
        "Vitals / I&O",
        "CBC",
        "BMP",
        "LFT",
        "CaMgPhos",
        "Coags",
    ]
    headers.extend(["Imaging", "Notes"] if include_imaging else ["Notes"])

    c.setFont("Times-Bold", 7.2 * font_scale)
    for label, x in zip(headers, col_x):
        c.drawString(x, y, label)


def render_rounding_sheet(patient_records, output_pdf: Path, patients_per_page=8, include_imaging=True, font_scale=1.0):
    patients = [coerce_patient_record(record) for record in patient_records]
    page_size = landscape(letter)
    page_w, page_h = page_size

    c = canvas.Canvas(str(output_pdf), pagesize=page_size)
    c.setTitle("Rounding Sheet")

    margin = 0.12 * inch
    top = page_h - 0.22 * inch
    bottom = 0.12 * inch

    usable_w = page_w - 2 * margin
    fixed_w = [
        0.55 * inch,
        1.45 * inch,
        1.28 * inch,
        0.78 * inch,
        1.10 * inch,
        0.78 * inch,
        0.72 * inch,
        0.72 * inch,
    ]
    if include_imaging:
        fixed_w.append(1.52 * inch)

    col_w = fixed_w + [usable_w - sum(fixed_w)]

    col_x = [margin]
    for width in col_w[:-1]:
        col_x.append(col_x[-1] + width)

    header_gap = 0.09 * inch
    row_h = (top - header_gap - bottom) / patients_per_page
    fishbone_h = 0.62 * inch
    cell_top_padding = 7
    patient_leading = 6.6 * font_scale
    detail_leading = 6.4 * font_scale
    patient_max_lines = max(1, int((row_h - cell_top_padding - 2) / patient_leading))
    detail_max_lines = max(1, int((row_h - cell_top_padding - 2) / detail_leading))

    y = top
    draw_header(c, y, col_x, include_imaging=include_imaging, font_scale=font_scale)
    y -= header_gap

    for patient in patients:
        if y - row_h < bottom:
            c.showPage()
            y = top
            draw_header(c, y, col_x, include_imaging=include_imaging, font_scale=font_scale)
            y -= header_gap

        labs = patient.labs

        c.setLineWidth(0.25)
        c.line(margin, y + 2, page_w - margin, y + 2)
        c.line(margin, y - row_h, page_w - margin, y - row_h)

        for x_pos in col_x:
            c.line(x_pos, y + 2, x_pos, y - row_h)
        c.line(page_w - margin, y + 2, page_w - margin, y - row_h)

        draw_room_text(c, patient.room, col_x[0] + 2, y - cell_top_padding, col_w[0] - 4, font_scale=font_scale)

        patient_text = f"{patient.patient_name}\n{patient.oneliner}".strip()
        draw_wrapped_text(
            c,
            patient_text,
            col_x[1] + 2,
            y - cell_top_padding,
            col_w[1] - 4,
            size=6.0 * font_scale,
            leading=patient_leading,
            max_lines=patient_max_lines,
        )

        vitals_text = f"{patient.vitals_summary}\n{patient.io_summary}".strip()
        draw_wrapped_text(
            c,
            vitals_text,
            col_x[2] + 2,
            y - cell_top_padding,
            col_w[2] - 4,
            size=5.8 * font_scale,
            leading=detail_leading,
            max_lines=detail_max_lines,
        )

        fishbone_y = y - (row_h - fishbone_h) / 2
        draw_cbc_cell(c, col_x[3], fishbone_y, col_w[3], fishbone_h, labs, font_scale=font_scale)
        draw_bmp_cell(c, col_x[4], fishbone_y, col_w[4], fishbone_h, labs, font_scale=font_scale)
        draw_lft_cell(c, col_x[5], fishbone_y, col_w[5], fishbone_h, labs, font_scale=font_scale)
        draw_mineral_cell(c, col_x[6], fishbone_y, col_w[6], fishbone_h, labs, font_scale=font_scale)
        draw_coag_cell(c, col_x[7], fishbone_y, col_w[7], fishbone_h, labs, font_scale=font_scale)

        if include_imaging:
            draw_wrapped_text(
                c,
                patient.imaging_summary,
                col_x[8] + 2,
                y - cell_top_padding,
                col_w[8] - 4,
                size=5.8 * font_scale,
                leading=detail_leading,
                max_lines=detail_max_lines,
            )

        y -= row_h

    c.save()
