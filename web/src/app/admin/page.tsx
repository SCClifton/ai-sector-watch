import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { isAdminAuthenticated } from "@/lib/admin-auth";
import { getRejectedCount, listPendingCompanies } from "@/lib/admin-companies";
import { AdminQueue } from "@/components/admin/AdminQueue";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Admin: review queue",
  robots: { index: false, follow: false },
};

export default async function AdminPage() {
  if (!(await isAdminAuthenticated())) redirect("/admin/login");

  const [pending, rejectedCount] = await Promise.all([
    listPendingCompanies(),
    getRejectedCount(),
  ]);

  return (
    <section className="mx-auto w-full max-w-[1100px] px-5 py-10">
      <AdminQueue pending={pending} rejectedCount={rejectedCount} />
    </section>
  );
}
