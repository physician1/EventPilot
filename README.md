# EventPilot

Team and project: EventPilot  
Members: Enock Okorno Ayiku and Haley Wodarczyk

EventPilot is a local event-planning prototype with live, cited web research and a separate fictional Boston rehearsal mode. React/Vite provides the interface; FastAPI and SQLite store events and research. Live research uses the OpenAI Responses API with web search. The live path is a single research agent, not an independent planner/critic team.

## Windows setup

Install Python 3.11 or newer and a current Node.js LTS release. Extract this folder, open PowerShell in it, then run each line:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
Copy-Item .env.example .env
notepad .env
```

For live research, enter your own OPENAI_API_KEY in .env, save and close Notepad. Never commit or share this file. Scripted rehearsal requires no key. API access requires connectivity and may incur model/search charges.

The release includes a built frontend. To rebuild from source (required after cloning GitHub, where dist is ignored):

```powershell
cd frontend
npm ci
npm run build -- --configLoader native
cd ..
```

Start the app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Keep PowerShell open. Visit http://127.0.0.1:8000/ . Ctrl+C stops the server. After a source update, rebuild the frontend, restart the server, then press Ctrl+F5 in the browser. If port 8000 is busy, stop your previous server or use --port 8001 and open that port instead.

Default data is eventpilot.sqlite in this folder. Use a backup when moving an existing database. This source package contains no personal events or API credentials. A lingering EVENTPILOT_DB environment variable overrides the default path; check it before using existing data. Do not delete a database merely to resolve a provider error.

## Demo

Create a birthday in Accra, Ghana; June 20, 2027; 18:00; four hours; 40 guests; USD 5,000; indoors. Select Live web search, read the consent, then request a venue, catering and entertainment shortlist with sources and explicit unknowns. Review Agent studio, Overview, Discover and Timeline. A completed report is research, not confirmed availability. To demonstrate offline, create a separate Boston event and select Scripted rehearsal; identify its suppliers as fictional.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run build -- --configLoader native
```

Observed October 24, 2026: 55 backend tests passed, 6 frontend tests passed, production build passed. One Starlette/httpx deprecation warning remains. Automated provider tests mock responses; they do not establish live supplier accuracy or worldwide coverage. See EVALUATION.md.

## Architecture and limitations

backend/main.py: persistence, routes, consent and run control. backend/research.py: live Responses/web-search request and citation extraction. backend/agent.py and planner.py: legacy catalog planner/critic workflow. frontend/src/ResearchReport.jsx: report rendering. livePlan.js: heuristic supplier/timeline projection and budget allocation. LiveOverview.jsx: editable provisional dashboard.

Live mode accepts entered locations without a city allowlist. Search coverage, capacity, availability and costs remain unverified. Rehearsal only covers Boston. Intake supports birthday, wedding and corporate event categories. Budgets are USD; no automatic currency conversion.

Live budget figures are provisional allocations: 70% of the saved budget is distributed across service categories, plus 15% of that subtotal for fees and 10% of the saved budget for contingency. They are not supplier quotes or verified market estimates. Missing suppliers are flagged. Dashboard edits are scoped to an event and research run in browser local storage; they are not synchronized to SQLite. New research starts a new projection. The live shortlist cannot be approved as a priced booking package.

No bookings, payments or external messages are sent. This is a local single-user prototype without production authentication. Consent permits selected event requirements and context to be shared with the provider; free-text preferences can contain personal information. Keep unnecessary personal information out of them. Stop/pause can discard a late response but cannot recall data already sent.

## Submission

Repository: https://github.com/physician1/EventPilot. The repository is public, so reviewers do not need an invitation. Exclude .env, SQLite databases, virtual environments and node_modules. Do not claim this snapshot supplies development commit history. The submission pack includes writing guidance, not AI-generated slides.

## Submission materials

- [Project report (PDF)](submission/EventPilot_Project_Report.pdf)
- [Editable report](submission/EventPilot_Project_Report.md)
- [Presentation and poster writing guide](submission/Presentation_and_Poster_Writing_Guide.md)
- [Demo and submission checklist](submission/Demo_and_Submission_Checklist.md)

Slides and poster must be manually designed to comply with the assignment.
