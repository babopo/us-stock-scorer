import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Button, ConfigProvider, Layout, Menu, Tag, theme } from "antd";
import { FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { BrowserRouter, NavLink, useLocation } from "react-router-dom";
import { Activity, BarChart3, DatabaseZap, FlaskConical, LogOut, Search, ShieldCheck } from "lucide-react";

import { isApiError, type StockScorerClient } from "@stock-scorer/api-client";

import { createDefaultAdminApiClient } from "../api/client";
import { BacktestingPanel } from "../features/backtesting/BacktestingPanel";
import { OperationsPanel } from "../features/operations/OperationsPanel";
import { ProviderStatus } from "../features/providers/ProviderStatus";
import { ScoreDebugger } from "../features/score/ScoreDebugger";

export const ADMIN_SESSION_TOKEN_STORAGE_KEY = "stock-scorer-admin-token";
const { Content, Header, Sider } = Layout;

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
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#f59e0b",
          borderRadius: 8,
          fontFamily: "\"Fira Sans\", Arial, sans-serif"
        }
      }}
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          {authStatus === "authenticated" ? (
            <AdminDashboard client={apiClient} onLogout={handleLogout} />
          ) : (
            <LoginPanel client={apiClient} onLogin={handleLogin} checkingSession={authStatus === "checking"} />
          )}
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  );
}

function AdminDashboard({ client, onLogout }: { client: StockScorerClient; onLogout(): void }) {
  const location = useLocation();
  const selectedKey = navigationItems.find((item) => location.pathname.startsWith(item.path))?.path || "/score";

  return (
    <Layout className="admin-layout">
      <Sider className="admin-sider" width={244} breakpoint="lg" collapsedWidth="0">
        <div className="admin-brand">
          <span>US Stock Scorer</span>
          <strong>美股评分工作台</strong>
        </div>
        <nav aria-label="Desktop sections">
          <Menu
            className="admin-menu"
            mode="inline"
            selectedKeys={[selectedKey]}
            items={navigationItems.map((item) => ({
              key: item.path,
              icon: item.icon,
              label: <NavLink to={item.path}>{item.label}</NavLink>
            }))}
          />
        </nav>
      </Sider>
      <Layout className="admin-main-layout">
        <Header className="admin-header">
          <div>
            <span className="eyebrow">Operations console</span>
            <strong>{navigationItems.find((item) => item.path === selectedKey)?.label || "数据查询"}</strong>
          </div>
          <div className="admin-header-actions">
            <Tag color="processing">Admin</Tag>
            <Button type="primary" icon={<LogOut aria-hidden="true" size={16} />} onClick={onLogout}>
              Log out
            </Button>
          </div>
        </Header>
        <MobileSectionTabs selectedKey={selectedKey} />
        <Content className="admin-content">
          {renderAdminPage(location.pathname, client)}
        </Content>
      </Layout>
    </Layout>
  );
}

function MobileSectionTabs({ selectedKey }: { selectedKey: string }) {
  return (
    <nav className="mobile-section-tabs" aria-label="Mobile sections">
      {navigationItems.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          className={({ isActive }) => (isActive || item.path === selectedKey ? "active" : "")}
        >
          {item.icon}
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function renderAdminPage(pathname: string, client: StockScorerClient) {
  if (pathname.startsWith("/strategy")) {
    return <StrategyPage client={client} />;
  }
  if (pathname.startsWith("/backtests")) {
    return <BacktestsPage client={client} />;
  }
  if (pathname.startsWith("/operations")) {
    return <OperationsPage client={client} />;
  }
  return <ScorePage client={client} />;
}

const navigationItems = [
  { path: "/score", label: "数据查询", icon: <Search aria-hidden="true" size={17} /> },
  { path: "/strategy", label: "策略管理", icon: <FlaskConical aria-hidden="true" size={17} /> },
  { path: "/backtests", label: "回测实验", icon: <BarChart3 aria-hidden="true" size={17} /> },
  { path: "/operations", label: "运维操作", icon: <DatabaseZap aria-hidden="true" size={17} /> }
];

function PageShell({ title, eyebrow, children }: { title: string; eyebrow: string; children: ReactNode }) {
  return (
    <section className="admin-page" aria-labelledby="admin-page-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1 id="admin-page-title">{title}</h1>
        </div>
        <span className="status-pill">
          <Activity aria-hidden="true" size={16} />
          Live
        </span>
      </div>
      {children}
    </section>
  );
}

function ScorePage({ client }: { client: StockScorerClient }) {
  return (
    <PageShell title="数据查询" eyebrow="Stock intelligence">
      <ScoreDebugger client={client} />
    </PageShell>
  );
}

function StrategyPage({ client }: { client: StockScorerClient }) {
  return (
    <PageShell title="策略管理" eyebrow="Strategy governance">
      <BacktestingPanel client={client} view="strategy" />
    </PageShell>
  );
}

function BacktestsPage({ client }: { client: StockScorerClient }) {
  return (
    <PageShell title="回测实验" eyebrow="Portfolio research">
      <BacktestingPanel client={client} view="backtests" />
    </PageShell>
  );
}

function OperationsPage({ client }: { client: StockScorerClient }) {
  return (
    <PageShell title="运维操作" eyebrow="Runtime controls">
      <div className="operations-page-grid">
        <ProviderStatus client={client} />
        <OperationsPanel client={client} />
      </div>
    </PageShell>
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
