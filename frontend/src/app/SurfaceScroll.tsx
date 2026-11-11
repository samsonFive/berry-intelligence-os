import { createContext, useContext, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigationType } from "react-router-dom";
import { SESSION_TRANSITION_EVENT } from "./PrivateQueryProvider";
import { SurfaceMemory, SURFACE_MEMORY_KEY } from "./surface-memory";
import type { SurfaceLocation } from "./surface-memory";

interface Readiness { location: SurfaceLocation; ready: boolean }
interface ScrollOwner { report: (value: Readiness) => void }
const Context = createContext<ScrollOwner | null>(null);
const currentPoint = () => ({ x: window.scrollX, y: window.scrollY });

/** UI-only coordinates; canonical investigation state and Detail pane memory have separate owners. */
export function SurfaceScroll({ children }: { children: ReactNode }) {
  const { pathname, key } = useLocation();
  const navigation = useNavigationType();
  const [memory, setMemory] = useState(() => {
    try { return new SurfaceMemory(sessionStorage.getItem(SURFACE_MEMORY_KEY)); }
    catch { return new SurfaceMemory(); }
  });
  const readiness = useRef<Readiness | null>(null);
  const schedule = useRef<() => void>(() => {});
  const [owner] = useState<ScrollOwner>(() => ({ report: value => { readiness.current = value; schedule.current(); } }));

  useLayoutEffect(() => {
    const previous = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    return () => { window.history.scrollRestoration = previous; };
  }, []);

  useLayoutEffect(() => {
    let frame = 0;
    let storageTimer: ReturnType<typeof setTimeout> | undefined;
    let discarded = false;
    let focusSurface = false;
    const persist = () => {
      if (discarded) return;
      try { sessionStorage.setItem(SURFACE_MEMORY_KEY, memory.serialize()); } catch { /* Memory remains usable without storage. */ }
    };
    const cancelFrame = () => { cancelAnimationFrame(frame); frame = 0; };
    schedule.current = () => {
      cancelFrame();
      const state = readiness.current;
      if (!state) return;
      if (!state.ready) { memory.defer(state.location); return; }
      if (!memory.pending(state.location)) return;
      const started = performance.now();
      let settledFrames = 0;
      const restore = () => {
        const latest = readiness.current;
        const target = latest?.ready ? memory.pending(latest.location) : null;
        if (!target) return;
        // Wait for committed data and layout (including grid sizing), never capture loading clamps.
        const fits = document.documentElement.scrollHeight - window.innerHeight >= target.y;
        if (++settledFrames < 2 || (!fits && performance.now() - started < 500)) {
          frame = requestAnimationFrame(restore); return;
        }
        window.scrollTo({ left: target.x, top: target.y, behavior: "instant" });
        memory.finish(currentPoint());
        const focused = document.activeElement;
        if (focusSurface && (focused === document.body || focused instanceof HTMLElement && focused.closest(".berry-nav")))
          document.getElementById("investigation-main")?.focus({ preventScroll: true });
        focusSurface = false;
        persist();
      };
      frame = requestAnimationFrame(restore);
    };
    focusSurface = memory.begin({ path: pathname, key }, navigation);
    schedule.current();
    const scroll = () => {
      if (readiness.current?.ready) memory.observe(currentPoint());
      clearTimeout(storageTimer);
      storageTimer = setTimeout(persist, 100);
    };
    const userScroll = (event: Event) => {
      if (event instanceof KeyboardEvent && !["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", " "].includes(event.key)) return;
      if (event.target instanceof HTMLElement && event.target.closest("input, textarea, select, [contenteditable=true]")) return;
      cancelFrame(); memory.finish(currentPoint());
    };
    const pageHide = () => { if (readiness.current?.ready) memory.observe(currentPoint()); persist(); };
    const clear = () => {
      discarded = true; cancelFrame(); clearTimeout(storageTimer); memory.clear();
      try { sessionStorage.removeItem(SURFACE_MEMORY_KEY); } catch { /* Storage can be unavailable. */ }
    };
    const pageShow = (event: PageTransitionEvent) => {
      if (!event.persisted) return;
      const position = currentPoint();
      clear();
      // Discard old private-session layout entries, retaining only the visible return viewport.
      const fresh = new SurfaceMemory();
      const location = { path: pathname, key };
      fresh.begin(location, "POP"); fresh.finish(position); fresh.defer(location);
      setMemory(fresh);
    };
    window.addEventListener("scroll", scroll, { passive: true });
    window.addEventListener("wheel", userScroll, { passive: true });
    window.addEventListener("touchmove", userScroll, { passive: true });
    window.addEventListener("keydown", userScroll);
    window.addEventListener("pagehide", pageHide);
    window.addEventListener("pageshow", pageShow);
    window.addEventListener(SESSION_TRANSITION_EVENT, clear);
    return () => {
      schedule.current = () => {};
      cancelFrame(); clearTimeout(storageTimer); persist();
      window.removeEventListener("scroll", scroll);
      window.removeEventListener("wheel", userScroll);
      window.removeEventListener("touchmove", userScroll);
      window.removeEventListener("keydown", userScroll);
      window.removeEventListener("pagehide", pageHide);
      window.removeEventListener("pageshow", pageShow);
      window.removeEventListener(SESSION_TRANSITION_EVENT, clear);
    };
  }, [memory, pathname, key, navigation]);
  return <Context.Provider value={owner}>{children}</Context.Provider>;
}

/** Call once per native surface when its data DOM (or final empty/error state) is ready. */
export function useSurfaceReady(ready: boolean): void {
  const owner = useContext(Context);
  const { pathname, key } = useLocation();
  useLayoutEffect(() => { owner?.report({ location: { path: pathname, key }, ready }); }, [owner, pathname, key, ready]);
}
