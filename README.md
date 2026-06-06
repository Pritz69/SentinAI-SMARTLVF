# SentinAI-SMARTLVF (Version 1.1.0)

SentinAI-SMARTLVF is an **Enterprise-Grade Stateful Multi-Agent Adversarial Red-Teaming & Vulnerability Testing Framework** designed to simulate automated prompt injections, context smuggling, RAG bypasses, and security evaluation loops against Target Environments using a Model Context Protocol (MCP) connection.

It leverages **LangGraph** as its core cyclical stateful engine, facilitating complex feedback loops (Attacker → Executor → Evaluator → Optimizer → Executor) with critical Human-in-the-Loop (HITL) checkpoints and Epistemic Memory.

---

## 🚀 Key Features & Enterprise Upgrades

We have upgraded the core red-teaming nodes of SentinAI to be fully resilient, observable, and defense-aware:

1. **Attacker Node (`attacker.py`)**: Profiles target systems based on system prompts to dynamically select the optimal attack technique. Integrates a library of templates (context injection, roleplay framing, bilingual pivoting, token smuggling) and compiles dynamic, randomized fallbacks if upstream LLMs fail.
2. **Executor Node (`executor.py`)**: Implements exponential backoff and jitter retry policies for API calls. Generates distributed tracing headers (`X-Correlation-ID`, `X-SentinAI-Simulation-ID`) and records full telemetry audit trails to `telemetry_audit.json`. Enforces input sanitization before dispatching payloads to prevent shell/SQL commands from executing on internal hosts.
3. **Evaluator Node (`evaluator.py`)**: Performs risk analysis along a multi-dimensional risk matrix (`info_disclosure`, `prompt_injection`, `guardrail_bypass`). Employs regex pattern matching and Shannon Entropy calculations to detect API/credential leaks, classifies chatbot refusals, and runs offline rule-based fallbacks during API outages.
4. **Optimizer Node (`optimizer.py`)**: Operates on a closed feedback loop parsing Evaluator findings (refusal indicators, failure categories). Mutates failed payloads programmatically via a mutator registry (Base64 wrapper, Leetspeak obfuscator, Delimiter injector, Multilingual pivoting, Adversarial suffixes).

---

## 🎯 Target Audience & Use Cases

### Target Customers
* **Enterprise Security Teams & CISOs**: Automatically audit and stress-test customer support chatbots, sales agents, and business intelligence RAG pipelines before production releases.
* **Red-Teaming Consultancies**: Scale adversarial simulations using automated mutation pipelines and few-shot memory.
* **AI Developers & Engineers**: Proactively profile system prompts and system guardrails for prompt leakage weaknesses.

### Key Use Cases
* **Prompt Leakage Prevention**: Audit RAG interfaces for exposure of configured credentials, database keys, or API tokens.
* **Guardrail Validation**: Validate the effectiveness of prompt-defense layers (like Llama Guard or NeMo Guardrails) against obfuscation attacks.
* **PII & Data Exfiltration Scans**: Verify that internal knowledge bases are not leaking sensitive user logs or system configuration data.

---

## 💻 Technology Stack

* **Core Logic & Orchestration**: [LangGraph](file:///d:/SentinAI-SMARTLVF/agents/graph.py) (Stateful multi-agent graphs), Python 3.14
* **APIs & Backend**: [FastAPI](file:///d:/SentinAI-SMARTLVF/main.py) (REST Web API), Uvicorn (ASGI web server)
* **Adversarial & Evaluator LLMs**: Groq Cloud API (Llama 3.1 8B, Llama 3.3 70B), Google Gemini API (Gemini 3.5 Flash)
* **Vector Embeddings & Long-Term Memory**: [ChromaDB](file:///d:/SentinAI-SMARTLVF/database/chroma_repo.py) (Semantic exploit database), SQLite (LangGraph state checkpointer)
* **Distributed Task Queue**: Celery, Redis (Broker & Result Backend)
* **Observability & Logging**: JSON-Lines Telemetry Auditing ([telemetry_audit.json](file:///d:/SentinAI-SMARTLVF/telemetry_audit.json)), correlation tracing headers
* **Frontend Dashboard**: React, Vite, CSS (Glassmorphic dark design)

---

## 🛠️ Architecture Overview

The system consists of the following components working together:

1. **FastAPI Web Server** ([main.py](file:///d:/SentinAI-SMARTLVF/main.py)): Exposes REST endpoints to launch simulations, query history, configure target databases, and approve pending payloads.
2. **LangGraph Agentic Orchestrator** ([agents/graph.py](file:///d:/SentinAI-SMARTLVF/agents/graph.py)): Dictates state management, linear transitions, and conditional routing.
3. **Epistemic Memory** ([agents/memory.py](file:///d:/SentinAI-SMARTLVF/agents/memory.py)): Integrates with local **ChromaDB** ([database/chroma_repo.py](file:///d:/SentinAI-SMARTLVF/database/chroma_repo.py)) to store successful exploits as vector embeddings for few-shot historical injection.
4. **Celery Worker Queue** ([celery_app.py](file:///d:/SentinAI-SMARTLVF/celery_app.py) / [tasks/simulation_worker.py](file:///d:/SentinAI-SMARTLVF/tasks/simulation_worker.py)): Asynchronously processes simulations and allows resume hooks across distributed tasks when enabled.
5. **Model Context Protocol (MCP) Client** ([core/mcp.py](file:///d:/SentinAI-SMARTLVF/core/mcp.py)): Wraps communication with the target system to execute the generated payloads.

```mermaid
graph TD
    User([Security Operator]) <-->|HTTP REST / API| FastAPI[FastAPI Web Server]
    FastAPI <-->|State & Control| LangGraph[LangGraph Orchestrator]
    FastAPI -->|Enqueue Task| Redis[(Redis Broker)]
    Celery[Celery Worker] <-->|Fetch/Execute| Redis
    Celery <-->|State & Control| LangGraph
    
    subgraph Agents [LangGraph Agent Nodes]
        attacker[Attacker Agent]
        executor[Executor Node]
        evaluator[Evaluator Agent]
        optimizer[Optimizer Agent]
        memorize[Memorization Node]
    end
    
    LangGraph --- Agents
    
    attacker -.->|Groq Llama-3.1| Groq[Groq API]
    evaluator -.->|Gemini 3.5 Flash| Gemini[Google Gemini API]
    optimizer -.->|Groq Llama-3.1| Groq
    
    executor -->|MCP Request| Target[Mock Target API]
    memorize -->|Store Success| Chroma[(ChromaDB Long-Term Memory)]
    LangGraph <-->|State Checkpointing| SQLite[(SQLite Checkpointer)]
```

---

## 🔄 Stateful Agent Graph Flow

The agentic loop is defined inside [agents/graph.py](file:///d:/SentinAI-SMARTLVF/agents/graph.py). It uses a standard state object, `SimulationState` ([agents/state.py](file:///d:/SentinAI-SMARTLVF/agents/state.py)), to keep track of payloads, target responses, evaluations, and execution history.

A **Human-in-the-Loop (HITL)** breakpoint is injected *before* the executor node, ensuring that no adversarial payload is ever sent to a target system without explicit user approval.

```mermaid
graph TD
    START([START]) --> attacker[attacker node: Profile Target & Generate Payload]
    attacker --> executor_gate{HITL Pause:<br/>Interrupt Before Executor}
    
    optimizer[optimizer node: Mutate Payload] --> executor_gate
    
    executor_gate -->|Human Approves| executor[executor node: Fire Payload via MCP]
    
    executor --> evaluator[evaluator node: Analyze Response & Score Risk Matrix]
    
    evaluator --> cond_edge{route_evaluation}
    
    cond_edge -->|Is Compromised| memorize[memorize node: Save to ChromaDB]
    cond_edge -->|Max Turns Exceeded| END([END])
    cond_edge -->|Keep Trying| optimizer
    
    memorize --> END
```

---

## 🧐 Multi-Dimensional Risk Evaluator Scanner Flow

The Evaluator Node analyzes responses using a dynamic regex/entropy pipeline and LLM semantics to score vulnerability severity along multiple vectors:

```mermaid
graph TD
    Response[Target Chat Response] --> RefusalCheck{Refusal Phrase Detected?}
    RefusalCheck -->|Yes| RefusalScore[Assign Low Threat Score:<br/>Info=0, Inj=0.1, Guard=0.1]
    RefusalCheck -->|No| ContentCheck{Heuristic Content Scanning}
    
    ContentCheck --> RegexScanner[Regex Secret Scanner:<br/>AWS, Stripe, JWT, Generic Key]
    ContentCheck --> EntropyScanner[Shannon Entropy Check:<br/>Entropy > 3.2, Length 16-128]
    
    RegexScanner -->|Matches| LeakDetected[Secret Leaked:<br/>Info=1.0, Guard=1.0]
    EntropyScanner -->|High Entropy Token| LeakDetected
    
    ContentCheck --> BypassCheck{Override / Bypass Terms?}
    BypassCheck -->|Yes| GuardBypass[Guardrail Bypass Flagged:<br/>Guard=0.9]
    BypassCheck -->|No| KeywordCheck{Objective Keywords Match?}
    KeywordCheck -->|High Overlap| SemanticCompromise[Semantic Bypass:<br/>Inj=0.7, Guard=0.4]
    KeywordCheck -->|Low Overlap| NormalResp[Neutral Response:<br/>Inj=0.5, Guard=0.4]
    
    LeakDetected --> Aggregation[Risk Matrix Score:<br/>Max of Info, Inj, Guard]
    RefusalScore --> Aggregation
    GuardBypass --> Aggregation
    SemanticCompromise --> Aggregation
    NormalResp --> Aggregation
```

---

## 🔧 Feedback-Loop Driven Optimizer Pipeline Flow

When the target chatbot blocks or refuses the attack, the Optimizer Node analyzes the specific classification feedback to select the appropriate programmatic mutator wrapping or alignment bypass:

```mermaid
graph TD
    FailFeedback[Evaluator Feedback Loop:<br/>Score, Refusal status, Vulnerabilities] --> Decision{Refusal Detected?}
    Decision -->|Yes: Target Blocked| ObfuscationRegistry[Programmatic Obfuscation mutators]
    Decision -->|No: Weak Injection| SuffixRegistry[Alignment Bypass mutators]
    
    ObfuscationRegistry --> Base64[Base64Mutator:<br/>Encode prompt payload]
    ObfuscationRegistry --> Trans[TranslationMutator:<br/>Bilingual pivoting wrapper]
    
    SuffixRegistry --> Leet[LeetMutator:<br/>Obfuscate keywords with leetspeak]
    SuffixRegistry --> Delim[DelimiterMutator:<br/>Insert spacings/dots]
    SuffixRegistry --> Suffix[AdversarialSuffixMutator:<br/>Append alignment jailbreaks]
    
    Base64 --> MutatedPayload[Adversarial Payload Mutation]
    Trans --> MutatedPayload
    Leet --> MutatedPayload
    Delim --> MutatedPayload
    Suffix --> MutatedPayload
```

---

## ⚡ API Execution & HITL Sequence

Here is the step-by-step process of running and approving a simulation run:

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Security Operator
    participant API as FastAPI / API Layer
    participant LG as LangGraph / Checkpointer
    participant Target as Target Chat API (MCP)

    Operator->>API: POST /api/v1/simulation/ (objective, max_turns)
    API->>LG: Initialize SimulationState & Run Attacker node
    LG-->>API: Paused before 'executor' (HITL Breakpoint)
    API-->>Operator: 200 OK (simulation_id, status: pending_approval)
    
    Operator->>API: GET /api/v1/hitl/{id}/pending
    API-->>Operator: Return payload raw text for inspection
    
    Operator->>API: POST /api/v1/hitl/{id}/approve
    API->>LG: Resume graph execution
    LG->>Target: Fire payload (execute_payload_node)
    Target-->>LG: Return chat response & performance metrics
    LG->>LG: Evaluate payload response (evaluate_response_node)
    
    alt Target is Compromised
        LG->>LG: Commit successful prompt to ChromaDB (memorize_success_node)
        LG-->>API: Terminated (END)
    else Target Blocked & Turns Remain
        LG->>LG: Generate mutated payload (optimize_payload_node)
        LG-->>API: Paused before 'executor' (HITL Breakpoint)
    end
```

---

## 🧩 Detailed Node Actions

### 1. `attacker` ([agents/nodes/attacker.py](file:///d:/SentinAI-SMARTLVF/agents/nodes/attacker.py))
* **Target Profiling**: Parses target's name and system instructions to classify target defense strength (`strict_keyword_filtering`, `rag_with_context_retrieval`) to align strategy generation.
* **Technique Templates Library**: Houses strategy templates like roleplay wrappers, token spacing, and translation vectors.
* **Few-shot memory seeding**: Retreives historical exploits from [ChromaDB](file:///d:/SentinAI-SMARTLVF/database/chroma_repo.py) using [memory_manager](file:///d:/SentinAI-SMARTLVF/agents/memory.py) to seed successful prompts into current generation loop context.
* **Dynamic Compiler Fallback**: Randomly matches objective constraints to strategies and obfuscates key tokens programmatically if the Groq model cascading fails.

### 2. `executor` ([agents/nodes/executor.py](file:///d:/SentinAI-SMARTLVF/agents/nodes/executor.py))
* **Pre-flight Sanitizer**: Scans payloads for dangerous patterns (`rm -rf`, `drop table`, `format c:`) and intercepts them.
* **Jittered Backoff & Retry**: Dynamically schedules backoffs and retries if external target endpoints respond with HTTP 429 (rate limited) or HTTP 5xx errors.
* **Distributed Tracing & Audit logging**: Injects tracing headers (`X-Correlation-ID`, `X-SentinAI-Simulation-ID`) and outputs runtime performance metrics to [telemetry_audit.json](file:///d:/SentinAI-SMARTLVF/telemetry_audit.json).

### 3. `evaluator` ([agents/nodes/evaluator.py](file:///d:/SentinAI-SMARTLVF/agents/nodes/evaluator.py))
* **Multi-Dimensional Risk Matrix**: Scores threat vectors independently (`info_disclosure`, `prompt_injection`, `guardrail_bypass`).
* **Regex & Shannon Entropy Scanning**: Runs regex models for secrets (AWS, Stripe, JWT, Generic tokens) and calculates text entropy (`Entropy > 3.2` for length $16-128$) to prevent binary/base64 block false-positives.
* **Refusal Classification**: Scans replies for standard safety refusal indicators ("I cannot comply", "blocked by safety").
* **Offline Hybrid Evaluator**: Runs lexical and semantic word overlap comparisons to determine target compromise when Gemini APIs fail.

### 4. `optimizer` ([agents/nodes/optimizer.py](file:///d:/SentinAI-SMARTLVF/agents/nodes/optimizer.py))
* **Feedback-Loop Driven Mutation**: Selects mutator routines targeting the specific failure reasoning and refusal metrics of the previous attempt.
* **Mutator Pipeline Pattern**: Programmatically chains mutations (Base64 encoding, keyword leetspeak replacement, delimiters injection, bilingual pivoting wrappers, adversarial suffix jailbreaks).

---

## 🏃 Getting Started

### 📦 Dependencies Installation
This project manages dependency libraries inside [pyproject.toml](file:///d:/SentinAI-SMARTLVF/pyproject.toml). Install them using `pip`:

```bash
pip install -r requirements.txt
```

### 🔑 Configuration setup
Create a `.env` file based on `.env.example` in the project root:
```env
GROQ_API_KEY="your-groq-api-key"
GOOGLE_API_KEY="your-google-api-key"
USE_CELERY=False
```

### 🏃 Running Server & Frontend
To run the FastAPI server backend:
```bash
uvicorn main:app --reload
```

To run the Vite-React frontend local server:
```bash
cd frontend
npm run dev
```

---

## 🧪 Verification & Testing

Verify system integrity using the python unit test suites:

1. **Integration and Stateful Simulation Tests**:
   ```bash
   python -m unittest test_app.py
   ```
2. **Upgraded Nodes & Programmatic Elements Tests**:
   ```bash
   python -m unittest test_advanced_nodes.py
   ```
