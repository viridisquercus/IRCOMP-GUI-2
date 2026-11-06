/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import { createRoot } from "react-dom/client";
import { WorkspaceProvider } from "./app/WorkspaceProvider";
import { App } from "./app/App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <WorkspaceProvider>
    <App />
  </WorkspaceProvider>,
);
