# Infravox AI Code Reviewer

An automated, multi-agent AI code review pipeline built with FastAPI and LangGraph.

This service accepts git diffs, analyzes them concurrently using 5 specialized LLM agents (Security, Performance, Correctness, Style, Test Coverage), and merges their findings into a single, unified review report.

## 🚀 Quick Start

**1. Set up the environment**
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

**2. Configure API Keys**
Copy `.env.example` to `.env` and add your Groq API key:
```bash
cp .env.example .env
```

**3. Start the Server**
```bash
uvicorn main:app --reload
```
The API will be available at `http://localhost:8000`. You can view the interactive documentation at `http://localhost:8000/docs`.

**4. Run the Batch Review Script**
In a separate terminal, run the batch script to process the test diffs:
```bash
python run_reviews.py
```
This will output the results to the console and save the JSON reports in the `reviews/` folder.

---

## 🏗️ Architectural Decisions

### State Schema Shape
I defined a single `ReviewState` typed dictionary that flows through the entire LangGraph pipeline. It holds the input (`diff`, `language`), but crucially, it provides **separate lists for each agent's findings** (e.g., `security_findings`, `performance_findings`). 

*Why?* This prevents race conditions. If all agents pushed to a single shared `findings` array concurrently, data could be lost or corrupted. Giving each agent its own "lane" in the state guarantees safe parallel execution.

### Agent Split
The agents are split into 5 distinct specialties:
1. **Security**: Hardcoded secrets, SQL injection, auth flaws.
2. **Performance**: N+1 queries, unbounded loops, sequential awaits.
3. **Correctness**: Null dereferences, undefined variables, silent failures.
4. **Style**: Readability, TS `any` usage, function length.
5. **Test Coverage**: Missing boundary, edge case, and error path tests.

*Why?* Narrowly scoping an LLM's system prompt significantly improves its accuracy. A single monolithic prompt trying to find everything usually misses subtle bugs. 5 focused agents act as domain experts, ensuring deep rather than shallow analysis.

### Merge Node Logic & Verdicts
The merge node runs *after* all 5 agents complete (fan-in). It performs:
1. **Deduplication**: If two agents flag an issue on the same/adjacent lines in the same category, they are merged. The finding with the higher severity is kept.
2. **Overall Severity**: The max severity across all findings.
3. **Verdict**: 
   - `critical` or `high` -> `request_changes` (Must not merge)
   - `medium` -> `needs_discussion` (Human judgment required)
   - `low` or `clean` -> `approve` (Safe to merge)
4. **Summarization**: A final, lightweight LLM call generates the PR summary and positive observations based on the collected findings.

### LLM Error Handling
LLMs can be flaky. I wrapped the Groq client in a Tenacity `@retry` block with exponential backoff to gracefully handle `429 Too Many Requests` rate limits. Furthermore, the JSON parsing logic attempts multiple extraction strategies (stripping markdown fences, finding first `{`) and falls back to an empty list `[]` instead of crashing the pipeline if the LLM output is malformed.

---

## 💭 Reflections

**Most Happy With:**
The robustness of the pipeline. The combination of retry logic, fallback JSON parsing, and the parallel fan-out/fan-in architecture means the system is fast (~10s per review) and highly resilient to LLM hallucinations or API hiccups. The targeted prompts also proved highly effective at catching the specific planted bugs in the test diffs.

**Least Happy With:**
The summarization node. Currently, it uses a smaller model (`gemma2-9b-it`) to save time and tokens, but occasionally its summaries can feel a bit generic. If I had more time, I would feed it more context (e.g., the commit messages or surrounding repo code) to ground its PR summaries in reality.

**AI Usage:**
Yes, I used an advanced AI coding assistant to help scaffold the boilerplate, write the initial Pydantic models, and construct the LangGraph wiring. This allowed me to focus heavily on the prompt engineering and architectural logic rather than typing out standard FastAPI boilerplate.
