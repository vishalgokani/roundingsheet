# Rounding Sheet

Generate a compact PDF rounding sheet from Epic-exported inpatient progress notes saved as plain-text files.

This repository keeps the original prototype in `old_roundingsheet/` unchanged. The current script is in `roundingsheet/make_rounding_sheet.py` and reads room number, patient name, vitals, I/O, labs, imaging, and the one-liner directly from the note text rather than from file names.

## Install

From Anaconda Prompt or a terminal:

```powershell
cd C:\GitHub\roundingsheet
conda create -n roundingsheet python=3.12 -y
conda activate roundingsheet
pip install -r requirements.txt
```

If the `roundingsheet` environment already exists but dependencies have not been installed yet:

```powershell
cd C:\GitHub\roundingsheet
conda activate roundingsheet
pip install -r requirements.txt
```

## Run

For future runs, activate the same conda environment first. Pass the directory containing the day's exported note `.txt` files as the positional argument. The file names do not matter.

```powershell
cd C:\GitHub\roundingsheet
conda activate roundingsheet
python .\roundingsheet\make_rounding_sheet.py C:\GitHub\roundingsheet\sample_notes
```

By default, the output PDF is written into the same directory as the input notes. For example, the command above writes:

```text
C:\GitHub\roundingsheet\sample_notes\rounding_sheet.pdf
```

The input directory can be anywhere on the computer. This writes `C:\todaysnotes\rounding_sheet.pdf` automatically:

```powershell
cd C:\GitHub\roundingsheet
conda activate roundingsheet
python .\roundingsheet\make_rounding_sheet.py C:\todaysnotes
```

You can still override the output path if needed:

```powershell
python .\roundingsheet\make_rounding_sheet.py C:\todaysnotes --output C:\somewhere_else\rounding_sheet.pdf
```

## Expected Note Format

Save one full progress note per patient as a `.txt` file. The script expects the Epic export to include these text anchors:

- `Patient Name:` near the top of the note.
- `Today's Date:` near the top of the note. Lab results from this date are preferred.
- `Location:` or `Locations:` near the top of the note.
- `Vital Signs`, followed by `Ranges:` with systolic, diastolic, temperature, pulse, respiratory rate, and SpO2 min/max rows.
- `Intake/Output Summary`, followed by `Intake`, `Output`, and `Net` rows.
- `New Labs and imaging- reviewed by me`, followed by Epic result tables with `Collection Time:` and `Result Value` rows.
- `Imaging` for imaging text.
- `Assessment/Plan:` or `Assessment`, followed immediately by the one-line patient summary.

The script keeps the most recent value for each lab from the note date when same-day labs are present. If no lab rows match the note date, it falls back to the most recent lab collection date in the note so overnight notes do not produce blank fishbones. Abnormal flags such as `(H)` and `(L)` are compacted to values like `10.2L` or `18H`.

## Output Columns

The PDF columns are:

1. Room
2. Patient / one-liner
3. Vitals / I&O
4. CBC
5. BMP
6. LFT
7. CaMgPhos
8. Coags
9. Imaging
10. Notes

The Notes column is intentionally blank for handwritten or typed rounding notes.

The current PDF layout targets about 8 patients per landscape letter page for legibility.

## Development Notes

The project is intentionally small for clinical workflow testing and eventual scholarly publication. Future publication-oriented additions may include package metadata, de-identified test fixtures, parser unit tests, example output images, and a JOSS paper draft.
