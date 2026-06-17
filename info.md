# Project Breakdown: What Exactly Did We Build?

If you're feeling confused about what this project actually *is*, don't worry! Let's break it down from the absolute beginning, as if we were explaining it to someone who has never coded before.

---

## 1. What is this? Is it Frontend? Backend? Full Stack?

This project is a **Backend API Service**. 

There is **NO frontend** here. There are no buttons, no webpages, and no user interface. 

Instead, it's an "API" (Application Programming Interface). Think of an API like a drive-thru window at a restaurant. A user (or another program) drives up, hands over an order (data), and the drive-thru window hands back the food (results). 

In our case, the "order" is a piece of code that a programmer wrote, and the "food" is a report saying, "Here are all the bugs in your code."

---

## 2. What was the Problem we were trying to solve?

When software engineers write new code, they create a **Pull Request (PR)**. Before that code is allowed to be added to the main application, other senior engineers have to read it line-by-line to look for bugs, security holes, or bad practices. This process is called a **Code Review**.

Code reviews take a massive amount of time. Human engineers get tired and miss things.

**Our Goal:** Build an automated AI system that can read a programmer's new code (a "diff") and automatically find the bugs in it *before* a human even has to look at it.

---

## 3. What Tech Stack did we use?

We used a combination of modern Backend and AI tools. Here is what each one does:

*   **Python:** The core programming language we used to write everything.
*   **FastAPI:** The "Drive-Thru Window". This is a tool that creates the web server. It listens for incoming requests on port `8000` and sends back the responses.
*   **Groq (LLaMA-3):** The "Brain". We did NOT build an AI model ourselves. Building an AI model takes millions of dollars. Instead, we are *renting* the brain of an existing AI model called LLaMA-3, which is hosted on a super-fast cloud service called **Groq**. 
*   **LangGraph:** The "Manager". If you give an AI a massive piece of code and say "find all bugs", it gets confused and misses things. So, we used LangGraph to create **5 different AI agents**. LangGraph is the manager that tells the 5 agents to work at the exact same time.

---

## 4. How are things connected? (The Workflow)

Here is exactly what happens when the system runs:

1.  **The Request:** A user (or our `run_reviews.py` script) sends a text file containing some code to our FastAPI server.
2.  **The Split (Fan-Out):** FastAPI hands the code to the LangGraph Manager. LangGraph says, *"Okay team, review this code!"* and hands the exact same code to 5 different AI Agents at the same time.
    *   **Agent 1 (Security):** Only looks for hackers' entry points.
    *   **Agent 2 (Performance):** Only looks for slow code.
    *   **Agent 3 (Correctness):** Only looks for crashes.
    *   **Agent 4 (Style):** Only looks for messy code.
    *   **Agent 5 (Testing):** Only looks for missing tests.
3.  **The AI Call:** All 5 agents dial out to the Groq Cloud API over the internet, asking the LLaMA-3 brain to analyze the code based on their specific specialty.
4.  **The Merge (Fan-In):** The 5 agents get their answers back from Groq. LangGraph collects all 5 reports. If two agents found the exact same bug, LangGraph deletes the duplicate.
5.  **The Response:** The final, clean report is handed back to FastAPI, which gives it back to the user as a JSON file.

---

## 5. How we built it (The Phases)

We built this step-by-step to make sure it didn't break:

*   **Phase 1 (Setup):** We installed Python, downloaded our tools (FastAPI, LangGraph), connected to the Groq API, and made sure our "Drive-Thru window" could open.
*   **Phase 2 (The AI Brain):** We wrote the deep instructions (Prompts) for the 5 agents. We wrote the LangGraph code that connects them all together and merges their answers.
*   **Phase 3 (The API):** We attached the AI Brain to the FastAPI Drive-Thru window so that users could actually talk to it using a `POST /review` request. We also wrote a Python script to test it.
*   **Phase 4 (Extra Endpoints):** We added extra features, like the ability to look up past reviews (`GET /reviews`). We also added safety nets so if the Groq AI crashed, our server wouldn't crash.
*   **Phase 5 (Documentation):** We wrote the `README.md` file to explain to other developers how to use our system.

---

## 6. How to Run It & Identify Errors

We were given 3 "Test Cases" (`diff1_python.txt`, `diff2_javascript.txt`, `diff3_typescript.txt`). These are fake pieces of code that have **intentional bugs planted in them**. 

Our job was to see if our AI could find the planted bugs.

**How to run the test:**
1. You start the FastAPI server in your terminal: `uvicorn main:app --reload`
2. You open a second terminal and run our script: `python run_reviews.py`

**What the script does:**
The script takes the 3 test cases and throws them at our server. The server processes them, and the script saves the results in the `reviews/` folder as `.json` files.

**How to read the results:**
If you open `reviews/diff1_review.json`, you will see something like this:
```json
{
  "severity": "critical",
  "title": "SQL Injection via f-string interpolation",
  "line": 7,
  ...
}
```
This means our AI successfully read the code, found the planted "SQL Injection" bug on line 7, and flagged it as a "critical" error. Because our AI successfully found these intentional errors, we know our system works perfectly!
