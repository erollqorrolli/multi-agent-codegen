"use client";

import { useEffect, useState } from "react";
import { api, type RunDetail as RunDetailData } from "@/lib/api";

// Monospace code + colour tone per agent (no icons).
const AGENT: Record<string, { code: string; tone: string }> = {
  architect: { code: "ARC", tone: "navy" },
  implementation: { code: "IMP", tone: "blue" },
  test: { code: "TST", tone: "blue" },
  security: { code: "SEC", tone: "red" },
  optimization: { code: "OPT", tone: "red" },
  sandbox: { code: "BOX", tone: "navy" },
};

export function RunDetail({ runId, onChanged }: { runId: string; onChanged: () => void }) {
  const [detail, setDetail] = useState<RunDetailData | null>(null);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState<string | null>(null);

  useEffect(() => {
    let es: EventSource | null = null;
    api
      .getRun(runId)
      .then((d) => {
        setDetail(d);
        // For an in-progress run, stream steps live via Server-Sent Events.
        if (d.status === "running" || d.status === "pending") {
          const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
          es = new EventSource(`${base}/api/runs/${runId}/events`);
          es.addEventListener("step", (e) => {
            const s = JSON.parse((e as MessageEvent).data);
            setDetail((prev) => {
              if (!prev || prev.steps.some((x) => x.sequence === s.sequence)) return prev;
              return { ...prev, steps: [...prev.steps, { ...s, input_tokens: null, output_tokens: null }] };
            });
          });
          es.addEventListener("done", () => {
            es?.close();
            api.getRun(runId).then(setDetail).catch(() => {});
          });
        }
      })
      .catch(() => setDetail(null));
    return () => es?.close();
  }, [runId]);

  if (!detail) return <div className="detail muted">Loading run</div>;

  const sendFeedback = async (verdict: string) => {
    await api.feedback(runId, verdict, comment);
    setSent(verdict);
    onChanged();
  };

  const files = Object.keys(detail.generated_files ?? {});

  return (
    <div className="detail">
      <div className="timeline">
        {detail.steps.map((s) => {
          const meta = AGENT[s.agent] ?? { code: s.agent.slice(0, 3).toUpperCase(), tone: "navy" };
          const out = s.output as { ran?: boolean; passed?: boolean; summary?: string };
          const sandbox = s.agent === "sandbox";
          const passed = sandbox && out.passed;
          const failed = sandbox && out.ran && !out.passed;
          return (
            <div className="step" key={s.sequence}>
              <span className={`tag tag-${meta.tone}`}>{meta.code}</span>
              <div className="step-body">
                <div className="step-head">
                  <strong>{s.agent}</strong>
                  <span className="step-model">{s.model}</span>
                  {sandbox && out.summary && (
                    <span className={`badge ${passed ? "succeeded" : failed ? "failed" : "pending"}`}>
                      {out.summary}
                    </span>
                  )}
                </div>
                <div className="step-meta">
                  {s.duration_ms != null && <span>{(s.duration_ms / 1000).toFixed(1)}s</span>}
                  {s.input_tokens != null && (
                    <span>{(s.input_tokens + (s.output_tokens ?? 0)).toLocaleString()} tokens</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="files">
        {files.length} generated file{files.length === 1 ? "" : "s"}
        {files.length > 0 && (
          <>
            {": "}
            <code>{files.slice(0, 6).join("  ")}</code>
          </>
        )}
      </div>

      <div className="feedback-bar">
        {sent ? (
          <span className="muted">
            Feedback recorded ({sent}). Any lessons from it were distilled for next time.
          </span>
        ) : (
          <>
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Optional: what was wrong or right? (this trains the agents)"
            />
            <button className="btn-navy" onClick={() => sendFeedback("accepted")}>
              Accept
            </button>
            <button className="btn-ghost" onClick={() => sendFeedback("rejected")}>
              Reject
            </button>
          </>
        )}
      </div>
    </div>
  );
}
