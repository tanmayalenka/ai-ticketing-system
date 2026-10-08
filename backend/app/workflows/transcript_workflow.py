from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        chunk_transcript,
        redact_pii,
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
        return {
            "transcript_id": transcript_id,
            "redaction": redaction,
            "chunking": chunking,
            "stages_completed": ["redact_pii", "chunk_transcript"],
        }