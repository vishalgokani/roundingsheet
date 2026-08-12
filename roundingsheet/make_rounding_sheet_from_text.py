import argparse
import re
from datetime import datetime
from pathlib import Path

try:
    from .pdf_renderer import FONT_SCALES, render_rounding_sheet
except ImportError:
    from pdf_renderer import FONT_SCALES, render_rounding_sheet


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
    value = normalize_spaces(value).replace("Ã‚", "")
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
    today = parse_today_date(text)
    oneliner = parse_oneliner(text)
    return {
        "room": parse_room(text),
        "patient_name": parse_patient_name(text),
        "oneliner": oneliner,
        "vitals_summary": parse_vitals(text),
        "io_summary": parse_intake_output(text),
        "labs": parse_labs(text, today=today),
        "notes": oneliner,
    }


def room_sort_key(record: dict):
    room = normalize_spaces(record.get("room", "")).lower()
    return room, record.get("patient_name", "").lower()


def parse_notes_from_directory(input_dir: Path):
    patient_records = [parse_note(path) for path in input_dir.glob("*.txt")]
    return sorted(patient_records, key=room_sort_key)


def generate_pdf(input_dir: Path, output_pdf: Path, patients_per_page=8, font_scale=1.0):
    patient_records = parse_notes_from_directory(input_dir)
    render_rounding_sheet(
        patient_records,
        output_pdf,
        patients_per_page=patients_per_page,
        font_scale=font_scale,
    )


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
        font_scale=FONT_SCALES[args.font_size],
    )
    print(f"Wrote {output_pdf}")


if __name__ == "__main__":
    main()
