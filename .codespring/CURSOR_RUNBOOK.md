# AI Job Application System (AJAS) — Cursor Runbook

> Keep this file open while building. Follow phases in order. Complete each phase before starting the next.

## How to use this runbook
1. Open Cursor IDE in your project folder
2. Open the Chat panel (Cmd+L)
3. For each phase: paste the "Say this to Cursor" prompt, wait for Cursor to finish, then run the verification steps
4. Only move to the next phase when verification passes

## Project Overview
The AI Job Application System (AJAS) is designed to streamline the job application process for job seekers by leveraging AI to match resumes with job postings, manage applications, and facilitate communication with recruiters. It provides a user-friendly interface for reviewing job matches, applying to jobs, and managing resumes.

## Tech Stack
- React + TypeScript (Frontend)
- Vite (Frontend)
- Azure Functions (Python v2) (Backend)
- Azure Cosmos DB (Serverless) (Database)
- Azure Blob Storage (Infrastructure)
- Azure Storage Queues (Infrastructure)
- Azure OpenAI (Utilities)
- Microsoft Graph API (Infrastructure)
- Azure Container Apps (Infrastructure)

---

## Phase 0: Project Setup
**What this phase does:** Scaffold the project structure and install dependencies.

**Say this to Cursor:**
```
Read my .codespring/ folder to understand the project. Then scaffold the codespring project structure with all dependencies installed and a working dev server.
```

**How to verify it worked:**
- [ ] Dev server starts without errors (npm run dev / yarn dev)
- [ ] You can open localhost:3000 in a browser
- [ ] No TypeScript errors in the terminal

**If something breaks, say this to Cursor:**
```
The setup failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Phase 1: Review & Decision UI
**What this phase does:** Build a user interface for reviewing AI-generated job matches, allowing users to approve or reject with comments.

**Say this to Cursor:**
```
Implement the Review & Decision UI as described in the frontend PRD. Use React and TypeScript to create a simple approve/reject interface that shows a summary and suggestions for job matches.
```

**How to verify it worked:**
- [ ] Users can see a list of job matches with summaries and suggestions.
- [ ] Users can approve or reject job matches and leave comments.
- [ ] The decisions are saved and retrievable.

**If something breaks, say this to Cursor:**
```
The Review & Decision UI failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 2: Auto-Apply
**What this phase does:** Enable users to automatically apply to jobs they approve via supported APIs.

**Say this to Cursor:**
```
Implement the Auto-Apply feature as outlined in the frontend PRD. Ensure it allows users to auto-fill and submit applications for approved jobs through Greenhouse and Lever APIs.
```

**How to verify it worked:**
- [ ] Users can submit applications directly from the job match interface.
- [ ] The application status is tracked and displayed.
- [ ] Manual application packages are generated when auto-submit is not possible.

**If something breaks, say this to Cursor:**
```
The Auto-Apply feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 3: Settings
**What this phase does:** Create a settings interface for users to adjust match thresholds and connect their email.

**Say this to Cursor:**
```
Build the Settings feature as described in the frontend PRD. Include options for adjusting the match threshold, connecting to Microsoft 365 for email ingestion, and toggling job source integrations.
```

**How to verify it worked:**
- [ ] Users can adjust the match threshold and see the changes reflected in job matches.
- [ ] Users can connect their Microsoft 365 email account.
- [ ] Users can enable or disable job source integrations.

**If something breaks, say this to Cursor:**
```
The Settings feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 4: Resume Management
**What this phase does:** Allow users to upload and manage their resumes, parsing them into a structured format.

**Say this to Cursor:**
```
Implement the Resume Management feature as outlined in the frontend PRD. Allow users to upload resumes, parse them into a structured schema, and manage their resume library.
```

**How to verify it worked:**
- [ ] Users can upload resumes in PDF or DOCX format.
- [ ] Resumes are parsed correctly into a structured format.
- [ ] Users can edit parsed fields and select an active resume for applications.

**If something breaks, say this to Cursor:**
```
The Resume Management feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 5: Job Source Integration
**What this phase does:** Integrate with job sources like Greenhouse and Lever to fetch job postings.

**Say this to Cursor:**
```
Build the Job Source Integration feature as described in the backend PRD. Ensure it fetches job postings from Greenhouse and Lever, normalizes, deduplicates, and persists them.
```

**How to verify it worked:**
- [ ] Job postings from Greenhouse and Lever are fetched and displayed.
- [ ] Duplicate postings are removed.
- [ ] Users can see the source of each job posting.

**If something breaks, say this to Cursor:**
```
The Job Source Integration feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 6: Matching & Ranking
**What this phase does:** Implement AI-driven matching to score job postings against user resumes.

**Say this to Cursor:**
```
Implement the Matching & Ranking feature as described in the backend PRD. Ensure it computes a match percentage between resumes and job postings and provides a rationale for the score.
```

**How to verify it worked:**
- [ ] Users can see a match percentage for each job posting.
- [ ] A brief rationale for the match score is displayed.
- [ ] Users can configure a minimum match threshold for saving jobs.

**If something breaks, say this to Cursor:**
```
The Matching & Ranking feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 7: Email Ingestion & Reply
**What this phase does:** Enable users to pull relevant emails and reply to them within the app.

**Say this to Cursor:**
```
Implement the Email Ingestion & Reply feature as described in the frontend PRD. Allow users to view and respond to recruiter emails related to job postings directly in AJAS.
```

**How to verify it worked:**
- [ ] Users can see a list of relevant emails linked to job postings.
- [ ] Users can reply to emails using templates and AI suggestions.
- [ ] Email threads are displayed correctly with attachments.

**If something breaks, say this to Cursor:**
```
The Email Ingestion & Reply feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 8: Learning Loop
**What this phase does:** Implement a feedback system that learns from user decisions to improve job matching.

**Say this to Cursor:**
```
Build the Learning Loop feature as described in the backend PRD. Capture user feedback on job matches and adjust matching weights and thresholds accordingly.
```

**How to verify it worked:**
- [ ] User decisions on job matches are recorded and used to adjust future matches.
- [ ] Users can see how their feedback influences match quality over time.
- [ ] The system provides insights into match performance metrics.

**If something breaks, say this to Cursor:**
```
The Learning Loop feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Final Phase: Testing & Polish
**Say this to Cursor:**
```
Review the entire codebase. Fix any TypeScript errors, broken imports, or missing connections between features. Make sure all features from the .codespring/PRDs/ folder are implemented.
```

**How to verify the full app works:**
- [ ] All features are accessible and function as intended.
- [ ] No TypeScript errors are present in the terminal.
- [ ] The application runs smoothly without crashes or major bugs.
- [ ] Users can complete the job application process from start to finish.
- [ ] All user feedback mechanisms are operational and effective.