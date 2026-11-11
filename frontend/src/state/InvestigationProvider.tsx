import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { parseInvestigation, sameContext, serializeInvestigation } from "../contracts/investigation";
import { initialInvestigation, reduceInvestigation } from "./reducer";
import type { InvestigationAction, InvestigationState } from "./reducer";

interface InvestigationValue extends InvestigationState {
  dispatch: (action: InvestigationAction) => boolean;
  getRevision: () => number;
}
const Context = createContext<InvestigationValue | null>(null);

export function InvestigationProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [state, setState] = useState(() => initialInvestigation(parseInvestigation(location.search)));
  const latest = useRef(state);
  latest.current = state;
  const lastHandledSearch = useRef(location.search);
  useLayoutEffect(() => {
    if (lastHandledSearch.current === location.search) return;
    lastHandledSearch.current = location.search;
    const restored = parseInvestigation(location.search);
    if (sameContext(latest.current.context, restored.context)) return;
    const next = { ...restored, revision: latest.current.revision + 1 };
    latest.current = next;
    setState(next);
  }, [location.search]);
  const dispatch = useCallback((action: InvestigationAction): boolean => {
    const result = reduceInvestigation(latest.current, action);
    if (!result.accepted) return false;
    latest.current = result.state;
    setState(result.state);
    if (result.changed) {
      const search = `?${serializeInvestigation(result.state.context)}`;
      lastHandledSearch.current = search;
      void navigate({ pathname: location.pathname, search }, { replace: result.history === "replace", preventScrollReset: true });
    }
    return true;
  }, [navigate, location.pathname]);
  const getRevision = useCallback(() => latest.current.revision, []);
  const value = useMemo(() => ({ ...state, dispatch, getRevision }), [state, dispatch, getRevision]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useInvestigation(): InvestigationValue {
  const value = useContext(Context);
  if (!value) throw new Error("useInvestigation requires InvestigationProvider.");
  return value;
}
