# AI Job Application System (AJAS) — Cursor Runbook

> Keep this file open while building. Follow phases in order. Complete each phase before starting the next.

## How to use this runbook
1. Open Cursor IDE in your project folder
2. Open the Chat panel (Cmd+L)
3. For each phase: paste the "Say this to Cursor" prompt, wait for Cursor to finish, then run the verification steps
4. Only move to the next phase when verification passes

## Project Overview
The AI Job Application System (AJAS) is designed to streamline the job application process for users by leveraging AI to match resumes with job postings. It allows users to manage their resumes, apply for jobs automatically, and track their application statuses, all in one place.

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
**What this phase does:** Build a user interface for reviewing AI-generated job matches, allowing users to approve or reject them with comments.

**Say this to Cursor:**
```
Implement the Review & Decision UI as described in the PRD. Create a simple interface for users to view job matches, see summaries and suggestions, and make approve/reject decisions with comments. Use Azure Functions for backend APIs.
```

**How to verify it worked:**
- [ ] Users can see a list of job matches with summaries.
- [ ] Users can approve or reject matches and leave comments.
- [ ] Decisions are saved and retrievable.

**If something breaks, say this to Cursor:**
```
The Review & Decision UI feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 2: Auto-Apply
**What this phase does:** Enable users to automatically apply for jobs that they approve directly from the app.

**Say this to Cursor:**
```
Implement the Auto-Apply feature as described in the PRD. Allow users to auto-fill and submit applications for approved jobs via supported APIs (Greenhouse, Lever). Use Azure Functions for backend processing.
```

**How to verify it worked:**
- [ ] Users can auto-apply for jobs with a single click.
- [ ] Application status is tracked and displayed.
- [ ] Users receive feedback on application submissions.

**If something breaks, say this to Cursor:**
```
The Auto-Apply feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 3: Settings
**What this phase does:** Create a settings page for users to adjust their match threshold, email connections, and job source toggles.

**Say this to Cursor:**
```
Build the Settings feature as outlined in the PRD. Allow users to configure their AI match threshold, connect their Microsoft 365 email, and toggle job sources (Greenhouse, Lever). Use Azure Cosmos DB for storing user settings.
```

**How to verify it worked:**
- [ ] Users can adjust their match threshold.
- [ ] Users can connect their Microsoft 365 email.
- [ ] Users can toggle job sources on and off.

**If something breaks, say this to Cursor:**
```
The Settings feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 4: Resume Management
**What this phase does:** Allow users to upload resumes, parse them into a structured format, and manage their resume library.

**Say this to Cursor:**
```
Implement the Resume Management feature as described in the PRD. Users should be able to upload resumes, correct parsing errors, and manage a library of resumes. Use Azure Blob Storage for storing resumes and Azure Functions for parsing.
```

**How to verify it worked:**
- [ ] Users can upload resumes and see them in their library.
- [ ] Users can edit parsed resume fields.
- [ ] Users can select an active resume for applications.

**If something breaks, say this to Cursor:**
```
The Resume Management feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 5: Job Source Integration
**What this phase does:** Integrate with job posting sources (Greenhouse, Lever) to fetch and display job postings.

**Say this to Cursor:**
```
Build the Job Source Integration feature as outlined in the PRD. Fetch job postings from Greenhouse and Lever, normalize and deduplicate them, and display them in the app. Use Azure Functions for the fetching logic.
```

**How to verify it worked:**
- [ ] Users can see a unified list of job postings from both sources.
- [ ] Duplicate postings are removed.
- [ ] Users can refresh the job feed without errors.

**If something breaks, say this to Cursor:**
```
The Job Source Integration feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 6: Matching & Ranking
**What this phase does:** Implement AI-driven matching between resumes and job postings, providing a match percentage and rationale.

**Say this to Cursor:**
```
Implement the Matching & Ranking feature as described in the PRD. Calculate an AI match percentage between resumes and job postings, providing a summary and rationale for the score. Use the AI Matching Service for computations.
```

**How to verify it worked:**
- [ ] Users can see a match percentage for each job posting.
- [ ] Users can view a summary and rationale for the match score.
- [ ] Users can configure a minimum match threshold.

**If something breaks, say this to Cursor:**
```
The Matching & Ranking feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 7: Email Ingestion & Reply
**What this phase does:** Enable users to pull relevant emails from Microsoft Graph and reply to them within the app.

**Say this to Cursor:**
```
Build the Email Ingestion & Reply feature as outlined in the PRD. Users should be able to pull related emails and reply to them directly in the app. Use Microsoft Graph API for email interactions.
```

**How to verify it worked:**
- [ ] Users can see a list of relevant emails linked to job postings.
- [ ] Users can reply to emails from within the app.
- [ ] Email threads are properly linked to job/application records.

**If something breaks, say this to Cursor:**
```
The Email Ingestion & Reply feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 8: Learning Loop
**What this phase does:** Implement a feedback loop to learn from user decisions and adjust matching algorithms accordingly.

**Say this to Cursor:**
```
Implement the Learning Loop feature as described in the PRD. Capture user feedback on job matches and adjust matching weights and thresholds based on their decisions. Ensure this is done without disrupting the user experience.
```

**How to verify it worked:**
- [ ] User decisions are logged and used to adjust future matches.
- [ ] Users can see how their feedback influences the system over time.
- [ ] The system remains responsive and user-friendly.

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
- [ ] No TypeScript errors or warnings are present.
- [ ] Users can seamlessly navigate through the app without issues.
- [ ] All integrations (email, job sources) work correctly.
- [ ] The application performs well under load.