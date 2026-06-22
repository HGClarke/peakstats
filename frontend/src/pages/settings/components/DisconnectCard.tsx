import { useState } from "react";
import { useNavigate } from "react-router";
import { disconnect } from "@/api/auth";

export function DisconnectCard() {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const handleDisconnect = async () => {
    setBusy(true);
    try {
      await disconnect();
      navigate("/", { replace: true });
    } catch {
      setBusy(false);
    }
  };

  return (
    <div className="bg-surface-card border border-bad/30 rounded-[14px] p-[18px_20px]">
      <div className="font-display font-medium text-[15px] mb-1">Disconnect Strava</div>
      <div className="text-[13px] text-subtle mb-4">Revokes access and deletes your synced data from Peakstats.</div>
      {confirming ? (
        <div className="flex items-center gap-3">
          <button type="button" disabled={busy} onClick={handleDisconnect}
            className="h-9 px-4 rounded-[9px] bg-bad text-white text-[13px] font-medium cursor-pointer disabled:opacity-60">
            {busy ? "Disconnecting…" : "Yes, disconnect"}
          </button>
          <button type="button" onClick={() => setConfirming(false)}
            className="h-9 px-4 rounded-[9px] border border-line text-subtle text-[13px] cursor-pointer hover:text-ink">
            Cancel
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setConfirming(true)}
          className="h-9 px-4 rounded-[9px] border border-bad/40 text-bad text-[13px] font-medium cursor-pointer hover:bg-bad-soft">
          Disconnect
        </button>
      )}
    </div>
  );
}
