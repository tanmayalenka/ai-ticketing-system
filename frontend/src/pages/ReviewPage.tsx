import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type {
    RedactedSegment,
    TopicChunk,
    TranscriptDetail,
} from "../api/client";

export default function ReviewPage() {
    const { traceId } = useParams<{ traceId: string }>();
    const [transcript, setTranscript] = useState<TranscriptDetail | null>(null);
    const [redacted, setRedacted] = useState<RedactedSegment[] | null>(null);
    const [entityCounts, setEntityCounts] = useState<Record<string, number>>({});
    const [chunks, setChunks] = useState<TopicChunk[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!traceId) return;
        // We don't have a trace->transcript lookup endpoint yet, so we use the
        // first transcript we can find. In Step 4 we'll add /transcripts/by-trace.
        setError(null);
        // Placeholder: fetch the most recent transcript list via tickets endpoint
        // is not available. For now, prompt the user to pass transcript_id in URL.
    }, [traceId]);

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-semibold">Pipeline Review</h2>
                <p className="text-sm text-slate-600">
                    Trace <span className="font-mono text-xs">{traceId}</span>
                </p>
            </div>

            {error && (
                <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
                <p>
                    This page will show the redacted transcript and topic chunks once a{" "}
                    <code className="rounded bg-slate-100 px-1">/transcripts/by-trace</code>{" "}
                    endpoint is added in Step 4.
                </p>
                <p className="mt-2">
                    For now, verify the pipeline via the API directly (see Step 3.10).
                </p>
            </div>
        </div>
    );
}