# Feature Specification: Caveat AI — Local-First Contract Review

**Status**: Draft
**Created**: 2026-05-08
**Input**: Build a local-first web application that helps US-based transactional lawyers review contracts without sending any document to the cloud. The user uploads up to 5 PDFs at once, the application runs Gemma 4 locally to identify risk clauses, missing provisions, and suggest redlines. The user can also chat with the loaded documents to compare clauses across files, draft tougher redlines, and extract data into tables. Every output cites the source. The user can export findings as a Word memo, signed PDF, redline package, or short email blurb. Target users are solo and boutique lawyers in the United States handling transactional work in English.

---

## Clarifications

### Session 2026-05-08

- Q: Target audience → A: Transactional lawyers (solo and boutique), United States only, English only
- Q: Sub-cases combined → A: Risk auditor + plain-English client summary in a single product
- Q: Application form factor → A: Local web application running on the lawyer's own machine (`localhost`), not a cloud service
- Q: Multi-document support → A: Up to 5 PDFs simultaneously, with a chat that has all loaded documents in context
- Q: Chat user → A: The lawyer only (not the client; the client never accesses the app directly)
- Q: Model choice → A: Gemma 4 31B Dense Q4_K_M as primary, E4B as automatic fallback for low-end hardware

### Open questions (deferred to /plan)

- [NEEDS CLARIFICATION: exact RAM/VRAM threshold for switching between 31B and E4B fallback]
- [NEEDS CLARIFICATION: whether user playbook customization ships in the MVP or is hardcoded for the contest]
- [NEEDS CLARIFICATION: format and storage location for analysis history (local SQLite vs flat JSON files)]

---

## User Scenarios & Testing

### User Story 1 — Single-document risk analysis (Priority: P1)

A US-based transactional lawyer receives a counterparty's draft Master Services Agreement in PDF. She drops the PDF onto Caveat AI in her browser. Within about 45 seconds, she sees a list of risk findings, each with a cited passage from the contract, an explanation of why it is a problem, and a suggested redline she can accept, edit, or dismiss.

**Why this priority**: This is the core promise. Without it, no other feature matters. A demo of just this story already justifies the product.

**Independent test**: Start the application from a clean state, upload a known MSA, verify the technical analysis identifies at least 80% of the high-severity clauses pre-flagged by an attorney baseline, and verify every cited passage exists verbatim in the source PDF.

**Acceptance scenarios**:

1. **Given** the application is running and idle, **When** the lawyer drops a single PDF (≤ 50 pages) into the upload zone, **Then** the system parses the document, classifies its type, runs the analysis pipeline, and presents findings within 60 seconds on recommended hardware.
2. **Given** the analysis is complete, **When** the lawyer reviews any finding, **Then** the cited passage is displayed alongside the explanation and matches text that exists verbatim in the source PDF.
3. **Given** the application is running, **When** the lawyer disconnects the network entirely (airplane mode), **Then** every step of the analysis still completes successfully.
4. **Given** the model output for any finding fails citation validation, **When** the system detects this, **Then** the finding is discarded and the analysis re-attempted with a more restrictive prompt; if it fails twice, the finding is omitted with a visible warning.

---

### User Story 2 — Plain-English client summary (Priority: P1)

The same lawyer needs to send the analysis to her client, who is not a lawyer. She switches to the "Client summary" tab and finds a one-page memo in plain English: what the contract is, what the client is committing to, the three biggest risks, and a clear recommendation. She edits two sentences, then exports it.

**Why this priority**: The differentiator from generic legal AI tools. Lawyers spend significant time translating their own analysis for clients; this collapses that work. Equal priority to P1 because the contest demo is much weaker without it.

**Independent test**: For the same MSA used in P1, generate the client summary, verify it is comprehensible to a non-lawyer (manually validated against the rubric below), and verify it includes the disclaimer text in full.

**Acceptance scenarios**:

1. **Given** the technical analysis is complete, **When** the lawyer opens the "Client summary" tab, **Then** the system displays a memo with four sections: "What this contract is", "What you're committing to", "The biggest risks", and "Recommendation".
2. **Given** the summary is displayed, **When** evaluated by a non-lawyer reader, **Then** the reader can correctly answer "what is the recommendation?" and "what are the top three risks?" without consulting the source contract.
3. **Given** the summary contains a disclaimer footer, **When** the lawyer exports the document, **Then** the disclaimer is preserved in the export and cannot be removed via UI controls.

---

### User Story 3 — Multi-document chat (Priority: P1)

The lawyer is conducting due diligence on an acquisition and has 5 contracts loaded simultaneously. She opens the "Chat" tab and asks: "Which of these contracts has the most aggressive limitation of liability?" The system responds with a side-by-side comparison table and a literal citation from the harshest contract. She follows up: "Draft a more aggressive redline of acme §4.2 — 24 months and full carve-outs." The system produces a proposed clause with the exact change suggested, also cited.

**Why this priority**: This is what justifies "intentional model choice" in the contest rubric. The 128K context window of Gemma 4 is what makes multi-document conversational analysis possible without retrieval-augmented complexity. Without this story, the project is just another single-document tool.

**Independent test**: Load 5 distinct contract types into the application. Pose 10 cross-document questions from a fixed test set. Verify that ≥ 8 of 10 responses contain at least one valid citation pointing to the correct source document and section.

**Acceptance scenarios**:

1. **Given** between 1 and 5 PDFs are loaded, **When** the lawyer opens the Chat tab, **Then** the system displays a context indicator showing the number of documents loaded and the approximate token usage out of 128,000.
2. **Given** a chat conversation is in progress, **When** the lawyer asks a question that requires comparing across documents, **Then** the response includes citations from each document referenced, with document name and section number.
3. **Given** the lawyer requests a redline draft via chat, **When** the system generates the proposed clause, **Then** the proposal is presented as a citation block visually distinct from the source quotes (different color or border treatment) and includes a button to add it directly to the export package.
4. **Given** the loaded documents would exceed the context window, **When** the lawyer attempts to load a 6th document, **Then** the system declines with a clear message indicating the cap rather than silently truncating any document.

---

### User Story 4 — Export package generation (Priority: P2)

After reviewing findings and chat outputs, the lawyer presses "Export". She picks Word memo and signed PDF as her two formats, points the output at her local matter folder, and the system generates both files with her firm letterhead, her bar registration, and the cited passages preserved.

**Why this priority**: Important for product completeness, but the contest demo can show review without showing export. Marking P2 protects the timeline.

**Independent test**: Trigger export with all four format options selected. Verify each file exists at the specified location, opens correctly in its native application, and contains the required disclaimer.

**Acceptance scenarios**:

1. **Given** an analysis is complete and the lawyer has accepted at least one finding, **When** she selects export formats and a destination folder, **Then** all selected files are written to disk with deterministic, human-readable filenames including the contract name and date.
2. **Given** an export is generated, **When** the resulting Word memo is opened in Microsoft Word, **Then** the firm letterhead, lawyer name, bar registration, and disclaimer footer are all present and correctly formatted.
3. **Given** any export format is generated, **When** the file is inspected, **Then** the disclaimer text is present and not removable through any documented UI flow.

---

### User Story 5 — Hardware capability detection and graceful fallback (Priority: P2)

A lawyer installs the application on her older Windows laptop with 16GB RAM and integrated graphics. On first launch, the system detects that 31B Dense will not run acceptably, downloads E4B instead, and displays a notice that she is running the lighter model and what that means for quality.

**Why this priority**: Necessary for distribution beyond the demo machine, but not strictly required for the contest video.

**Independent test**: Run first-launch on three reference hardware tiers (high-end with GPU, mid-range, low-end). Verify the correct model is selected and the user is informed of the choice.

**Acceptance scenarios**:

1. **Given** the application is launched for the first time, **When** the system queries the host hardware, **Then** it selects 31B if RAM ≥ 32GB and either GPU VRAM ≥ 16GB or unified memory ≥ 32GB is available; otherwise E4B.
2. **Given** the model is downloaded, **When** the user inspects settings, **Then** the active model variant is clearly displayed.

---

### Edge Cases

- A scanned PDF (image-based, no text layer) is uploaded → the system declines with a clear message that OCR is not supported in the MVP, rather than producing garbage analysis.
- A PDF in a non-English language is uploaded → the system declines with a message that the MVP supports English only.
- A contract governed by non-US law is uploaded → the system runs analysis but adds a banner noting the playbook is calibrated for US contracts, and findings may be less accurate.
- A non-contract PDF is uploaded (e.g., an invoice or news article) → the classifier identifies it as "not a contract" and asks the user to confirm before proceeding.
- The user closes the browser tab mid-analysis → the local server continues processing; on reconnection, the user sees the completed analysis.
- Two analyses are requested in parallel → the system queues them rather than running concurrently (single-model serialization).
- The user accepts 30 redlines, then dismisses 25 of them → the export includes only the 5 still accepted.
- The model produces an empty or malformed JSON response → the system retries up to 2 times, then surfaces an error rather than fabricating findings.
- The lawyer asks the chat about something not in the loaded documents → the bot responds with "I don't see that in the loaded contracts" rather than guessing from training data.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST run as a local web application accessible at `http://localhost:<port>` without requiring deployment to any external server.
- **FR-002**: The system MUST accept up to 5 PDF documents uploaded simultaneously via drag-and-drop or file picker.
- **FR-003**: The system MUST extract text from text-based PDFs without performing OCR; image-only PDFs are out of scope for the MVP.
- **FR-004**: The system MUST classify each uploaded document into one of a known set of contract types (MSA, NDA, SaaS Agreement, Employment Agreement, Other) before running the main analysis.
- **FR-005**: The system MUST identify risk clauses, missing standard provisions, and proposed redlines for each loaded document, organized by severity (high / medium / low / missing). Analysis is calibrated for US contract norms.
- **FR-006**: The system MUST attach a literal quotation from the source document to every finding, validated by exact substring match against the source text. Findings whose citations fail validation MUST be discarded.
- **FR-007**: The system MUST generate a plain-English client summary for the active document, including: contract description, client commitments, top 3 risks, and a recommendation.
- **FR-008**: The system MUST provide a chat interface that has all currently loaded documents in context, supports multi-turn conversation, and produces responses with citations.
- **FR-009**: The system MUST allow the lawyer to accept, edit, dismiss, or "ask in chat" for any finding, and these decisions MUST persist for the duration of the session.
- **FR-010**: The system MUST export accepted findings and the client summary as: Word memo (.docx), signed PDF (.pdf), redline package (annotated original .docx with track changes), and email-ready text blurb.
- **FR-011**: All exports MUST include a non-removable disclaimer noting that the document was generated by an AI tool and does not replace attorney review.
- **FR-012**: The system MUST function fully with no network access after the model has been downloaded once at install time.
- **FR-013**: The system MUST detect host hardware on first launch and select Gemma 4 31B Dense Q4_K_M for capable hardware, falling back to Gemma 4 E4B otherwise.
- **FR-014**: The system MUST display a status indicator visible at all times showing: which model variant is active, and that no network requests are being made.
- **FR-015**: The system MUST refuse to load a 6th document if 5 are already loaded, with a clear message; it MUST NOT silently truncate any document to fit.

### Non-Functional Requirements

- **NFR-001 (Privacy)**: Zero network requests MUST be made by the application after model download is complete. This is verifiable by packet capture during a 30-minute usage session.
- **NFR-002 (Latency)**: Single-document analysis of a 30-page PDF MUST complete within 60 seconds on recommended hardware (32GB RAM, GPU with ≥16GB VRAM or Apple M2 Pro+ with 32GB unified memory).
- **NFR-003 (Latency)**: Chat responses MUST begin streaming text to the UI within 5 seconds of the user submitting a question.
- **NFR-004 (Honesty)**: When the model expresses uncertainty or says it cannot answer from the loaded documents, the system MUST display this verbatim without rephrasing it as a confident answer.
- **NFR-005 (Accessibility)**: All interactive elements MUST be reachable by keyboard, and the application MUST meet WCAG 2.2 AA contrast minimums.
- **NFR-006 (Portability)**: The application MUST run on macOS (Apple Silicon), Windows 11, and Ubuntu 22.04 from the same codebase.

### Key Entities

- **Document**: An uploaded PDF, with extracted text, detected contract type, page count, and a list of findings. Stored locally only.
- **Finding**: A single risk identified in a document, with severity, title, cited passage, explanation, optional suggested redline, and an accepted/dismissed state.
- **Chat Session**: A conversation tied to a set of loaded documents, consisting of message turns. Messages from the model carry citations.
- **Export Package**: A configured set of output formats and a destination directory, generated on demand from accepted findings, the client summary, and optionally accepted chat redlines.
- **Playbook**: A named template of expected clauses and US market norms for a given contract type, used to drive the analysis. Ships with built-in playbooks for each supported contract type; user customization is out of MVP scope.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A 30-page contract is analyzed end-to-end in under 60 seconds on recommended hardware in 9 of 10 trials.
- **SC-002**: Across a test set of 10 real US contracts, the system identifies at least 80% of high-severity clauses that an attorney baseline review pre-flagged.
- **SC-003**: Across the same test set, fewer than 5% of model outputs fail citation validation.
- **SC-004**: In 10 cross-document chat queries against a 5-document set, ≥ 8 responses contain at least one valid citation pointing to the correct source document and section.
- **SC-005**: Zero network requests are observed by packet capture during a 30-minute usage session in airplane mode.
- **SC-006**: A non-lawyer reader, given the client summary, correctly answers "what is the recommendation?" and "what are the top three risks?" in 8 of 10 trials, without seeing the source contract.
- **SC-007**: The application starts and serves the first request within 10 seconds on recommended hardware (excluding initial model download).

---

## Out of Scope (for MVP)

- iOS, Android, or any mobile platform
- Any hosted / SaaS version of the application
- OCR for image-based PDFs
- Languages other than English
- Jurisdictions outside the United States (no UK / Canadian / Australian common-law variants; no civil-law jurisdictions)
- User-customizable playbooks (built-in playbooks only for MVP)
- Comparison between two versions of the same contract (e.g., diff between v1 and v2)
- Integration with cloud document storage (Google Drive, OneDrive, iManage, NetDocuments, etc.)
- Multi-user collaboration or commenting
- E-signature integration
- Billing / time tracking integration
- Drafting contracts from scratch (out of scope; competing with Spellbook is not the strategy)
- Caselaw research or jurisprudence lookup

---

## Dependencies & Assumptions

- The end user has Ollama installed on their machine, or the application's installer/onboarding helps them install it.
- The end user has at least 16GB of RAM and an x86_64 or ARM64 CPU from the last 5 years.
- The user has a modern browser (Chrome, Firefox, Safari, or Edge) for the local web UI.
- Gemma 4 31B Dense and Gemma 4 E4B are available on the Ollama public registry under standard names by the time of release.
- The user is a US-licensed attorney working with English-language contracts.
