import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InvestigationApiError } from "../api/client";

export const SESSION_TRANSITION_EVENT = "berry:session-transition";
export function clearPrivateSession(): void { window.dispatchEvent(new Event(SESSION_TRANSITION_EVENT)); }
export function PrivateQueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({
    queryCache: new QueryCache({ onError: error => {
      if (error instanceof InvestigationApiError && error.requiresSession) clearPrivateSession();
    } }),
    defaultOptions: { queries: { staleTime: 30_000, gcTime: 5 * 60_000, retry: false, refetchOnWindowFocus: false } },
  }));
  useEffect(() => {
    const clear = () => { void client.cancelQueries(); client.clear(); };
    const pageShow = (event: PageTransitionEvent) => { if (event.persisted) clear(); };
    window.addEventListener(SESSION_TRANSITION_EVENT, clear);
    window.addEventListener("pageshow", pageShow);
    return () => { window.removeEventListener(SESSION_TRANSITION_EVENT, clear); window.removeEventListener("pageshow", pageShow); client.clear(); };
  }, [client]);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
