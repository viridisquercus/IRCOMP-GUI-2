/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useRef,
  type Dispatch,
  type ReactNode,
} from "react";
import { createController } from "./controller";
import { dirty } from "./selectors";
import { initialState, reducer, type Action, type State } from "./state";

type Controller = ReturnType<typeof createController>;
const Context = createContext<{
  state: State;
  dispatch: Dispatch<Action>;
  controller: Controller;
} | null>(null);

/** Keep the shared state available to all three views. */
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const reference = useRef(state);
  reference.current = state;
  const controller = useRef<Controller | null>(null);
  if (!controller.current)
    controller.current = createController(() => reference.current, dispatch);
  useEffect(() => {
    void controller.current!.boot();
  }, []);
  useEffect(() => {
    const preventLoss = (event: BeforeUnloadEvent) => {
      if (dirty(reference.current)) event.preventDefault();
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

export function useWorkspace() {
  const context = useContext(Context);
  if (!context) throw new Error("WorkspaceProvider is required.");
  return context;
}
