import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createApiClient } from "../api/client";
import { ticketsApi, type TicketsApi } from "../api/tickets";

interface AuthState {
  username: string | null;
  isAuthenticated: boolean;
  api: TicketsApi;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

interface AuthProviderProps {
  children: ReactNode;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

/**
 * Holds the access token IN MEMORY (not localStorage) so an XSS bug
 * cannot simply read it from storage. Trade-off: a page refresh logs
 * the user out; production apps add a refresh token in an httpOnly
 * cookie or a backend-for-frontend.
 */
export function AuthProvider({
  children,
  baseUrl = "",
  fetchImpl,
}: AuthProviderProps) {
  const [username, setUsername] = useState<string | null>(null);
  const tokenRef = useRef<string | null>(null);

  const logout = useCallback(() => {
    tokenRef.current = null;
    setUsername(null);
  }, []);

  const api = useMemo(
    () =>
      ticketsApi(
        createApiClient({
          baseUrl,
          fetchImpl,
          getToken: () => tokenRef.current,
          onUnauthorized: logout, // expired token → back to login
        }),
      ),
    [baseUrl, fetchImpl, logout],
  );

  const login = useCallback(
    async (user: string, password: string) => {
      const token = await api.login(user, password);
      tokenRef.current = token.access_token;
      setUsername(user);
    },
    [api],
  );

  const value = useMemo<AuthState>(
    () => ({
      username,
      isAuthenticated: username !== null,
      api,
      login,
      logout,
    }),
    [username, api, login, logout],
  );
  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
