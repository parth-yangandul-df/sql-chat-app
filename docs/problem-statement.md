# Problem Statement: Lack of Context Awareness in Chatbot Follow-Ups

## 1. Objective

Identify and clearly define the core issue affecting the chatbot system, specifically:

* Why **follow-up queries fail**
* Why the system **falls back to LLM unnecessarily**
* Why the chatbot does not behave as a **stateful assistant**

---

## 2. Current System Overview

### Architecture Summary

* **Frontend:** React (chat UI)
* **Backend:** FastAPI + LangGraph
* **Data Access:** Predefined SQL tools (intent → query mapping)
* **LLM Usage:** Intent classification + fallback responses

---

### Expected Behavior

The chatbot should:

* Handle **structured data queries**
* Support **multi-turn conversations**
* Allow users to **refine results step-by-step**
* Prefer **domain tools over LLM fallback**
* Maintain **context within a session**

---

## 3. Observed Problem

### Core Issue

> The chatbot fails to maintain context across follow-up queries, resulting in incorrect or irrelevant responses.

---

### Example Scenario

#### Turn 1

```
User: Show all benched resources
```

**System Behavior:**

* Correctly maps to tool
* Executes SQL query
* Returns expected results

---

#### Turn 2

```
User: Which of these know Python?
```

**Expected Behavior:**

* Understand “these” refers to previous result
* Apply additional filter: `skill = 'Python'`
* Reuse same tool with updated filters

---

**Actual Behavior:**

* Loses reference to previous result
* Does not apply existing filters
* Falls back to LLM
* Produces generic or incorrect response

---

## 4. Root Cause Analysis

### 4.1 Stateless Query Handling

Each user query is treated as an **independent request**, instead of part of a conversation.

* No memory of previous filters
* No linkage between turns

---

### 4.2 Absence of Structured Context

The system does not maintain a structured representation of:

* Current intent
* Applied filters
* Last executed tool
* Result scope

---

### 4.3 No Follow-Up Interpretation Logic

The system cannot interpret:

* References like “these”, “those”
* Incremental refinements
* Corrections or modifications

---

### 4.4 Over-Reliance on LLM Fallback

Instead of:

* Reusing domain tools

The system:

* Defaults to LLM when context is unclear
* Produces non-deterministic outputs

---

### 4.5 Missing Query Evolution Model

The system lacks the concept of:

> “A query evolving over multiple turns”

Instead, it treats:

* Every input as a fresh query

---

## 5. Impact

### Functional Impact

* Follow-up queries fail frequently
* Incorrect or irrelevant responses
* Inability to refine results

---

### System Behavior Impact

* Domain tools are underutilized
* Increased dependency on LLM
* Loss of determinism in responses

---

### User Experience Impact

* Chatbot feels inconsistent
* Users lose trust in results
* Increased friction in interaction

---

## 6. Constraints

* Must **minimize LLM usage**
* Must prioritize **tool-based execution**
* Must maintain **low latency**
* Context required only **within current session**

---

## 7. Summary

The chatbot’s primary issue is not lack of intelligence, but lack of **state management**.

> The system fails because it does not maintain and evolve a structured context across user interactions.

As a result:

* Follow-up queries break
* Tool reuse fails
* LLM fallback increases unnecessarily

---

## 8. One-Line Problem Definition

> The chatbot is stateless, while the problem requires a stateful, context-driven query system.

---
