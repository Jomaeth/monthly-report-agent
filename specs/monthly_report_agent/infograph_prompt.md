You are designing a single, publication-quality infographic poster.

LAYOUT (strict, do not deviate):
  • Top band (≈12% of canvas height):
      - Workflow title, large and bold.
      - One-line value tagline directly underneath, in the brand purple #9B0A68.
  • Middle band (≈70%):
      - Four labelled blocks arranged top-to-bottom (or left-to-right if landscape):
        INPUTS → AI TASKS → REVIEW GATES → OUTPUTS & OWNERS.
      - Each block uses a distinct visual treatment (icon row, numbered chevrons, gated checkpoints, deliverable cards).
      - Arrows connect the blocks to show flow.
  • Bottom band (≈18%):
      - Risk Level badge (large pill, colour-coded — see below).
      - "AI Role:" line.
      - "Human Owner:" line — the single accountable person/role.
      - Brand mark: OpenDeedigital (ODD) × HKIC.

VISUAL STYLE:
  • Modern, flat-vector infographic. NOT a literal copy of the supplied Mermaid wireframe — re-imagine the layout.
  • Brand palette ONLY:
      primary  = #F36B15  (use for headers, arrows, accents)
      secondary= #9B0A68 (use for tagline, badges)
      accent   = #C83D3D   (use sparingly for warnings / stop conditions)
      dark     = #231F20     (text)
      light    = #FFF7F0    (background)
  • Use construction-industry visual metaphors where natural (hard hats, blueprints, gauges, crane, RFI tag) but avoid clutter.
  • Use clean sans-serif typography. English labels only in headers; Chinese / bilingual labels are NOT required.
  • Risk badge colour rule:
      GO         → green pill
      CONTROL    → amber pill, traffic-light icon
      High CONTROL → red-orange pill, raised-hand icon
      STOP       → red pill with lock icon

DO NOT:
  • Do not reproduce the Mermaid wireframe verbatim — treat it ONLY as a logical reference.
  • Do not invent numbers, KPI values, or company names other than the brand mark above.
  • Do not place text directly over icons; keep readable spacing.
  • Do not use shadows, 3D effects, or stock-photo collages.


WORKFLOW TO ILLUSTRATE:

  Title:        Monthly Project Health Report Agent — From Excel Data Pack to Director Dashboard
  Tagline:      "Same data pack, different user views: Director sees exceptions; PM sees actions; QS sees commercial detail."
  Risk Level:   CONTROL
  AI Role:      Validate, calculate, narrate, render — never sign
  Human Owner:  Project Manager (final approver); Section owners: Planner, QS, Safety Officer, QAQC, Procurement Manager, Technical Manager

  INPUTS:
  • 8-sheet Excel data pack (00_Project_Profile, 01_Area_Progress, 02_Programme_Milestones, 03_Submission_RFI, 04_Procurement, 05_Safety_Quality, 06_Commercial_Cost, 07_Risk_Action_Decision)
  • Previous month report
  • Metric dictionary
  • RAG thresholds
  • Report template
  • Review checklist

  AI TASKS (these become the central illustrated steps):
  1. Load Excel workbook
  2. Validate required columns, missing values, formula errors
  3. Normalize status labels (e.g., OPEN / open / Pending / pending)
  4. Calculate KPI: planned vs actual progress, delay days, overdue RFI, procurement variance, safety / quality exceptions, GP, cashflow, commitment
  5. Apply RAG status
  6. Generate charts: progress bar, milestone delay, RFI aging, commercial dashboard
  7. Generate Director / PM / QS summaries
  8. Render Markdown / HTML / PDF draft
  9. Generate human review checklist

  REVIEW GATES (each must be visibly attributed to its named human role):
  • Project Manager — checks: Overall narrative is fair and complete (STOP if: Narrative omits a Red exception)
  • Construction Manager — checks: Progress section reflects site reality (STOP if: Red progress item has no recovery action)
  • Planner — checks: Programme delay calculations (STOP if: Critical path milestone delay not flagged Red)
  • Technical Manager — checks: RFI / submission bottleneck (STOP if: Overdue RFI with programme impact not escalated)
  • Procurement Manager — checks: Material risk and long-lead items (STOP if: Long-lead item delay not flagged)
  • Safety Officer / QAQC — checks: Safety and quality red items (STOP if: Red safety item missing owner, due date, or evidence)
  • QS / Commercial Manager — checks: GP, VO, cashflow figures and wording (STOP if: Commercial number conflicts with QS records)
  • Project Director — checks: Approves Director Executive Dashboard before issue (STOP if: Any of the above gates remain blocked)

  OUTPUTS:
  • Director Executive Dashboard
  • Progress by Zone section
  • Programme Risk section
  • Submission / RFI Bottleneck section
  • Procurement Readiness section
  • Safety / Quality Exception section
  • Commercial Health section
  • Actions & Decisions page
  • Data Quality Log
  • Review Checklist

REFERENCE WIREFRAME:
  The attached image is a Mermaid flowchart showing the same logic. Use it ONLY to confirm
  the flow direction and which steps are AI vs human. Do NOT reproduce its visual style.

OUTPUT:
  A single infographic image, 1200×1600 px portrait, ready to print or paste into a slide.
