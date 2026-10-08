import { useEffect, useState } from "react";
import { listTickets, type TicketSummary } from "../api/client";

export default function TicketListPage() {
    const [tickets, setTickets] = useState<TicketSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        listTickets()
            .then(setTickets)
            .catch((e) =>
                setError((e as any)?.response?.data?.detail ?? (e as Error).message)
            )
            .finally(() => setLoading(false));
    }, []);

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-semibold">Tickets</h2>
                <p className="text-sm text-slate-600">
                    All generated tickets from transcript processing.
                </p>
            </div>

            {loading && <p className="text-sm text-slate-500">Loading…</p>}
            {error && <p className="text-sm text-red-600">{error}</p>}

            {!loading && !error && tickets.length === 0 && (
                <div className="rounded border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
                    No tickets yet. Upload a transcript to get started.
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
                            <th className="px-4 py-2">Created</th>
                        </tr>
                        </thead>
                        <tbody>
                        {tickets.map((t) => (
                            <tr key={t.id} className="border-t border-slate-100">
                                <td className="px-4 py-2 font-medium">{t.title}</td>
                                <td className="px-4 py-2 capitalize">{t.priority}</td>
                                <td className="px-4 py-2">{t.category ?? "—"}</td>
                                <td className="px-4 py-2 capitalize">{t.status}</td>
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