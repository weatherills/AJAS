# AI Job Application System (AJAS) — Cursor Runbook

> Keep this file open while building. Follow phases in order. Complete each phase before starting the next.

## How to use this runbook
1. Open Cursor IDE in your project folder
2. Open the Chat panel (Cmd+L)
3. For each phase: paste the "Say this to Cursor" prompt, wait for Cursor to finish, then run the verification steps
4. Only move to the next phase when verification passes

## Project Overview
The AI Job Application System (AJAS) is designed to streamline the job application process for job seekers by leveraging AI to match resumes with job postings. It provides features like resume management, job source integration, and an intuitive review interface to enhance user experience and efficiency.

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
**What this phase does:** Build a UI for users to review job matches, make decisions, and leave comments.

**Say this to Cursor:**
```
Implement the Review & Decision UI as described in the frontend PRD. Use React and TypeScript to create a simple approve/reject interface with comments, and display a summary and AI suggestion for each job match.
```

**How to verify it worked:**
- [ ] Users can see job matches with summaries and suggestions.
- [ ] Users can approve or reject matches and leave comments.
- [ ] Decisions are saved and retrievable.

**If something breaks, say this to Cursor:**
```
The Review & Decision UI phase failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Phase 2: Auto-Apply
**What this phase does:** Enable users to automatically apply to jobs if approved.

**Say this to Cursor:**
```
Develop the Auto-Apply feature as per the frontend PRD. Allow users to submit applications programmatically via supported APIs (Greenhouse, Lever) or generate a manual application package if necessary.
```

**How to verify it worked:**
- [ ] Users can submit applications directly from the UI for approved jobs.
- [ ] Application status is tracked and displayed.
- [ ] Manual application packages are generated correctly when needed.

**If something breaks, say this to Cursor:**
```
The Auto-Apply phase failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Phase 3: Settings
**What this phase does:** Create a settings page for users to adjust their preferences.

**Say this to Cursor:**
```
Implement the Settings feature as described in the frontend PRD. Allow users to set their match threshold, connect their email, and toggle job source integrations.
```

**How to verify it worked:**
- [ ] Users can adjust their match threshold and see changes reflected in job matches.
- [ ] Email connection setup works without errors.
- [ ] Users can enable or disable job sources.

**If something breaks, say this to Cursor:**
```
The Settings phase failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Phase 4: Resume Management
**What this phase does:** Allow users to upload and manage their resumes.

**Say this to Cursor:**
```
Build the Resume Management feature according to the frontend PRD. Users should be able to upload resumes, parse them into a structured format, edit fields, and select an active resume for applications.
```

**How to verify it worked:**
- [ ] Users can upload resumes and see them parsed correctly.
- [ ] Users can edit parsed fields and save changes.
- [ ] Users can select an active resume for their applications.

**If something breaks, say this to Cursor:**
```
The Resume Management phase failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Phase 5: Job Source Integration
**What this phase does:** Integrate job postings from external sources.

**Say this to Cursor:**
```
Implement the Job Source Integration feature as described in the backend PRD. Fetch job postings from Greenhouse and Lever, normalize the data, and ensure no duplicates are displayed.
```

**How to verify it worked:**
- [ ] Job postings from Greenhouse and Lever are displayed without duplicates.
- [ ] Users can filter postings by source.
- [ ] The integration respects rate limits and handles errors gracefully.

**If something breaks, say this to Cursor:**
```
The Job Source Integration phase failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Phase 6: Matching & Ranking
**What this phase does:** Implement AI-driven matching between resumes and job postings.

**Say this to Cursor:**
```
Develop the Matching & Ranking feature as per the backend PRD. Calculate match percentages between resumes and job postings, and provide a summary and rationale for each match.
```

**How to verify it worked:**
- [ ] Users can see match percentages for job postings.
- [ ] Summaries and rationales for matches are displayed.
- [ ] Users can configure their match threshold.

**If something breaks, say this to Cursor:**
```
The Matching & Ranking phase failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Phase 7: Email Ingestion & Reply
**What this phase does:** Enable users to manage emails related to job applications.

**Say this to Cursor:**
```
Implement the Email Ingestion & Reply feature as described in the frontend PRD. Users should be able to pull emails from Microsoft Graph, view related threads, and reply directly from the app.
```

**How to verify it worked:**
- [ ] Users can see relevant emails linked to job applications.
- [ ] Users can reply to emails within the app.
- [ ] Email threads and attachments are displayed correctly.

**If something breaks, say this to Cursor:**
```
The Email Ingestion & Reply phase failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Phase 8: Learning Loop
**What this phase does:** Implement a feedback loop to improve job matching.

**Say this to Cursor:**
```
Develop the Learning Loop feature as described in the backend PRD. Capture user feedback on job matches and adjust matching weights and thresholds accordingly.
```

**How to verify it worked:**
- [ ] User decisions on job matches are logged correctly.
- [ ] The system adapts to user feedback over time.
- [ ] Users can see how their feedback influences future matches.

**If something breaks, say this to Cursor:**
```
The Learning Loop phase failed with this error: [paste error here]. Fix it without changing the project structure.
```

---

## Final Phase: Testing & Polish
**Say this to Cursor:**
```
Review the entire codebase. Fix any TypeScript errors, broken imports, or missing connections between features. Make sure all features from the .codespring/PRDs/ folder are implemented.
```

**How to verify the full app works:**
- [ ] All features are accessible and function as intended.
- [ ] No TypeScript errors are present.
- [ ] The application runs smoothly without crashes or performance issues.
- [ ] User feedback is correctly captured and reflected in job matching.
- [ ] All integrations with external APIs work without errors.