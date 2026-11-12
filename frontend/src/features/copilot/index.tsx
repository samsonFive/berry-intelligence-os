import { Component, createContext, useContext, useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { useAgent, useAgentContext, useCopilotKit, useFrontendTool } from "@copilotkit/react-core/v2/headless";
import { z } from "zod";
import { getInvestigation } from "../../api/client.ts";
import { useInvestigation } from "../../state/InvestigationProvider.tsx";
import { compareCommand, detailCommand, fresh, staleCommand } from "./command-actions.ts";
import type { CommandHost, CommandResult } from "./command-actions.ts";
import { catalogSearchResults } from './catalog-results.ts';
import type { CatalogOption } from './catalog-results.ts';
import "./copilot.css";

const ROOT = "/api/investigations/v1/copilot";
class CopilotBoundary extends Component<{ children: ReactNode; fallback: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFailure(); }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}
const Gate = createContext<{
  configured: boolean; loading: boolean; statusError: string; active: { current: number | null }; generation: { current: number };
  result: CommandResult | null; lastResult: { current: CommandResult | null }; setResult: (result: CommandResult | null) => void;
}>({ configured: false, loading: true, statusError: "", active: { current: null }, generation: { current: 0 }, result: null, lastResult: { current: null }, setResult: () => {} });

/** Mounted once by the shell. Discovery never starts a model turn. */
export function CopilotProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState({ configured: false, loading: true, statusError: "" });
  const [result, updateResult] = useState<CommandResult | null>(null);
  const lastResult = useRef<CommandResult | null>(null);
  const setResult = (value: CommandResult | null) => { lastResult.current = value; updateResult(value); };
  const active = useRef<number | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${ROOT}/status`, { credentials: "same-origin", cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok || response.redirected) throw new Error("Ask Berry could not connect to this session.");
        const body = await response.json();
        setStatus({ configured: body.configured === true, loading: false, statusError: "" });
      }).catch(error => { if (!controller.signal.aborted) setStatus({ configured: false, loading: false, statusError: error instanceof Error ? error.message : "Ask Berry is unavailable." }); });
    return () => controller.abort();
  }, []);
  const value = { ...status, active, generation, result, lastResult, setResult };
  const unavailable = { ...value, configured: false, loading: false,
    statusError: "Ask Berry could not start in this session. Continue with the investigation controls." };
  return <Gate.Provider value={value}>
    {status.configured ? <CopilotBoundary
      onFailure={() => { generation.current += 1; active.current = null; }}
      fallback={<Gate.Provider value={unavailable}>{children}</Gate.Provider>}>
      <CopilotKitProvider runtimeUrl={ROOT} useSingleEndpoint agentId="default" showDevConsole={false} enableInspector={false}>
        {children}
      </CopilotKitProvider>
    </CopilotBoundary> : children}
  </Gate.Provider>;
}

const revisionSchema = z.number().int().nonnegative().describe("The current investigation revision from the read-only context. Never guess or increment it.");
const idSchema = z.string().regex(/^[A-Za-z0-9_.-]{1,180}$/);

/** No alternate canvas: all controlled catalog tools dispatch shared actions. */
export function CopilotTools() {
  const gate = useContext(Gate);
  return gate.configured ? <RegisteredTools /> : null;
}
function RegisteredTools() {
  const { context, revision, dispatch, getRevision } = useInvestigation();
  const gate = useContext(Gate);
  const latest = useRef({ context, dispatch, getRevision });
  latest.current = { context, dispatch, getRevision };
  const host = (): CommandHost => {
    const commandGeneration = gate.generation.current;
    return { ...latest.current, read: getInvestigation,
      getRevision: () => gate.active.current !== null && commandGeneration === gate.generation.current ? latest.current.getRevision() : -1 };
  };
  const run = async (expected: number, action: (host: CommandHost) => Promise<CommandResult>) => {
    if (gate.active.current !== expected) { const result = staleCommand(); gate.setResult(result); return result; }
    const commandGeneration = gate.generation.current;
    try { const result = await action(host()); if (commandGeneration === gate.generation.current) gate.setResult(result); return result; }
    catch { const result = { ok: false, code: "unavailable", message: "The requested records could not be loaded. Your current investigation is preserved." }; if (commandGeneration === gate.generation.current) gate.setResult(result); return result; }
  };
  useAgentContext({ description: "Berry investigation selectors only. Source bodies, authored workspaces and account details are not included. Actions must use the exact revision and canonical IDs. No ranking or factual synthesis is authorized.", value: {
    revision, ctx_v: context.ctx_v, berry: context.berry, countries: context.countries,
    geo_basis: context.geo_basis, actor_roles: context.actor_roles, relationship_types: context.relationship_types,
    news_from: context.news_from, news_to: context.news_to, company_set: context.company_set, focus: context.focus,
    cohort_companies: context.cohort_companies, cohort_varieties: context.cohort_varieties,
    lens: context.lens, comparison_kind: context.comparison_kind,
  } });
  useFrontendTool({ name: "search_catalog", description: "Find canonical company, variety or country IDs using authored catalog names and aliases. Results include exact_name, exact_alias or substring match basis. A unique exact match can resolve the requested name; multiple exact matches remain ambiguous and must not be guessed. Bounded results preserve exact matches first and disclose truncation. Matching does not approve an identity or claim.",
    parameters: z.object({ revision: revisionSchema, kind: z.enum(["company", "variety", "geography"]), query: z.string().min(1).max(120) }),
    handler: async ({ revision: expected, kind, query }) => {
      const invocation = host();
      if (gate.active.current !== expected || !fresh(invocation, expected)) return staleCommand();
      const result = await getInvestigation<Record<string, CatalogOption[]>>("/options", { ...latest.current.context, q: query, q_scope: "catalog" }, expected);
      if (!fresh(invocation, expected)) return staleCommand();
      const rows = result.data[kind === "company" ? "companies" : kind === "variety" ? "varieties" : "countries"] ?? [];
      return catalogSearchResults(rows, kind, query);
    },
  });
  useFrontendTool({ name: "show_portfolio_comparison", description: "Open PortfolioComparison in the existing main field. Use canonical IDs from search_catalog. Countries may change only when explicitly requested. This does not rank companies or varieties.",
    parameters: z.object({ revision: revisionSchema, kind: z.enum(["company", "variety"]), ids: z.array(idSchema).min(1).max(5), countries: z.array(idSchema).max(20).optional() }),
    handler: args => run(args.revision, h => compareCommand(h, args)),
  });
  useFrontendTool({ name: "show_company_summary", description: "Open CompanySummary through the shared focus/detail controls. Does not pin, follow or approve the company.",
    parameters: z.object({ revision: revisionSchema, id: idSchema }),
    handler: args => run(args.revision, h => detailCommand(h, { ...args, type: "company", focus: true })),
  });
  useFrontendTool({ name: "show_evidence_detail", description: "Open EvidenceDetail in the existing Reader. Only an ID is passed; the backend resolves selected source content. Publication review does not approve claims.",
    parameters: z.object({ revision: revisionSchema, id: idSchema }),
    handler: args => run(args.revision, h => detailCommand(h, { ...args, type: "source" })),
  });
  useFrontendTool({ name: "show_related_developments", description: "Focus a company or variety so the existing RelatedDevelopments rail uses the declared relevance precedence. Keeps applied scope and cohorts unchanged.",
    parameters: z.object({ revision: revisionSchema, type: z.enum(["company", "variety"]), id: idSchema }),
    handler: args => run(args.revision, h => detailCommand(h, { ...args, focus: true })),
  });
  useFrontendTool({ name: "show_geography_connections", description: "Open GeographyConnections for the existing investigation, using recorded company connections only. Company presence never proves variety growing.",
    parameters: z.object({ revision: revisionSchema }),
    handler: args => run(args.revision, async h => {
      if (!fresh(h, args.revision)) return staleCommand();
      const accepted = h.dispatch({ type: "setLens", lens: "geography", origin: "copilot", expectedRevision: args.revision });
      return accepted ? { ok: true, code: "applied", message: "Geography opened in the main analytical field." } : staleCommand();
    }),
  });
  useFrontendTool({ name: "show_sensory_demo", description: "Open the isolated SensoryDemo in the main field. All fictitious specimens and overall-liking scores are synthetic, outside canonical intelligence and standard exports.",
    parameters: z.object({ revision: revisionSchema }),
    handler: args => run(args.revision, async h => {
      if (!fresh(h, args.revision)) return staleCommand();
      return h.dispatch({ type: "setLens", lens: "sensory", origin: "copilot", expectedRevision: args.revision })
        ? { ok: true, code: "applied", message: "The labeled synthetic sensory demonstration is open." } : staleCommand();
    }),
  });
  return null;
}

export function CopilotCommand({ onClose }: { onClose: () => void }) {
  const gate = useContext(Gate);
  return <aside className="berry-detail berry-copilot" aria-label="Ask Berry command">
    <header><div><p className="berry-eyebrow">Ask Berry</p><h2>Work with this investigation</h2></div><button type="button" className="berry-button" onClick={onClose} aria-label="Close Ask Berry">Close</button></header>
    {gate.loading ? <p role="status">Checking availability…</p> : !gate.configured ? <p role="status">{gate.statusError || "Ask Berry is not configured in this environment. Continue with the investigation controls."}</p> : <CommandForm onClose={onClose} />}
  </aside>;
}
function CommandForm({ onClose }: { onClose: () => void }) {
  const { agent, isReady } = useAgent({ agentId: "default" });
  const { copilotkit } = useCopilotKit();
  const { getRevision } = useInvestigation();
  const gate = useContext(Gate);
  const [command, setCommand] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const subscription = copilotkit.subscribe({ onError: () => { setError("Ask Berry could not complete this command. Your investigation controls remain available."); setRunning(false); gate.active.current = null; } });
    return () => subscription.unsubscribe();
  }, [copilotkit, gate.active]);
  useEffect(() => () => { if (gate.active.current !== null) { gate.generation.current += 1; gate.active.current = null; void copilotkit.stopAgent({ agent }); } }, [agent, copilotkit, gate.active, gate.generation]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!command.trim() || running || agent.isRunning || !isReady) return;
    const commandGeneration = ++gate.generation.current;
    gate.active.current = getRevision(); gate.setResult(null); setError(""); setRunning(true);
    // Each command uses current selectors. Retaining half of a previous tool
    // exchange could orphan tool results; no prior conversation is needed.
    agent.setMessages([]);
    agent.addMessage({ id: crypto.randomUUID(), role: "user", content: command.trim() });
    try { await copilotkit.runAgent({ agent }); }
    catch { setError("Ask Berry could not complete this command. Try again or use the investigation controls."); }
    finally {
      if (commandGeneration !== gate.generation.current) return;
      if (!gate.lastResult.current) gate.setResult({ ok: false, code: "no_action", message: "No supported view change was applied. Try a specific company, comparison or source command." });
      gate.active.current = null; setRunning(false);
    }
  };
  return <>
    <p>Commands update the same analytical field and Reader. Conversation lasts for this page session.</p>
    <form onSubmit={submit}><label htmlFor="berry-command">What would you like to inspect?</label><textarea id="berry-command" value={command} maxLength={1000} rows={4} onChange={event => setCommand(event.target.value)} placeholder="Compare Fall Creek and Costa in China" />
      <div className="berry-command-actions"><button type="submit" className="berry-button berry-button--primary" disabled={!isReady || running || agent.isRunning || !command.trim()}>{running ? "Working…" : "Run command"}</button>{running && <button type="button" className="berry-button" onClick={() => { gate.generation.current += 1; gate.active.current = null; gate.setResult({ ok: false, code: "cancelled", message: "Command canceled. The current investigation is preserved." }); void copilotkit.stopAgent({ agent }); setRunning(false); }}>Cancel</button>}</div>
    </form>
    {!isReady && <p role="status">Connecting to Ask Berry…</p>}
    {error && <p role="alert">{error}</p>}
    {gate.result && <p role="status">{gate.result.message}</p>}
    {gate.result?.ok && <button type="button" className="berry-button" onClick={onClose}>Return to investigation</button>}
  </>;
}
