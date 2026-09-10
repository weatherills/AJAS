# AI Job Application System (AJAS) — Cursor Runbook

> Keep this file open while building. Follow phases in order. Complete each phase before starting the next.

## How to use this runbook
1. Open Cursor IDE in your project folder
2. Open the Chat panel (Cmd+L)
3. For each phase: paste the "Say this to Cursor" prompt, wait for Cursor to finish, then run the verification steps
4. Only move to the next phase when verification passes

## Project Overview
The AI Job Application System (AJAS) is designed to streamline the job application process for job seekers by leveraging AI to match resumes with job postings. It provides features such as resume management, job source integration, and automated application submission to enhance the job search experience.

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
**What this phase does:** Build a user interface for reviewing AI-generated job matches, allowing users to approve or reject them with comments.

**Say this to Cursor:**
```
Implement the Review & Decision UI as described in the frontend PRD. Use React and TypeScript to create a list view for job matches, with options to approve/reject and add comments. Ensure it connects to the backend APIs for match details.
```

**How to verify it worked:**
- [ ] Users can view a list of job matches with summaries and scores
- [ ] Users can approve or reject matches and add comments
- [ ] The UI updates correctly based on user actions

**If something breaks, say this to Cursor:**
```
The Review & Decision UI phase failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 2: Auto-Apply
**What this phase does:** Enable users to automatically apply to job postings that they approve.

**Say this to Cursor:**
```
Build the Auto-Apply feature as outlined in the frontend PRD. Implement functionality to auto-fill and submit applications via Greenhouse and Lever APIs, and create a manual application package for unsupported sources.
```

**How to verify it worked:**
- [ ] Users can submit applications directly from the job match UI
- [ ] Successful submissions are tracked with status updates
- [ ] Manual application packages are generated correctly when needed

**If something breaks, say this to Cursor:**
```
The Auto-Apply phase failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 3: Settings
**What this phase does:** Create a settings interface for users to configure their match threshold, email connections, and job source toggles.

**Say this to Cursor:**
```
Implement the Settings feature as described in the frontend PRD. Allow users to adjust their AI match threshold, connect to Microsoft 365 for email ingestion, and toggle job source integrations.
```

**How to verify it worked:**
- [ ] Users can adjust the match threshold and see changes reflected in job matches
- [ ] Users can connect their Microsoft 365 account successfully
- [ ] Users can enable or disable job source integrations

**If something breaks, say this to Cursor:**
```
The Settings phase failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 4: Resume Management
**What this phase does:** Allow users to upload, parse, and manage their resumes.

**Say this to Cursor:**
```
Build the Resume Management feature as outlined in the frontend PRD. Implement functionality for users to upload resumes, parse them into a structured format, and manage their resume library.
```

**How to verify it worked:**
- [ ] Users can upload resumes and see them parsed into a structured format
- [ ] Users can edit parsed fields and select an active resume for applications
- [ ] The resume library displays all uploaded resumes correctly

**If something breaks, say this to Cursor:**
```
The Resume Management phase failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 5: Job Source Integration
**What this phase does:** Integrate with job sources like Greenhouse and Lever to fetch job postings.

**Say this to Cursor:**
```
Implement the Job Source Integration feature as described in the backend PRD. Set up a system to periodically fetch job postings from Greenhouse and Lever, ensuring deduplication and compliance with rate limits.
```

**How to verify it worked:**
- [ ] Job postings are fetched and displayed in the job feed without duplicates
- [ ] The system respects rate limits and handles errors gracefully
- [ ] Users can filter job postings by source

**If something breaks, say this to Cursor:**
```
The Job Source Integration phase failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 6: Matching & Ranking
**What this phase does:** Implement AI-driven matching between resumes and job postings.

**Say this to Cursor:**
```
Build the Matching & Ranking feature as described in the backend PRD. Implement the logic to calculate match percentages between resumes and job postings, and provide a rationale for the scores.
```

**How to verify it worked:**
- [ ] Match percentages are calculated and displayed for each job posting
- [ ] Users can see a brief explanation for each match score
- [ ] Users can configure their match threshold to filter results

**If something breaks, say this to Cursor:**
```
The Matching & Ranking phase failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 7: Email Ingestion & Reply
**What this phase does:** Enable users to ingest relevant emails and reply to them within the app.

**Say this to Cursor:**
```
Implement the Email Ingestion & Reply feature as described in the frontend PRD. Set up integration with Microsoft Graph to pull emails and allow users to reply directly from AJAS.
```

**How to verify it worked:**
- [ ] Users can see relevant emails linked to job postings
- [ ] Users can reply to emails using templates and AI suggestions
- [ ] All email interactions are logged correctly

**If something breaks, say this to Cursor:**
```
The Email Ingestion & Reply phase failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Phase 8: Learning Loop
**What this phase does:** Implement a feedback system to learn from user decisions on job matches.

**Say this to Cursor:**
```
Build the Learning Loop feature as described in the backend PRD. Capture user feedback on job matches and adjust the matching algorithm based on this feedback over time.
```

**How to verify it worked:**
- [ ] User decisions on job matches are logged and used to adjust future recommendations
- [ ] Users can see how their feedback influences match scoring
- [ ] The system maintains performance while adapting to user preferences

**If something breaks, say this to Cursor:**
```
The Learning Loop phase failed with this error: [paste error here]. Fix it without changing other phases.
```

---

## Final Phase: Testing & Polish
**Say this to Cursor:**
```
Review the entire codebase. Fix any TypeScript errors, broken imports, or missing connections between features. Make sure all features from the .codespring/PRDs/ folder are implemented.
```

**How to verify the full app works:**
- [ ] All features are accessible and function as expected
- [ ] No TypeScript errors in the terminal
- [ ] The application runs smoothly without performance issues
- [ ] Users can complete the job application process from start to finish
- [ ] All integrations (email, job sources) work without errors