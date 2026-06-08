from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.adapters import FakeJiraAdapter, FakeSlackAdapter
from app.models import (
    ActionType,
    AgentRun,
    ApprovalDecision,
    ApprovalStatus,
    CustomerReplyDraft,
    EscalationDraft,
    QAEvaluation,
    RunStatus,
    SlaRisk,
    TicketClassification,
    TicketStatus,
    utc_now,
)
from app.providers import BaseLLMProvider, MockLLMProvider
from app.services import (
    ApprovalService,
    KnowledgeRetrievalService,
    MetricsService,
    NodeTimer,
    RunRepository,
    TicketService,
    TraceService,
    customer_reply_payload,
    minutes_until,
)


class WorkflowState(TypedDict, total=False):
    run_id: str
    ticket_id: str
    ticket: dict[str, Any]
    classification: dict[str, Any]
    sla_risk: dict[str, Any]
    citations: list[dict[str, Any]]
    customer_reply: dict[str, Any]
    escalation: dict[str, Any] | None
    qa: dict[str, Any]
    approval_id: str | None
    final_action: str | None
    errors: list[dict[str, Any]]


class AgentWorkflowService:
    def __init__(
        self,
        tickets: TicketService,
        runs: RunRepository,
        retrieval: KnowledgeRetrievalService,
        approvals: ApprovalService,
        traces: TraceService,
        metrics: MetricsService,
        provider: BaseLLMProvider | None = None,
        jira: FakeJiraAdapter | None = None,
        slack: FakeSlackAdapter | None = None,
        max_tool_attempts: int = 2,
    ):
        self.tickets = tickets
        self.runs = runs
        self.retrieval = retrieval
        self.approvals = approvals
        self.traces = traces
        self.metrics = metrics
        self.provider = provider or MockLLMProvider()
        self.jira = jira or FakeJiraAdapter()
        self.slack = slack or FakeSlackAdapter()
        self.max_tool_attempts = max_tool_attempts
        self.graph = self._build_graph()

    async def analyze_ticket(self, ticket_id: str) -> AgentRun:
        ticket = self.tickets.get(ticket_id)
        ticket.status = TicketStatus.ANALYZING
        self.tickets.save(ticket)
        run = self.runs.create(ticket_id)
        run.status = RunStatus.RUNNING
        run.current_state = "intake_classifier"
        self.runs.save(run)
        state: WorkflowState = {
            "run_id": run.id,
            "ticket_id": ticket.id,
            "ticket": ticket.model_dump(mode="json"),
            "errors": [],
        }
        final_state = await self.graph.ainvoke(state)
        run = self.runs.get(run.id)
        run.state = dict(final_state)
        if run.status != RunStatus.AWAITING_APPROVAL:
            run.status = RunStatus.COMPLETED
            run.completed_at = utc_now()
            ticket.status = (
                TicketStatus.ESCALATED
                if run.final_action == ActionType.ENGINEERING_ESCALATION
                else TicketStatus.RESOLVED
            )
            self.tickets.save(ticket)
        self.runs.save(run)
        return run

    async def approve(self, run_id: str, decision: ApprovalDecision) -> AgentRun:
        approval = self.approvals.decide(run_id, decision, ApprovalStatus.APPROVED)
        run = self.runs.get(run_id)
        ticket = self.tickets.get(run.ticket_id)
        if approval.action_type == ActionType.ENGINEERING_ESCALATION:
            await self.jira.create_issue(approval.proposed_payload)
            await self.slack.post_message("#support-escalations", approval.proposed_payload)
            final_action = ActionType.ENGINEERING_ESCALATION
            ticket.status = TicketStatus.ESCALATED
        elif approval.action_type == ActionType.CUSTOMER_REPLY:
            await self.slack.post_message("#support-drafts", approval.proposed_payload)
            final_action = ActionType.CUSTOMER_REPLY
            ticket.status = TicketStatus.RESOLVED
        else:
            final_action = ActionType.HUMAN_REVIEW
            ticket.status = TicketStatus.RESOLVED
        self.traces.record(
            run_id,
            "finalizer",
            "approval_finalized",
            {"approval_id": approval.id, "final_action": final_action},
        )
        run.status = RunStatus.COMPLETED
        run.current_state = "finalizer"
        run.final_action = final_action
        run.completed_at = utc_now()
        run.state["final_action"] = final_action
        self.tickets.save(ticket)
        self.runs.save(run)
        return run

    async def reject(self, run_id: str, decision: ApprovalDecision) -> AgentRun:
        approval = self.approvals.decide(run_id, decision, ApprovalStatus.REJECTED)
        run = self.runs.get(run_id)
        ticket = self.tickets.get(run.ticket_id)
        self.traces.record(
            run_id,
            "finalizer",
            "approval_rejected",
            {"approval_id": approval.id, "notes": decision.reviewer_notes},
        )
        ticket.status = TicketStatus.REJECTED
        run.status = RunStatus.COMPLETED
        run.current_state = "finalizer"
        run.final_action = "rejected"
        run.completed_at = utc_now()
        run.state["final_action"] = "rejected"
        self.tickets.save(ticket)
        self.runs.save(run)
        return run

    def _build_graph(self):
        graph = StateGraph(WorkflowState)
        graph.add_node("intake_classifier", self._intake_classifier)
        graph.add_node("sla_risk_scorer", self._sla_risk_scorer)
        graph.add_node("knowledge_retriever", self._knowledge_retriever)
        graph.add_node("customer_reply_drafter", self._customer_reply_drafter)
        graph.add_node("engineering_escalation_drafter", self._engineering_escalation_drafter)
        graph.add_node("qa_evaluator", self._qa_evaluator)
        graph.add_node("human_approval", self._human_approval)
        graph.add_node("finalizer", self._finalizer)
        graph.set_entry_point("intake_classifier")
        graph.add_edge("intake_classifier", "sla_risk_scorer")
        graph.add_edge("sla_risk_scorer", "knowledge_retriever")
        graph.add_edge("knowledge_retriever", "customer_reply_drafter")
        graph.add_edge("customer_reply_drafter", "engineering_escalation_drafter")
        graph.add_edge("engineering_escalation_drafter", "qa_evaluator")
        graph.add_conditional_edges(
            "qa_evaluator",
            self._approval_route,
            {"approval": "human_approval", "final": "finalizer"},
        )
        graph.add_edge("human_approval", END)
        graph.add_edge("finalizer", END)
        return graph.compile()

    async def _intake_classifier(self, state: WorkflowState) -> WorkflowState:
        node = "intake_classifier"
        with NodeTimer() as timer:
            result = await self.provider.complete_json("classify", {"ticket": state["ticket"]})
            classification = TicketClassification.model_validate(result.content)
        trace = self.traces.record(
            state["run_id"],
            node,
            "model_call",
            classification.model_dump(mode="json"),
            timer.latency_ms + result.latency_ms,
            {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
        )
        self.metrics.record_usage(
            trace.id,
            self.provider.name,
            result.model,
            result.input_tokens,
            result.output_tokens,
            result.latency_ms,
            result.estimated_cost,
        )
        self._update_run(state["run_id"], node, {"classification": classification.model_dump(mode="json")})
        return {"classification": classification.model_dump(mode="json")}

    async def _sla_risk_scorer(self, state: WorkflowState) -> WorkflowState:
        node = "sla_risk_scorer"
        with NodeTimer() as timer:
            minutes = minutes_until(self.tickets.get(state["ticket_id"]).sla_due_at)
            classification = state["classification"]
            if minutes <= 60 or classification["urgency"] == "critical":
                level = "high"
                action = "prepare escalation and page human reviewer"
            elif minutes <= 240 or classification["urgency"] == "high":
                level = "medium"
                action = "prioritize response and keep reviewer in loop"
            else:
                level = "low"
                action = "standard support handling"
            risk = SlaRisk(
                risk_level=level,
                minutes_remaining=minutes,
                reason=f"{classification['urgency']} urgency with {minutes} minutes until SLA",
                recommended_action=action,
            )
        self.traces.record(state["run_id"], node, "transition", risk.model_dump(mode="json"), timer.latency_ms)
        self._update_run(state["run_id"], node, {"sla_risk": risk.model_dump(mode="json")})
        return {"sla_risk": risk.model_dump(mode="json")}

    async def _knowledge_retriever(self, state: WorkflowState) -> WorkflowState:
        node = "knowledge_retriever"
        last_error: Exception | None = None
        for attempt in range(1, self.max_tool_attempts + 1):
            with NodeTimer() as timer:
                try:
                    query = f"{state['ticket']['subject']} {state['ticket']['body']}"
                    citations = await self.retrieval.search(query)
                    payload = [item.model_dump(mode="json") for item in citations]
                    self.traces.record(
                        state["run_id"],
                        node,
                        "tool_call",
                        {"attempt": attempt, "citations": payload},
                        timer.latency_ms,
                    )
                    self._update_run(state["run_id"], node, {"citations": payload})
                    return {"citations": payload}
                except Exception as exc:  # pragma: no cover - exercised by retry tests
                    last_error = exc
                    self.traces.record(
                        state["run_id"],
                        node,
                        "failure",
                        {"attempt": attempt, "error": str(exc)},
                        timer.latency_ms,
                    )
        errors = state.get("errors", []) + [{"node": node, "error": str(last_error)}]
        self._update_run(state["run_id"], node, {"citations": [], "errors": errors})
        return {"citations": [], "errors": errors}

    async def _customer_reply_drafter(self, state: WorkflowState) -> WorkflowState:
        node = "customer_reply_drafter"
        with NodeTimer() as timer:
            result = await self.provider.complete_json(
                "customer_reply",
                {"ticket": state["ticket"], "citations": state.get("citations", [])},
            )
            reply = CustomerReplyDraft.model_validate(result.content)
        trace = self.traces.record(
            state["run_id"],
            node,
            "model_call",
            reply.model_dump(mode="json"),
            timer.latency_ms + result.latency_ms,
            {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
        )
        self.metrics.record_usage(
            trace.id,
            self.provider.name,
            result.model,
            result.input_tokens,
            result.output_tokens,
            result.latency_ms,
            result.estimated_cost,
        )
        self._update_run(state["run_id"], node, {"customer_reply": reply.model_dump(mode="json")})
        return {"customer_reply": reply.model_dump(mode="json")}

    async def _engineering_escalation_drafter(self, state: WorkflowState) -> WorkflowState:
        node = "engineering_escalation_drafter"
        classification = state["classification"]
        sla = state["sla_risk"]
        should_escalate = classification["likely_owner"] == "engineering" or sla["risk_level"] == "high"
        if not should_escalate:
            self.traces.record(state["run_id"], node, "transition", {"skipped": True})
            self._update_run(state["run_id"], node, {"escalation": None})
            return {"escalation": None}
        with NodeTimer() as timer:
            result = await self.provider.complete_json(
                "engineering_escalation",
                {
                    "ticket": state["ticket"],
                    "classification": classification,
                    "sla_risk": sla,
                    "citations": state.get("citations", []),
                },
            )
            escalation = EscalationDraft.model_validate(result.content)
        trace = self.traces.record(
            state["run_id"],
            node,
            "model_call",
            escalation.model_dump(mode="json"),
            timer.latency_ms + result.latency_ms,
            {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
        )
        self.metrics.record_usage(
            trace.id,
            self.provider.name,
            result.model,
            result.input_tokens,
            result.output_tokens,
            result.latency_ms,
            result.estimated_cost,
        )
        self._update_run(state["run_id"], node, {"escalation": escalation.model_dump(mode="json")})
        return {"escalation": escalation.model_dump(mode="json")}

    async def _qa_evaluator(self, state: WorkflowState) -> WorkflowState:
        node = "qa_evaluator"
        with NodeTimer() as timer:
            classification = state["classification"]
            sla = state["sla_risk"]
            has_escalation = bool(state.get("escalation"))
            risk_flags = []
            if classification["confidence"] < 0.7:
                risk_flags.append("low_classification_confidence")
            if not state.get("citations"):
                risk_flags.append("missing_grounding")
            if sla["risk_level"] == "high":
                risk_flags.append("high_sla_risk")
            action_type = (
                ActionType.ENGINEERING_ESCALATION
                if has_escalation
                else ActionType.CUSTOMER_REPLY
            )
            qa = QAEvaluation(
                confidence=min(classification["confidence"], state["customer_reply"]["confidence"]),
                grounded=bool(state.get("citations")),
                tone=state["customer_reply"]["tone"],
                risk_flags=risk_flags,
                requires_human_approval=True,
                action_type=action_type,
                reason="External and engineering-facing actions require approval",
            )
        self.traces.record(state["run_id"], node, "transition", qa.model_dump(mode="json"), timer.latency_ms)
        self._update_run(state["run_id"], node, {"qa": qa.model_dump(mode="json")})
        return {"qa": qa.model_dump(mode="json")}

    async def _human_approval(self, state: WorkflowState) -> WorkflowState:
        node = "human_approval"
        action_type = ActionType(state["qa"]["action_type"])
        payload = (
            state["escalation"]
            if action_type == ActionType.ENGINEERING_ESCALATION
            else customer_reply_payload(CustomerReplyDraft.model_validate(state["customer_reply"]))
        )
        approval = self.approvals.create(state["run_id"], action_type, payload or {})
        run = self.runs.get(state["run_id"])
        run.status = RunStatus.AWAITING_APPROVAL
        run.current_state = node
        run.final_action = action_type
        run.state.update(dict(state))
        run.state["approval_id"] = approval.id
        self.runs.save(run)
        ticket = self.tickets.get(state["ticket_id"])
        ticket.status = TicketStatus.AWAITING_APPROVAL
        self.tickets.save(ticket)
        self.traces.record(
            state["run_id"],
            node,
            "approval_pause",
            {"approval_id": approval.id, "action_type": action_type},
        )
        return {"approval_id": approval.id, "final_action": action_type}

    async def _finalizer(self, state: WorkflowState) -> WorkflowState:
        node = "finalizer"
        final_action = ActionType.CUSTOMER_REPLY
        self.traces.record(state["run_id"], node, "transition", {"final_action": final_action})
        self._update_run(
            state["run_id"],
            node,
            {"final_action": final_action, "completed_at": utc_now().isoformat()},
            status=RunStatus.COMPLETED,
        )
        return {"final_action": final_action}

    def _approval_route(self, state: WorkflowState) -> str:
        return "approval" if state["qa"]["requires_human_approval"] else "final"

    def _update_run(
        self,
        run_id: str,
        current_state: str,
        state_update: dict[str, Any],
        status: RunStatus | None = None,
    ) -> None:
        run = self.runs.get(run_id)
        run.current_state = current_state
        if status:
            run.status = status
        run.state.update(state_update)
        self.runs.save(run)
