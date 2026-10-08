import { useEffect, useMemo, useState } from "react";
import {
    approveDraft,
    rejectDraft,
    type TicketDraftPayload,
    type TicketDraftResponse,
    CATEGORIES,
    PRIORITIES,
} from "../api/client";

function ConfidenceBadge({ value }: { value: number | undefined }) {
    if (value === undefined) return null;
    const tone =
        value >= 0.8
            ? "bg-green-100 text-green-800 border-green-200"
            : value >= 0.55
                ? "bg-amber-100 text-amber-800 border-amber-200"
                : "bg-red-100 text-red-800 border-red-200";
    return (
        <span
            className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${tone}`}
    title="Model self-reported confidence"
        >
        {Math.round(value * 100)}%
        </span>
);
}

function CandidateList({
                           candidates,
                           recommendation,
                       }: {
    candidates: TicketDraftResponse["duplicate_candidates"];
    recommendation: TicketDraftResponse["duplicate_recommendation"];
}) {
    if (candidates.length === 0) return null;
    const tone =
        recommendation === "link_to_existing"
            ? "border-red-200 bg-red-50"
            : recommendation === "needs_human_decision"
                ? "border-amber-200 bg-amber-50"
                : "border-slate-200 bg-slate-50";
    return (
        <div className={`rounded border p-3 text-sm ${tone}`}>
    <p className="font-medium">
        Possible duplicate tickets ({candidates.length})
    </p>
    <ul className="mt-1 space-y-0.5 text-xs">
        {candidates.map((c) => (
                <li key={c.ticket_id} className="font-mono">
                {c.ticket_id.slice(0, 8)}… · similarity{" "}
    {(c.similarity * 100).toFixed(1)}%
    </li>
))}
    </ul>
    <p className="mt-1 text-xs italic">
        Recommendation: <strong>{recommendation.replace(/_/g, " ")}</strong>
    </p>
    </div>
);
}

export default function TicketDraftReview({
                                              draft,
                                              onDecision,
                                          }: {
    draft: TicketDraftResponse;
    onDecision: () => void;
}) {
    const initial: TicketDraftPayload = useMemo(
        () => draft.reviewed_payload ?? draft.payload,
        [draft]
    );
    const [form, setForm] = useState<TicketDraftPayload>(initial);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
    const [err, setErr] = useState<string | null>(null);
    const [dirty, setDirty] = useState(false);

    useEffect(() => {
        setForm(initial);
        setDirty(false);
    }, [initial]);

    const update = <K extends keyof TicketDraftPayload>(
        key: K,
        value: TicketDraftPayload[K]
    ) => {
        setForm((f) => ({ ...f, [key]: value }));
        setDirty(true);
    };

    const doApprove = async () => {
        setBusy("approve");
        setErr(null);
        try {
            await approveDraft(draft.trace_id, form);
            onDecision();
        } catch (e: unknown) {
            setErr((e as any)?.response?.data?.detail ?? (e as Error).message);
        } finally {
            setBusy(null);
        }
    };

    const doReject = async () => {
        setBusy("reject");
        setErr(null);
        try {
            await rejectDraft(draft.trace_id, reason);
            onDecision();
        } catch (e: unknown) {
            setErr((e as any)?.response?.data?.detail ?? (e as Error).message);
        } finally {
            setBusy(null);
        }
    };

    const isPending = draft.status === "pending";
    const conf = form.confidence ?? {};

    return (
        <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase text-slate-500">
            Ticket draft
    </h3>
    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
        {draft.model_name} · {draft.prompt_version} · status: {draft.status}
    </span>
    </div>

    <CandidateList
    candidates={draft.duplicate_candidates}
    recommendation={draft.duplicate_recommendation}
    />

    {/* Title */}
    <div>
        <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
        Title <ConfidenceBadge value={conf.title} />
    </label>
    <input
    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
    value={form.title}
    onChange={(e) => update("title", e.target.value)}
    disabled={!isPending}
    />
    </div>

    {/* Description */}
    <div>
        <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
        Description <ConfidenceBadge value={conf.description} />
    </label>
    <textarea
    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
    rows={6}
    value={form.description}
    onChange={(e) => update("description", e.target.value)}
    disabled={!isPending}
    />
    </div>

    {/* Priority + Category + Team */}
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
    <div>
        <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
        Priority <ConfidenceBadge value={conf.priority} />
    </label>
    <select
    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm capitalize disabled:bg-slate-50"
    value={form.priority}
    onChange={(e) =>
    update("priority", e.target.value as TicketDraftPayload["priority"])
}
    disabled={!isPending}
>
    {PRIORITIES.map((p) => (
        <option key={p} value={p}>
        {p}
        </option>
    ))}
    </select>
    </div>

    <div>
    <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
        Category <ConfidenceBadge value={conf.category} />
    </label>
    <select
    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
    value={form.category}
    onChange={(e) => update("category", e.target.value)}
    disabled={!isPending}
>
    {CATEGORIES.map((c) => (
        <option key={c} value={c}>
        {c}
        </option>
    ))}
    {!CATEGORIES.includes(form.category as any) && form.category && (
        <option value={form.category}>{form.category}</option>
    )}
    </select>
    </div>

    <div>
    <label className="text-xs font-medium text-slate-600">
        Suggested team
    </label>
    <input
    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
    value={form.suggested_team}
    onChange={(e) => update("suggested_team", e.target.value)}
    disabled={!isPending}
    />
    </div>
    </div>

    {/* Customer impact */}
    <div>
        <label className="text-xs font-medium text-slate-600">
        Customer impact
    </label>
    <input
    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
    value={form.customer_impact ?? ""}
    onChange={(e) =>
    update("customer_impact", e.target.value || null)
}
    disabled={!isPending}
    />
    </div>

    {/* Citations */}
    <div>
        <p className="text-xs font-medium text-slate-600">Citations</p>
        <div className="mt-1 flex flex-wrap gap-1">
        {(form.citations ?? []).map((sid) => (
            <span
                key={sid}
    className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-600"
        >
        {sid}
        </span>
))}
    </div>
    </div>

    {err && (
        <div className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">
            {err}
            </div>
    )}

    {isPending ? (
            <div className="space-y-2 border-t border-slate-100 pt-4">
            <div className="flex flex-wrap items-center gap-2">
            <button
                onClick={doApprove}
        disabled={busy !== null}
        className="rounded bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-800 disabled:opacity-50"
        >
        {busy === "approve"
            ? "Submitting…"
            : dirty
                ? "Edit and Approve"
                : "Approve"}
        </button>
        <button
        onClick={doReject}
        disabled={busy !== null || !reason.trim()}
        title={!reason.trim() ? "Provide a rejection reason below" : ""}
        className="rounded border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
        {busy === "reject" ? "Rejecting…" : "Reject"}
        </button>
        </div>
        <textarea
        className="w-full rounded border border-slate-300 px-3 py-2 text-xs"
        placeholder="Rejection reason (required to reject)"
        rows={2}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        />
        </div>
    ) : (
        <div className="rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            Reviewed by <strong>{draft.reviewed_by ?? "—"}</strong>
        {draft.reviewed_at
            ? ` on ${new Date(draft.reviewed_at).toLocaleString()}`
            : ""}
        {draft.review_notes ? ` · reason: ${draft.review_notes}` : ""}
        </div>
    )}
    </div>
);
}