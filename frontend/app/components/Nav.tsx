"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  async function signOut() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  const linkClass = (path: string) =>
    `text-sm ${pathname === path ? "text-paper" : "text-muted hover:text-paper"}`;

  return (
    <header className="border-b border-line px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-8">
        <span className="font-mono text-xs tracking-wide text-muted">merch ops</span>
        <nav className="flex gap-6">
          <Link href="/dashboard" className={linkClass("/dashboard")}>
            Orders
          </Link>
          <Link href="/approvals" className={linkClass("/approvals")}>
            Approvals
          </Link>
        </nav>
      </div>
      <button onClick={signOut} className="text-sm text-muted hover:text-paper">
        Sign out
      </button>
    </header>
  );
}
