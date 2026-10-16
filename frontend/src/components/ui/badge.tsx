import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "cyan" | "green" | "amber" | "red";
};

const tones = {
  neutral: "border-white/10 bg-white/[0.04] text-slate-400",
  cyan: "border-cyan-300/20 bg-cyan-300/[0.08] text-cyan-200",
  green: "border-emerald-300/20 bg-emerald-300/[0.08] text-emerald-300",
  amber: "border-amber-300/20 bg-amber-300/[0.08] text-amber-200",
  red: "border-rose-300/20 bg-rose-300/[0.08] text-rose-300",
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
