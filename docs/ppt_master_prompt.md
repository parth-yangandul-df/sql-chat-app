### Slide 1: Title Slide
**Speaker Notes:**
Welcome to the QueryWise presentation. Today we'll showcase how we're using **agentic AI** — specifically LangGraph — to revolutionize how business users query databases. QueryWise isn't just another text-to-SQL tool; it's a coordinated team of specialized AI agents that work together to transform natural language questions into accurate, safe SQL queries.

---

### Slide 2: Problem Statement
**Speaker Notes:**
Imagine you're a project manager and you need to answer: "Which of my projects are over budget this month?" In the PRMS dashboard, you'd need to: open the projects tab, filter by your projects, find the budget column, cross-reference with actual costs, check completion status, and maybe export to Excel to compare. This takes 5-10 minutes of clicking. Now imagine doing this 20 times a day. That's the reality for many users. The data exists — it's just hidden behind too many clicks. QueryWise removes this friction by letting users just ask the question.

---

### Slide 3: Before & After Example
**Speaker Notes:**
Let me show you what this looks like in practice. Take the question "Which projects are over budget this month?" Before QueryWise, you'd click through the projects tab, filter to your projects, find the budget columns, cross-reference with actual costs, maybe export to Excel to manually calculate. This takes 5-10 minutes. With QueryWise, you just type the question and get the answer in 5 seconds. Same for "Who is available next month?" Instead of clicking through resources, availability calendars, and cross-referencing project assignments, you just ask. This isn't just faster — it changes what questions people actually ask. Suddenly, exploring data becomes effortless.

---

### Slide 4: Solution Overview
**Speaker Notes:**
Here's how QueryWise works, step by step. Step one: you type a question. Step two: the system figures out what you're asking — are you asking about resources? Clients? Projects? Step three: it looks up what tables and columns contain that information and generates the SQL query. Step four: it runs the query and takes the raw results and turns them into a clear answer. And if anything goes wrong, the system automatically tries to fix it. The user never sees any of this — they just get their answer.

---

### Slide 5: LangGraph — The Traffic Controller
**Speaker Notes:**
You might wonder — how do all these AI agents work together without stepping on each other's toes? The answer is **LangGraph**. Think of LangGraph as an air traffic controller. When planes (AI agents) are on the ground, the controller decides which one takes off, when to taxi, and when to land. In our system, LangGraph is that controller. It decides when the QueryComposer writes SQL, passes that SQL to the Validator, and if it's good, sends it to the Executor. If it's bad, LangGraph routes it back to fix the problem. Each arrow in our flowchart — each transition from one agent to the next — is LangGraph doing its job. It's what makes the whole system feel like one cohesive unit rather than a bunch of disconnected parts.

---

### Slide 6: Agentic AI Architecture
**Speaker Notes:**
Think of our system as a team with different roles. The QueryComposer does the heavy lifting — taking a question and writing the SQL query. The SQLValidator is like an editor, checking that the SQL is safe and makes sense. The ErrorHandler is the troubleshooter — if something goes wrong, this agent figures out what to fix. The ResultInterpreter takes the raw database results and turns them into something a human can understand. And we also have 5 domain experts who know the answers to common questions without needing AI at all — that's our fast path.

---

### Slide 7: The Semantic Layer
**Speaker Notes:**
You might wonder — how does the AI know what "active client" means? How does it know which columns to use? The answer is the **semantic layer**. Before we even answer any questions, we build a knowledge base of business terms, metrics, and rules. When someone asks "show me active clients," the system looks up exactly what "active client" means in our context. No guessing. No hallucination. Just accurate answers because the AI has been taught the business definitions.

---

### Slide 8: LangGraph Pipeline Deep Dive
**Speaker Notes:**
We've talked about the team members. Now let's see how they work together. The system has two paths. For simple, common questions like "show me active clients," we skip the AI entirely and use pre-built templates — it's instant. For more complex questions, the full AI team kicks in. How does it decide? It calculates a confidence score. High confidence means fast path. Low confidence means full AI path. And LangGraph makes sure each team member passes their work to the next — the SQL writer passes to the checker, who passes to the executor, who passes to the translator. No dropped balls.

---

### Slide 9: The Four LLM Agents
**Speaker Notes:**
Each agent on our team has one job. The QueryComposer is the main writer. The SQLValidator is the proofreader. The ErrorHandler is the fixer — if the database says there's an error, this agent analyzes it, figures out what went wrong, and tries a corrected version. Up to 3 times. Finally, the ResultInterpreter takes whatever the database returns — rows and columns — and turns it into sentences the user can understand.

---

### Slide 10: Domain Agents
**Speaker Notes:**
In addition to the AI team, we have 5 domain experts. These are specialists who know the answers to common questions without needing AI at all. "Show me active clients" doesn't need to go through the full AI pipeline — the client expert already knows the SQL for that. Same for resource availability, project budgets, timesheets, and your own personal data. This makes common queries nearly instant. And if a question is too complex, it seamlessly escalates to the full AI team.

---

### Slide 11: Intent Classification
**Speaker Notes:**
How does the system know what you're asking? We built an **intent classifier** that recognizes 24 types of questions. When you type something, it calculates a confidence score — how sure it is about what you mean. If it's very confident, like "who is available," it uses the fast template path. If it's less confident, like "show me trends," it sends it to the AI team for a custom SQL query. This hybrid approach gives us both speed for simple questions and flexibility for complex ones.

---

### Slide 12: Query Pipeline Flow
**Speaker Notes:**
Let's walk through the full journey. You type a question. The system figures out what you mean — intent classification. It then writes the SQL, either from a template or custom. Then it checks that the SQL is safe. Then it runs it against the database. If the database says there's an error, the ErrorHandler automatically tries to fix it and retry — up to 3 times. Finally, the ResultInterpreter takes the raw database results and turns them into a clear answer you can understand. All of this happens in seconds.

---

### Slide 13: Tech Stack
**Speaker Notes:**
What's under the hood? We use Python with FastAPI for the backend — it's modern, fast, and well-supported. The frontend uses React for a clean interface. PostgreSQL stores our semantic layer and handles vector search for intelligent matching. For AI, we're provider-agnostic — you can use Anthropic Claude, OpenAI, Ollama, or Groq. And everything runs in Docker, so starting the system is as simple as one command.

---

### Slide 14: Use Cases
**Speaker Notes:**
Here are real examples of what you can ask. Resource managers: "who is available next month?" Project leads: "which projects are over budget?" Finance: "what needs approval this week?" And for everyone: "what's my utilization?" These are the kinds of questions that would normally take minutes of clicking through the dashboard — now you just ask.

---

### Slide 15: Safety & Reliability
**Speaker Notes:**
We didn't just build features — we built safety. First, there's a blocklist that stops dangerous commands, and the database connection is read-only so nothing can be modified. Second, if something goes wrong, the ErrorHandler tries to fix it automatically — up to 3 times. Third, we have limits so queries don't overwhelm the system. And everything is logged for compliance. This is enterprise-grade reliability.

---

### Slide 16: Future Scope
**Speaker Notes:**
QueryWise is a foundation, not a finished product. We're adding role-based access control so different people see different data. New domain experts for HR, finance, sales. Multi-language support so you can ask in any language. Advanced analytics that don't just answer questions but surface trends and anomalies. And integrations so you can use QueryWise right where you already work — Slack, Teams, your company portal. The agentic architecture makes adding all of this straightforward.

---

### Slide 17: Conclusion
**Speaker Notes:**
Here's what makes QueryWise different. Instead of one AI that might get it right or wrong, we have a team — specialized agents that check, validate, and correct each other. The semantic layer means they understand our business, not just generic patterns. The ErrorHandler means when something goes wrong, it gets fixed automatically. It's safe, reliable, and designed for everyone. Just ask your question in plain English — get your answer in seconds. Thank you.
