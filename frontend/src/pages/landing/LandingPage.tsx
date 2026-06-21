import { Nav } from "./components/Nav";
import { Hero } from "./components/Hero";
import { DashboardPreview } from "./components/DashboardPreview";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-surface-page transition-colors duration-300 font-[Archivo,sans-serif]">

      {/* Grid background */}
      <div className="ld-grid absolute inset-0 pointer-events-none" />

      {/* Orange glow blob */}
      <div
        className="absolute pointer-events-none rounded-full"
        style={{
          top: -220,
          right: -140,
          width: 640,
          height: 640,
          background: "radial-gradient(circle, rgba(252,76,2,0.18), transparent 68%)",
          filter: "blur(8px)",
        }}
      />

      <div className="relative z-10 max-w-[1240px] mx-auto">
        <Nav />

        {/* Hero */}
        <div className="grid grid-cols-1 lg:grid-cols-[1.02fr_1.12fr] gap-14 lg:gap-[56px] items-center px-5 py-12 lg:px-11 lg:pt-[80px] lg:pb-[90px]">
          <Hero />
          <DashboardPreview />
        </div>
      </div>
    </div>
  );
}
