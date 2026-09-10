"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { apiGet, apiPost } from "@/lib/api";
import Nav from "../components/Nav";

type PendingApproval = {
  thread_id: string;
  draft: string;
  at_risk_tasks: string[];
  created_at: string;
};

export default function ApprovalsPage() {
  const router = useRouter();
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace("/login");
        return;
      }
      loadApprovals();
    });
  }, [router]);

  async function loadApprovals() {
    setLoading(true);
    try {
      const data = await apiGet("/approvals");
      setApprovals(data);
    } finally {
      setLoading(false);
    }
  }

  async function decide(threadId: string, decision: "approve" | "reject") {
    setDeciding(threadId);
    try {
      await apiPost(`/approvals/${threadId}/decide`, { decision });
      await loadApprovals();
    } finally {
      setDeciding(null);
    }
  }

  async function runScan() {
    await apiPost("/tna/scan");
    await loadApprovals();
  }

  return (
    <main>
      <Nav />
      <div className="px-6 py-8 max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-medium">Approvals</h1>
          <button onClick={runScan} className="text-xs border border-line px-3 py-1 hover:border-signal">
            Run TNA scan now
          </button>
        </div>

        {loading ? (
          <p className="text-muted text-sm">Loading...</p>
        ) : approvals.length === 0 ? (
          <p className="text-muted text-sm">
            Nothing waiting on you. The watcher agent drafts a reminder here whenever a TNA
            deadline is at risk - nothing sends until you approve it.
          </p>
        ) : (
          <div className="space-y-4">
            {approvals.map((a) => (
              <div key={a.thread_id} className="border border-line p-4">
                <p className="text-xs text-muted font-mono mb-2">
                  {new Date(a.created_at).toLocaleString()}
                </p>
                <p className="text-sm mb-3 whitespace-pre-wrap">{a.draft}</p>
                <ul className="text-xs text-muted mb-4 list-disc list-inside">
                  {a.at_risk_tasks.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
                <div className="flex gap-3">
                  <button
                    onClick={() => decide(a.thread_id, "approve")}
                    disabled={deciding === a.thread_id}
                    className="text-xs bg-signal text-ink px-3 py-1.5 font-medium hover:opacity-90 disabled:opacity-50"
                  >
                    Approve &amp; send
                  </button>
                  <button
                    onClick={() => decide(a.thread_id, "reject")}
                    disabled={deciding === a.thread_id}
                    className="text-xs border border-line px-3 py-1.5 hover:border-alert disabled:opacity-50"
                  >
                    Discard
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
