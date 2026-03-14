# CLAUDE.md

Purpose:
This file defines the persistent project context, critical rules, working principles, and safety constraints that Claude must follow when assisting on Fantazia Finance.

Claude must treat this file as the primary and authoritative source of project guidance at the start of every session.

Last updated: 2026-03-13

---

# 0. ABSOLUTE PRIORITY

Claude must protect the integrity of the project.

The main objective is NOT to generate a lot of code quickly.

The main objective is to help Alexandre improve Fantazia Finance safely, coherently, and progressively.

Claude must avoid actions that could:

- break the project structure
- delete important code
- rewrite large parts of the project unnecessarily
- introduce unnecessary complexity
- create inconsistencies between modules
- destroy working functionality during refactors
- replace the current working architecture with a new stack without explicit request

When in doubt, Claude must choose the safest and most conservative path.

---

# 1. PROJECT IDENTITY

Project name:
Fantazia Finance

Fantazia Finance is the core project of the Fantazia ecosystem.

Fantazia Finance is currently a Streamlit-based financial analysis application.

It is designed to help users explore, compare, understand, and analyze financial markets through practical interactive tools.

Fantazia Finance is NOT a financial advisory service.

Fantazia Finance is an analysis and exploration platform.

Core goals of the platform:

- financial market exploration
- stock and asset comparison
- portfolio analysis
- financial dashboards
- market data visualization
- investment research support
- economic and financial understanding

Claude must preserve this identity in all technical and product decisions.

---

# 2. USER CONTEXT

User:
Alexandre

Location:
Belgium

Main interests:
- finance
- investing
- economic analysis
- entrepreneurship
- artificial intelligence
- software development
- building independent digital platforms

Alexandre prefers:
- structured reasoning
- practical solutions
- step-by-step guidance
- modular systems
- realistic implementation plans

Claude should behave like a careful technical collaborator.

---

# 3. CURRENT PROJECT STATE

Fantazia Finance is NOT a blank-slate architecture project.

It is an already functional Streamlit application in active evolution.

The project is currently in an MVP / iterative improvement phase.

This means:

- architecture changes must remain conservative
- working features must be preserved
- refactors must be incremental
- maintainability should improve without destabilizing the app
- migration from local JSON storage toward PostgreSQL / Supabase is in progress or planned

Current objectives:

1. preserve the existing working application
2. improve maintainability progressively
3. stabilize data persistence and database migration
4. keep financial data integrations working
5. expand features without destructive rewrites

Claude must optimize for safe incremental progress first.

---

# 4. CURRENT STATUS

Frontend / App layer

- Streamlit application already implemented
- Fantazia Finance V3.9 branding already present
- interface includes FR/EN translations
- custom visual theme is implemented
- sidebar controls are implemented
- tabs already exist:
  - Dashboard
  - Watchlists
  - Simulator
  - Stock sheet
  - Help
  - Assistant

Authentication

- user signup/login system already implemented
- passwords are hashed with salt
- current local persistence uses users.json

User data features

- watchlists already implemented
- alerts already implemented
- personal notes already implemented
- news subscriptions already implemented

Database

- SQLAlchemy engine setup already present
- DB_URL secret is supported
- database debug check already exists
- one-shot JSON -> PostgreSQL / Supabase migration logic already exists
- current project still contains local JSON persistence and migration compatibility logic

Market data / providers

- Yahoo Finance is currently used
- Twelve Data support exists
- Finnhub support exists
- Polygon support exists for real-time best-effort prices
- Finnhub is used for company news
- Alpha Vantage API key exists in secrets, but should not be assumed to be actively integrated unless confirmed in code

Optional features / utilities

- PDF export support is optional via reportlab
- auto-refresh support is optional
- watermark / branding logic exists

Claude must respect existing functionality and avoid rebuilding components that already exist.

---

# 5. CURRENT FOCUS

Current development priority should be treated as:

- preserve and stabilize the current Streamlit app
- improve code organization without destructive rewrites
- secure migration from JSON-based persistence to PostgreSQL / Supabase
- preserve authentication, watchlists, alerts, notes, and news subscriptions
- improve maintainability of the large monolithic app.py incrementally

Unless Alexandre explicitly asks otherwise, Claude should assume that the current focus is:
1. stabilization
2. data persistence cleanup
3. safe modularization
4. targeted feature improvements

Claude should align suggestions with this focus and avoid unnecessary scope expansion.

---

# 6. HIGH LEVEL PRODUCT VISION

Fantazia Finance should evolve into a modular financial analysis platform.

Possible platform modules include:

- stock comparison tools
- portfolio analytics
- financial dashboards
- company analysis tools
- market visualization tools
- economic data exploration
- research interfaces
- financial metrics and insights
- user-linked watchlists, alerts, notes, and followed news

Claude must design solutions that allow progressive expansion.

---

# 7. TECHNICAL DIRECTION

Current real stack:

Frontend / App UI
- Streamlit

Core language
- Python

Data handling / analytics
- pandas
- numpy

Visualization
- plotly.express

Market data and APIs
- yfinance
- requests
- Twelve Data
- Finnhub
- Polygon
- possible Alpha Vantage secret support

Persistence
- local JSON files currently exist
- SQLAlchemy engine already exists
- PostgreSQL / Supabase migration path already exists

Optional utilities
- reportlab for PDF export
- streamlit_autorefresh if installed

Important architecture reality:

This project is currently a single large Streamlit application centered around app.py.

Claude must NOT assume the app is already separated into Next.js, FastAPI, or microservices.

Claude may propose future modularization, but must treat the current architecture as:

- a working Streamlit monolith
- with evolving persistence
- with multiple integrated features already present

---

# 8. EXTERNAL DATA SOURCES

Claude must respect the external services already chosen or already present in the code.

Current known providers:

Primary historical market data:
- Yahoo Finance (yfinance)

Fallback / additional historical data:
- Twelve Data
- Finnhub

Real-time best-effort prices:
- Polygon

Company / stock news:
- Finnhub

Secrets currently present in code:
- TWELVE_API_KEY
- FINNHUB_API_KEY
- ALPHAVANTAGE_API_KEY
- POLYGON_API_KEY
- DB_URL

Persistence / database:
- local JSON files currently exist
- PostgreSQL / Supabase migration path exists through DB_URL + SQLAlchemy

Claude should not propose replacing these providers without clear justification.

Claude should not assume Alpha Vantage is actively used unless verified in code.

---

# 9. OUT OF SCOPE FOR MVP

The following features are out of scope unless Alexandre explicitly requests them:

- full rewrite to another stack
- advanced authentication / identity platform migration
- complex user permission systems
- real-time websocket infrastructure
- mobile applications
- microservices architecture
- enterprise-level infrastructure
- complex notification systems
- large-scale backend/API redesign
- unnecessary cloud architecture redesign

Claude must avoid introducing these features during MVP stabilization and evolution.

---

# 10. CRITICAL ARCHITECTURE RULES

Claude must follow these rules strictly:

1. Do not tightly couple unrelated modules.

2. Do not mix display logic, business logic, and persistence even more than they already are.

3. When improving structure, move incrementally toward modularization.

4. Do not rewrite the whole app just because the file is large.

5. Do not introduce frameworks without strong justification.

6. Avoid aggressive refactoring.

7. Avoid renaming important files unnecessarily.

8. Do not silently change data models.

9. Do not remove working behavior.

10. Prefer incremental improvements over destructive rewrites.

11. Preserve compatibility with current JSON-backed behavior unless migration is explicitly completed.

---

# 11. SAFETY RULES FOR CODE MODIFICATION

Before modifying code, Claude must think:

1. What exists currently?
2. What already works?
3. What is the smallest safe change?
4. Could this break anything?
5. Is there a safer alternative?

Claude must prefer:

- additive changes
- localized edits
- preserving interfaces
- backward compatibility
- refactoring by extraction, not by rewrite

Avoid:

- rewriting entire files unnecessarily
- style-only refactors
- multi-file edits when not required
- deleting code without explanation
- replacing working JSON logic before DB logic is fully validated

---

# 12. MINIMAL EDIT RULE

Claude must avoid rewriting entire files when only small changes are required.

Preferred approach:

1. identify the smallest possible change
2. modify only necessary lines or sections
3. preserve remaining code unchanged

Full file rewrites should be rare.

If app.py must be improved, prefer:
- extracting helper functions
- extracting utility modules
- isolating persistence logic
- isolating API/provider logic
- isolating UI sections gradually

Do NOT perform a full app.py rewrite unless explicitly requested.

---

# 13. DEVELOPMENT PRINCIPLES

Claude must prioritize:

1. simplicity
2. readability
3. maintainability
4. modularity
5. working implementations
6. safe iteration

Avoid:

- unnecessary complexity
- premature optimization
- theoretical over-design
- architectural rewrites without product need

---

# 14. CODING STANDARDS

Code should:

- prioritize clarity
- use descriptive naming
- keep functions focused
- keep modules reasonably small when extracting code
- avoid unnecessary abstractions

Claude should avoid:

- overly dense code
- magical abstractions
- deeply nested logic
- hidden side effects

When working in this project, Claude should prefer:
- practical Python
- explicit data flow
- readable Streamlit logic
- predictable persistence behavior

---

# 15. DEPENDENCY RULES

Dependencies must be introduced carefully.

Before suggesting one, Claude must consider:

- necessity
- maintenance cost
- stability
- compatibility with the current Streamlit-based stack

Avoid unnecessary libraries.

Do not introduce dependencies just to compensate for weak code organization if the issue can be solved with plain Python refactoring.

---

# 16. DATABASE SAFETY RULE

Database schema and persistence changes must be handled conservatively.

Claude must avoid:

- deleting tables
- renaming tables without migrations
- removing used columns
- changing column types recklessly
- breaking compatibility with current user data

Preferred approach:

- preserve current data
- add migrations carefully
- keep JSON compatibility while migration is incomplete
- treat database migration as a high-risk area

The JSON -> DB migration logic already exists and should be preserved carefully until migration is fully completed.

---

# 17. DATA PERSISTENCE RULE

Fantazia Finance currently uses both:
- local JSON persistence
- emerging database persistence / migration logic

Claude must understand that persistence is currently transitional.

This means:
- local JSON files are still part of the real system
- migration helpers are not dead code unless Alexandre confirms migration is fully done
- user accounts, watchlists, alerts, notes, and news subscriptions are sensitive persistence features

Do not remove transitional logic casually.

---

# 18. API / PROVIDER DESIGN RULES

Provider integrations should be:

- simple
- predictable
- easy to debug
- resilient to missing API keys
- resilient to provider failures

Avoid:

- overcomplicated provider orchestration
- silent provider replacement
- hiding source provenance from the user

Preserve the current logic where the source can vary per ticker and fallback behavior exists.

---

# 19. FINANCIAL INFORMATION RULES

Claude must:

- avoid fabricating financial data
- avoid inventing sources
- avoid unsupported claims
- avoid giving financial advice

Fantazia Finance must remain:
- an analysis platform
- a research platform
- a data exploration platform

It must NOT become:
- a personal investment advisor
- a system making unsupported promises
- a platform presenting invented market facts

---

# 20. AI FEATURE RULES

AI features should support:

- summarization
- financial concept explanations
- structured analysis
- information extraction
- in-app assistance / FAQ-style guidance

AI features must NOT:

- fabricate financial data
- invent market facts
- provide financial advice
- pretend certainty where uncertainty exists

If AI is added or extended, keep generated output clearly separated from sourced financial data.

---

# 21. WORKFLOW EXPECTATIONS

Claude should assist with:

- architecture review
- safe refactoring
- Streamlit app organization
- persistence cleanup
- database migration safety
- provider integration cleanup
- bug fixing
- targeted feature improvements

Claude should behave like a careful senior technical collaborator.

Claude should NOT behave like a reckless rewrite agent.

---

# 22. KNOWN CONSTRAINTS

Current constraints include:

- MVP priority
- avoid destructive refactors
- preserve working Streamlit behavior
- avoid unnecessary schema changes
- keep persistence stable
- maintain support for existing user features
- large monolithic app.py must be improved gradually, not explosively

Claude must respect these constraints.

---

# 23. SUCCESS CRITERIA

Claude is successful when it helps Alexandre produce:

- working code
- understandable architecture
- stable system evolution
- maintainable platform
- safer persistence
- gradual modularization without breaking the app

Claude is NOT successful if it produces:

- fragile architecture
- unnecessary rewrites
- broken functionality
- excessive complexity
- stack drift away from the real current project
- loss of user data or persistence compatibility

---

# FINAL REMINDER

Protect the project.

Fantazia Finance is already a real working Streamlit application.

Improve it progressively.

Favor small safe improvements.

Do not destroy working systems.

When uncertain, choose the smallest safe change or ask Alexandre.

---

END OF FILE