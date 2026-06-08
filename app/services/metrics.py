from app.core.storage import JsonStateStore


class MetricsService:
    def __init__(self, store: JsonStateStore):
        self.store = store

    async def record_node_metrics(self, node: str, latency_ms: float, tokens: int = 0, cost_usd: float = 0.0) -> None:
        def mutate(state):
            item = state["metrics"].setdefault("node_metrics", {}).setdefault(node, {"count": 0, "latency_ms": 0.0, "tokens": 0, "cost_usd": 0.0})
            item["count"] += 1
            item["latency_ms"] += latency_ms
            item["tokens"] += tokens
            item["cost_usd"] += cost_usd
            state["metrics"]["cost_usd"] = state["metrics"].get("cost_usd", 0.0) + cost_usd

        await self.store.update(mutate)

    async def agent_performance(self) -> dict:
        state = await self.store.load()
        runs = list(state["runs"].values())
        approvals = list(state["approvals"].values())
        nodes = {}
        for node, data in state["metrics"].get("node_metrics", {}).items():
            count = data.get("count") or 1
            nodes[node] = {**data, "avg_latency_ms": round(data.get("latency_ms", 0.0) / count, 2)}
        return {
            "run_count": len(runs),
            "total_runs": len(runs),
            "completed_runs": len([r for r in runs if r["status"] == "completed"]),
            "pending_approval_runs": len([r for r in runs if r["status"] in {"awaiting_approval", "pending_approval"}]),
            "pending_approvals": len([a for a in approvals if a["status"] == "pending"]),
            "estimated_cost_usd": round(state["metrics"].get("cost_usd", 0.0), 6),
            "node_metrics": nodes,
        }

