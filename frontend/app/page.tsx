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
      setError(null);
    } catch (e) {
      setError(`Cannot reach the API on :8000 — is the backend running? (${(e as Error).message})`);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  // Deep-link: #<run-id> (or #first) opens that run once on load.
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
    <>
      <header className="masthead">
        <div className="masthead-inner">
          <div className="wordmark">Multi-Agent Code Generator</div>
          <div className="tagline">
            From a GitHub issue to a tested pull request — designed, written, tested, audited, and
            tuned by five coordinated agents, improving from your feedback.
          </div>
        </div>
      </header>

      <main className="container">
        {error && <div className="notice">{error}</div>}

        <div className="grid">
          <section className="panel">
            <h2>File an issue</h2>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Issue title"
            />
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Requirements or acceptance criteria (optional)"
              rows={4}
            />
            <button onClick={submit} disabled={busy || !title.trim()}>
              {busy ? "Running pipeline" : "Generate"}
            </button>
            <p className="muted" style={{ marginTop: 12 }}>
              Runs the full pipeline and returns a result. On the free Gemini tier this takes a
              little time.
            </p>
          </section>

          <section className="panel">
            <h2>Learned lessons / {lessons.length}</h2>
            {lessons.length === 0 && (
              <p className="muted">None yet. Rejecting a result teaches the agents.</p>
            )}
            {AGENTS.map((agent) => {
              const items = lessons.filter((l) => l.agent === agent);
              if (!items.length) return null;
              return (
                <div key={agent} className="lesson-group">
                  <span className="agent-chip">{agent}</span>
                  <ul className="lesson-list">
                    {items.map((l, i) => (
                      <li key={i}>
                        {l.lesson}{" "}
                        <span className="lesson-weight">
                          [×{l.times_applied} · w {l.weight.toFixed(1)}]
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </section>
        </div>

        <section className="panel" style={{ marginTop: 18 }}>
          <h2>Runs / {runs.length}</h2>
          {runs.length === 0 && <p className="muted">No runs yet.</p>}
          {runs.map((r) => (
            <div key={r.id}>
              <div
                className="row clickable"
                onClick={() => setExpanded(expanded === r.id ? null : r.id)}
              >
                <div>
                  <div>
                    <span className="caret">{expanded === r.id ? "–" : "+"}</span>
                    {r.issue_title}
                  </div>
                  <div className="muted mono" style={{ fontSize: 12, marginTop: 2 }}>
                    {r.repo ?? "local"} · {(r.total_input_tokens + r.total_output_tokens).toLocaleString()}{" "}
                    tokens · {new Date(r.created_at).toLocaleString()}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
                  {r.pr_url && (
                    <a href={r.pr_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                      View PR
                    </a>
                  )}
                  <span className={`badge ${r.status}`}>{r.status}</span>
                </div>
              </div>
              {expanded === r.id && <RunDetail runId={r.id} onChanged={refresh} />}
            </div>
          ))}
        </section>
      </main>
    </>
  );
}
