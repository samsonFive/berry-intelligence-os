import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ExperienceApp, defaultFeatures } from "./app/App";
import LandscapePage from "./features/landscape/LandscapePage";
import { DetailHost } from "./features/detail/DetailHost";
import { CopilotCommand, CopilotProvider, CopilotTools } from "./features/copilot";
import "./design/berry.css";

const root = document.getElementById("root");
if (!root) throw new Error("The investigation application mount is missing.");
createRoot(root).render(<StrictMode><ExperienceApp features={{ ...defaultFeatures, Landscape: LandscapePage, Detail: DetailHost, Command: CopilotCommand, Provider: CopilotProvider, Tools: CopilotTools }} /></StrictMode>);
