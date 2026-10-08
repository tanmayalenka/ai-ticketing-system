import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
    getTranscriptByTrace,
    getTranscriptChunks,
    getSummary,
    type TranscriptDetail,
    type TopicChunk,
    type SummaryResponse,
} from "../api/client";

function Badge({
                   value,
                   pass,
                   label,
               }: {
    value: number;
    pass?: boolean;
    label: string;
}) {
    const tone =
        pass === true
            ? "bg-green-100 text-green-800 border-green-200"
            : pass === false
                ? "bg-red-100 text-red-800 border-red-200"
                : value >= 0.75
                    ? "bg-green-100 text-green-800 border-green-200"
                    : value >= 0.5
                        ? "bg-amber-100 text-amber-800 border-amber-200"
                        : "bg-red-100 text-red-800 border-red-200";
    return (
        <span
            className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${tone}`}
        >
      <span>{label}</span>
      <span className="font-mono">{(value * 100).toFixed(0)}%</span>
    </span>
    );
}

export default function ReviewPage() {
    const { traceId } = useParams<{ traceId: string }>();
    const [transcript, setTranscript] = useState<TranscriptDetail | null>(null);
    const [chunks, setChunks] = useState<TopicChunk[]>([]);
    const [summary, setSummary] = useState<SummaryResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [selectedChunk, setSelectedChunk] = useState<number | null>(null);
    const [expanded, setExpanded] = useState<Set<number>>(new Set());
    const chunkRefs = useRef<Record<number, HTMLDivElement | null>>({});

    useEffect(() => {
        if (!traceId) return;

        let cancelled = false;
        let interval: ReturnType<typeof setInterval> | undefined;

        async function load() {
            if (cancelled) return;
            setError(null);
            try {
                const t = await getTranscriptByTrace(traceId!);
                if (cancelled) return;
                setTranscript(t);

                let chunksReady = false;
                let summaryReady = false;

                try {
                    const c = await getTranscriptChunks(t.id);
                    if (!cancelled) {
                        setChunks(c.chunks);
                        chunksReady = true;
                    }
                } catch {
                    /* chunks not ready yet */
                }

                try {
                    const s = await getSummary(t.id);
                    if (!cancelled) {
                        setSummary(s);
                        summaryReady = true;
                    }
                } catch {
                    /* summary not ready yet */
                }

                // Stop polling once we have everything we need.
                if (chunksReady && summaryReady && interval !== undefined) {
                    clearInterval(interval);
                    interval = undefined;
                }
            } catch (e: unknown) {
                if (!cancelled) {
                    setError(
                        (e as any)?.response?.data?.detail ??
                        (e as Error).message ??
                        "Failed to load"
                    );
                }
            }
        }

        load();
        interval = setInterval(load, 3000);

        return () => {
            cancelled = true;
            if (interval !== undefined) clearInterval(interval);
        };
    }, [traceId]);

    const segmentToChunk = useMemo(() => {
        const map: Record<string, number> = {};
        for (const c of chunks) for (const sid of c.segment_ids) map[sid] = c.chunk_index;
        return map;
    }, [chunks]);

    const highlightSegment = (sid: string) =>
        selectedChunk !== null && segmentToChunk[sid] === selectedChunk;

    const focusChunk = (index: number) => {
        setSelectedChunk(index);
        setExpanded((prev) => new Set(prev).add(index));
        // scroll into view after the DOM updates
        setTimeout(() => {
            chunkRefs.current[index]?.scrollIntoView({
                behavior: "smooth",
                block: "start",
            });
        }, 0);
    };

    if (error) {
        return (
            <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
            </div>
        );
    }

    if (!transcript) {
        return <p className="text-sm text-slate-500">Loading…</p>;
    }

    return (
        <div className="space-y-6">
            {/* ---------- Header ---------- */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h2 className="text-2xl font-semibold">Review</h2>
                    <p className="text-xs text-slate-500">
                        Trace <span className="font-mono">{transcript.trace_id}</span> ·
                        Status <span className="font-medium">{transcript.status}</span>
                    </p>
                </div>
                {summary && (
                    <div className="flex items-center gap-2">
                        <Badge
                            value={summary.citation_validity}
                            label="Citation validity"
                            pass={summary.citation_validity === 1}
                        />
                        <Badge
                            value={summary.groundedness_score}
                            label="Groundedness"
                            pass={summary.overall_pass}
                        />
                        <span className="rounded border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600">
              {summary.model_name} · {summary.prompt_version}
            </span>
                    </div>
                )}
            </div>

            {!summary && (
                <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                    Pipeline is still running. Summaries will appear here once the
                    workflow completes.
                </div>
            )}

            {/* ---------- Call summary ---------- */}
            {summary && (
                <div className="rounded-lg border border-slate-200 bg-white p-5">
                    <div className="mb-2 flex items-center justify-between">
                        <h3 className="text-sm font-semibold uppercase text-slate-500">
                            Call summary
                        </h3>
                        <div className="flex gap-2">
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs capitalize text-slate-700">
                {summary.payload.call_summary.resolution_status.replace("_", " ")}
              </span>
                            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs capitalize text-slate-700">
                {summary.payload.call_summary.sentiment}
              </span>
                        </div>
                    </div>
                    <p className="text-sm font-medium text-slate-900">
                        {summary.payload.call_summary.primary_issue}
                    </p>
                    <p className="mt-2 text-sm text-slate-700">
                        {summary.payload.call_summary.overview}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1">
                        {summary.payload.call_summary.citations.map((sid) => (
                            <span
                                key={sid}
                                className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-600"
                            >
                {sid}
              </span>
                        ))}
                    </div>
                </div>
            )}

            {/* ---------- Issue summaries ---------- */}
            {summary && summary.payload.issue_summaries.length > 0 && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase text-slate-500">
                        Issues
                    </h3>
                    {summary.payload.issue_summaries.map((issue) => (
                        <div
                            key={issue.chunk_index}
                            className={`cursor-pointer rounded-lg border bg-white p-4 transition ${
                                selectedChunk === issue.chunk_index
                                    ? "border-blue-400 ring-1 ring-blue-200"
                                    : "border-slate-200 hover:border-slate-300"
                            }`}
                            onClick={() => focusChunk(issue.chunk_index)}
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <p className="text-sm font-semibold text-slate-900">
                                        {issue.title}
                                    </p>
                                    <p className="mt-1 text-sm text-slate-700">
                                        {issue.description}
                                    </p>
                                </div>
                                <Badge value={issue.confidence} label="Conf" />
                            </div>
                            <div className="mt-2 flex flex-wrap gap-1">
                                {issue.citations.map((sid) => (
                                    <span
                                        key={sid}
                                        className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-600"
                                    >
                    {sid}
                  </span>
                                ))}
                                <span className="ml-2 text-[11px] text-slate-400">
                  chunk {issue.chunk_index}
                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* ---------- Action items ---------- */}
            {summary && summary.payload.action_items.length > 0 && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase text-slate-500">
                        Action items
                    </h3>
                    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                            <tr>
                                <th className="px-4 py-2">Description</th>
                                <th className="px-4 py-2">Owner</th>
                                <th className="px-4 py-2">Deadline</th>
                                <th className="px-4 py-2">Citations</th>
                            </tr>
                            </thead>
                            <tbody>
                            {summary.payload.action_items.map((a, i) => (
                                <tr key={i} className="border-t border-slate-100">
                                    <td className="px-4 py-2">{a.description}</td>
                                    <td className="px-4 py-2">{a.owner}</td>
                                    <td className="px-4 py-2 text-slate-500">
                                        {a.deadline ?? "—"}
                                    </td>
                                    <td className="px-4 py-2">
                                        <div className="flex flex-wrap gap-1">
                                            {a.citations.map((sid) => (
                                                <span
                                                    key={sid}
                                                    className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[11px] text-slate-600"
                                                >
                            {sid}
                          </span>
                                            ))}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* ---------- Chunk viewer ---------- */}
            {chunks.length > 0 && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase text-slate-500">
                        Source chunks
                    </h3>
                    {chunks.map((c) => {
                        const isOpen = expanded.has(c.chunk_index);
                        const isSelected = selectedChunk === c.chunk_index;
                        return (
                            <div
                                key={c.chunk_index}
                                ref={(el) => {
                                    chunkRefs.current[c.chunk_index] = el;
                                }}
                                className={`rounded-lg border bg-white ${
                                    isSelected ? "border-blue-400" : "border-slate-200"
                                }`}
                            >
                                <button
                                    onClick={() => {
                                        setExpanded((prev) => {
                                            const next = new Set(prev);
                                            if (next.has(c.chunk_index)) next.delete(c.chunk_index);
                                            else next.add(c.chunk_index);
                                            return next;
                                        });
                                    }}
                                    className="flex w-full items-center justify-between px-4 py-3 text-left"
                                >
                                    <div>
                                        <p className="text-sm font-medium text-slate-900">
                                            Chunk {c.chunk_index} · {c.topic_label ?? "untitled"}
                                        </p>
                                        <p className="mt-0.5 text-xs text-slate-500">
                                            {c.segment_ids.length} segments · speakers:{" "}
                                            {c.speakers.join(", ")} · coherence{" "}
                                            {c.coherence_score?.toFixed(2) ?? "—"}
                                        </p>
                                    </div>
                                    <span className="text-xs text-slate-400">
                    {isOpen ? "Hide" : "Show"}
                  </span>
                                </button>
                                {isOpen && (
                                    <div className="border-t border-slate-100 px-4 py-3 text-sm">
                                        {c.segment_ids.map((sid, i) => {
                                            const raw = c.text.split("\n")[i] ?? "";
                                            const highlighted = highlightSegment(sid);
                                            return (
                                                <div
                                                    key={sid}
                                                    className={`mb-1 rounded px-2 py-1 ${
                                                        highlighted
                                                            ? "bg-yellow-100 text-slate-900"
                                                            : "text-slate-700"
                                                    }`}
                                                >
                          <span className="mr-2 font-mono text-[11px] text-slate-400">
                            {sid}
                          </span>
                                                    {raw}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}