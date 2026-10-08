import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.config import settings
from app.workflows.activities import chunk_transcript, redact_pii
from app.workflows.transcript_workflow import TranscriptProcessingWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("worker")


async def main() -> None:
    client = await Client.connect(
        settings.temporal_host, namespace=settings.temporal_namespace
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[TranscriptProcessingWorkflow],
        activities=[redact_pii, chunk_transcript],
    )
    log.info("Worker started on task queue: %s", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())