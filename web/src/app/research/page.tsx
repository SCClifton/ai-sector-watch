import type { Metadata } from "next";

import { ResearchContent } from "@/components/research/ResearchContent";

export const metadata: Metadata = {
  title: "Research",
  description:
    "Daily frontier AI papers, lab releases, benchmarks, model cards, and research artifacts from primary sources.",
};

export default function ResearchPage() {
  return <ResearchContent />;
}
