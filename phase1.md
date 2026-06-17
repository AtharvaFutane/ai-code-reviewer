# Phase 1 — Complete Reference Guide (For Your Learning)

> **What was Phase 1 about?**  
> Setting up the entire project foundation — like building the skeleton of a house before adding walls and rooms. We created the folder structure, installed all the tools we need, connected to the AI (Groq), and verified everything works.

---

## 📁 What Files Did We Create & Why?

Here's every single file we created, what it does, and why it exists:

---

### 1. `.gitignore` — "Don't track these files"

**What it is**: A special file that tells Git (version control) to IGNORE certain files/folders when you push to GitHub.

**Why we need it**: Some files should NEVER go to GitHub:
- `.env` — contains your secret API key (if someone gets this, they can use YOUR Groq account)
- `__pycache__/` — Python auto-generates these cached files, they're junk
- `venv/` — your virtual environment is huge (hundreds of MB) and each computer creates its own

**What's inside**:
```
.env              ← Your secret API key file (NEVER push this!)
__pycache__/      ← Python's auto-generated cache files
*.pyc             ← Compiled Python files (auto-generated)
.venv/            ← Virtual environment folder
venv/             ← Virtual environment folder (alternate name)
*.egg-info/       ← Package metadata (auto-generated)
```

**Think of it like**: A bouncer at a club door — these files are on the "do not enter" list for GitHub.

---

### 2. `.env.example` — "Template for secrets"

**What it is**: A TEMPLATE showing what environment variables your app needs, but with FAKE values.

**Why we need it**: When someone clones your repo from GitHub, they won't have your `.env` (it's gitignored). But they need to know WHAT variables to set. So `.env.example` says "here are the keys you need, go fill in your own values."

**Key variables explained**:
```bash
GROQ_API_KEY=gsk_xxx...          # Your Groq AI key (get free at console.groq.com)
GROQ_PRIMARY_MODEL=llama-3.3-70b-versatile   # Which AI model to use for reviewing code
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant     # Backup model if primary fails
GROQ_SUMMARY_MODEL=gemma2-9b-it              # Lighter model for generating summaries
APP_HOST=0.0.0.0                 # Listen on all network interfaces
APP_PORT=8000                    # Which port the server runs on
LLM_TEMPERATURE=0                # 0 = deterministic (same input = same output every time)
MAX_FINDINGS_PER_AGENT=10        # Don't return more than 10 issues per agent
```

**This file IS pushed to GitHub** (it has no real secrets, just placeholder values).

---

### 3. `.env` — "Your actual secrets"

**What it is**: The REAL version of `.env.example` with YOUR actual Groq API key.

**Why it's separate**: You NEVER want your real API key on GitHub. If someone finds it, they can:
- Use your API quota (you get rate-limited)
- Run up charges on paid tiers
- Impersonate your account

**This file is NOT pushed to GitHub** (`.gitignore` blocks it).

---

### 4. `requirements.txt` — "Shopping list of Python packages"

**What it is**: Lists every external Python library our project needs, with specific version numbers.

**Why version numbers matter**: If you just say "install fastapi", pip might install version 1.0 today and version 2.0 tomorrow — and version 2.0 might break your code. Pinning versions means "install EXACTLY this version" so it works the same for everyone.

**Each package explained**:
```
fastapi==0.111.0          # The web framework — handles HTTP requests, builds our API
uvicorn[standard]==0.29.0 # The server that RUNS FastAPI (like how a browser runs HTML)
langgraph==0.2.14         # LangGraph — orchestrates our 5 AI agents in parallel
langchain>=0.2.6,<0.3     # LangChain — toolkit for working with LLMs (AI models)
langchain-groq>=0.1.6     # Connector between LangChain and Groq's API
langchain-core>=0.2.27    # Core building blocks of LangChain
pydantic>=2.7.4           # Data validation — ensures our JSON has the right shape
python-dotenv==1.0.1      # Reads the .env file and loads variables into the app
httpx==0.27.0             # HTTP client — used by run_reviews.py to call our API
tenacity==8.3.0           # Retry logic — if Groq fails, try again automatically
```

**What happened with versions**: The blueprint originally specified exact versions that were incompatible with each other (dependency conflict). We had to relax some pins:
- `pydantic==2.7.1` → `pydantic>=2.7.4` (langchain-core on Python 3.12 needs ≥2.7.4)
- `langchain-core==0.2.11` → `langchain-core>=0.2.27` (langgraph 0.2.14 needs ≥0.2.27)

---

### 5. `main.py` — "The front door of the application"

**What it is**: The entry point — this is the file you run to start the entire server.

**How it works, line by line**:

```python
from dotenv import load_dotenv
load_dotenv()  # ← THIS MUST BE FIRST! Reads .env file and loads variables
               #    into the computer's environment so other code can access them
```

**Why `load_dotenv()` must be first**: If any module tries to read `os.getenv("GROQ_API_KEY")` BEFORE `load_dotenv()` runs, it gets `None` (empty) because the variables haven't been loaded yet. So we load them BEFORE importing anything else.

```python
app = FastAPI(
    title="Infravox AI Code Reviewer",
    description="LangGraph-powered multi-agent PR diff reviewer",
    version="1.0.0",
)
```

This creates the FastAPI "app" — think of it as creating a restaurant. The `title` and `description` show up in the auto-generated API docs at `http://localhost:8000/docs`.

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

**CORS** = Cross-Origin Resource Sharing. By default, browsers block requests from one website to another (security). This middleware says "allow requests from ANYWHERE" — useful for development/demos.

```python
app.include_router(router)  # ← Plugs in all our API endpoints (routes)
```

```python
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

**`if __name__ == "__main__"`**: This runs only when you execute `python main.py` directly (not when it's imported by another file).

**`uvicorn.run()`**: Starts the web server. `reload=True` means it auto-restarts when you change code (great for development).

**To start the server**: `uvicorn main:app --reload` (this is the one command you'll use most).

---

### 6. `app/__init__.py` — "This folder is a Python package"

**What it is**: An empty file that tells Python "this `app/` folder is a package you can import from."

**Why it exists**: Without this file, Python wouldn't recognize `app` as a package, and `from app.api.models import ReviewRequest` would fail with `ModuleNotFoundError`.

**Every subfolder also needs one**: That's why we also created:
- `app/api/__init__.py`
- `app/graph/__init__.py`
- `app/llm/__init__.py`
- `app/storage/__init__.py`

---

### 7. `app/api/models.py` — "The data contracts"

**What it is**: Defines the EXACT shape of data going in and out of our API using **Pydantic models**.

**What is Pydantic?**: A library that lets you define "this data MUST look like THIS":
```python
class ReviewRequest(BaseModel):
    diff: str         # MUST be a string
    language: str     # MUST be a string
    context: Optional[str] = None  # Optional — can be missing or null
```

If someone sends `{"diff": 123, "language": "python"}`, Pydantic rejects it because `diff` should be a string, not a number. This prevents bugs caused by bad input.

**The models we defined**:

| Model | Purpose | Used Where |
|-------|---------|-----------|
| `ReviewRequest` | What the user SENDS to our API | `POST /review` request body |
| `Finding` | A single code issue found by an agent | Inside ReviewReport |
| `ReviewReport` | The FULL review result | `POST /review` response, `GET /review/{id}` response |
| `ReviewSummary` | A lightweight summary | `GET /reviews` list response |
| `HealthResponse` | Server status info | `GET /health` response |

**Key types explained**:
```python
SeverityLevel = Literal["critical", "high", "medium", "low"]
```
This means severity can ONLY be one of these 4 values. If the LLM returns "CRITICAL" (uppercase) or "severe", Pydantic rejects it. This enforces consistency.

```python
review_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
```
`uuid.uuid4()` generates a random unique ID like `"550e8400-e29b-41d4-a716-446655440000"`. Every review gets a unique one automatically.

**This is a "fixed contract"** — the assignment evaluates us on this exact schema, so we NEVER change field names or types.

---

### 8. `app/graph/state.py` — "The shared whiteboard"

**What it is**: Defines the data structure that flows through our entire LangGraph pipeline — every agent reads from it and writes to it.

**Analogy**: Imagine 5 doctors examining the same patient file. The file has sections for each doctor to write their findings. `ReviewState` is that file.

```python
class ReviewState(TypedDict):
    # INPUT — set at the start, never changed
    diff: str                    # The code diff to review
    language: str                # "python", "javascript", etc.
    context: Optional[str]       # Optional description of the PR
    start_time: float            # When we started (for timing)

    # AGENT OUTPUTS — each agent writes to its OWN field only
    security_findings: List[RawFinding]       # Security agent writes here
    performance_findings: List[RawFinding]    # Performance agent writes here
    correctness_findings: List[RawFinding]    # Correctness agent writes here
    style_findings: List[RawFinding]          # Style agent writes here
    test_coverage_findings: List[RawFinding]  # Test coverage agent writes here

    # MERGE OUTPUT — written by merge node at the end
    review_report: Optional[Dict]   # The final combined report
```

**Why TypedDict?**: LangGraph requires the state to be a `TypedDict` (a dictionary with predefined keys and types). It's like a form with fixed fields — you can't add random new fields.

**Why each agent has its OWN field**: If all 5 agents tried to write to the same `findings` list simultaneously, they'd overwrite each other (a "race condition"). By giving each agent its own field (`security_findings`, `performance_findings`, etc.), they can run in parallel without conflicts.

**`make_initial_state()`**: A helper function that creates a fresh state with all lists empty and the timer started. Called once per review request.

---

### 9. `app/llm/client.py` — "The AI phone line"

**What it is**: Handles ALL communication with Groq's LLM API. Every agent calls through this file.

**Three main functions**:

#### `get_llm()` — Create a Groq client
```python
def get_llm(model_override=None):
    model = model_override or os.getenv("GROQ_PRIMARY_MODEL", "llama-3.3-70b-versatile")
    return ChatGroq(model=model, temperature=0, api_key=os.getenv("GROQ_API_KEY"))
```
- `temperature=0` means the AI gives the SAME answer every time for the same input (deterministic). Important for consistent code reviews.
- `model_override` lets us use a different model for the summary step (a lighter/cheaper one).

#### `invoke_llm_with_retry()` — Call the AI with automatic retries
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
async def invoke_llm_with_retry(llm, system_prompt, user_message):
```
- **Why retries?**: Groq's free tier has rate limits. If you send too many requests at once, it returns a 429 (too many requests) error. Instead of crashing, we wait and try again.
- **Exponential backoff**: Wait 2s, then 4s, then 8s between retries. This gives the API time to recover.
- **`async`**: This function is asynchronous — it doesn't block the server while waiting for Groq to respond.

#### `extract_json_from_response()` — Parse AI output safely
```python
def extract_json_from_response(text):
```
**Why this is needed**: We ask the AI to return JSON like `{"findings": [...]}`. But AI models are unpredictable — sometimes they return:
- Pure JSON ✅ — great, parse it directly
- JSON wrapped in \`\`\`json ... \`\`\` — need to strip the markdown fences
- JSON mixed with explanation text — need to extract just the JSON part
- Complete garbage — return empty `{"findings": []}` instead of crashing

This function tries 4 different parsing strategies and falls back gracefully. **No crash, ever.**

#### `parse_raw_findings()` — Normalize the AI's output
```python
def parse_raw_findings(response_text, category, max_findings=10):
```
- Takes raw AI response, extracts the JSON, normalizes field names
- **Injects the category** (e.g., "security") — the AI doesn't need to know its own category
- **Caps at 10 findings** — prevents one agent from producing 50 findings
- **Skips malformed findings** — if a finding is missing a title or description, it's silently dropped
- **Normalizes severity** — if the AI says "CRITICAL" (uppercase), it becomes "critical" (lowercase)

---

### 10. `app/storage/store.py` — "The filing cabinet"

**What it is**: Stores completed reviews in memory so you can look them up later.

**In-memory means**: The data lives in Python's memory (RAM), NOT in a database. When you restart the server, all reviews are GONE. This is fine for the assignment — they only need "session storage."

```python
class ReviewStore:
    def __init__(self):
        self._store: Dict[str, ReviewReport] = {}   # review_id → full report
        self._meta: Dict[str, str] = {}              # review_id → language
        self._lock = asyncio.Lock()                  # Prevents data corruption
```

**Why `asyncio.Lock()`?**: If two requests arrive at the same time and both try to write to the dictionary simultaneously, the data can get corrupted. A lock says "only ONE operation at a time" — like a bathroom lock, one person at a time.

**Why `asyncio.Lock` and not `threading.Lock`?**: FastAPI uses `asyncio` (asynchronous I/O), not threads. Using the wrong type of lock would either not work or cause deadlocks.

**`review_store = ReviewStore()`**: This creates a SINGLE instance (singleton) that the entire app shares. Every route imports and uses this same object.

---

### 11. `app/api/routes.py` — "The menu of endpoints"

**What it is**: Defines the API endpoints — the URLs your server responds to.

**In Phase 1, we only created `/health`**:
```python
@router.get("/health")
async def health_check():
```
This endpoint:
1. Tries to call Groq with a simple "Reply with: ok" message
2. If Groq responds with "ok", it's connected ✅
3. Returns status, connection status, review count, and model name

**Why `/health` first?**: It's the simplest endpoint and lets us verify Groq is working before building anything complex. The other endpoints (`POST /review`, `GET /review/{id}`, `GET /reviews`) will be added in Phase 3 and 4.

---

### 12. `diffs/` folder — "The test cases"

Contains 3 code diff files that have INTENTIONAL bugs planted in them:

| File | Language | What it contains |
|------|----------|-----------------|
| `diff1_python.txt` | Python | Payment service with SQL injection, hardcoded API key, missing auth |
| `diff2_javascript.txt` | JavaScript | User controller with N+1 queries, plaintext passwords, undefined variables |
| `diff3_typescript.txt` | TypeScript | Order service with infinite loops, sequential awaits, NaN bugs |

These are the "exam questions" — our AI agents need to find as many of these planted bugs as possible.

---

### 13. `reviews/` folder — "Where results go"

Currently empty (just has `.gitkeep` to preserve the folder in Git). After Phase 3, this will contain:
- `diff1_review.json`
- `diff2_review.json`
- `diff3_review.json`

---

## 🔧 What Commands Did We Run & Why?

### 1. Create virtual environment
```bash
python -m venv venv
```
**What this does**: Creates an isolated Python environment in a `venv/` folder. This means packages we install (fastapi, langchain, etc.) go into `venv/`, NOT your system Python. This prevents conflicts with other projects.

**Analogy**: Like having a separate toolbox for each project instead of dumping all tools in one drawer.

### 2. Activate the virtual environment
```bash
.\venv\Scripts\activate    # Windows
source venv/bin/activate   # Mac/Linux
```
**What this does**: Tells your terminal "use Python and pip from the venv folder, not the system-wide ones." You'll see `(venv)` in your terminal prompt when it's active.

### 3. Install dependencies
```bash
pip install -r requirements.txt
```
**What this does**: Reads `requirements.txt` and downloads+installs every package listed. pip also installs their dependencies (packages THEY need), which is why you see way more packages being installed than the 10 we listed.

### 4. Test imports
```bash
python -c "from app.api.models import ReviewReport; print('Models OK')"
```
**What this does**: Runs a one-line Python command to verify all our modules can be imported without errors. If there's a typo, missing import, or circular dependency, it would fail here.

### 5. Start the server
```bash
uvicorn main:app --reload
```
**What this means**:
- `uvicorn` — the ASGI server (runs our FastAPI app)
- `main:app` — "look in `main.py` for the variable called `app`"
- `--reload` — auto-restart when code changes (development convenience)

### 6. Test the health endpoint
```bash
python -c "import httpx; r = httpx.get('http://127.0.0.1:8000/health'); print(r.json())"
```
**What this does**: Makes an HTTP GET request to our running server's `/health` endpoint and prints the response. This confirmed Groq API connectivity.

---

## 🏗️ Folder Structure After Phase 1

```
Infra_Assignment/
├── .env                          ← Your real API key (gitignored)
├── .env.example                  ← Template for others (pushed to GitHub)
├── .gitignore                    ← Files to exclude from Git
├── requirements.txt              ← Python dependencies list
├── main.py                       ← Server entry point (run this!)
│
├── app/                          ← Main application package
│   ├── __init__.py               ← Makes 'app' a Python package
│   │
│   ├── api/                      ← API layer (handles HTTP)
│   │   ├── __init__.py
│   │   ├── models.py             ← Data shapes (Pydantic schemas)
│   │   └── routes.py             ← Endpoint definitions (just /health for now)
│   │
│   ├── graph/                    ← LangGraph pipeline (Phase 2)
│   │   ├── __init__.py
│   │   └── state.py              ← Shared state schema
│   │
│   ├── llm/                      ← AI/LLM communication
│   │   ├── __init__.py
│   │   └── client.py             ← Groq client + retry logic + JSON parsing
│   │
│   └── storage/                  ← Data persistence
│       ├── __init__.py
│       └── store.py              ← In-memory review store
│
├── diffs/                        ← Test diff files (the "exam questions")
│   ├── diff1_python.txt
│   ├── diff2_javascript.txt
│   └── diff3_typescript.txt
│
├── reviews/                      ← Output folder (empty for now)
│   └── .gitkeep
│
└── venv/                         ← Virtual environment (gitignored)
```

---

## 🧠 Key Concepts Explained

### What is FastAPI?
A modern Python web framework for building APIs (Application Programming Interfaces). An API is like a waiter in a restaurant — the client (browser, script, Postman) sends a request (order), the API processes it (kitchen), and returns a response (food).

FastAPI is special because:
- It auto-generates documentation at `/docs` (try opening `http://localhost:8000/docs` in your browser!)
- It uses Pydantic for automatic request validation
- It's async-native (handles many requests simultaneously)

### What is LangGraph?
A framework for building AI agent workflows as **graphs** (nodes connected by edges). In our case:
- **Nodes** = Functions (5 reviewer agents + 1 merge node)
- **Edges** = Data flow (START → agents → merge → END)
- **State** = Shared data that flows through the graph

LangGraph handles the parallel execution for us — we just say "run these 5 nodes simultaneously" and it does it.

### What is Groq?
A cloud AI service that runs LLM (Large Language Model) inference VERY fast. We send it a prompt ("review this code for security issues") and it returns a response. The free tier gives us access to models like `llama-3.3-70b-versatile`.

### What is async/await?
Normal (synchronous) code runs one line at a time:
```python
result1 = call_groq()    # Wait 3 seconds...
result2 = call_groq()    # Wait 3 more seconds...
# Total: 6 seconds
```

Async code can start multiple operations and wait for all of them:
```python
result1, result2 = await asyncio.gather(call_groq(), call_groq())
# Total: ~3 seconds (both run simultaneously!)
```

This is why our 5 agents take ~8 seconds total instead of ~25 seconds (5 × 5s each).

### What is a "diff"?
The output of `git diff` — it shows what lines were added (+) and removed (-) between two versions of code. Our app reviews these diffs to find bugs, just like a human code reviewer would.

---

## 🐛 Problems We Encountered & How We Fixed Them

### Problem 1: Dependency version conflicts
**What happened**: The blueprint specified exact versions that were incompatible:
- `langgraph==0.2.14` needs `langchain-core>=0.2.27`
- But blueprint said `langchain-core==0.2.11`

**Fix**: Relaxed version pins to allow compatible ranges: `langchain-core>=0.2.27,<0.3`

### Problem 2: Pydantic version too old
**What happened**: `pydantic==2.7.1` was too old for `langchain-core>=0.2.27` on Python 3.12+.

**Fix**: Changed to `pydantic>=2.7.4,<3`

### Problem 3: Groq model decommissioned
**What happened**: The blueprint specified `llama3-70b-8192` but Groq retired this model.

**Fix**: Updated to `llama-3.3-70b-versatile` (current best on free tier). Since the model name comes from `.env` (not hardcoded), this was just a config change.

### Problem 4: GitHub push rejected (secret detection)
**What happened**: GitHub's push protection detected the fake Stripe key `sk_live_4eC39HqLyjWDarjtT1zdp7dc` in `diff1_python.txt` and blocked the push.

**Fix**: Went to GitHub's security page and marked it as "used in tests" since it's a PLANTED BUG in the test diff (not a real key).

---

## ✅ Phase 1 Verification Checklist

| Check | Result |
|-------|--------|
| `pip install -r requirements.txt` succeeds | ✅ All packages installed |
| All modules import without errors | ✅ Models, State, LLM Client, Store all OK |
| `uvicorn main:app` starts the server | ✅ Running on port 8000 |
| `GET /health` returns 200 | ✅ Status code 200 |
| `groq_connected: true` in health response | ✅ Groq API working |
| State schema designed | ✅ `ReviewState` TypedDict with all fields |
| Diff files in `diffs/` directory | ✅ All 3 present |
| Git repo initialized and pushed | ✅ On GitHub |

---

## 🔜 What's Next (Phase 2)?

Phase 2 builds the actual AI pipeline:
1. **5 System Prompts** — Detailed instructions for each specialist agent
2. **5 Agent Functions** — Each calls Groq with its prompt and parses results
3. **Merge Node** — Combines all findings, deduplicates, scores, decides verdict
4. **LangGraph Pipeline** — Wires everything into a parallel fan-out/fan-in graph
