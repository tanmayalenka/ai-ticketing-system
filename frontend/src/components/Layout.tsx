import { Link, useLocation } from "react-router-dom";
import type {ReactNode} from "react";

const nav = [
    { to: "/", label: "Upload" },
    { to: "/tickets", label: "Tickets" },
];

export default function Layout({ children }: { children: ReactNode }) {
    const { pathname } = useLocation();
    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <header className="border-b border-slate-200 bg-white">
                <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
                    <h1 className="text-lg font-semibold">AI Ticketing</h1>
                    <nav className="flex gap-1">
                        {nav.map((n) => (
                            <Link
                                key={n.to}
                                to={n.to}
                                className={`rounded px-3 py-1.5 text-sm font-medium transition ${
                                    pathname === n.to
                                        ? "bg-slate-900 text-white"
                                        : "text-slate-600 hover:bg-slate-100"
                                }`}
                            >
                                {n.label}
                            </Link>
                        ))}
                    </nav>
                </div>
            </header>
            <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        </div>
    );
}