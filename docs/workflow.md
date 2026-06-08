# Workflow

The workflow uses LangGraph when available. If LangGraph cannot import in a constrained local environment, the app keeps the same graph abstraction and executes a documented sequential fallback with the same node names and state contract.

## Nodes

1. `intake_classifier`
   Classifies category, priority, sentiment, confidence, and rationale.

2. `sla_risk_scorer`
   Scores SLA risk using priority, customer tier, outage terms, breach terms, and production impact.

3. `knowledge_retriever`
   Searches the internal KB adapter with retry handling and records every tool call.

4. `customer_reply_drafter`
   Drafts a customer-safe reply using local mock LLM behavior and retrieved KB context.

5. `engineering_escalation_drafter`
   Drafts a Jira-ready escalation when SLA risk, incident, auth, API, or integration signals warrant it.

6. `qa_evaluator`
   Checks confidence, KB failures, risky categories, and high-SLA-risk conditions.

7. `human_approval`
   Creates a pending approval. The system always pauses before customer replies or engineering tickets.

8. `finalizer`
   During initial analysis, marks the run as awaiting approval without dispatching external actions. After approval, it sends fake Zendesk/Jira/Slack actions. After rejection, it records rejection.

## Failure Handling

Tool failures retry up to `CONTROL_TOWER_MAX_TOOL_ATTEMPTS`. Exhausted retries set `failure_state`, lower QA confidence, and force human review. The trace endpoint shows every failed attempt.

## Routing

High-SLA-risk tickets draft an engineering escalation. Low-confidence or risky actions also require approval. Because all outbound customer and engineering actions require approval, the approval gate is universal by design.

