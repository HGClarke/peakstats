import { ArrowLeft } from "lucide-react";
import { Link } from "react-router";
import { Logo } from "@/components/Logo";

export default function NotFoundPage() {
  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center gap-6 bg-surface-page transition-colors duration-300 font-[Archivo,sans-serif] px-6 text-center">
      <Logo />

      <div className="font-mono text-[12px] tracking-[0.14em] uppercase text-strava">
        Error 404
      </div>

      <h1 className="font-display font-semibold text-[32px] sm:text-[42px] tracking-[-0.02em] text-ink">
        Page not found
      </h1>

      <p className="text-[16px] leading-[1.6] text-body max-w-[420px]">
        That route doesn't exist. The trail must have washed out — let's get you
        back on course.
      </p>

      <Link
        to="/"
        className="inline-flex items-center gap-1.5 font-mono text-[13px] tracking-[0.03em] text-strava hover:underline"
      >
        <ArrowLeft size={14} aria-hidden />
        Back to home
      </Link>
    </div>
  );
}
