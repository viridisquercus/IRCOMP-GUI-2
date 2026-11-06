/**
 * @file main.tsx
 * @brief Entry point of the web client
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 */
import { createRoot } from "react-dom/client";
import { WorkspaceProvider } from "./app/WorkspaceProvider";
import { App } from "./app/App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <WorkspaceProvider>
    <App />
  </WorkspaceProvider>,
);
