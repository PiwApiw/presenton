"use client";

import { cn } from "@/lib/utils";

import type { ImageSourceId } from "./image-sources";

const SOURCE_OPTIONS: Array<{ id: ImageSourceId; label: string }> = [
  { id: "stock", label: "Stock photos" },
  { id: "ai", label: "AI generate" },
];

export function ImageSourceToggle({
  value,
  options,
  labels,
  titles,
  onChange,
  className,
}: {
  value: ImageSourceId;
  options: ImageSourceId[];
  labels?: Partial<Record<ImageSourceId, string>>;
  titles?: Partial<Record<ImageSourceId, string>>;
  onChange: (source: ImageSourceId) => void;
  className?: string;
}) {
  if (options.length < 2) return null;

  return (
    <div
      role="group"
      aria-label="Image source"
      className={cn(
        "inline-flex flex-none items-center gap-1 rounded-full border border-[#EDEEEF] bg-white p-1",
        className,
      )}
    >
      {SOURCE_OPTIONS.filter((option) => options.includes(option.id)).map(
        (option) => {
          const active = value === option.id;
          return (
            <button
              key={option.id}
              type="button"
              aria-pressed={active}
              title={titles?.[option.id]}
              onClick={() => onChange(option.id)}
              className={cn(
                "rounded-full px-3 py-1 text-[13px] font-medium transition",
                active
                  ? "bg-[#191919] text-white"
                  : "text-[#5A5A5A] hover:bg-[#F4F4F4]",
              )}
            >
              {labels?.[option.id] ?? option.label}
            </button>
          );
        },
      )}
    </div>
  );
}
