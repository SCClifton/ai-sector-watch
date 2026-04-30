import { Sparkles, TrendingUp } from "lucide-react";

import type { Company } from "@/lib/types";
import {
  RECENTLY_FUNDED_DAYS,
  RECENTLY_VERIFIED_DAYS,
  isRecentlyFunded,
  isRecentlyVerified,
} from "@/lib/freshness";
import { cn } from "@/lib/cn";

type Variant = "icon" | "chip";

interface Props {
  company: Company;
  variant?: Variant;
  className?: string;
}

export function FreshnessBadges({ company, variant = "icon", className }: Props) {
  const verified = isRecentlyVerified(company);
  const funded = isRecentlyFunded(company);
  if (!verified && !funded) return null;

  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      {verified && (
        <Badge
          variant={variant}
          tone="verified"
          icon={<Sparkles className="h-3 w-3" />}
          label="Recently verified"
          title={`Verified in the last ${RECENTLY_VERIFIED_DAYS} days`}
        />
      )}
      {funded && (
        <Badge
          variant={variant}
          tone="funded"
          icon={<TrendingUp className="h-3 w-3" />}
          label="Newly funded"
          title={`Total raised confirmed in the last ${RECENTLY_FUNDED_DAYS} days`}
        />
      )}
    </span>
  );
}

function Badge({
  variant,
  tone,
  icon,
  label,
  title,
}: {
  variant: Variant;
  tone: "verified" | "funded";
  icon: React.ReactNode;
  label: string;
  title: string;
}) {
  const palette =
    tone === "verified"
      ? "border-accent/40 bg-accent-soft text-accent"
      : "border-success/40 bg-success/10 text-success";

  if (variant === "icon") {
    return (
      <span
        className={cn(
          "inline-flex items-center justify-center rounded-full border p-0.5",
          palette,
        )}
        title={title}
        aria-label={label}
      >
        {icon}
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        palette,
      )}
      title={title}
    >
      {icon}
      {label}
    </span>
  );
}
