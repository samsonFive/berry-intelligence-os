import { Fragment, useEffect, useRef, useState } from "react";
import type { ComponentType, ReactNode } from "react";
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { PRESENTATION_CONTEXT, investigationHref, isNativeSurfacePath, serializeInvestigation } from "../contracts/investigation";
import { InvestigationProvider, useInvestigation } from "../state/InvestigationProvider";
import { PrivateQueryProvider, clearPrivateSession } from "./PrivateQueryProvider";
import { SurfaceScroll, useSurfaceReady } from "./SurfaceScroll";
import { legacyHref } from "./legacy";
import { InvestigationScopeBar } from "../components/InvestigationScopeBar";
import { InvestigationSidebar, WorkspaceNavigation } from "../components/WorkspaceChrome";

export interface FeatureSlots {
  Landscape: ComponentType; Briefing: ComponentType; Workspaces: ComponentType; Learn: ComponentType;
  Detail?: ComponentType<{ suspended?: boolean }>; Command?: ComponentType<{ onClose: () => void }>;
  Provider?: ComponentType<{ children: ReactNode }>; Tools?: ComponentType;
}
function LegacyBoundary({ title, href, description }: { title: string; href: string; description: string }) {
  useSurfaceReady(true);
  return <section className="berry-feature-boundary"><p className="berry-eyebrow">Existing workspace</p><h1>{title}</h1><p>{description}</p><a href={href}>Open {title}</a><p>Opening this workspace uses its existing page. Your investigation remains in this tab’s history.</p></section>;
}
function LandscapeBoundary() {
  useSurfaceReady(true);
  return <section><h1>Landscape</h1><p>The source-backed investigation view is being integrated.</p><a href="/landscapes/explorer">Open existing Landscape Explorer</a></section>;
}
function LearnDestination({ Feature }: { Feature: ComponentType }) {
  const { pathname } = useLocation();
  const { context } = useInvestigation();
  return isNativeSurfacePath(pathname) ? <Feature /> : <Navigate to={investigationHref("/app/learn", context)} replace />;
}
const defaultFeatures: FeatureSlots = {
  Landscape: LandscapeBoundary,
  Briefing: () => <LegacyBoundary title="Briefing" href="/news" description="Read current developments with the existing visual News cards and shared Reader." />,
  Workspaces: () => <LegacyBoundary title="Workspaces" href="/workspaces" description="Develop and organize authored analysis in the existing versioned workspace." />,
  Learn: () => <LegacyBoundary title="Learn" href="/learn" description="Explore the existing educational lessons and their research context." />,
};
const destinations = [["landscape", "Landscape"], ["briefing", "Briefing"], ["workspaces", "Workspaces"], ["learn", "Learn"]] as const;
function Shell({ features }: { features: FeatureSlots }) {
  const { context, issues } = useInvestigation();
  const { pathname } = useLocation();
  const [commandOpen, setCommandOpen] = useState(false);
  const previousDetail = useRef(context.detail_path);
  useEffect(() => {
    if (previousDetail.current !== context.detail_path) setCommandOpen(false);
    previousDetail.current = context.detail_path;
  }, [context.detail_path]);
  const { Landscape, Briefing, Workspaces, Learn, Detail, Command } = features;
  const search = `?${serializeInvestigation(context)}`;
  return <div className="berry-app berry-shell">
    <a className="berry-skip-link" href="#investigation-main">Skip to investigation</a>
    <header className="berry-topbar" data-region="app-chrome"><Link className="berry-brand" to={investigationHref("/app/landscape", context)} aria-label="Berry intelligence home"><img src="/static/berry-intelligence-icon.png" width="36" height="36" alt="" /><span><b>berry</b> intelligence<small>YOUR INDUSTRY, IN VIEW</small></span></Link>
      <nav className="berry-nav" aria-label="Primary">{destinations.map(([path, label]) => path === 'workspaces'
        ? <a key={path} href={legacyHref('/workspaces', pathname, context)}>{label}</a>
        : <NavLink key={path} to={{ pathname: `/app/${path}`, search }}>{label}</NavLink>)}</nav>
      <div className="berry-topbar-actions">
      <Link className="berry-button berry-button--quiet" to={investigationHref('/app/workspaces', context)}>Save / export</Link>
      {Command && <button type="button" className="berry-button berry-button--ghost" aria-expanded={commandOpen} onClick={() => setCommandOpen(open => !open)}>Ask Berry</button>}
      <details className="berry-utilities"><summary>More</summary><div className="berry-utilities-menu">{[
        ['/entities/company', 'Browse companies'], ['/entities/variety', 'Browse varieties'],
        ['/search', 'Search catalog'], ['/research-ops', 'Research tools'],
        ['/review-ops', 'Review'], ['/operations', 'Operations'], ['/guide', 'Help'],
      ].map(([href, label]) => <a key={href} href={legacyHref(href, pathname, context)}>{label}</a>)}</div></details>
      <form action="/logout" method="post" onSubmit={clearPrivateSession}><button type="submit" className="berry-button berry-button--quiet">Sign out</button></form>
      </div>
    </header>
    <WorkspaceNavigation />
    {issues.length > 0 && <section className="berry-context-issues" role="status" aria-label="Investigation selection issues"><ul>{issues.map((issue, index) => <li key={`${issue.field}-${index}`}>{issue.message}</li>)}</ul></section>}
    <div className="berry-context-layout"><InvestigationSidebar /><div className="berry-workspace" data-region="investigation-workspace"><main id="investigation-main" className="berry-main berry-document" data-region="main-workspace" tabIndex={-1}>{pathname !== "/app/landscape" && <InvestigationScopeBar />}<Routes>
      <Route path="/app/landscape" element={<Landscape />} /><Route path="/app/briefing" element={<Briefing />} /><Route path="/app/workspaces" element={<Workspaces />} /><Route path="/app/learn" element={<Learn />} />
      <Route path="/app/learn/concept/:learningId" element={<LearnDestination Feature={Learn} />} /><Route path="/app/learn/lesson/:learningId" element={<LearnDestination Feature={Learn} />} />
      <Route path="*" element={<Navigate to={investigationHref("/app/landscape", context)} replace />} />
    </Routes></main>{Detail && <Detail suspended={commandOpen} />}{commandOpen && Command && <Command onClose={() => setCommandOpen(false)} />}</div></div>
  </div>;
}
export function ExperienceApp({ features = defaultFeatures }: { features?: FeatureSlots }) {
  const Provider = features.Provider ?? Fragment;
  const Tools = features.Tools;
  return <BrowserRouter><PrivateQueryProvider><InvestigationProvider><Provider>{Tools && <Tools />}<SurfaceScroll><Shell features={features} /></SurfaceScroll></Provider></InvestigationProvider></PrivateQueryProvider></BrowserRouter>;
}
export { defaultFeatures, PRESENTATION_CONTEXT };
