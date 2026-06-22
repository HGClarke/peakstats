import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { SettingsProvider } from "@/app/providers/SettingsProvider";

/** A fresh QueryClient per call so tests never share cache. */
export function createQueryWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <SettingsProvider>{children}</SettingsProvider>
      </QueryClientProvider>
    );
  };
}

export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  return render(ui, { wrapper: createQueryWrapper(), ...options });
}
