/**
 * @file WorkspaceProvider.tsx
 * @brief React context holding the state shared by all the views
 * @author Lukas (Viridis) Dubsik
 * @version 0.1
 */
import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useRef,
  type Dispatch,
  type ReactNode,
} from "react";
import { createController, type Controller } from "./controller";
import { dirty } from "./selectors";
import { initialState, reducer, type Action, type State } from "./state";

/* Types */
type WorkspaceContext = {
  state: State;
  dispatch: Dispatch<Action>;
  controller: Controller;
};

const Context = createContext<WorkspaceContext | null>(null);

/* Components */
/**
 * @brief Keep the shared state available to all three views
 */
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  // The controller is created once, so it reads the state through a ref
  // to always get the newest one (not the one from the first render)
  const latest = useRef(state);
  latest.current = state;
  const controller = useRef<Controller | null>(null);
  if (!controller.current)
    controller.current = createController(() => latest.current, dispatch);

  // Load the catalogue and reconnect to the previous workspace
  useEffect(() => {
    void controller.current!.boot();
  }, []);

  // Warn before closing the tab with unsaved work
  useEffect(() => {
    const preventLoss = (event: BeforeUnloadEvent) => {
      if (dirty(latest.current)) event.preventDefault();
    };
    window.addEventListener("beforeunload", preventLoss);
    return () => window.removeEventListener("beforeunload", preventLoss);
  }, []);

  return (
    <Context.Provider
      value={{ state, dispatch, controller: controller.current }}
    >
      {children}
    </Context.Provider>
  );
}

/* Hooks */
/**
 * @brief Get the shared state, dispatch and controller
 */
export function useWorkspace(): WorkspaceContext {
  const context = useContext(Context);
  if (!context) throw new Error("WorkspaceProvider is required.");
  return context;
}
