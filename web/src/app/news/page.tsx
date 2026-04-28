import type { Metadata } from "next";

import { StubPage } from "@/components/StubPage";

export const metadata: Metadata = {
  title: "News",
};

export default function NewsPage() {
  return (
    <StubPage
      eyebrow="Pipeline"
      title="News & weekly digest"
      body="The most recent items the pipeline has ingested, plus the weekly markdown digest of what changed. Stub for now: the prototype focuses on the map page first."
    />
  );
}
