import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        chunk_transcript,
        create_ticket_draft,
        detect_duplicates,
        mark_draft_rejected,
        persist_approved_ticket,
        redact_pii,
        route_ticket_activity,
        summarize_call,
    )

LLM_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)

REVIEW_TIMEOUT = timedelta(hours=24)


@workflow.defn
class TranscriptProcessingWorkflow:
    def __init__(self) -> None:
        self._decision: dict | None = None

    @workflow.signal
    async def agent_decision(self, payload: dict) -> None:
        """Called by the API when the agent approves or rejects the draft.

        payload = {"action": "approve"|"reject", "reviewed_by": str,
                   "reviewed_payload": dict | None, "reason": str | None}
        """
        self._decision = payload

    @workflow.query
    def current_state(self) -> dict:
        return {
            "awaiting_decision": self._decision is None,
            "decision": self._decision,
        }

    @workflow.run
    async def run(self, transcript_id: str) -> dict:
        redaction = await workflow.execute_activity(
            redact_pii, transcript_id,
            start_to_close_timeout=timedelta(minutes=2),
        )
        chunking = await workflow.execute_activity(
            chunk_transcript, transcript_id,
            start_to_close_timeout=timedelta(minutes=3),
        )
        summarization = await workflow.execute_activity(
            summarize_call, transcript_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=LLM_RETRY,
        )
        duplicates = await workflow.execute_activity(
            detect_duplicates, transcript_id,
            start_to_close_timeout=timedelta(minutes=2),
        )
        draft_result = await workflow.execute_activity(
            create_ticket_draft, transcript_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=LLM_RETRY,
        )

        # --- Pause for human decision ---
        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=REVIEW_TIMEOUT,
            )
        except asyncio.TimeoutError:
            workflow.logger.warning("Agent review timed out for %s", transcript_id)
            return {
                "transcript_id": transcript_id,
                "stages_completed": [
                    "redact_pii", "chunk_transcript", "summarize_call",
                    "detect_duplicates", "create_ticket_draft",
                ],
                "outcome": "review_timeout",
                "draft_id": draft_result["draft_id"],
            }

        decision = self._decision or {}
        action = decision.get("action")
        reviewed_by = decision.get("reviewed_by") or "unknown"

        if action == "approve":
            reviewed_payload = decision.get("reviewed_payload") or {}
            persisted = await workflow.execute_activity(
                persist_approved_ticket,
                args=[draft_result["draft_id"], reviewed_payload, reviewed_by],
                start_to_close_timeout=timedelta(minutes=2),
            )

            # Route the freshly-created ticket. Non-fatal if it fails:
            # the ticket exists, and a human can assign it manually.
            routing: dict | None = None
            try:
                routing = await workflow.execute_activity(
                    route_ticket_activity,
                    persisted["ticket_id"],
                    start_to_close_timeout=timedelta(minutes=1),
                )
            except Exception as exc:  # pragma: no cover
                workflow.logger.warning(
                    "Routing failed for ticket %s: %s",
                    persisted.get("ticket_id"), exc,
                )

            outcome = "approved"
        elif action == "reject":
            rejected = await workflow.execute_activity(
                mark_draft_rejected,
                args=[
                    draft_result["draft_id"],
                    decision.get("reason") or "",
                    reviewed_by,
                    ],
                start_to_close_timeout=timedelta(minutes=2),
            )
            persisted = rejected
            outcome = "rejected"
        else:
            persisted = {}
            outcome = "unknown_action"

        return {
            "transcript_id": transcript_id,
            "outcome": outcome,
            "redaction": redaction,
            "chunking": chunking,
            "summarization": summarization,
            "duplicates": duplicates,
            "draft": draft_result,
            "persisted": persisted,
            "routing": routing,
        }