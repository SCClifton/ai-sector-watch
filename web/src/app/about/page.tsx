import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Github, Linkedin, MessageCircle } from "lucide-react";

export const metadata: Metadata = {
  title: "About",
  description:
    "Methodology, scope, data quality, and source code for AI Sector Watch.",
};

const GITHUB_URL = "https://github.com/SCClifton/ai-sector-watch";
const ISSUES_URL = `${GITHUB_URL}/issues`;
const LINKEDIN_URL = "https://www.linkedin.com/in/sam-c-clifton/";

export default function AboutPage() {
  return (
    <article className="mx-auto w-full max-w-[900px] px-5 py-12">
      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
        Methodology
      </div>
      <h1 className="mt-2 text-4xl font-semibold tracking-tight text-text sm:text-5xl">
        About
      </h1>
      <p className="mt-3 text-[14px] text-text-muted">
        Methodology, scope, data quality, and source code.
      </p>

      <Section title="What this is">
        <p>
          AI Sector Watch is a public map of the Australian and New Zealand AI startup
          landscape. It combines a verified company index with a weekly agent pipeline that
          scans public sources for new activity.
        </p>
      </Section>

      <Section title="What is tracked">
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Scope" value="AU + NZ" />
          <Stat label="Sectors" value="21" />
          <Stat label="Cadence" value="Weekly" />
        </div>
        <p className="mt-5">
          The index tracks AI-native and AI-enabled companies across the fixed taxonomy
          documented in the repository. Inputs include startup news, RSS feeds, arXiv,
          Hugging Face papers, and related public signals.
        </p>
      </Section>

      <Section title="How discovery works">
        <p>
          A scheduled GitHub Actions job fetches each source, then an LLM extracts company
          mentions from every item. New ANZ candidates are validated, classified against the
          sector taxonomy, geocoded with a static city table, and written to Supabase as
          pending review. The public dashboard reads only verified companies.
        </p>
        <div className="mt-5 overflow-hidden rounded-xl border border-border bg-surface/50 p-4">
          <Image
            src="/architecture.svg"
            alt="AI Sector Watch architecture: GitHub Actions cron triggers the weekly pipeline, which fetches public sources, runs LLM extraction, validates and classifies candidates, geocodes them against the ANZ city table, and upserts to Supabase Postgres. The dashboard reads verified records."
            width={1120}
            height={500}
            className="w-full"
            unoptimized
          />
        </div>
      </Section>

      <Section title="Data quality and disclaimers">
        <p>
          The data is auto-extracted from public sources and manually reviewed before
          publication. It can still contain errors, omissions, stale links, or imperfect
          sector tags. For corrections, open an issue in the project tracker.
        </p>
        <div className="mt-4">
          <Link
            href={ISSUES_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-border-strong bg-surface px-3.5 py-2 text-[13px] font-medium text-text transition-colors hover:border-accent hover:text-accent"
          >
            <MessageCircle className="h-3.5 w-3.5" />
            Report a correction
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </Section>

      <Section title="Built by">
        <p>
          Built by Sam Clifton as an open research and engineering project. The repository
          is the primary record: source code, workflow files, schema, taxonomy, and
          operating notes are all public.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Link
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-[13px] font-semibold text-bg transition-colors hover:bg-accent-hover"
          >
            <Github className="h-3.5 w-3.5" />
            GitHub repository
          </Link>
          <Link
            href={LINKEDIN_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-border-strong bg-surface px-4 py-2 text-[13px] font-medium text-text transition-colors hover:border-accent hover:text-accent"
          >
            <Linkedin className="h-3.5 w-3.5" />
            LinkedIn
          </Link>
        </div>
      </Section>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold tracking-tight text-text">{title}</h2>
      <div className="mt-3 text-[14px] leading-relaxed text-text-muted">{children}</div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        {label}
      </div>
      <div className="mt-1 text-[18px] font-semibold tabular-nums text-text">{value}</div>
    </div>
  );
}
