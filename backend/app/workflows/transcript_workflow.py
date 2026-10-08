from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        chunk_transcript,
        redact_pii,
        summarize_call,
    )

# LLM calls are flaky; give them a couple retries with backoff.
LLM_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)


@workflow.defn
class TranscriptProcessingWorkflow:
    @workflow.run
    async def run(self, transcript_id: str) -> dict:
        redaction = await workflow.execute_activity(
            redact_pii,
            transcript_id,
            start_to_close_timeout=timedelta(minutes=2),
        )
        chunking = await workflow.execute_activity(
            chunk_transcript,
            transcript_id,
            start_to_close_timeout=timedelta(minutes=3),
        )
        summarization = await workflow.execute_activity(
            summarize_call,
            transcript_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=LLM_RETRY,
        )
        return {
            "transcript_id": transcript_id,
            "redaction": redaction,
            "chunking": chunking,
            "summarization": summarization,
            "stages_completed": [
                "redact_pii",
                "chunk_transcript",
                "summarize_call",
            ],
        }