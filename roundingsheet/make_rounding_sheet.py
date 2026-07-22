import argparse
import re
from datetime import datetime
from pathlib import Path
from textwrap import wrap

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


LAB_NAME_MAP = {
    "wbc": "WBC",
    "hgb": "HGB",
    "hemoglobin": "HGB",
    "hct": "HCT",
    "hematocrit": "HCT",
    "platelet count": "PLT",
    "platelets": "PLT",
    "plt": "PLT",
    "sodium": "NA",
    "na": "NA",
    "potassium": "K",
    "k": "K",
    "chloride": "CL",
    "cl": "CL",
    "co2": "HCO3",
    "bicarb": "HCO3",
    "bicarbonate": "HCO3",
    "bun": "BUN",
    "creatinine": "CRET",
    "creat": "CRET",
    "cr": "CRET",
    "glucose": "GLU",
    "calcium": "CA",
    "magnesium": "MG",
    "phosphorus": "PO4",
    "phosphorus inorganic": "PO4",
    "phos": "PO4",
    "pt": "PT",
    "protime": "PT",
    "inr": "INR",
    "ptt": "PTT",
    "aptt": "PTT",
    "partial thromboplastin time": "PTT",
    "ast": "AST",
    "ast sgot": "AST",
    "alt": "ALT",
    "alt sgpt": "ALT",
    "alk phos": "ALKPHOS",
    "alkaline phosphatase": "ALKPHOS",
    "alp": "ALKPHOS",
    "bilirubin total": "TBIL",
    "total bilirubin": "TBIL",
    "bilirubin direct": "DBIL",
    "direct bilirubin": "DBIL",
}


FONT_SCALES = {
    "extra-small": 0.85,
    "small": 0.95,
    "medium": 1.0,
    "large": 1.15,
}


def read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def normalize_spaces(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def parse_patient_name(text: str) -> str:
    match = re.search(r"(?im)^\s*Patient Name:\s*(.+?)(?:\t| {2,}|$)", text)
    return normalize_spaces(match.group(1)) if match else ""


def parse_room(text: str) -> str:
    match = re.search(r"(?im)\bLocations?:\s*(.+?)(?:\t| {2,}|$)", text)
    return normalize_spaces(match.group(1)) if match else ""


def parse_today_date(text: str):
    match = re.search(r"(?im)\bToday's Date:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})", text)
    if not match:
        return None

    value = match.group(1)
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def parse_oneliner(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"(?i)^\s*Assessment(?:/Plan)?\s*:?\s*$", line):
            for candidate in lines[index + 1 :]:
                candidate = candidate.strip()
                if candidate:
                    return normalize_spaces(candidate)
    return ""


def extract_min_max(line: str):
    min_match = re.search(r"\bMin:\s*([^\s,]+)", line, flags=re.I)
    max_match = re.search(r"\bMax:\s*([^\s,]+)", line, flags=re.I)
    if not min_match or not max_match:
        return "", ""
    return min_match.group(1), max_match.group(1)


def parse_vitals(text: str) -> str:
    lines = text.splitlines()
    systolic = diastolic = temp = pulse = resp = spo2 = None

    for line in lines:
        stripped = line.strip()
        if re.match(r"(?i)^Systolic\b", stripped):
            systolic = extract_min_max(stripped)
        elif re.match(r"(?i)^Diastolic\b", stripped):
            diastolic = extract_min_max(stripped)
        elif re.match(r"(?i)^Temp\b", stripped):
            temp = extract_min_max(stripped)
        elif re.match(r"(?i)^Pulse\b", stripped):
            pulse = extract_min_max(stripped)
        elif re.match(r"(?i)^Resp\b", stripped):
            resp = extract_min_max(stripped)
        elif re.match(r"(?i)^SpO2\b", stripped):
            spo2 = extract_min_max(stripped)

    pieces = []
    if systolic and diastolic:
        pieces.append(f"BP {systolic[0]}-{systolic[1]}/{diastolic[0]}-{diastolic[1]}")
    if temp:
        pieces.append(f"T {temp[0]}-{temp[1]}F")
    if pulse:
        pieces.append(f"HR {pulse[0]}-{pulse[1]}")
    if resp:
        pieces.append(f"RR {resp[0]}-{resp[1]}")
    if spo2:
        pieces.append(f"SPO2 {spo2[0]}-{spo2[1]}%")

    return "  ".join(pieces)


def parse_intake_output(text: str) -> str:
    intake = output = net = ""
    in_io_block = False

    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"(?i)^Intake/Output Summary\b", stripped):
            in_io_block = True
            continue
        if not in_io_block:
            continue
        if not stripped and (intake or output or net):
            break

        match = re.match(r"(?i)^(Intake|Output|Net)\s+(.+)$", stripped)
        if not match:
            continue
        label = match.group(1).lower()
        value = normalize_spaces(match.group(2))
        if label == "intake":
            intake = value
        elif label == "output":
            output = value
        elif label == "net":
            net = value

    parts = []
    if intake or output:
        parts.append(f"I/O {intake or '?'} / {output or '?'}")
    if net:
        parts.append(f"net {net}")
    return " ".join(parts)


def parse_imaging(text: str) -> str:
    match = re.search(
        r"(?ims)^\s*Imaging:?\s*$\n(?P<body>.*?)(?=^\s*Assessment(?:/Plan)?\s*:?\s*$|\Z)",
        text,
    )
    if not match:
        return ""
    lines = [normalize_spaces(line) for line in match.group("body").splitlines()]
    return "\n".join(line for line in lines if line)


def parse_collection_time(value: str):
    value = normalize_spaces(value)
    for fmt in ("%m/%d/%y %I:%M %p", "%m/%d/%Y %I:%M %p"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def normalize_lab_name(name: str) -> str:
    name = re.sub(r"\([^)]*\)", "", name)
    name = name.replace(",", " ")
    return normalize_spaces(name).lower()


def lab_key(name: str):
    normalized = normalize_lab_name(name)
    return LAB_NAME_MAP.get(normalized)


def result_header(lines, collection_time_index: int) -> str:
    for index in range(collection_time_index - 1, -1, -1):
        candidate = lines[index].strip()
        if candidate:
            return candidate.upper()
    return ""


def allowed_lab_keys(header: str):
    if "CBC" in header:
        return {"WBC", "HGB", "HCT", "PLT"}
    if "METABOLIC PANEL" in header or "HEPATIC" in header:
        return {"NA", "K", "CL", "HCO3", "GLU", "BUN", "CRET", "CA", "AST", "ALT", "ALKPHOS", "TBIL", "DBIL"}
    if "MAGNESIUM" in header:
        return {"MG"}
    if "PHOSPHORUS" in header or "PHOS" in header:
        return {"PO4"}
    if "PROTHROMBIN" in header or "PT" == header or "INR" in header:
        return {"PT", "INR"}
    if "PARTIAL THROMBOPLASTIN" in header or "PTT" in header or "APTT" in header:
        return {"PTT"}
    if "POTASSIUM" in header:
        return {"K"}
    return set()


def clean_lab_value(value: str) -> str:
    value = normalize_spaces(value).replace("Â", "")
    return re.sub(r"\s+\(([HL])\)$", r"\1", value)


def iter_lab_blocks(text: str):
    lines = text.splitlines()

    for index, line in enumerate(lines):
        time_match = re.search(r"(?i)Collection Time:\s*(.+)$", line)
        if not time_match:
            continue

        collected_at = parse_collection_time(time_match.group(1))
        allowed_keys = allowed_lab_keys(result_header(lines, index))
        if not collected_at or not allowed_keys:
            continue

        result_index = None

        for lookahead in range(index + 1, len(lines)):
            if re.search(r"(?i)Collection Time:\s*", lines[lookahead]):
                break
            if re.match(r"(?i)^\s*Result\s+Value\s*$", lines[lookahead]):
                result_index = lookahead
                break

        if result_index is None:
            continue

        next_time_index = len(lines)
        for lookahead in range(result_index + 1, len(lines)):
            if re.search(r"(?i)Collection Time:\s*", lines[lookahead]):
                next_time_index = lookahead
                break

        for row_index in range(result_index + 1, next_time_index):
            row = lines[row_index]
            if not row.strip():
                continue
            if re.match(r"(?i)^\s*Narrative\s*$", row):
                break

            columns = [part.strip() for part in re.split(r"\t+| {2,}", row.strip()) if part.strip()]
            if len(columns) < 2:
                continue

            key = lab_key(columns[0])
            if not key or key not in allowed_keys:
                continue

            yield collected_at, key, clean_lab_value(columns[1])


def parse_labs(text: str, today=None) -> dict:
    lab_rows = list(iter_lab_blocks(text))
    if not lab_rows:
        return {}

    available_dates = {collected_at.date() for collected_at, _, _ in lab_rows}
    selected_date = today if today in available_dates else max(available_dates)

    latest = {}
    for collected_at, key, value in lab_rows:
        if collected_at.date() != selected_date:
            continue

        previous = latest.get(key)
        previous_time = previous[0] if previous else None
        if previous is None or collected_at >= previous_time:
            latest[key] = (collected_at, value)

    return {key: value for key, (_, value) in latest.items()}


def parse_note(path: Path):
    text = read_note(path)
    vitals = parse_vitals(text)
    intake_output = parse_intake_output(text)
    today = parse_today_date(text)
    return {
        "room": parse_room(text),
        "patient_name": parse_patient_name(text),
        "oneliner": parse_oneliner(text),
        "vitals": f"{vitals}\n{intake_output}".strip(),
        "labs": parse_labs(text, today=today),
        "imaging": parse_imaging(text),
    }


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


def generate_pdf(input_dir: Path, output_pdf: Path, patients_per_page=8, include_imaging=True, font_scale=1.0):
    page_size = landscape(letter)
    page_w, page_h = page_size

    c = canvas.Canvas(str(output_pdf), pagesize=page_size)
    c.setTitle("Rounding Sheet")

    margin = 0.12 * inch
    top = page_h - 0.22 * inch
    bottom = 0.12 * inch

    usable_w = page_w - 2 * margin
    fixed_w = [
        0.55 * inch,  # Room
        1.45 * inch,  # Patient / one-liner
        1.28 * inch,  # Vitals / I&O
        0.78 * inch,  # CBC
        1.10 * inch,  # BMP
        0.78 * inch,  # LFT
        0.72 * inch,  # Ca/Mg/Phos
        0.72 * inch,  # Coags
    ]
    if include_imaging:
        fixed_w.append(1.52 * inch)  # Imaging

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
    patient_files = sorted(input_dir.glob("*.txt"))

    y = top
    draw_header(c, y, col_x, include_imaging=include_imaging, font_scale=font_scale)
    y -= header_gap

    for path in patient_files:
        if y - row_h < bottom:
            c.showPage()
            y = top
            draw_header(c, y, col_x, include_imaging=include_imaging, font_scale=font_scale)
            y -= header_gap

        note = parse_note(path)
        labs = note["labs"]

        c.setLineWidth(0.25)
        c.line(margin, y + 2, page_w - margin, y + 2)
        c.line(margin, y - row_h, page_w - margin, y - row_h)

        for x_pos in col_x:
            c.line(x_pos, y + 2, x_pos, y - row_h)
        c.line(page_w - margin, y + 2, page_w - margin, y - row_h)

        draw_room_text(c, note["room"], col_x[0] + 2, y - cell_top_padding, col_w[0] - 4, font_scale=font_scale)

        patient_text = f"{note['patient_name']}\n{note['oneliner']}".strip()
        draw_wrapped_text(c, patient_text, col_x[1] + 2, y - cell_top_padding, col_w[1] - 4, size=6.0 * font_scale, leading=patient_leading, max_lines=patient_max_lines)

        draw_wrapped_text(c, note["vitals"], col_x[2] + 2, y - cell_top_padding, col_w[2] - 4, size=5.8 * font_scale, leading=detail_leading, max_lines=detail_max_lines)

        fishbone_y = y - (row_h - fishbone_h) / 2
        draw_cbc_cell(c, col_x[3], fishbone_y, col_w[3], fishbone_h, labs, font_scale=font_scale)
        draw_bmp_cell(c, col_x[4], fishbone_y, col_w[4], fishbone_h, labs, font_scale=font_scale)
        draw_lft_cell(c, col_x[5], fishbone_y, col_w[5], fishbone_h, labs, font_scale=font_scale)
        draw_mineral_cell(c, col_x[6], fishbone_y, col_w[6], fishbone_h, labs, font_scale=font_scale)
        draw_coag_cell(c, col_x[7], fishbone_y, col_w[7], fishbone_h, labs, font_scale=font_scale)

        if include_imaging:
            draw_wrapped_text(c, note["imaging"], col_x[8] + 2, y - cell_top_padding, col_w[8] - 4, size=5.8 * font_scale, leading=detail_leading, max_lines=detail_max_lines)

        y -= row_h

    c.save()


def patients_per_page_arg(value: str) -> int:
    try:
        patients_per_page = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("patients per page must be an integer from 6 to 10") from exc

    if not 6 <= patients_per_page <= 10:
        raise argparse.ArgumentTypeError("patients per page must be an integer from 6 to 10")
    return patients_per_page


def font_size_arg(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in FONT_SCALES:
        choices = ", ".join(FONT_SCALES)
        raise argparse.ArgumentTypeError(f"font size must be one of: {choices}")
    return normalized


def main():
    parser = argparse.ArgumentParser(description="Generate a compact PDF rounding sheet from Epic-exported progress note text files.")
    parser.add_argument("input_dir", type=Path, help="Directory containing one .txt progress note per patient.")
    parser.add_argument(
        "--patients-per-page",
        type=patients_per_page_arg,
        default=8,
        help="Number of patient rows per page, from 6 to 10. Default: 8.",
    )
    parser.add_argument(
        "--no-imaging",
        action="store_true",
        help="Remove the Imaging column and expand the blank Notes column into that space.",
    )
    parser.add_argument(
        "--font-size",
        type=font_size_arg,
        default="medium",
        choices=list(FONT_SCALES),
        help="PDF font size preset. Choices: extra-small, small, medium, large. Default: medium.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output PDF path. Defaults to rounding_sheet.pdf inside the input note directory.",
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {args.input_dir}")
    if not args.input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {args.input_dir}")

    output_pdf = args.output if args.output else args.input_dir / "rounding_sheet.pdf"
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    generate_pdf(
        args.input_dir,
        output_pdf,
        patients_per_page=args.patients_per_page,
        include_imaging=not args.no_imaging,
        font_scale=FONT_SCALES[args.font_size],
    )
    print(f"Wrote {output_pdf}")


if __name__ == "__main__":
    main()
