/**
 * @file main.tsx
 * @brief Entry point of the web client
 * @author Lukas (Viridis) Dubsik
 * @version 0.1
 */
// Shared styles first, the components build on them
import "./styles/base.css";
import { createRoot } from "react-dom/client";
import { WorkspaceProvider } from "./app/WorkspaceProvider";
import { App } from "./app/App";

createRoot(document.getElementById("root")!).render(
  <WorkspaceProvider>
    <App />
  </WorkspaceProvider>,
);
