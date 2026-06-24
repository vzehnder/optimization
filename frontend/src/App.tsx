import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { FormEvent, ReactNode, useState } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import {
  ApiError,
  bootstrapAdmin,
  getCurrentUser,
  login,
  logout,
  type AuthSessionResponse,
  type CurrentUser,
  type CurrentUserResponse,
} from "./api/client";
import { ScenarioDraftEditorView } from "./DraftEditor";
import { ErrorBoundary } from "./ErrorBoundary";
import "./styles.css";
import {
  ForbiddenView,
  NotFoundView,
  PublicationPreviewView,
  ProjectDetailView,
  ProjectListView,
  RunDetailView,
  ScenarioDetailView,
  ScenarioVersionDetailView,
} from "./Workspace";

const identityQueryKey = ["current-user"];

function reactRouteFromServerPath(path: string): string {
  if (path === "/react") return "/";
  if (path.startsWith("/react/")) return path.slice("/react".length);
  return "/";
}

function currentReactPath(location: ReturnType<typeof useLocation>): string {
  return `/react${location.pathname}${location.search}`;
}

function landingRoute(user: CurrentUser): string {
  return user.role === "client" ? "/client" : "/projects";
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "No se pudo completar la accion.";
}

function useAcceptAuthSession() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return (session: AuthSessionResponse) => {
    queryClient.setQueryData<CurrentUserResponse>(identityQueryKey, {
      user: session.user,
      bootstrap_required: false,
    });
    navigate(reactRouteFromServerPath(session.redirect_path), {
      replace: true,
    });
  };
}

function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <main className="auth-main">
      <section className="auth-panel">{children}</section>
    </main>
  );
}

function BootstrapView() {
  const acceptAuthSession = useAcceptAuthSession();
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: bootstrapAdmin,
    onSuccess: acceptAuthSession,
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    mutation.mutate({
      email: String(form.get("email") || ""),
      display_name: String(form.get("display_name") || ""),
      password: String(form.get("password") || ""),
    });
  }

  return (
    <AuthFrame>
      <h1>Crear admin</h1>
      {error ? <p role="alert">{error}</p> : null}
      <form className="auth-form" onSubmit={submit}>
        <label htmlFor="bootstrap-email">Email</label>
        <input
          id="bootstrap-email"
          name="email"
          type="email"
          autoComplete="username"
          required
        />
        <label htmlFor="bootstrap-name">Nombre</label>
        <input
          id="bootstrap-name"
          name="display_name"
          type="text"
          autoComplete="name"
        />
        <label htmlFor="bootstrap-password">Password</label>
        <input
          id="bootstrap-password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
        />
        <button type="submit" disabled={mutation.isPending}>
          Crear admin
        </button>
      </form>
    </AuthFrame>
  );
}

function LoginView() {
  const acceptAuthSession = useAcceptAuthSession();
  const location = useLocation();
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: login,
    onSuccess: acceptAuthSession,
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    mutation.mutate({
      email: String(form.get("email") || ""),
      password: String(form.get("password") || ""),
      next: currentReactPath(location),
    });
  }

  return (
    <AuthFrame>
      <h1>Iniciar sesion</h1>
      {error ? <p role="alert">{error}</p> : null}
      <form className="auth-form" onSubmit={submit}>
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="username"
          required
        />
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        <button type="submit" disabled={mutation.isPending}>
          Entrar
        </button>
      </form>
    </AuthFrame>
  );
}

function ClientHome() {
  return (
    <section className="content-panel">
      <h1>Portal cliente</h1>
      <p>Vista cliente lista para publicaciones autorizadas.</p>
    </section>
  );
}

function SystemStatus() {
  return (
    <section className="content-panel">
      <h1>Estado del sistema</h1>
      <p>Frontend React conectado al API FastAPI.</p>
    </section>
  );
}

function ShellHeader({ user }: { user: CurrentUser }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.setQueryData<CurrentUserResponse>(identityQueryKey, {
        user: null,
        bootstrap_required: false,
      });
      navigate("/", { replace: true });
    },
  });

  return (
    <>
      <header className="topbar">
        <Link className="brand" to="/">
          <span className="brand-mark" aria-hidden="true">
            Z
          </span>
          <span>BESS Workspace</span>
        </Link>
        <div className="identity">
          <strong>{user.display_name || user.email}</strong>
          <span className="role-badge">{user.role}</span>
          <button
            className="secondary-button"
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            Salir
          </button>
        </div>
      </header>
      <nav className="primary-nav" aria-label="Navegacion principal">
        {user.role !== "client" ? (
          <>
            <Link to="/projects">Analista</Link>
            <Link to="/system">Sistema</Link>
          </>
        ) : (
          <Link to="/client">Cliente</Link>
        )}
      </nav>
    </>
  );
}

function AuthenticatedRoutes({ user }: { user: CurrentUser }) {
  const isClient = user.role === "client";
  return (
    <div className="app-frame">
      <ShellHeader user={user} />
      <main id="main-content">
        <Routes>
          <Route index element={<Navigate to={landingRoute(user)} replace />} />
          <Route
            path="projects"
            element={isClient ? <ForbiddenView /> : <ProjectListView />}
          />
          <Route
            path="projects/:projectId"
            element={isClient ? <ForbiddenView /> : <ProjectDetailView />}
          />
          <Route
            path="scenarios/:scenarioId"
            element={isClient ? <ForbiddenView /> : <ScenarioDetailView />}
          />
          <Route
            path="scenarios/:scenarioId/draft"
            element={isClient ? <ForbiddenView /> : <ScenarioDraftEditorView />}
          />
          <Route
            path="scenario-versions/:versionId"
            element={
              isClient ? <ForbiddenView /> : <ScenarioVersionDetailView />
            }
          />
          <Route
            path="runs/:runId"
            element={isClient ? <ForbiddenView /> : <RunDetailView />}
          />
          <Route
            path="publications/:publicationId/preview"
            element={isClient ? <ForbiddenView /> : <PublicationPreviewView />}
          />
          <Route
            path="system"
            element={isClient ? <ForbiddenView /> : <SystemStatus />}
          />
          <Route
            path="client"
            element={isClient ? <ClientHome /> : <ForbiddenView />}
          />
          <Route path="*" element={<NotFoundView />} />
        </Routes>
      </main>
    </div>
  );
}

function Shell() {
  const identity = useQuery({
    queryKey: identityQueryKey,
    queryFn: ({ signal }) => getCurrentUser(signal),
    retry: false,
  });

  if (identity.isPending) {
    return <p role="status">Cargando sesion</p>;
  }

  if (identity.isError) {
    return (
      <div role="alert">
        <p>No se pudo cargar la sesion.</p>
        <button type="button" onClick={() => void identity.refetch()}>
          Reintentar
        </button>
      </div>
    );
  }

  if (identity.data.bootstrap_required && !identity.data.user) {
    return <BootstrapView />;
  }

  if (!identity.data.user) {
    return <LoginView />;
  }

  return <AuthenticatedRoutes user={identity.data.user} />;
}

export function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000 } },
      }),
  );
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename="/react">
          <Shell />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
