"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { apiGet, apiPost } from "@/lib/api";
import Nav from "../components/Nav";

type Order = {
  order_ref: string;
  style: string | null;
  ship_date: string | null;
  status: string | null;
  last_assessment: string | null;
  last_risk_flag: boolean | null;
};

export default function DashboardPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace("/login");
        return;
      }
      loadOrders();
    });
  }, [router]);

  async function loadOrders() {
    setLoading(true);
    try {
      const data = await apiGet("/orders");
      setOrders(data);
    } finally {
      setLoading(false);
    }
  }

  async function assessOrder(orderRef: string) {
    setAssessing(orderRef);
    try {
      const { job_id } = await apiPost(`/orders/${orderRef}/assess`);
      // Poll until the background job finishes.
      const poll = setInterval(async () => {
        try {
          const result = await apiGet(`/orders/assess/${job_id}`);
          clearInterval(poll);
          setAssessing(null);
          await loadOrders();
        } catch {
          // still running (202) - keep polling
        }
      }, 1500);
    } catch {
      setAssessing(null);
    }
  }

  return (
    <main>
      <Nav />
      <div className="px-6 py-8 max-w-5xl mx-auto">
        <h1 className="text-xl font-medium mb-6">Orders</h1>

        {loading ? (
          <p className="text-muted text-sm">Loading...</p>
        ) : orders.length === 0 ? (
          <p className="text-muted text-sm">No orders yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-line">
                <th className="py-2 font-normal">Order</th>
                <th className="py-2 font-normal">Style</th>
                <th className="py-2 font-normal">Ship date</th>
                <th className="py-2 font-normal">Risk</th>
                <th className="py-2 font-normal"></th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.order_ref} className="border-b border-line">
                  <td className="py-3 font-mono">{o.order_ref}</td>
                  <td className="py-3">{o.style ?? "-"}</td>
                  <td className="py-3 font-mono text-muted">
                    {o.ship_date ? new Date(o.ship_date).toLocaleDateString() : "-"}
                  </td>
                  <td className="py-3">
                    {o.last_risk_flag === null ? (
                      <span className="text-muted">Not assessed</span>
                    ) : o.last_risk_flag ? (
                      <span className="text-signal">At risk</span>
                    ) : (
                      <span className="text-steady">On track</span>
                    )}
                  </td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => assessOrder(o.order_ref)}
                      disabled={assessing === o.order_ref}
                      className="text-xs border border-line px-3 py-1 hover:border-signal disabled:opacity-50"
                    >
                      {assessing === o.order_ref ? "Assessing..." : "Assess"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
