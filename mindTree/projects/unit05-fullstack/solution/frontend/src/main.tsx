import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { createMockFetch } from "./api/mockServer";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./styles.css";

// Unit 5 default: the real FastAPI backend. VITE_USE_MOCK=true keeps
// the Unit 4 in-memory mock for frontend-only work.
const useMock = import.meta.env.VITE_USE_MOCK === "true";
const fetchImpl = useMock ? createMockFetch() : undefined;
const baseUrl = useMock
  ? ""
  : (import.meta.env.VITE_API_BASE_URL ?? "/api");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider baseUrl={baseUrl} fetchImpl={fetchImpl}>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
