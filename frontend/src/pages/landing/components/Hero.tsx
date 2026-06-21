import { stravaLoginUrl } from "@/api/auth";
import { Button } from "@/components/ui/button";

export function Hero() {
  return (
    <div>
      <div className="font-mono text-[12px] tracking-[0.14em] uppercase text-strava mb-[22px]">
        Ride analytics for everyday riders
      </div>

      <h1 className="font-display font-semibold text-[31px] sm:text-[42px] lg:text-[54px] leading-[1.04] tracking-[-0.02em] text-ink mt-0 mb-[22px]">
        Make sense of<br className="hidden sm:inline" /> every mile you ride.
      </h1>

      <p className="text-[18px] leading-[1.6] text-body max-w-[455px] mb-[34px]">
        Whether you ride to work, chase weekend miles, or are just getting
        started, Peakstats turns your Strava rides into a clear, beautiful
        picture of your progress. Every ride counts — no racing required.
      </p>

      <div className="mb-[18px]">
        <Button
          asChild
          className="h-14 px-7 bg-strava hover:bg-strava/90 text-white font-display font-semibold text-base rounded-[11px] shadow-[0_8px_24px_rgba(252,76,2,0.32)] hover:shadow-[0_14px_34px_rgba(252,76,2,0.42)] hover:-translate-y-0.5 transition-all duration-150"
        >
          <a href={stravaLoginUrl}>
            <span className="w-[22px] h-[22px] rounded-[6px] bg-white/[0.92] flex items-center justify-center shrink-0 mr-1">
              <span className="block w-[2.5px] h-[11px] bg-strava rotate-[38deg] rounded-[2px]" />
            </span>
            Connect with Strava
          </a>
        </Button>
      </div>

      <p className="font-mono text-[11.5px] tracking-[0.03em] text-faint">
        Read-only access · We never post on your behalf · Disconnect anytime
      </p>
    </div>
  );
}
