import type { Metadata } from "next";

import { NewsContent } from "@/components/news/NewsContent";

export const metadata: Metadata = {
  title: "News",
  description:
    "Chronological feed of relevant ANZ AI news linked to companies, plus pipeline cost.",
};

export default function NewsPage() {
  return <NewsContent />;
}
