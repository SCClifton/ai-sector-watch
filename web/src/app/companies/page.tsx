import type { Metadata } from "next";

import { StubPage } from "@/components/StubPage";

export const metadata: Metadata = {
  title: "Companies",
};

export default function CompaniesPage() {
  return (
    <StubPage
      eyebrow="Browse"
      title="Companies"
      body="A searchable directory of every verified ANZ AI startup we track, with a detail layout for each profile. Stub for now: the prototype focuses on the map page first."
    />
  );
}
