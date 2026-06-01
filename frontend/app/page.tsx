import { SystemDashboard } from "@/components/system-dashboard";

export default function HomePage() {
  return (
    <div className="shell">
      <header className="flex flex-col gap-4 py-4 sm:py-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <p className="eyebrow">Wilo Site Dashboard</p>
          <h1 className="mt-1 text-[clamp(1.5rem,3vw,2.35rem)] font-semibold tracking-[-0.05em] text-[var(--wilo-ink)]">
            Main tank, slave tank, pump state, and LoRa link
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--wilo-muted)] sm:text-[0.95rem]">
            A simple operations dashboard for the installed system. It shows tank levels, sensor
            health, relay state, electrical readings, and controller decisions without marketing
            content or oversized layout blocks.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="status-pill">LoRa link</span>
          <span className="status-pill">Raspberry Pi control</span>
          <span className="status-pill">Live tank state</span>
        </div>
      </header>

      <main id="top" className="py-4 sm:py-6">
        <section>
          <SystemDashboard />
        </section>
      </main>
    </div>
  );
}
