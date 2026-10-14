import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { createMockFetch } from "./api/mockServer";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./styles.css";

const useMock = import.meta.env.VITE_USE_MOCK !== "false";
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
