import argparse
import asyncio

from app.core.config import get_settings
from app.services.factory import ServiceContainer


async def run_demo() -> None:
    container = ServiceContainer(get_settings())
    tickets = await container.tickets.list()
    selected = tickets[0]
    run = await container.workflow.analyze_ticket(selected.ticket_id)
    trace = await container.trace.list_events(run.run_id)
    approvals = await container.approvals.list_pending()
    print("Support Escalation Agent Control Tower demo")
    print(f"Ticket: {selected.subject} ({selected.ticket_id})")
    print(f"Run: {run.run_id} status={run.status} final_action={run.final_action}")
    print(f"Trace events: {len(trace)}")
    print(f"Pending approvals: {len(approvals)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["demo"])
    args = parser.parse_args()
    if args.command == "demo":
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
