# QueryWise — PPT Master Prompt

---

You are an expert presentation designer. Create a complete, professional PowerPoint presentation for the **QueryWise** project using the slide-by-slide content provided below.

## Project Summary

**QueryWise** is a natural-language-to-SQL application with a semantic metadata layer. Users ask questions in plain English; the system classifies intent, builds database context from a curated semantic layer (glossary terms, metric definitions, data dictionary entries, knowledge documents), generates SQL, executes it against target databases (PostgreSQL, BigQuery, Databricks, SQL Server), and returns human-readable answers.

The core innovation is the **semantic layer** — a structured business knowledge store that sits between the user's question and the LLM, providing exact SQL expressions, business formulas, code-to-label mappings, and policy context so the model never guesses.

The query pipeline is orchestrated by **LangGraph**, featuring intent classification (24 intents across 5 domains), hybrid retrieval (vector + keyword + foreign-key expansion), multi-step SQL generation with validation, automatic error recovery (up to 3 retries), and a result interpreter that converts raw SQL output into natural language.

QueryWise supports multiple LLM providers (Anthropic, OpenAI, Ollama, OpenRouter, Groq), enforces read-only safety at two layers, and includes an embeddable chat widget for third-party integration.

---

## Slide Design Rules

Apply these rules to every slide:

- **Maximum 5 bullet points per slide** — split content across multiple slides rather than overcrowding
- **No paragraphs** — only concise, scannable bullet points
- **Minimal and clean** — clarity over completeness on any single slide
- **No redundancy** — each slide covers unique ground; no repeated information
- **Simple language** — avoid unnecessary jargon; explain technical concepts plainly
- **Professional tone** — presentation-ready, not documentation
- **Logical flow** — slides build on each other from problem to solution to value

---

## Required Slide Structure

Create exactly the following 13 slides in order. Each slide must include a **title**, **bullet points**, and **speaker notes**.

---

### Slide 1: Title Slide

**Title:** QueryWise: Natural Language to SQL with Semantic Intelligence

**Subtitle:** Ask questions in plain English. Get answers from your data.

**Speaker Notes:**
Welcome to the QueryWise presentation. QueryWise bridges the gap between business users who have questions and the databases that hold the answers — without requiring any SQL knowledge.

---

### Slide 2: Problem Statement

**Title:** The Problem: Data Locked Behind Technical Barriers

**Bullet Points:**
- Business users depend on data teams for every query, creating bottlenecks
- Writing SQL requires technical expertise most users don't have
- LLM-generated SQL often hallucinates — guessing table names, column meanings, and business logic
- Raw SQL results are hard to interpret without domain context
- Existing text-to-SQL tools lack understanding of company-specific terminology and policies

**Speaker Notes:**
Most organizations have a growing gap between the people who need data insights and the people who can extract them. Data teams are overwhelmed with ad-hoc requests. Generic AI tools try to help but fail because they don't understand the business context — what "active client" means, how revenue is calculated, or which codes map to which labels. This leads to wrong answers, wasted time, and mistrust in self-service analytics.

---

### Slide 3: Solution Overview

**Title:** The Solution: Semantic Intelligence Meets Natural Language

**Bullet Points:**
- Users ask questions in plain English — no SQL required
- A curated semantic layer provides the LLM with exact business context
- SQL is generated, validated, and executed safely against the target database
- Results are translated into clear, human-readable answers
- Supports multiple databases and LLM providers for maximum flexibility

**Speaker Notes:**
QueryWise solves this by inserting a semantic layer between the user's question and the LLM. Instead of the model guessing what tables or columns mean, it receives precise, curated business knowledge — glossary definitions, metric formulas, data dictionary entries, and policy documents. The result is accurate SQL, executed safely, with answers anyone can understand.

---

### Slide 4: Key Features

**Title:** Key Features

**Bullet Points:**
- Natural language queries with multi-turn conversation support
- Curated semantic layer: glossary, metrics, data dictionary, and knowledge documents
- Hybrid retrieval combining vector search, keyword matching, and schema relationships
- Multi-database support: PostgreSQL, BigQuery, Databricks, SQL Server
- Embeddable chat widget for integration into existing platforms

**Speaker Notes:**
QueryWise is built around five core capabilities. The semantic layer is the heart — it stores curated business knowledge that makes every query context-aware. Hybrid retrieval ensures the right tables and columns are selected. Multi-database support means it works with whatever infrastructure you have. And the embeddable widget lets you deploy it anywhere — intranets, portals, or Slack.

---

### Slide 5: System Architecture

**Title:** System Architecture

**Bullet Points:**
- **Frontend:** React 19 admin UI + end-user chatbot with embeddable widget
- **Backend:** Python 3.12 with FastAPI and LangGraph orchestration
- **Semantic Store:** PostgreSQL with pgvector for vector-embedded business metadata
- **LLM Layer:** Provider-agnostic — Anthropic, OpenAI, Ollama, OpenRouter, Groq
- **Database Connectors:** Plugin system for PostgreSQL, BigQuery, Databricks, SQL Server

**Speaker Notes:**
QueryWise has three main layers. The frontend provides an admin interface for managing the semantic layer and a chat interface for end users. The backend orchestrates the entire query pipeline using LangGraph. The semantic store holds all business metadata as vector embeddings for intelligent retrieval. The LLM layer is provider-agnostic, so you're never locked in. And the connector system lets you query any supported database through a unified interface.

---

### Slide 6: The Semantic Layer

**Title:** The Semantic Layer: Where Business Knowledge Lives

**Bullet Points:**
- **Glossary:** Definitions of business terms with exact SQL expressions
- **Metrics:** Pre-defined calculations and formulas (e.g., utilization rate, ECL)
- **Data Dictionary:** Column-level meanings and code-to-label mappings
- **Knowledge Documents:** Policy context, domain rules, and reference material
- All content is vector-embedded for intelligent, context-aware retrieval

**Speaker Notes:**
This is QueryWise's core innovation. The semantic layer is a curated knowledge store that tells the LLM exactly what things mean. When a user asks about "active resources," the system doesn't guess — it retrieves the precise SQL expression from the glossary. When a column contains status codes like "A" or "I," the data dictionary maps them to "Active" and "Inactive." This eliminates hallucination at the source.

---

### Slide 7: How It Works — Query Pipeline

**Title:** How It Works: From Question to Answer

**Bullet Points:**
- **Step 1:** Intent classification matches the question to 1 of 24 predefined intents
- **Step 2:** High-confidence intents use fast SQL templates; others proceed to semantic retrieval
- **Step 3:** Hybrid retrieval gathers relevant tables, columns, and business context
- **Step 4:** LLM generates SQL, which is validated and executed in read-only mode
- **Step 5:** Results are interpreted into natural language with automatic error recovery (up to 3 retries)

**Speaker Notes:**
Every query follows a structured pipeline. First, intent classification determines what the user is asking — is it about resources, projects, timesheets, or something else? High-confidence matches use pre-built SQL templates for speed. Everything else goes through semantic retrieval, where the system gathers the right context. The LLM then generates SQL, which is validated for safety before execution. If errors occur, the system retries automatically. Finally, raw results are translated into plain English.

---

### Slide 8: Tech Stack

**Title:** Technology Stack

**Bullet Points:**
- **Backend:** Python 3.12, FastAPI, LangGraph, SQLAlchemy (async), Alembic
- **Frontend:** React 19, TypeScript, Vite, Mantine UI, React Query
- **Databases:** PostgreSQL 16 with pgvector; target DBs via connector plugins
- **LLM Providers:** Anthropic Claude, OpenAI, Ollama, OpenRouter, Groq
- **Infrastructure:** Docker Compose for one-command deployment

**Speaker Notes:**
QueryWise is built on modern, well-supported technologies. The backend uses FastAPI for high-performance async operations and LangGraph for reliable pipeline orchestration. The frontend uses React with Mantine UI for a clean, responsive interface. Everything runs in Docker Compose — one command to start the entire stack. And the LLM provider abstraction means you can switch models without changing any application code.

---

### Slide 9: Use Cases

**Title:** Practical Use Cases

**Bullet Points:**
- **Resource Management:** "Who is available for a new project next month?"
- **Client Reporting:** "Show me all active clients and their project status"
- **Project Tracking:** "Which projects are over budget or behind schedule?"
- **Timesheet Analysis:** "What timesheets are pending approval this week?"
- **Self-Service:** "What's my current project allocation and utilization?"

**Speaker Notes:**
QueryWise is designed for real-world business questions. Resource managers can find available people without writing complex joins. Project leads can track budgets and timelines in plain English. Finance teams can analyze timesheet approvals instantly. And every employee can check their own allocation and utilization without filing a ticket. These are just examples — the semantic layer adapts to any domain.

---

### Slide 10: Unique Value Proposition

**Title:** What Makes QueryWise Different

**Bullet Points:**
- **No hallucination:** The LLM never guesses — it uses curated business context
- **Domain agents:** Pre-built templates for 24 intents across 5 business domains
- **Graceful degradation:** Works even when embeddings are unavailable (keyword fallback)
- **Multi-LLM support:** No vendor lock-in — switch providers without code changes
- **Audit trail:** Every query, SQL statement, and result is persisted for compliance

**Speaker Notes:**
What sets QueryWise apart is discipline. Most text-to-SQL tools let the LLM freestyle — QueryWise constrains it with verified business knowledge. Domain agents handle common queries instantly with pre-built templates. If vector search fails, keyword search takes over — the system never crashes. You can switch LLM providers with a single environment variable. And every query is logged for full auditability.

---

### Slide 11: Safety & Reliability

**Title:** Safety & Reliability

**Bullet Points:**
- Read-only enforcement at two layers: SQL blocklist and connector-level restrictions
- Row limits (1,000) and execution timeouts (30 seconds) prevent runaway queries
- Automatic error recovery with up to 3 intelligent retry attempts
- Background embedding generation — never blocks the user experience
- Auto-setup with sample schema for instant evaluation and testing

**Speaker Notes:**
Safety isn't an afterthought — it's built into every layer. SQL is validated against a comprehensive blocklist before execution. Database connectors enforce read-only transactions as a second line of defense. Row limits and timeouts protect against expensive queries. If something goes wrong, the error handler retries with refined context. And background embedding generation means the system is always responsive, even while learning new content.

---

### Slide 12: Future Scope

**Title:** Future Scope

**Bullet Points:**
- Role-based access control for row-level and column-level data permissions
- Expanded domain agents for HR, finance, sales, and operations
- Multi-language support for non-English queries and responses
- Advanced analytics: trend detection, anomaly alerts, and forecasting
- Deeper integrations: Slack, Microsoft Teams, and enterprise portals

**Speaker Notes:**
QueryWise is a foundation, not a finished product. Role-based access control will let organizations restrict data at the row and column level. New domain agents will cover more business functions. Multi-language support will make it accessible globally. Advanced analytics will go beyond answering questions to surfacing insights proactively. And deeper integrations will embed QueryWise wherever teams already work.

---

### Slide 13: Conclusion

**Title:** Conclusion

**Bullet Points:**
- QueryWise turns natural language into accurate, contextual database queries
- The semantic layer eliminates LLM hallucination with curated business knowledge
- Built for safety, flexibility, and enterprise-grade reliability
- Deployable in minutes with Docker Compose — no complex setup required
- **Ask questions in plain English. Get answers from your data.**

**Speaker Notes:**
QueryWise represents a new approach to self-service analytics. Instead of training business users to write SQL or accepting unreliable AI-generated queries, it gives the AI the business context it needs to get it right. The result is a system that's safe, accurate, and accessible to everyone. Thank you.

---

## Output Format Requirements

- Produce exactly **13 slides** in the order specified above
- Each slide must have a **clear title**, **bullet points** (max 5), and **speaker notes**
- Use a **clean, professional design** with consistent typography and spacing
- Include a **visual element suggestion** for each slide (e.g., icon, diagram placeholder, chart type)
- Maintain a **coherent visual theme** throughout the presentation
- Ensure **no content redundancy** — each slide covers unique information
- The final output should be **presentation-ready** with no major edits needed
