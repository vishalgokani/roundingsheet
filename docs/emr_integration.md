# EMR Integration Design

This document describes how hospital IT could connect the rounding sheet renderer to Epic, Cerner, or another EMR without requiring clinicians to manually copy progress notes.

## Goal

The desired clinical workflow is a one-click print option inside the EMR:

1. The clinician selects a patient list or census.
2. The clinician clicks an option such as `Fishbone Rounding Sheet`.
3. The EMR or an internal hospital service presents layout options:
   - patients per page, 6 to 10
   - font size: extra-small, small, medium, or large
4. A hospital-owned service retrieves the approved structured data.
5. The service maps those data to the normalized patient-record structure.
6. The renderer creates a PDF.
7. The PDF opens in EMR print preview, downloads, or routes to the hospital's standard print workflow.

## What This Repository Provides

The repository provides:

- a working text-note implementation for testing and publication examples
- a shared PDF renderer in `roundingsheet/pdf_renderer.py`
- a normalized patient-record shape that future EMR adapters can pass to the renderer

The repository does not provide:

- Epic or Cerner credentials
- screen scraping or login automation
- direct access to a hospital EMR
- assumptions about a hospital's database tables, APIs, or reporting exports

## Possible Hospital Integration Patterns

Hospital IT should choose the integration pattern that fits the local EMR build, security model, and governance process. Plausible patterns include:

- an Epic or Cerner custom print/report workflow that launches the renderer through an internal service
- an embedded internal web app launched from the EMR with patient-list context
- a SMART on FHIR app if the local FHIR resources provide adequate census, encounter, vitals, lab, and patient-list context
- an Epic SlicerDicer, Reporting Workbench, Clarity, Caboodle, or other locally approved export/reporting workflow
- a hospital backend service that queries an approved reporting database or clinical data warehouse
- another local interface already approved for clinical reporting and printing

The best path depends on what the institution already supports. The renderer is intentionally separated from data retrieval so hospital IT can connect the approved source without rewriting the PDF layout.

## Normalized Patient Record

The renderer accepts one record per patient. A future EMR adapter should construct records with these fields:

```python
{
    "room": "example1",
    "patient_name": "Synthetic Patient",
    "oneliner": "65-year-old admitted with acute decompensated heart failure.",
    "vitals_summary": "BP 100-128/62-78  T 97.8-99.1F HR 72-94 RR 16-22 SPO2 92-98%",
    "io_summary": "I/O 1200 ml / 2600 ml net -1400 ml",
    "labs": {
        "WBC": "8.7",
        "HGB": "12.1",
        "HCT": "36",
        "PLT": "220",
        "NA": "138",
        "K": "4.1",
        "CL": "102",
        "HCO3": "26",
        "BUN": "24H",
        "CRET": "1.2",
        "GLU": "118H",
        "CA": "8.9",
        "MG": "2.0",
        "PO4": "3.4",
        "AST": "31",
        "ALT": "28",
        "ALKPHOS": "92",
        "TBIL": "0.8",
        "DBIL": "0.2",
        "PT": "12.8",
        "INR": "1.1",
        "PTT": "31",
    },
    "notes": "",
}
```

Lab flags should be compact strings such as `18H` or `10.2L`. The renderer also accepts grouped lab dictionaries named `cbc`, `bmp`, `lft`, `ca_mg_phos`, and `coags`; those are merged into the same fishbone lab dictionary internally.

## Recommended IT Responsibilities

Hospital IT should define:

- how the clinician's selected census or patient list is identified
- which EMR source supplies room, patient name, vitals, I/O, and labs
- whether the output opens in print preview, downloads, or routes to a printer
- where the renderer runs, such as an internal server, virtual desktop environment, or approved clinical reporting host
- how audit logging, access control, PHI handling, and retention are governed locally

No protected health information should be stored in this public repository.
