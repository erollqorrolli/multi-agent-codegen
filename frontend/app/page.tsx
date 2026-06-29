"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Lesson, type RunSummary } from "@/lib/api";
import { RunDetail } from "@/components/RunDetail";

const AGENTS = ["architect", "implementation", "test", "security", "optimization"];

export default function Dashboard() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [title, setTitle] = useState("Build a REST API for expense tracking with auth");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [r, l] = await Promise.all([api.listRuns(), api.listLessons()]);
      setRuns(r);
      setLessons(l);
    } catch (e) {
      setError(`Backend unreachable — is it running on :8000? (${(e as Error).message})`);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000); // poll while runs are in flight
    return () => clearInterval(id);
  }, [refresh]);

  // Deep-link support: #<run-id> (or #first) opens that run on load. Applied once
  // so it never fights the user's own expand/collapse.
  const hashApplied = useRef(false);
  useEffect(() => {
    if (hashApplied.current || runs.length === 0) return;
    const hash = decodeURIComponent(window.location.hash.replace(/^#/, ""));
    if (hash === "first") {
      setExpanded(runs[0].id);
      hashApplied.current = true;
    } else if (runs.some((r) => r.id === hash)) {
      setExpanded(hash);
      hashApplied.current = true;
    }
  }, [runs]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.generate(title, body);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container">
      <header style={{ marginBottom: 24 }}>
        <h1>🤖 Multi-Agent Code Generator</h1>
        <p className="muted">
          architect → implementation → test · security · optimization → PR, with a learning loop
        </p>
      </header>

      {error && (
        <div className="panel" style={{ borderColor: "var(--err)", marginBottom: 20 }}>
          <span style={{ color: "var(--err)" }}>{error}</span>
        </div>
      )}

      <div className="grid">
        <section className="panel">
          <h2>File an issue</h2>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Issue title" />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Requirements / acceptance criteria (optional)"
            rows={4}
          />
          <button onClick={submit} disabled={busy || !title.trim()}>
            {busy ? "Running 5 agents…" : "Generate"}
          </button>
          <p className="muted" style={{ marginTop: 10 }}>
            Runs the full pipeline synchronously. Free-tier Gemini — give it a moment.
          </p>
        </section>

        <section className="panel">
          <h2>Learned lessons ({lessons.length})</h2>
          {lessons.length === 0 && <p className="muted">None yet — reject a PR to teach the system.</p>}
          {AGENTS.map((agent) => {
            const items = lessons.filter((l) => l.agent === agent);
            if (!items.length) return null;
            return (
              <div key={agent} style={{ marginBottom: 12 }}>
                <span className="agent-chip">{agent}</span>
                <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                  {items.map((l, i) => (
                    <li key={i} className="muted" style={{ marginBottom: 4 }}>
                      {l.lesson} <em>(×{l.times_applied}, w={l.weight.toFixed(1)})</em>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </section>
      </div>

      <section className="panel" style={{ marginTop: 20 }}>
        <h2>Runs ({runs.length})</h2>
        {runs.length === 0 && <p className="muted">No runs yet.</p>}
        {runs.map((r) => (
          <div key={r.id}>
            <div
              className="row clickable"
              onClick={() => setExpanded(expanded === r.id ? null : r.id)}
            >
              <div>
                <div>
                  <span className="caret">{expanded === r.id ? "▾" : "▸"}</span> {r.issue_title}
                </div>
                <div className="muted">
                  {r.repo ?? "local"} · {(r.total_input_tokens + r.total_output_tokens).toLocaleString()}{" "}
                  tokens · {new Date(r.created_at).toLocaleString()}
                </div>
              </div>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                {r.pr_url && (
                  <a href={r.pr_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                    PR ↗
                  </a>
                )}
                <span className={`badge ${r.status}`}>{r.status}</span>
              </div>
            </div>
            {expanded === r.id && <RunDetail runId={r.id} onChanged={refresh} />}
          </div>
        ))}
      </section>
    </div>
  );
}
