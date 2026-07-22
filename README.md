# Rounding Sheet

Generate a compact PDF rounding sheet from Epic-exported inpatient progress notes saved as plain-text files.

The current script is [roundingsheet/make_rounding_sheet.py](roundingsheet/make_rounding_sheet.py). It reads room number, patient name, vitals, I/O, labs, imaging, and the one-liner directly from note text rather than from file names. The original prototype remains in `old_roundingsheet/`.

## Install

From Anaconda Prompt or a terminal:

```powershell
cd C:\GitHub\roundingsheet
conda create -n roundingsheet python=3.12 -y
conda activate roundingsheet
pip install -r requirements.txt
```

If the conda environment already exists:

```powershell
cd C:\GitHub\roundingsheet
conda activate roundingsheet
pip install -r requirements.txt
```

## Run

Activate the environment, then pass the folder containing progress-note `.txt` files:

```powershell
cd C:\GitHub\roundingsheet
conda activate roundingsheet
python .\roundingsheet\make_rounding_sheet.py C:\GitHub\roundingsheet\sample_notes
```

By default, the PDF is written into the same folder as the input notes:

```text
C:\GitHub\roundingsheet\sample_notes\rounding_sheet.pdf
```

## Layout Options

Choose 6 to 10 patients per page:

```powershell
python .\roundingsheet\make_rounding_sheet.py C:\GitHub\roundingsheet\sample_notes --patients-per-page 6
python .\roundingsheet\make_rounding_sheet.py C:\GitHub\roundingsheet\sample_notes --patients-per-page 10
```

Choose a font preset:

```powershell
python .\roundingsheet\make_rounding_sheet.py C:\GitHub\roundingsheet\sample_notes --font-size small
python .\roundingsheet\make_rounding_sheet.py C:\GitHub\roundingsheet\sample_notes --font-size large
```

Available font sizes are `extra-small`, `small`, `medium`, and `large`. The default is `medium`.

Remove the Imaging column and widen the blank Notes column:

```powershell
python .\roundingsheet\make_rounding_sheet.py C:\GitHub\roundingsheet\sample_notes --no-imaging
```

Options can be combined:

```powershell
python .\roundingsheet\make_rounding_sheet.py C:\GitHub\roundingsheet\sample_notes --patients-per-page 6 --font-size large --no-imaging
```

## Expected Note Format

Save one full progress note per patient as a `.txt` file. The script expects these text anchors:

- `Patient Name:` near the top of the note.
- `Today's Date:` near the top of the note. Lab results from this date are preferred.
- `Location:` or `Locations:` near the top of the note.
- `Vital Signs`, followed by `Ranges:` with min/max rows.
- `Intake/Output Summary`, followed by `Intake`, `Output`, and `Net` rows.
- `New Labs and imaging- reviewed by me`, followed by Epic result tables with `Collection Time:` and `Result Value`.
- `Imaging` for imaging text, unless using `--no-imaging`.
- `Assessment/Plan:` or `Assessment`, followed immediately by the one-line patient summary.

The script keeps the most recent value for each lab from the note date when same-day labs are present. If no lab rows match the note date, it falls back to the most recent lab collection date in the note. Abnormal flags such as `(H)` and `(L)` are compacted to values like `10.2L` or `18H`.

## Sample Notes

The top-level notes in [sample_notes](sample_notes) are entirely synthetic and intended for testing, demonstrations, and publication figures.
