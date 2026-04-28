import type { Metadata } from "next";
import { Suspense } from "react";

import { CompaniesDirectory } from "@/components/companies/CompaniesDirectory";

export const metadata: Metadata = {
  title: "Companies",
  description: "Every verified ANZ AI startup we track.",
};

export default function CompaniesPage() {
  return (
    <Suspense fallback={<DirectoryShell />}>
      <CompaniesDirectory />
    </Suspense>
  );
}

function DirectoryShell() {
  return (
    <section className="mx-auto w-full max-w-[1200px] px-5 py-10">
      <div>
        <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
          Browse
        </div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-text sm:text-4xl">
          Companies
        </h1>
      </div>
    </section>
  );
}
