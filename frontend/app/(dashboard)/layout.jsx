"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";
import Nav, { MobileNav, MobileLinks } from "@/components/Nav";
import { Spinner } from "@/components/ui";

export default function DashboardLayout({ children }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api("/auth/me")
      .then((me) => setEmail(me.email))
      .catch(() => {})
      .finally(() => setReady(true));
  }, [router]);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner label="Checking session…" />
      </div>
    );
  }

  return (
    <div className="md:flex min-h-screen">
      <Nav userEmail={email} />
      <div className="flex-1 min-w-0">
        <MobileNav userEmail={email} />
        <MobileLinks />
        <main className="p-4 md:p-8 max-w-6xl">{children}</main>
      </div>
    </div>
  );
}
