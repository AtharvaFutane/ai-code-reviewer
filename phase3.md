# Phase 3 — Complete Reference Guide (For Your Learning)

> **What was Phase 3 about?**  
> We took the AI pipeline we built in Phase 2 and put it behind an API endpoint (`POST /review`). Then we wrote a Python script to automatically read the 3 diff files from disk, send them to our API, and save the resulting JSON reports into the `reviews/` folder.

---

## 📁 What Files Did We Create/Modify?

| File | Purpose |
|------|---------|
| `app/api/routes.py` | (Modified) Added the actual API endpoints to serve our LangGraph pipeline |
| `run_reviews.py` | (New) The batch runner script that tests our whole system |
| `reviews/*.json` | (Generated) The final AI review outputs for the 3 diffs |

---

## File 1: `app/api/routes.py` — "The API Endpoints"

We added the core endpoints that allow other programs to talk to our review system.

### The POST `/review` Endpoint

```python
@router.post("/review", response_model=ReviewReport)
async def create_review(request: ReviewRequest):
```
**What happens here:**
1. **Validation**: Pydantic automatically checks that the incoming request has a `diff` and a `language`.
2. **State Creation**: We create the `ReviewState` dictionary.
3. **Pipeline Execution**: `await pipeline.ainvoke(initial_state)` starts the LangGraph pipeline we built in Phase 2.
4. **Result Extraction**: We get the merged report out of the final state.
5. **Persistence**: `await review_store.save(...)` saves it to our in-memory dictionary.
6. **Return**: The API sends the JSON report back to the caller.

### The GET Endpoints (Phase 4 sneak peek)

We also added the retrieval endpoints since the code was straightforward:
- `GET /review/{id}`: Looks up a specific review in the in-memory store.
- `GET /reviews`: Lists summaries of all reviews completed since the server started.

---

## File 2: `run_reviews.py` — "The Batch Runner"

The assignment requires a script that runs all 3 diffs automatically. 

### Why write a separate script?
We *could* test our API manually using Postman or `curl`. But a script:
1. Is repeatable (you can run it 50 times while tweaking prompts)
2. Automatically saves the JSON to the right folder
3. Prints a nice human-readable summary
4. Evaluates whether the system works end-to-end

### How the script works:

1. **Find files**: It uses `Path("diffs").glob("*.txt")` to find our 3 test files.
2. **Context mapping**: It has a dictionary to map filenames to languages (e.g., `diff1_python.txt` -> `python`) and provides a helpful context string for each to give the AI a hint.
3. **HTTP Client**: It uses `httpx.Client()` to make HTTP POST requests to our running FastAPI server.
4. **Save to disk**: When the API replies with JSON, it writes that JSON to the `reviews/` folder.

### The Windows Encoding Bug We Hit
When the script tried to print `print(f"\n{'─' * 60}")` (a fancy solid line), it crashed on Windows with a `'charmap' codec` error. 

**Why?** The Windows Command Prompt uses an older character encoding that sometimes chokes on Unicode characters. We fixed it by changing the fancy line `─` to a standard dash `-`.

---

## 📊 The Results: Did the AI find the bugs?

The script finished and produced 3 JSON files in your `reviews/` folder. Here's a summary of what our AI agents caught:

### `diff1_python.txt`
- **Verdict**: `REQUEST_CHANGES` (Critical)
- **Findings**: 21 issues found
- **Highlights**: Caught the SQL Injection via f-strings (Critical), the hardcoded Stripe secret key (Critical), and missing tests for null inputs.

### `diff2_javascript.txt`
- **Verdict**: `REQUEST_CHANGES` (Critical)
- **Findings**: 17 issues found
- **Highlights**: Caught plaintext password storage (Critical), the N+1 database query pattern in the loop (High), and missing null checks.

### `diff3_typescript.txt`
- **Verdict**: `REQUEST_CHANGES` (Critical)
- **Findings**: 15 issues found
- **Highlights**: Caught the infinite while loop (Critical), missing authorization checks (High), and multiple Null Dereference bugs.

*The prompts we engineered in Phase 2 worked perfectly! The AI caught the exact planted bugs the assignment reviewers are looking for.*

---

## ✅ Phase 3 Verification Checklist

| Check | Result |
|-------|--------|
| `POST /review` endpoint implemented | ✅ |
| `run_reviews.py` script created | ✅ |
| Script successfully reads from `diffs/` | ✅ |
| Script successfully posts to API | ✅ |
| Script successfully writes to `reviews/` | ✅ |
| All 3 diffs reviewed | ✅ (3/3 completed) |

---

## 🔜 What's Next (Phase 4 & 5)?

We are actually almost entirely done! 
- Phase 4 was "add the remaining endpoints" (which we just did in `routes.py`) and "error handling" (which we built into our agents and client in Phase 2).
- Phase 5 is writing the `README.md` and pushing the final code.

Let's commit Phase 3, and then we'll write the README!
