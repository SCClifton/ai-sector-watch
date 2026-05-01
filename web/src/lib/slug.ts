// Stable, collision-tolerant slug helper. For 52 companies, name-based slugs
// are unique in practice; if a real collision shows up, we fall back to
// the company id suffix.

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export function buildSlugMap<T extends { id: string; name: string }>(
  items: T[],
): Map<string, T> {
  const map = new Map<string, T>();
  const baseCounts = new Map<string, number>();
  for (const item of items) {
    const base = slugify(item.name);
    baseCounts.set(base, (baseCounts.get(base) ?? 0) + 1);
  }
  for (const item of items) {
    const base = slugify(item.name);
    if ((baseCounts.get(base) ?? 0) === 1) {
      map.set(base, item);
      continue;
    }
    // Collision: append last 6 chars of id for stability.
    const tail = item.id.replace(/-/g, "").slice(-6);
    map.set(`${base}-${tail}`, item);
  }
  return map;
}

export function findBySlug<T extends { id: string; name: string }>(
  items: T[],
  slug: string,
): T | undefined {
  return buildSlugMap(items).get(slug);
}

export function slugFor(item: { id: string; name: string }, all: { id: string; name: string }[]): string {
  // Reverse lookup: find the slug that maps back to this item.
  const map = buildSlugMap(all);
  for (const [s, candidate] of map.entries()) {
    if (candidate.id === item.id) return s;
  }
  return slugify(item.name);
}
