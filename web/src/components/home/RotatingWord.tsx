"use client";

import { type CSSProperties, useEffect, useMemo, useState } from "react";

interface Props {
  words: string[];
  intervalMs?: number;
}

export function RotatingWord({ words, intervalMs = 2400 }: Props) {
  const [index, setIndex] = useState(0);
  const longest = useMemo(
    () => Math.max(0, ...words.map((w) => w.length)),
    [words],
  );

  useEffect(() => {
    if (words.length <= 1) return;
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % words.length);
    }, intervalMs);
    return () => clearInterval(id);
  }, [words.length, intervalMs]);

  return (
    <span
      className="relative inline-block align-baseline sm:min-w-[var(--rotating-word-width)]"
      style={{ "--rotating-word-width": `${longest}ch` } as CSSProperties}
      aria-live="polite"
    >
      {words.map((word, i) => (
        <span
          key={word}
          aria-hidden={i !== index}
          className="absolute left-0 top-0 whitespace-nowrap transition-all duration-500 ease-out will-change-transform"
          style={{
            opacity: i === index ? 1 : 0,
            transform: `translateY(${i === index ? "0" : i < index ? "-12px" : "12px"})`,
          }}
        >
          {word}
        </span>
      ))}
      <span className="invisible">{words[index]}</span>
    </span>
  );
}
