import Link from "next/link";
import { ArrowLeft } from "lucide-react";

interface Props {
  title: string;
  eyebrow: string;
  body: string;
}

export function StubPage({ title, eyebrow, body }: Props) {
  return (
    <section className="mx-auto w-full max-w-[900px] px-5 py-20">
      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
        {eyebrow}
      </div>
      <h1 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-text sm:text-4xl">
        {title}
      </h1>
      <p className="mt-4 max-w-2xl text-balance text-base leading-relaxed text-text-muted">
        {body}
      </p>

      <div className="mt-10 rounded-lg border border-border bg-surface px-5 py-5">
        <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-text-subtle">
          Coming in Phase 2
        </div>
        <p className="mt-2 text-[13px] text-text-muted">
          Feature parity with the current Streamlit dashboard, plus a polished detail layout
          tailored to this surface. The map page is the live preview of the new design language;
          this view will follow.
        </p>
        <div className="mt-4">
          <Link
            href="/map"
            className="inline-flex items-center gap-1.5 text-[13px] font-medium text-accent hover:text-accent-hover"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to the map
          </Link>
        </div>
      </div>
    </section>
  );
}
