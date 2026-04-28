import type { Metadata } from "next";

import { StubPage } from "@/components/StubPage";

export const metadata: Metadata = {
  title: "About",
};

export default function AboutPage() {
  return (
    <StubPage
      eyebrow="Methodology"
      title="About"
      body="How AI Sector Watch is built: the agent pipeline, the source list, the sector taxonomy, and the people behind it. Stub for now: the prototype focuses on the map page first."
    />
  );
}
