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
**What this phase does:** Build a UI for users to review AI-generated job matches, approve or reject them, and leave comments.

**Say this to Cursor:**
```
Implement the Review & Decision UI based on the frontend PRD. Use React and TypeScript to create a simple interface for reviewing job matches, displaying summaries, and allowing users to approve or reject with comments.
```

**How to verify it worked:**
- [ ] Users can view a list of job matches with summaries.
- [ ] Users can approve or reject job matches and leave comments.
- [ ] The UI updates to reflect user decisions.

**If something breaks, say this to Cursor:**
```
The Review & Decision UI has an issue: [paste error here]. Diagnose and fix it without altering previous phases.
```

---

## Phase 2: Auto-Apply
**What this phase does:** Enable users to automatically apply to jobs they approve, filling out necessary information via APIs.

**Say this to Cursor:**
```
Develop the Auto-Apply feature according to the frontend PRD. Implement functionality that allows users to auto-fill and submit applications for approved jobs through Greenhouse and Lever APIs.
```

**How to verify it worked:**
- [ ] Users can submit applications for approved jobs automatically.
- [ ] The system tracks the status of each application.
- [ ] Users receive confirmation of application submissions.

**If something breaks, say this to Cursor:**
```
The Auto-Apply feature has an issue: [paste error here]. Diagnose and fix it without altering previous phases.
```

---

## Phase 3: Settings
**What this phase does:** Create a settings page for users to configure their match threshold, email connections, and job source toggles.

**Say this to Cursor:**
```
Implement the Settings feature based on the frontend PRD. Create a page where users can adjust their match threshold, connect their Microsoft 365 email, and enable or disable job sources.
```

**How to verify it worked:**
- [ ] Users can adjust the match threshold and save changes.
- [ ] Users can connect their Microsoft 365 email account.
- [ ] Users can toggle job sources on and off.

**If something breaks, say this to Cursor:**
```
The Settings feature has an issue: [paste error here]. Diagnose and fix it without altering previous phases.
```

---

## Phase 4: Resume Management
**What this phase does:** Allow users to upload and manage their resumes, parsing them into a structured format.

**Say this to Cursor:**
```
Build the Resume Management feature according to the frontend PRD. Enable users to upload resumes, parse them into a structured schema, and manage their resume library.
```

**How to verify it worked:**
- [ ] Users can upload resumes in PDF/DOCX format.
- [ ] The system parses resumes into a structured format.
- [ ] Users can edit parsed fields and select an active resume.

**If something breaks, say this to Cursor:**
```
The Resume Management feature has an issue: [paste error here]. Diagnose and fix it without altering previous phases.
```

---

## Phase 5: Job Source Integration
**What this phase does:** Integrate with job sources like Greenhouse and Lever to fetch job postings.

**Say this to Cursor:**
```
Implement the Job Source Integration feature based on the backend PRD. Set up a system to fetch job postings from Greenhouse and Lever, ensuring deduplication and rate limiting.
```

**How to verify it worked:**
- [ ] The system fetches job postings from both sources.
- [ ] Job postings are deduplicated and stored correctly.
- [ ] Users can view a unified list of job postings.

**If something breaks, say this to Cursor:**
```
The Job Source Integration feature has an issue: [paste error here]. Diagnose and fix it without altering previous phases.
```

---

## Phase 6: Matching & Ranking
**What this phase does:** Implement AI-driven matching to compare resumes with job postings.

**Say this to Cursor:**
```
Develop the Matching & Ranking feature according to the backend PRD. Create an AI model to compute match percentages between resumes and job postings, providing summaries and explanations.
```

**How to verify it worked:**
- [ ] The system calculates match percentages for job postings.
- [ ] Users can see summaries and explanations for each match.
- [ ] Users can configure the minimum match threshold.

**If something breaks, say this to Cursor:**
```
The Matching & Ranking feature has an issue: [paste error here]. Diagnose and fix it without altering previous phases.
```

---

## Phase 7: Email Ingestion & Reply
**What this phase does:** Enable users to pull in relevant emails and reply to them within the app.

**Say this to Cursor:**
```
Implement the Email Ingestion & Reply feature based on the frontend PRD. Allow users to ingest emails from Microsoft Graph and reply to them directly in the app.
```

**How to verify it worked:**
- [ ] Users can view relevant emails linked to job applications.
- [ ] Users can reply to emails using templates and AI suggestions.
- [ ] All interactions are logged and linked to the appropriate job postings.

**If something breaks, say this to Cursor:**
```
The Email Ingestion & Reply feature has an issue: [paste error here]. Diagnose and fix it without altering previous phases.
```

---

## Phase 8: Learning Loop
**What this phase does:** Implement a feedback system to learn from user decisions and improve matching over time.

**Say this to Cursor:**
```
Develop the Learning Loop feature according to the backend PRD. Capture user feedback on job matches and adjust matching weights and thresholds based on this feedback.
```

**How to verify it worked:**
- [ ] The system captures user decisions on job matches.
- [ ] The matching algorithm adjusts based on user feedback.
- [ ] Users can see how their feedback influences future matches.

**If something breaks, say this to Cursor:**
```
The Learning Loop feature has an issue: [paste error here]. Diagnose and fix it without altering previous phases.
```

---

## Final Phase: Testing & Polish
**Say this to Cursor:**
```
Review the entire codebase. Fix any TypeScript errors, broken imports, or missing connections between features. Make sure all features from the .codespring/PRDs/ folder are implemented.
```

**How to verify the full app works:**
- [ ] All features function correctly without errors.
- [ ] Users can seamlessly navigate between features.
- [ ] The application is responsive and performs well under load.
- [ ] All user settings persist across sessions.
- [ ] The system accurately reflects user feedback in job matching.