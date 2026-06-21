import { useEffect } from "react";
import { useNavigate } from "react-router";
import { useAthlete, logout, disconnect } from "@/api/auth";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";

export default function AppHome() {
  const { data, isLoading, error } = useAthlete();
  const navigate = useNavigate();

  useEffect(() => {
    if (error) navigate("/", { replace: true });
  }, [error, navigate]);

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  const handleDisconnect = async () => {
    await disconnect();
    navigate("/", { replace: true });
  };

  if (isLoading || !data) {
    return (
      <div className="min-h-screen bg-surface-page flex items-center justify-center">
        <span className="font-mono text-[12px] tracking-[0.06em] text-subtle">
          Loading…
        </span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-page text-ink">
      <div className="h-[74px] px-11 flex items-center justify-between border-b border-line-subtle">
        <Logo />
        <ThemeToggle />
      </div>
      <div className="max-w-[1240px] mx-auto px-11 py-16 flex flex-col items-center gap-6">
        {data.avatar_url ? (
          <img
            src={data.avatar_url}
            alt=""
            aria-hidden
            className="w-20 h-20 rounded-full border border-line object-cover"
          />
        ) : null}
        <h1 className="font-display font-semibold text-[28px] tracking-[-0.02em]">
          {data.name}
        </h1>
        <p className="font-mono text-[12px] tracking-[0.06em] text-subtle">
          You're connected with Strava.
        </p>
        <div className="flex items-center gap-3 mt-2">
          <Button variant="outline" onClick={handleLogout}>
            Log out
          </Button>
          <Button
            variant="outline"
            onClick={handleDisconnect}
            className="text-strava border-strava/40 hover:bg-strava/10"
          >
            Disconnect Strava
          </Button>
        </div>
      </div>
    </div>
  );
}
