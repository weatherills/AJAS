# AI Job Application System (AJAS) — Cursor Runbook

> Keep this file open while building. Follow phases in order. Complete each phase before starting the next.

## How to use this runbook
1. Open Cursor IDE in your project folder
2. Open the Chat panel (Cmd+L)
3. For each phase: paste the "Say this to Cursor" prompt, wait for Cursor to finish, then run the verification steps
4. Only move to the next phase when verification passes

## Project Overview
The AI Job Application System (AJAS) is designed to streamline the job application process for users by leveraging AI to match resumes with job postings. It provides features for reviewing job matches, auto-applying to jobs, managing resumes, and integrating with job sources and email systems.

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
**What this phase does:** Build a UI for users to review AI-generated job matches, approve or reject them, and add comments.

**Say this to Cursor:**
```
Implement the Review & Decision UI based on the frontend PRD. Use React and TypeScript to create a simple interface that allows users to view job matches, see summaries and suggestions, and make decisions with comments.
```

**How to verify it worked:**
- [ ] Users can see a list of job matches with summaries.
- [ ] Users can approve or reject matches and add comments.
- [ ] The decisions are saved and retrievable.

**If something breaks, say this to Cursor:**
```
The Review & Decision UI failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 2: Auto-Apply
**What this phase does:** Enable users to auto-apply for jobs they approve directly from the app.

**Say this to Cursor:**
```
Implement the Auto-Apply feature based on the frontend PRD. Allow users to submit job applications programmatically via supported APIs or generate a manual application package when necessary.
```

**How to verify it worked:**
- [ ] Users can auto-apply to jobs from the Review & Decision UI.
- [ ] The application status is tracked and displayed.
- [ ] Users receive feedback on submission success or failure.

**If something breaks, say this to Cursor:**
```
The Auto-Apply feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 3: Settings
**What this phase does:** Create a settings page for users to configure their match threshold, email connection, and job source toggles.

**Say this to Cursor:**
```
Implement the Settings feature based on the frontend PRD. Create a UI that allows users to adjust their match threshold, connect their email, and toggle job sources.
```

**How to verify it worked:**
- [ ] Users can adjust their match threshold and save it.
- [ ] Users can connect their Microsoft 365 email account.
- [ ] Users can enable or disable job sources.

**If something breaks, say this to Cursor:**
```
The Settings feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 4: Resume Management
**What this phase does:** Allow users to upload, parse, and manage their resumes.

**Say this to Cursor:**
```
Implement the Resume Management feature based on the frontend PRD. Enable users to upload resumes, parse them into a structured format, and manage their resume library.
```

**How to verify it worked:**
- [ ] Users can upload resumes in PDF/DOCX format.
- [ ] Resumes are parsed correctly into a structured schema.
- [ ] Users can edit and manage their resumes.

**If something breaks, say this to Cursor:**
```
The Resume Management feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 5: Job Source Integration
**What this phase does:** Integrate with job sources like Greenhouse and Lever to fetch job postings.

**Say this to Cursor:**
```
Implement the Job Source Integration feature based on the backend PRD. Set up the system to fetch job postings from Greenhouse and Lever, ensuring deduplication and rate limiting.
```

**How to verify it worked:**
- [ ] Job postings are fetched and displayed in the app.
- [ ] Duplicate postings are removed.
- [ ] The system respects rate limits from job sources.

**If something breaks, say this to Cursor:**
```
The Job Source Integration feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 6: Matching & Ranking
**What this phase does:** Implement AI-driven matching between resumes and job postings.

**Say this to Cursor:**
```
Implement the Matching & Ranking feature based on the backend PRD. Create the logic to compute match percentages between resumes and job postings using AI.
```

**How to verify it worked:**
- [ ] Match percentages are calculated and displayed for each job posting.
- [ ] Users can configure a minimum match threshold.
- [ ] The rationale for match scores is provided.

**If something breaks, say this to Cursor:**
```
The Matching & Ranking feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 7: Email Ingestion & Reply
**What this phase does:** Enable the app to ingest emails related to job applications and allow users to reply.

**Say this to Cursor:**
```
Implement the Email Ingestion & Reply feature based on the frontend PRD. Set up the integration with Microsoft Graph to pull relevant emails and allow users to respond within the app.
```

**How to verify it worked:**
- [ ] Relevant emails are ingested and linked to job postings.
- [ ] Users can reply to emails from within the app.
- [ ] Email threads are displayed correctly.

**If something breaks, say this to Cursor:**
```
The Email Ingestion & Reply feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 8: Learning Loop
**What this phase does:** Implement a feedback loop that learns from user decisions to improve job matching.

**Say this to Cursor:**
```
Implement the Learning Loop feature based on the backend PRD. Create a system that captures user feedback on job matches and adjusts matching weights accordingly.
```

**How to verify it worked:**
- [ ] User decisions are logged and used to adjust matching criteria.
- [ ] Users can see how their feedback influences future matches.
- [ ] The system maintains a history of adjustments for transparency.

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
- [ ] There are no TypeScript errors in the terminal.
- [ ] The app performs smoothly without crashes.
- [ ] All user interactions are logged correctly.
- [ ] The user experience is intuitive and cohesive.