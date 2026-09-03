# AI Job Application System (AJAS) — Cursor Runbook

> Keep this file open while building. Follow phases in order. Complete each phase before starting the next.

## How to use this runbook
1. Open Cursor IDE in your project folder
2. Open the Chat panel (Cmd+L)
3. For each phase: paste the "Say this to Cursor" prompt, wait for Cursor to finish, then run the verification steps
4. Only move to the next phase when verification passes

## Project Overview
The AI Job Application System (AJAS) is designed to streamline the job application process for job seekers by leveraging AI to match resumes with job postings. It allows users to manage resumes, apply for jobs automatically, and track application statuses, all while providing a user-friendly interface.

## Tech Stack
- Azure Functions (Consumption)
- Azure Container Apps
- Azure Storage Queues
- Azure Cosmos DB (Serverless)
- Azure Blob Storage
- Microsoft Graph API
- AI Matching Service
- Azure OpenAI

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
**What this phase does:** Build a user interface for reviewing AI-generated job matches, allowing users to approve or reject applications with comments.

**Say this to Cursor:**
```
Create a Review & Decision UI that enables users to view AI-generated job matches, see summaries and suggestions, and make approve/reject decisions with comments. Use Azure Functions for the backend APIs.
```

**How to verify it worked:**
- [ ] Users can view a list of job matches.
- [ ] Users can approve or reject matches and leave comments.
- [ ] The decisions are saved and retrievable.

**If something breaks, say this to Cursor:**
```
The Review & Decision UI failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 2: Auto-Apply
**What this phase does:** Implement functionality for users to automatically apply to jobs when approved.

**Say this to Cursor:**
```
Build the Auto-Apply feature that allows users to submit job applications programmatically via supported APIs (Greenhouse, Lever) or generate a manual application package. Use Azure Functions for backend logic.
```

**How to verify it worked:**
- [ ] Users can submit applications directly from the job match interface.
- [ ] The application status is tracked and retrievable.
- [ ] Manual application packages are generated correctly when needed.

**If something breaks, say this to Cursor:**
```
The Auto-Apply feature failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 3: Settings
**What this phase does:** Create a settings interface for users to customize their matching preferences and email connections.

**Say this to Cursor:**
```
Develop a Settings interface that allows users to adjust their AI match threshold, connect their Microsoft 365 email, and toggle job source integrations. Use Azure Cosmos DB to persist settings.
```

**How to verify it worked:**
- [ ] Users can adjust their match threshold.
- [ ] Users can connect their Microsoft 365 email account.
- [ ] Settings persist across sessions.

**If something breaks, say this to Cursor:**
```
The Settings feature failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 4: Resume Management
**What this phase does:** Enable users to upload, parse, and manage their resumes.

**Say this to Cursor:**
```
Implement the Resume Management feature that allows users to upload resumes, parse them into a structured schema, and manage a library of resumes. Use Azure Blob Storage for file storage and Azure Functions for parsing.
```

**How to verify it worked:**
- [ ] Users can upload resumes in PDF/DOCX format.
- [ ] Resumes are parsed correctly into a structured format.
- [ ] Users can edit and manage their resume library.

**If something breaks, say this to Cursor:**
```
The Resume Management feature failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 5: Job Source Integration
**What this phase does:** Integrate with job posting sources to fetch and manage job postings.

**Say this to Cursor:**
```
Build the Job Source Integration feature to fetch job postings from Greenhouse and Lever, ensuring deduplication and compliance with rate limits. Use Azure Functions for the backend logic.
```

**How to verify it worked:**
- [ ] Job postings are fetched and displayed without duplicates.
- [ ] The system respects rate limits and handles errors gracefully.
- [ ] Users can refresh the job postings list on demand.

**If something breaks, say this to Cursor:**
```
The Job Source Integration feature failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 6: Matching & Ranking
**What this phase does:** Implement AI-driven matching between resumes and job postings.

**Say this to Cursor:**
```
Create the Matching & Ranking feature that computes match percentages between resumes and job postings using AI. Store the results in Azure Cosmos DB and provide a summary for users.
```

**How to verify it worked:**
- [ ] Users can see match percentages and summaries for job postings.
- [ ] The matching logic works as expected based on user-configurable thresholds.
- [ ] Results are stored and retrievable for future reference.

**If something breaks, say this to Cursor:**
```
The Matching & Ranking feature failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 7: Email Ingestion & Reply
**What this phase does:** Enable users to ingest emails related to job applications and reply within the app.

**Say this to Cursor:**
```
Implement the Email Ingestion & Reply feature that pulls relevant emails from Microsoft Graph and allows users to reply directly from AJAS. Ensure proper linking to job postings and applications.
```

**How to verify it worked:**
- [ ] Users can view and reply to emails related to job applications.
- [ ] Emails are correctly linked to job postings and applications.
- [ ] The reply functionality works with templates and AI suggestions.

**If something breaks, say this to Cursor:**
```
The Email Ingestion & Reply feature failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 8: Learning Loop
**What this phase does:** Implement a learning mechanism to adapt the matching algorithm based on user feedback.

**Say this to Cursor:**
```
Create the Learning Loop feature that captures user decisions on job matches and adjusts the matching algorithm accordingly. Store user feedback in Azure Cosmos DB for future tuning.
```

**How to verify it worked:**
- [ ] User feedback is captured and stored correctly.
- [ ] The matching algorithm adapts based on user decisions over time.
- [ ] Users can see how their feedback influences future matches.

**If something breaks, say this to Cursor:**
```
The Learning Loop feature failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Final Phase: Testing & Polish
**Say this to Cursor:**
```
Review the entire codebase. Fix any TypeScript errors, broken imports, or missing connections between features. Make sure all features from the .codespring/PRDs/ folder are implemented.
```

**How to verify the full app works:**
- [ ] All features are accessible and functional without errors.
- [ ] The application can handle user interactions smoothly.
- [ ] Data flows correctly between features (e.g., resumes, job matches, email replies).
- [ ] No TypeScript errors are present in the terminal.
- [ ] The application meets the requirements outlined in the PRDs.