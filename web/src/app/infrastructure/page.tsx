import type { Metadata } from "next";

import { InfraEconomicsDashboard } from "@/components/infra/InfraEconomicsDashboard";

export const metadata: Metadata = {
  title: "Infrastructure Economics",
  description:
    "Interactive AI token cost and data-center scenario dashboard for AI Sector Watch.",
};

export default function InfrastructurePage() {
  return <InfraEconomicsDashboard />;
}
