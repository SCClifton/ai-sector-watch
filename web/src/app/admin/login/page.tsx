import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { isAdminAuthenticated } from "@/lib/admin-auth";
import { LoginForm } from "@/components/admin/LoginForm";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Admin sign in",
  robots: { index: false, follow: false },
};

export default async function AdminLoginPage() {
  if (await isAdminAuthenticated()) redirect("/admin");
  return (
    <section className="mx-auto flex w-full max-w-[380px] flex-1 items-center px-5 py-16">
      <div className="w-full">
        <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
          Restricted
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-text">
          Admin sign in
        </h1>
        <p className="mt-2 text-[13px] text-text-muted">
          Enter the admin password to access the review queue. Sessions expire after 12 hours.
        </p>
        <div className="mt-6">
          <LoginForm />
        </div>
      </div>
    </section>
  );
}
