# Job Search & Career Strategy — [YOUR NAME]

## Overview

This is [YOUR NAME]'s career planning and job search workspace. It contains:
- **Strategic career documents** in `career/` — background, strategy
- **Job applications** in per-company folders under `leads/`
- **Base resume** — `[Your Name].pdf` in the project root

**Start here:** Read `career/career_strategy_guide.md` before any task. It contains your full situation assessment, target role categories, narrative framing, and job search intelligence.

---

## Who You Are (Quick Reference)

<!-- Fill in your details -->
- Current role, company, location
- Years of experience, key domains
- What you're looking for
- Key constraints (location, comp, etc.)

---

## Workflow: New Job Listing

When a new job listing is added, follow this process:

### Step 1: Strategic Fit Analysis

Before touching the resume, read `career/career_strategy_guide.md` and assess:

- **Role category match:** Does this fall into one of your target categories?
- **Coding interview risk:** Does the listing suggest a coding interview? Warn if likely.
- **Level match:** Is this the right seniority level?
- **Remote/location:** Is it remote-friendly or in your target location?
- **Narrative alignment:** Which of your key stories/achievements are most relevant?

### Step 2: Fit Analysis Presentation

Present the analysis before drafting, highlighting:
- Strong alignment areas
- Gaps to address
- Which narrative angle to lead with
- Anything that needs your input

### Step 3: Tailored Resume Draft

Draft a tailored resume as an HTML file in the job listing's folder, using the standard HTML/CSS template.

### Step 4: Keyword Optimization

Final pass comparing the listing's exact phrases against the resume text. Weave missing keywords into existing bullets via small word swaps rather than adding buzzword sections.

### Step 5: Post-Application Tracking

After applying, note the date and details in `leads/applications.yaml`.

---

## Critical Rules

- **Never fabricate or inflate experience.** If unsure whether you did something, ask. Getting caught misrepresenting is worse than a keyword gap.
- **Don't merge roles together.** Each position's scope, title, and responsibilities must be accurate.
- **Your title is "[YOUR ACTUAL TITLE]"** — not inflated. If the role involved duties beyond the title, describe the duties honestly while keeping the accurate title.
- **Keyword alignment over keyword stuffing.** Swap individual words in existing bullets to match the listing's language. Don't add filler bullets or a "skills" section.
- **Ask before assuming** on anything that isn't clearly documented.
- **Never use internal tool names, project codenames, or confidential information** in any external document. Describe tools generically by what they do.

---

## Key Experience Details (Confirmed)

<!--
Add details you've confirmed about your experience that aren't on the base resume but are real.
Format:

- **Company — Project/Achievement:** Description of what you did, with context about what is safe to claim and what would be overstating.
-->

---

## The Story You Tell Externally

<!--
Write your external narrative here. This should be 2-3 paragraphs summarizing:
- Who you are professionally
- What differentiates you
- What you're looking for

Key talking points:
- Point 1
- Point 2
- Point 3
-->

---

## HTML/CSS Template

Use the template from your first tailored resume as the base. Key styling:

- Font: Georgia / Times New Roman serif, 10.5pt body
- Letter size with 0.6in/0.75in margins
- `break-inside: avoid` and `page-break-inside: avoid` on `.job` and `.additional` blocks
- Bold key phrases with `<strong>` tags
- Section title styling: uppercase, letter-spaced, with bottom border
- Two-column layout for Additional Relevant Experience list

## Folder Structure

```
project/
├── CLAUDE.md                          # project instructions
├── [Your Name].pdf                    # base resume
├── career/                            # career strategy docs
│   └── career_strategy_guide.md
└── leads/                             # one subfolder per job application
    └── CompanyName/
        ├── CompanyName.txt            # job listing
        ├── resume_role_name.html      # tailored resume
        ├── cover_letter.html          # cover letter (when applicable)
        └── *.pdf                      # printed versions
```
