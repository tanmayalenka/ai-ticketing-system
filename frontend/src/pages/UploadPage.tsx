import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    getHealth,
    uploadTranscript,
    type TranscriptUploadResponse,
    type Health,
} from "../api/client";

export default function UploadPage() {
    const nav = useNavigate();
    const [health, setHealth] = useState<Health | null>(null);
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState<TranscriptUploadResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [dragging, setDragging] = useState(false);

    useEffect(() => {
        getHealth().then(setHealth).catch(() => setHealth(null));
    }, []);

    const onDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files?.[0];
        if (f) {
            setFile(f);
            setResult(null);
            setError(null);
        }
    }, []);

    const onSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const f = e.target.files?.[0];
        if (f) {
            setFile(f);
            setResult(null);
            setError(null);
        }
    };

    const onUpload = async () => {
        if (!file) return;
        setUploading(true);
        setError(null);
        try {
            const res = await uploadTranscript(file);
            setResult(res);
        } catch (e: unknown) {
            const msg =
                (e as any)?.response?.data?.detail ??
                (e as Error).message ??
                "Upload failed";
            setError(String(msg));
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-semibold">Upload Transcript</h2>
                <p className="text-sm text-slate-600">
                    Drop a diarized transcript file (.json, .srt, .vtt) to generate a
                    ticket draft.
                </p>
            </div>

            <div
                onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={`rounded-lg border-2 border-dashed bg-white p-12 text-center transition ${
                    dragging ? "border-blue-500 bg-blue-50" : "border-slate-300"
                }`}
            >
                <input
                    id="file-input"
                    type="file"
                    accept=".json,.srt,.vtt"
                    className="hidden"
                    onChange={onSelect}
                />
                {file ? (
                    <div className="space-y-2">
                        <p className="text-sm font-medium text-slate-800">{file.name}</p>
                        <p className="text-xs text-slate-500">
                            {(file.size / 1024).toFixed(1)} KB
                        </p>
                        <div className="flex justify-center gap-2 pt-2">
                            <button
                                onClick={onUpload}
                                disabled={uploading}
                                className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                            >
                                {uploading ? "Uploading…" : "Upload"}
                            </button>
                            <button
                                onClick={() => {
                                    setFile(null);
                                    setResult(null);
                                    setError(null);
                                }}
                                className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
                            >
                                Clear
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-2">
                        <p className="text-slate-600">Drag and drop a transcript here, or</p>
                        <label
                            htmlFor="file-input"
                            className="inline-block cursor-pointer rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
                        >
                            Browse files
                        </label>
                        <p className="text-xs text-slate-400">
                            Supported: .json, .srt, .vtt (max 25 MB)
                        </p>
                    </div>
                )}
            </div>

            {error && (
                <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            {result && (
                <div className="rounded border border-green-200 bg-green-50 p-4 text-sm">
                    <p className="font-medium text-green-800">Upload successful</p>
                    <p className="mt-1 text-green-700">
                        Trace ID: <span className="font-mono">{result.trace_id}</span>
                    </p>
                    <p className="text-green-700">
                        {result.segment_count} segments parsed · Status: {result.status}
                    </p>
                    <button
                        onClick={() => nav(`/review/${result.trace_id}`)}
                        className="mt-3 rounded bg-green-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-800"
                    >
                        Open review (placeholder for Step 5)
                    </button>
                </div>
            )}

            <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h3 className="mb-2 text-sm font-semibold">System Health</h3>
                {health ? (
                    <ul className="grid grid-cols-2 gap-2 text-sm md:grid-cols-5">
                        {Object.entries(health.checks).map(([k, v]) => (
                            <li key={k} className="flex items-center gap-2">
                <span
                    className={`inline-block h-2 w-2 rounded-full ${
                        v === "ok" ? "bg-green-500" : "bg-red-500"
                    }`}
                />
                                <span className="capitalize">{k}</span>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-sm text-slate-500">
                        Backend unreachable. Is FastAPI running on :8000?
                    </p>
                )}
            </div>
        </div>
    );
}