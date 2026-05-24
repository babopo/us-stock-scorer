import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { LogOut, ShieldCheck } from "lucide-react";

import { isApiError, type StockScorerClient } from "@stock-scorer/api-client";

import { createDefaultAdminApiClient } from "../api/client";
import { OperationsPanel } from "../features/operations/OperationsPanel";
import { ProviderStatus } from "../features/providers/ProviderStatus";
import { ScoreDebugger } from "../features/score/ScoreDebugger";

export const ADMIN_SESSION_TOKEN_STORAGE_KEY = "stock-scorer-admin-token";

interface AppProps {
  client?: StockScorerClient;
}

export function App({ client }: AppProps) {
  const [authToken, setAuthToken] = useState(() => readStoredAdminToken());
  const [authStatus, setAuthStatus] = useState<"anonymous" | "checking" | "authenticated">(() =>
    authToken ? "checking" : "anonymous"
  );

  const clearAuth = useCallback(() => {
    clearStoredAdminToken();
    setAuthToken(null);
    setAuthStatus("anonymous");
  }, []);

  const handleAuthError = useCallback(
    (error: unknown) => {
      if (isAuthError(error)) {
        clearAuth();
      }
    },
    [clearAuth]
  );

  const queryClient = useMemo(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: handleAuthError
        }),
        mutationCache: new MutationCache({
          onError: handleAuthError
        }),
        defaultOptions: {
          queries: {
            retry: false,
            refetchOnWindowFocus: false
          },
          mutations: {
            retry: false
          }
        }
      }),
    [handleAuthError]
  );
  const apiClient = useMemo(() => client || createDefaultAdminApiClient(authToken || undefined), [authToken, client]);

  useEffect(() => {
    let active = true;
    if (!authToken) {
      setAuthStatus("anonymous");
      return () => {
        active = false;
      };
    }

    setAuthStatus("checking");
    apiClient
      .getAdminSession()
      .then(() => {
        if (active) {
          setAuthStatus("authenticated");
        }
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        if (isAuthError(error)) {
          clearAuth();
          return;
        }
        setAuthStatus("anonymous");
      });

    return () => {
      active = false;
    };
  }, [apiClient, authToken, clearAuth]);

  function handleLogin(nextToken: string) {
    storeAdminToken(nextToken);
    setAuthToken(nextToken);
    setAuthStatus("checking");
  }

  async function handleLogout() {
    try {
      await apiClient.logoutAdmin();
    } finally {
      clearAuth();
      queryClient.clear();
    }
  }

  return (
    <QueryClientProvider client={queryClient}>
      {authStatus === "authenticated" ? (
        <AdminDashboard client={apiClient} onLogout={handleLogout} />
      ) : (
        <LoginPanel client={apiClient} onLogin={handleLogin} checkingSession={authStatus === "checking"} />
      )}
    </QueryClientProvider>
  );
}

function AdminDashboard({ client, onLogout }: { client: StockScorerClient; onLogout(): void }) {
  return (
    <main className="admin-shell product-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">US Stock Scorer</p>
          <h1>美股评分工作台</h1>
        </div>
        <div className="topbar-actions">
          <nav aria-label="Workspace sections">
            <a href="#score-debugger-title">六维评分</a>
            <a href="#provider-status-title">数据源</a>
            <a href="#operations-title">数据操作</a>
          </nav>
          <button className="logout-button" type="button" onClick={onLogout}>
            <LogOut aria-hidden="true" size={17} />
            Log out
          </button>
        </div>
      </header>
      <div className="workspace">
        <ScoreDebugger client={client} />
        <div className="side-stack">
          <ProviderStatus client={client} />
          <OperationsPanel client={client} />
        </div>
      </div>
    </main>
  );
}

function LoginPanel({
  client,
  onLogin,
  checkingSession
}: {
  client: StockScorerClient;
  onLogin(token: string): void;
  checkingSession: boolean;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);
    try {
      const response = await client.loginAdmin(username.trim(), password);
      onLogin(response.access_token);
    } catch (error) {
      setErrorMessage(formatAuthError(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="admin-shell login-shell">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">US Stock Scorer</p>
            <h1 id="login-title">工作台登录</h1>
          </div>
          <span className="status-pill">
            <ShieldCheck aria-hidden="true" size={16} />
            Secure access
          </span>
        </div>

        {checkingSession ? <div className="empty-state auth-check">Checking session...</div> : null}
        {errorMessage ? (
          <div className="error-panel" role="alert">
            {errorMessage}
          </div>
        ) : null}

        <form className="login-form" onSubmit={submitLogin}>
          <label htmlFor="admin-username">Username</label>
          <input
            id="admin-username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            disabled={isSubmitting}
          />

          <label htmlFor="admin-password">Password</label>
          <input
            id="admin-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            disabled={isSubmitting}
          />

          <button type="submit" disabled={isSubmitting || checkingSession}>
            {isSubmitting ? "Logging in..." : "Log in"}
          </button>
        </form>
      </section>
    </main>
  );
}

function readStoredAdminToken(): string | null {
  const storage = getSessionStorage();
  return storage ? storage.getItem(ADMIN_SESSION_TOKEN_STORAGE_KEY) : null;
}

function storeAdminToken(token: string) {
  const storage = getSessionStorage();
  if (storage) {
    storage.setItem(ADMIN_SESSION_TOKEN_STORAGE_KEY, token);
  }
}

function clearStoredAdminToken() {
  const storage = getSessionStorage();
  if (storage) {
    storage.removeItem(ADMIN_SESSION_TOKEN_STORAGE_KEY);
  }
}

function getSessionStorage(): Storage | null {
  if (typeof sessionStorage === "undefined") {
    return null;
  }
  return sessionStorage;
}

function isAuthError(error: unknown): boolean {
  return isApiError(error) && (error.status === 401 || error.status === 403 || error.code === "unauthorized" || error.code === "forbidden");
}

function formatAuthError(error: unknown): string {
  if (isApiError(error)) {
    if (error.status === 401) {
      return "Invalid username or password";
    }
    return `${error.code}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Login failed";
}
