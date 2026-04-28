import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CompanyProfile } from "@/components/companies/CompanyProfile";
import { listVerifiedCompanies } from "@/lib/companies-server";
import { findBySlug } from "@/lib/slug";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const companies = await listVerifiedCompanies();
    const company = findBySlug(companies, slug);
    if (!company) return { title: "Company not found" };
    return {
      title: company.name,
      description: company.summary?.slice(0, 160) ?? `${company.name} on AI Sector Watch.`,
    };
  } catch {
    return { title: "Company" };
  }
}

export default async function CompanyDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const companies = await listVerifiedCompanies();
  const company = findBySlug(companies, slug);
  if (!company) notFound();
  return <CompanyProfile company={company} />;
}
