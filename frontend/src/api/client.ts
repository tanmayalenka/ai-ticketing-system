import axios from "axios";

export const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api",
    timeout: 30000,
});

export type Health = { status: string; checks: Record<string, string> };

export async function getHealth(): Promise<Health> {
    const { data } = await api.get("/health");
    return data;
}

// ---------- Transcripts ----------

export type Segment = {
    id: string;
    speaker: string;
    start: number;
    end: number;
    text: string;
};

export type TranscriptUploadResponse = {
    transcript_id: string;
    trace_id: string;
    status: string;
    message: string;
    segment_count: number;
};

export async function uploadTranscript(file: File): Promise<TranscriptUploadResponse> {
    const form = new FormData();
    form.append("file", file);
    const { data } = await api.post("/transcripts/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
}

export type TranscriptDetail = {
    id: string;
    trace_id: string;
    source_format: string;
    original_filename: string;
    status: string;
    segments: Segment[];
    metadata: Record<string, unknown>;
    created_at: string;
};

export async function getTranscript(id: string): Promise<TranscriptDetail> {
    const { data } = await api.get(`/transcripts/${id}`);
    return data;
}

// ---------- Tickets ----------

export type TicketSummary = {
    id: string;
    title: string;
    priority: string;
    category: string | null;
    status: string;
    assigned_agent_id: string | null;
    created_at: string;
};

export type RedactedSegment = {
    id: string;
    speaker: string;
    start: number;
    end: number;
    text: string;
};

export async function getRedactedTranscript(
    transcriptId: string
): Promise<{
    transcript_id: string;
    trace_id: string;
    segments: RedactedSegment[];
    entities_detected: Record<string, number>;
}> {
    const { data } = await api.get(`/transcripts/${transcriptId}/redacted`);
    return data;
}

export type TopicChunk = {
    chunk_index: number;
    topic_label: string | null;
    text: string;
    segment_ids: string[];
    speakers: string[];
    start_time: number;
    end_time: number;
    coherence_score: number | null;
};

export async function getTranscriptChunks(
    transcriptId: string
): Promise<{
    transcript_id: string;
    trace_id: string;
    chunk_count: number;
    chunks: TopicChunk[];
}> {
    const { data } = await api.get(`/transcripts/${transcriptId}/chunks`);
    return data;
}

export type CallSummary = {
    overview: string;
    primary_issue: string;
    resolution_status: "resolved" | "unresolved" | "follow_up_needed" | "unclear";
    sentiment: "positive" | "neutral" | "negative" | "mixed";
    citations: string[];
};

export type IssueSummary = {
    chunk_index: number;
    title: string;
    description: string;
    citations: string[];
    confidence: number;
};

export type ActionItem = {
    description: string;
    owner: string;
    deadline: string | null;
    citations: string[];
};

export type MultiLevelSummary = {
    call_summary: CallSummary;
    issue_summaries: IssueSummary[];
    action_items: ActionItem[];
};

export type SummaryResponse = {
    transcript_id: string;
    trace_id: string;
    payload: MultiLevelSummary;
    groundedness_score: number;
    citation_validity: number;
    overall_pass: boolean;
    model_name: string;
    prompt_version: string;
    created_at: string;
};

export async function getSummary(
    transcriptId: string
): Promise<SummaryResponse> {
    const { data } = await api.get(`/transcripts/${transcriptId}/summary`);
    return data;
}

export async function getTranscriptByTrace(
    traceId: string
): Promise<TranscriptDetail> {
    const { data } = await api.get(`/transcripts/by-trace/${traceId}`);
    return data;
}

export type DuplicateCandidate = {
    ticket_id: string;
    similarity: number;
};

export type DraftConfidence = Record<string, number>;

export type TicketDraftPayload = {
    title: string;
    description: string;
    priority: "low" | "medium" | "high" | "critical";
    category: string;
    suggested_team: string;
    customer_impact: string | null;
    citations: string[];
    confidence: DraftConfidence;
};

export type TicketDraftResponse = {
    draft_id: string;
    transcript_id: string;
    trace_id: string;
    status: "pending" | "approved" | "rejected" | "expired";
    payload: TicketDraftPayload;
    reviewed_payload: TicketDraftPayload | null;
    duplicate_candidates: DuplicateCandidate[];
    duplicate_recommendation:
        | "create_new"
        | "link_to_existing"
        | "needs_human_decision";
    review_notes: string | null;
    reviewed_by: string | null;
    reviewed_at: string | null;
    model_name: string;
    prompt_version: string;
    created_at: string;
};

export async function getDraftByTrace(
    traceId: string
): Promise<TicketDraftResponse> {
    const { data } = await api.get(`/tickets/drafts/by-trace/${traceId}`);
    return data;
}

export async function approveDraft(
    traceId: string,
    reviewedPayload: TicketDraftPayload,
    reviewedBy = "agent"
) {
    const { data } = await api.post(`/tickets/drafts/${traceId}/approve`, {
        reviewed_by: reviewedBy,
        reviewed_payload: reviewedPayload,
    });
    return data as { status: string; draft_id: string };
}

export async function rejectDraft(
    traceId: string,
    reason: string,
    reviewedBy = "agent"
) {
    const { data } = await api.post(`/tickets/drafts/${traceId}/reject`, {
        reviewed_by: reviewedBy,
        reason,
    });
    return data as { status: string; draft_id: string };
}

export type TicketListRow = {
    id: string;
    title: string;
    priority: string;
    category: string | null;
    status: string;
    assigned_agent_id: string | null;
    assigned_agent_name: string | null;
    assignment_reason: string | null;
    assigned_at: string | null;
    created_at: string;
    trace_id: string | null;
};

export type TicketFilters = {
    status?: string;
    priority?: string;
    category?: string;
    assigned_agent_id?: string;
};

export async function listTickets(
    filters: TicketFilters = {}
): Promise<TicketListRow[]> {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v);
    }
    const qs = params.toString();
    const { data } = await api.get(`/tickets${qs ? `?${qs}` : ""}`);
    return data;
}

export type AgentRow = {
    id: string;
    name: string;
    email: string;
    team: string;
    status: "online" | "offline" | "busy";
    max_capacity: number;
    current_load: number;
    utilization: number;
    last_assigned_at: string | null;
    skills: { skill: string; proficiency: number }[];
};

export async function listAgents(): Promise<AgentRow[]> {
    const { data } = await api.get("/agents");
    return data;
}

export type TeamWorkload = {
    team: string;
    agent_count: number;
    online_count: number;
    total_capacity: number;
    total_load: number;
    utilization: number;
};

export async function getWorkload(): Promise<{
    teams: TeamWorkload[];
    total_agents: number;
    online_agents: number;
}> {
    const { data } = await api.get("/agents/workload");
    return data;
}

export const CATEGORIES = [
    "authentication",
    "billing",
    "technical_issue",
    "account_management",
    "feature_request",
    "how_to",
    "other",
] as const;

export const PRIORITIES = ["low", "medium", "high", "critical"] as const;