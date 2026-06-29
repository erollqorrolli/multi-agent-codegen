"use client";

import { useEffect, useState } from "react";
import { api, type RunDetail as RunDetailData } from "@/lib/api";

const AGENT_ICON: Record<string, string> = {
  architect: "🏛",
  implementation: "⌨️",
  test: "🧪",
  security: "🔒",
  optimization: "⚡",
  sandbox: "📦",
};

export function RunDetail({ runId, onChanged }: { runId: string; onChanged: () => void }) {
  const [detail, setDetail] = useState<RunDetailData | null>(null);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState<string | null>(null);

  useEffect(() => {
    api.getRun(runId).then(setDetail).catch(() => setDetail(null));
  }, [runId]);

  if (!detail) return <div className="muted detail">Loading run…</div>;

  const sendFeedback = async (verdict: string) => {
    await api.feedback(runId, verdict, comment);
    setSent(verdict);
    onChanged(); // refresh lessons in the parent
  };

  return (
    <div className="detail">
      <div className="timeline">
        {detail.steps.map((s) => {
          const sandbox = s.agent === "sandbox";
          const passed = sandbox && (s.output as { passed?: boolean }).passed;
          const failed = sandbox && (s.output as { ran?: boolean; passed?: boolean }).ran && !passed;
          return (
            <div className="step" key={s.sequence}>
              <span className="step-icon">{AGENT_ICON[s.agent] ?? "•"}</span>
              <div className="step-body">
                <div className="step-head">
                  <strong>{s.agent}</strong>
                  <span className="muted">{s.model}</span>
                  {sandbox && (
                    <span className={`badge ${passed ? "succeeded" : failed ? "failed" : "pending"}`}>
                      {(s.output as { summary?: string }).summary ?? "ran"}
                    </span>
                  )}
                </div>
                <div className="muted step-meta">
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

      <div className="files muted">
        {Object.keys(detail.generated_files ?? {}).length} generated file(s):{" "}
        {Object.keys(detail.generated_files ?? {}).slice(0, 6).join(", ") || "—"}
      </div>

      <div className="feedback-bar">
        {sent ? (
          <span className="muted">
            Feedback recorded ({sent}). The system distilled any lessons from it.
          </span>
        ) : (
          <>
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Optional: why? (teaches the agents)"
            />
            <button className="ok-btn" onClick={() => sendFeedback("accepted")}>
              Accept
            </button>
            <button className="err-btn" onClick={() => sendFeedback("rejected")}>
              Reject
            </button>
          </>
        )}
      </div>
    </div>
  );
}
