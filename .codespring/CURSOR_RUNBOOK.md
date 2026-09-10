# AI Job Application System (AJAS) — Cursor Runbook

> Keep this file open while building. Follow phases in order. Complete each phase before starting the next.

## How to use this runbook
1. Open Cursor IDE in your project folder
2. Open the Chat panel (Cmd+L)
3. For each phase: paste the "Say this to Cursor" prompt, wait for Cursor to finish, then run the verification steps
4. Only move to the next phase when verification passes

## Project Overview
The AI Job Application System (AJAS) is designed to streamline the job application process for job seekers by leveraging AI to match resumes with job postings. It provides features such as resume management, job source integration, and an auto-apply function, making the application process efficient and user-friendly.

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
Create a Review & Decision UI that allows users to review job matches, view summaries, and make approve/reject decisions with comments. Use React and TypeScript for the frontend.
```

**How to verify it worked:**
- [ ] Users can see a list of job matches with summaries.
- [ ] Users can approve or reject matches and leave comments.
- [ ] The decisions are saved and can be viewed later.

**If something breaks, say this to Cursor:**
```
The Review & Decision UI failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 2: Auto-Apply
**What this phase does:** Implement the auto-apply feature that allows users to submit job applications automatically for approved matches.

**Say this to Cursor:**
```
Build the Auto-Apply feature that enables users to submit applications directly from the Review & Decision UI for approved jobs. Ensure it integrates with Greenhouse and Lever APIs.
```

**How to verify it worked:**
- [ ] Users can submit applications for approved jobs.
- [ ] The application status is tracked and displayed.
- [ ] Users receive confirmation of their submissions.

**If something breaks, say this to Cursor:**
```
The Auto-Apply feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 3: Settings
**What this phase does:** Create a settings page for users to configure their match threshold, email connections, and job source toggles.

**Say this to Cursor:**
```
Develop a Settings page that allows users to adjust their AI match threshold, connect their Microsoft 365 email, and toggle job source integrations (Greenhouse, Lever).
```

**How to verify it worked:**
- [ ] Users can adjust the match threshold and save changes.
- [ ] Users can connect their Microsoft 365 email account.
- [ ] Users can enable or disable job source integrations.

**If something breaks, say this to Cursor:**
```
The Settings feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 4: Resume Management
**What this phase does:** Implement the resume management system, allowing users to upload, parse, and manage their resumes.

**Say this to Cursor:**
```
Create the Resume Management feature that allows users to upload resumes (PDF/DOCX), parse them into a structured schema, and manage their resume library. Ensure it supports editing and selecting active resumes.
```

**How to verify it worked:**
- [ ] Users can upload resumes and see them listed in their library.
- [ ] Users can edit parsed resume fields.
- [ ] Users can select an active resume for job applications.

**If something breaks, say this to Cursor:**
```
The Resume Management feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 5: Job Source Integration
**What this phase does:** Integrate with job sources (Greenhouse and Lever) to fetch job postings.

**Say this to Cursor:**
```
Build the Job Source Integration feature that fetches job postings from Greenhouse and Lever, normalizes the data, and ensures no duplicates are shown to users.
```

**How to verify it worked:**
- [ ] Users can see a list of job postings from both sources.
- [ ] No duplicate job postings are displayed.
- [ ] The job postings refresh correctly without errors.

**If something breaks, say this to Cursor:**
```
The Job Source Integration feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 6: Matching & Ranking
**What this phase does:** Implement the AI-driven matching and ranking system for resumes against job postings.

**Say this to Cursor:**
```
Create the Matching & Ranking feature that computes an AI match percentage between resumes and job postings, providing a summary and rationale for the scores.
```

**How to verify it worked:**
- [ ] Users can see match percentages for their resumes against job postings.
- [ ] Summaries and rationales are provided for each match.
- [ ] Users can configure the minimum match threshold.

**If something breaks, say this to Cursor:**
```
The Matching & Ranking feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 7: Email Ingestion & Reply
**What this phase does:** Enable users to ingest emails related to job applications and reply to them within the app.

**Say this to Cursor:**
```
Build the Email Ingestion & Reply feature that pulls relevant emails via Microsoft Graph and allows users to reply directly from the app with templates and AI suggestions.
```

**How to verify it worked:**
- [ ] Users can see a list of relevant emails linked to job applications.
- [ ] Users can reply to emails using templates and AI suggestions.
- [ ] All email interactions are logged correctly.

**If something breaks, say this to Cursor:**
```
The Email Ingestion & Reply feature failed with this error: [paste error here]. Fix it without changing other features.
```

---

## Phase 8: Learning Loop
**What this phase does:** Implement a learning loop that captures user feedback to improve future job matches.

**Say this to Cursor:**
```
Create the Learning Loop feature that captures user decisions on job matches and adjusts the AI's matching weights and thresholds based on this feedback.
```

**How to verify it worked:**
- [ ] User decisions on job matches are logged and used to adjust future recommendations.
- [ ] Users can see how their feedback impacts match quality over time.
- [ ] The system adapts to user preferences without manual intervention.

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
- [ ] All features are accessible and functional without errors.
- [ ] Users can complete the job application process from start to finish.
- [ ] The app performs well without significant delays or crashes.
- [ ] All user settings persist correctly across sessions.
- [ ] The system accurately reflects user feedback in job matching.