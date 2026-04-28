import Link from "next/link";
import { ArrowRight, MapPin, Sparkles, Newspaper } from "lucide-react";

export default function Home() {
  return (
    <div className="relative flex flex-1 flex-col">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_30%_-10%,rgba(244,183,64,0.10),transparent_40%),radial-gradient(circle_at_85%_20%,rgba(79,141,255,0.08),transparent_45%)]"
      />

      <section className="mx-auto w-full max-w-[1100px] px-5 pt-20 pb-14 sm:pt-28 sm:pb-20">
        <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
          <Sparkles className="h-3.5 w-3.5 text-accent" />
          ANZ AI startup ecosystem
        </div>
        <h1 className="mt-4 text-balance text-4xl font-semibold leading-[1.05] tracking-tight text-text sm:text-6xl">
          A live map of the AI companies
          <br className="hidden sm:block" />
          <span className="text-accent">building from Australia and New Zealand.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-balance text-lg leading-relaxed text-text-muted">
          Updated weekly by an automated agent pipeline. Sector-tagged, geocoded, with funding
          and headcount where we can verify them. Independent and free to use.
        </p>

        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Link
            href="/map"
            className="group inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-[14px] font-semibold text-bg transition-colors hover:bg-accent-hover"
          >
            <MapPin className="h-4 w-4" />
            Open the map
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link
            href="/companies"
            className="inline-flex items-center gap-2 rounded-md border border-border-strong bg-surface px-5 py-2.5 text-[14px] font-medium text-text transition-colors hover:border-accent hover:text-accent"
          >
            Browse companies
          </Link>
          <Link
            href="/news"
            className="inline-flex items-center gap-2 rounded-md px-3 py-2.5 text-[14px] font-medium text-text-muted transition-colors hover:text-text"
          >
            <Newspaper className="h-4 w-4" />
            News digest
          </Link>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-[1100px] grid-cols-1 gap-3 px-5 pb-20 sm:grid-cols-3">
        {[
          {
            label: "Coverage",
            value: "Australia & New Zealand",
            note: "Founded or HQ'd in ANZ.",
          },
          {
            label: "Cadence",
            value: "Weekly",
            note: "Pipeline runs every Monday morning.",
          },
          {
            label: "Method",
            value: "Agent-curated",
            note: "LLM extraction, human-promoted.",
          },
        ].map((card) => (
          <div
            key={card.label}
            className="rounded-lg border border-border bg-surface p-5 transition-colors hover:border-border-strong"
          >
            <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-text-subtle">
              {card.label}
            </div>
            <div className="mt-2 text-lg font-semibold text-text">{card.value}</div>
            <p className="mt-1 text-[13px] text-text-muted">{card.note}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
