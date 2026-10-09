import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
    listTickets,
    listAgents,
    getWorkload,
    type AgentRow,
    type TeamWorkload,
    type TicketFilters,
    type TicketListRow,
    CATEGORIES,
    PRIORITIES,
} from "../api/client";

function UtilizationBar({ value }: { value: number }) {
    const pct = Math.round(value * 100);
    const tone =
        pct >= 90
            ? "bg-red-500"
            : pct >= 70
                ? "bg-amber-500"
                : "bg-green-500";
    return (
        <div className="flex items-center gap-2">
            <div className="h-1.5 w-16 overflow-hidden rounded bg-slate-200">
                <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-xs text-slate-600">{pct}%</span>
        </div>
    );
}

function WorkloadPanel({ workload }: { workload: TeamWorkload[] }) {
    if (workload.length === 0) return null;
    return (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold uppercase text-slate-500">
                Team workload
            </h3>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {workload.map((t) => (
                    <div key={t.team} className="rounded border border-slate-100 p-3">
                        <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-900">
                {t.team}
              </span>
                            <span className="text-xs text-slate-500">
                {t.online_count}/{t.agent_count} online
              </span>
                        </div>
                        <div className="mt-2 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                {t.total_load}/{t.total_capacity} tickets
              </span>
                            <UtilizationBar value={t.utilization} />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function TicketListPage() {
    const [tickets, setTickets] = useState<TicketListRow[]>([]);
    const [agents, setAgents] = useState<AgentRow[]>([]);
    const [workload, setWorkload] = useState<TeamWorkload[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filters, setFilters] = useState<TicketFilters>({});

    // Load agents once
    useEffect(() => {
        listAgents().then(setAgents).catch(() => {});
        getWorkload()
            .then((w) => setWorkload(w.teams))
            .catch(() => {});
    }, []);

    // Reload tickets when filters change
    useEffect(() => {
        setLoading(true);
        setError(null);
        listTickets(filters)
            .then(setTickets)
            .catch((e) =>
                setError((e as any)?.response?.data?.detail ?? (e as Error).message)
            )
            .finally(() => setLoading(false));
    }, [filters]);

    const set = (key: keyof TicketFilters, value: string) =>
        setFilters((f) => ({ ...f, [key]: value || undefined }));

    const activeFilterCount = useMemo(
        () => Object.values(filters).filter(Boolean).length,
        [filters]
    );

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <h2 className="text-2xl font-semibold">Tickets</h2>
                    <p className="text-sm text-slate-600">
                        All tickets, with assignment and workload context.
                    </p>
                </div>
                {activeFilterCount > 0 && (
                    <button
                        onClick={() => setFilters({})}
                        className="rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
                    >
                        Clear {activeFilterCount} filter{activeFilterCount > 1 ? "s" : ""}
                    </button>
                )}
            </div>

            <WorkloadPanel workload={workload} />

            {/* Filters */}
            <div className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-4">
                <select
                    className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                    value={filters.status ?? ""}
                    onChange={(e) => set("status", e.target.value)}
                >
                    <option value="">All statuses</option>
                    <option value="open">open</option>
                    <option value="in_progress">in_progress</option>
                    <option value="closed">closed</option>
                </select>

                <select
                    className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                    value={filters.priority ?? ""}
                    onChange={(e) => set("priority", e.target.value)}
                >
                    <option value="">All priorities</option>
                    {PRIORITIES.map((p) => (
                        <option key={p} value={p}>
                            {p}
                        </option>
                    ))}
                </select>

                <select
                    className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                    value={filters.category ?? ""}
                    onChange={(e) => set("category", e.target.value)}
                >
                    <option value="">All categories</option>
                    {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                            {c}
                        </option>
                    ))}
                </select>

                <select
                    className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                    value={filters.assigned_agent_id ?? ""}
                    onChange={(e) => set("assigned_agent_id", e.target.value)}
                >
                    <option value="">Any assignee</option>
                    {agents.map((a) => (
                        <option key={a.id} value={a.id}>
                            {a.name}
                        </option>
                    ))}
                </select>
            </div>

            {loading && <p className="text-sm text-slate-500">Loading…</p>}
            {error && <p className="text-sm text-red-600">{error}</p>}

            {!loading && !error && tickets.length === 0 && (
                <div className="rounded border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
                    No tickets match the current filters.
                </div>
            )}

            {tickets.length > 0 && (
                <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                        <tr>
                            <th className="px-4 py-2">Title</th>
                            <th className="px-4 py-2">Priority</th>
                            <th className="px-4 py-2">Category</th>
                            <th className="px-4 py-2">Status</th>
                            <th className="px-4 py-2">Assigned</th>
                            <th className="px-4 py-2">Created</th>
                        </tr>
                        </thead>
                        <tbody>
                        {tickets.map((t) => (
                            <tr key={t.id} className="border-t border-slate-100">
                                <td className="px-4 py-2 font-medium">
                                    {t.trace_id ? (
                                        <Link
                                            to={`/review/${t.trace_id}`}
                                            className="text-slate-900 hover:underline"
                                        >
                                            {t.title}
                                        </Link>
                                    ) : (
                                        t.title
                                    )}
                                </td>
                                <td className="px-4 py-2 capitalize">{t.priority}</td>
                                <td className="px-4 py-2">{t.category ?? "—"}</td>
                                <td className="px-4 py-2 capitalize">
                                    {t.status.replace("_", " ")}
                                </td>
                                <td className="px-4 py-2">
                                    {t.assigned_agent_name ? (
                                        <span
                                            title={t.assignment_reason ?? ""}
                                            className="cursor-help border-b border-dotted border-slate-400"
                                        >
                        {t.assigned_agent_name}
                      </span>
                                    ) : (
                                        <span className="text-slate-400">unassigned</span>
                                    )}
                                </td>
                                <td className="px-4 py-2 text-slate-500">
                                    {new Date(t.created_at).toLocaleString()}
                                </td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}