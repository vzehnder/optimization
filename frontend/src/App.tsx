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
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { AdminUsersView } from "./Admin";
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
import {
  ClientPortalHomeView,
  ClientProjectView,
  ClientPublicationView,
} from "./ClientPortal";
import { ScenarioDraftEditorView } from "./DraftEditor";
import { ErrorBoundary } from "./ErrorBoundary";
import { GlobalCatalogView } from "./GlobalCatalog";
import {
  ConsoleListView,
  ConsoleRootPlanIdentity,
  ConsoleShellView,
  OperatorConsoleEditorView,
} from "./OperatorConsole";
import "./styles.css";
import {
  ForbiddenView,
  HydraulicDiagramEditorView,
  HydraulicTimeSeriesSetDetailView,
  NotFoundView,
  PublicationPreviewView,
  ProjectDetailView,
  ProjectListView,
  RunComparisonView,
  RunDetailView,
  ScenarioDetailView,
  ScenarioVersionDetailView,
  TimeSeriesCatalogView,
  TimeSeriesSetDetailView,
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

function isExternalIdentity(user: CurrentUser): boolean {
  return user.role === "external";
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
      ts_next_canonical_read: session.ts_next_canonical_read,
    });
    navigate(reactRouteFromServerPath(session.landing_path), {
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

function SystemStatus() {
  return (
    <section className="content-panel">
      <h1>Estado del sistema</h1>
      <p>Frontend React conectado al API FastAPI.</p>
    </section>
  );
}

interface RootProps {
  user: CurrentUser;
  landingPath: string;
  canonicalCatalogRead?: boolean;
}

function LogoutButton() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.setQueryData<CurrentUserResponse>(identityQueryKey, {
        user: null,
        bootstrap_required: false,
        landing_path: null,
        ts_next_canonical_read: false,
      });
      navigate("/", { replace: true });
    },
  });

  return (
    <button
      className="secondary-button"
      type="button"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
    >
      Salir
    </button>
  );
}

function IdentityStrip({ user }: { user: CurrentUser }) {
  return (
    <div className="identity">
      <strong>{user.display_name || user.email}</strong>
      <span className="role-badge">{user.role}</span>
      <LogoutButton />
    </div>
  );
}

// A root the identity may not enter says only that, and still lets it leave.
function DeniedRoot({ user, landingPath }: RootProps) {
  return (
    <div className="app-frame">
      <header className="topbar">
        <IdentityStrip user={user} />
      </header>
      <main id="main-content">
        <section className="content-panel">
          <h1>No encontrado</h1>
          <p>El recurso solicitado no existe.</p>
          <Link
            className="button-link"
            to={reactRouteFromServerPath(landingPath)}
          >
            Volver
          </Link>
        </section>
      </main>
    </div>
  );
}

function AnalystRoot({ user, landingPath, canonicalCatalogRead }: RootProps) {
  if (isExternalIdentity(user))
    return <DeniedRoot user={user} landingPath={landingPath} />;

  return (
    <div className="app-frame">
      <header className="topbar">
        <Link className="brand" to="/">
          <span className="brand-mark" aria-hidden="true">
            Z
          </span>
          <span>BESS Workspace</span>
        </Link>
        <IdentityStrip user={user} />
      </header>
      <nav className="primary-nav" aria-label="Navegacion principal">
        <Link to="/projects">Analista</Link>
        {canonicalCatalogRead ? (
          <Link to="/time-series/catalog">Catalogo</Link>
        ) : null}
        {user.role === "admin" ? <Link to="/admin/users">Admin</Link> : null}
        <Link to="/system">Sistema</Link>
      </nav>
      <main id="main-content">
        <Outlet />
      </main>
    </div>
  );
}

function ConsoleRoot({ user }: RootProps) {
  return (
    <div className="app-frame">
      <header className="topbar console-topbar">
        <ConsoleRootPlanIdentity />
        <IdentityStrip user={user} />
      </header>
      <main id="main-content">
        <Outlet />
      </main>
    </div>
  );
}

function PortalRoot({ user, landingPath }: RootProps) {
  if (!isExternalIdentity(user))
    return <DeniedRoot user={user} landingPath={landingPath} />;

  return (
    <div className="app-frame">
      <header className="topbar portal-topbar">
        <Link className="portal-shell-link" to="/client">
          Portal cliente
        </Link>
        <IdentityStrip user={user} />
      </header>
      <nav className="primary-nav" aria-label="Navegacion del informe">
        <Link to="/client">Cliente</Link>
      </nav>
      <main id="main-content">
        <Outlet />
      </main>
    </div>
  );
}

// The one landing decision belongs to the backend; this only follows it.
function LandingRedirect({ landingPath }: { landingPath: string }) {
  const route = reactRouteFromServerPath(landingPath);
  if (route === "/") return <NotFoundView />;
  return <Navigate to={route} replace />;
}

function AuthenticatedRoutes({
  user,
  landingPath,
  canonicalCatalogRead,
}: {
  user: CurrentUser;
  landingPath: string;
  canonicalCatalogRead: boolean;
}) {
  return (
    <Routes>
      <Route index element={<LandingRedirect landingPath={landingPath} />} />
      <Route
        element={
          <AnalystRoot
            user={user}
            landingPath={landingPath}
            canonicalCatalogRead={canonicalCatalogRead}
          />
        }
      >
        <Route path="projects" element={<ProjectListView />} />
        <Route
          path="projects/:projectId"
          element={
            <ProjectDetailView
              canManageExternalAccess={user.role === "admin"}
            />
          }
        />
        <Route
          path="projects/:projectId/time-series-sets"
          element={
            <TimeSeriesCatalogView
              canBulkMigrateHydraulicSeries={user.role === "admin"}
            />
          }
        />
        <Route
          path="projects/:projectId/time-series-sets/hydraulic/:hydraulicTimeSeriesSetId"
          element={<HydraulicTimeSeriesSetDetailView />}
        />
        <Route
          path="projects/:projectId/time-series-sets/:timeSeriesSetId"
          element={<TimeSeriesSetDetailView />}
        />
        <Route path="scenarios/:scenarioId" element={<ScenarioDetailView />} />
        <Route
          path="scenarios/:scenarioId/draft"
          element={<ScenarioDraftEditorView />}
        />
        <Route
          path="scenarios/:scenarioId/consoles/:consoleId"
          element={<OperatorConsoleEditorView />}
        />
        <Route
          path="scenarios/:scenarioId/runs/compare"
          element={<RunComparisonView />}
        />
        <Route
          path="scenarios/:scenarioId/hydraulic-diagram"
          element={<HydraulicDiagramEditorView />}
        />
        <Route
          path="scenario-versions/:versionId"
          element={<ScenarioVersionDetailView />}
        />
        <Route path="runs/:runId" element={<RunDetailView />} />
        <Route
          path="publications/:publicationId/preview"
          element={<PublicationPreviewView />}
        />
        <Route
          path="time-series/catalog"
          element={
            // Chapter 11.1: before the C6 cutover the canonical read surface
            // exists only for the verification accounts. Everyone else keeps
            // the pre-cutover behaviour, which is that the route is not there.
            canonicalCatalogRead ? <GlobalCatalogView /> : <NotFoundView />
          }
        />
        <Route path="system" element={<SystemStatus />} />
        <Route
          path="admin/users"
          element={
            user.role === "admin" ? <AdminUsersView /> : <ForbiddenView />
          }
        />
        <Route path="*" element={<NotFoundView />} />
      </Route>
      <Route element={<ConsoleRoot user={user} landingPath={landingPath} />}>
        <Route path="console" element={<ConsoleListView />} />
        <Route path="console/:consoleId" element={<ConsoleShellView />} />
      </Route>
      <Route element={<PortalRoot user={user} landingPath={landingPath} />}>
        <Route path="client" element={<ClientPortalHomeView />} />
        <Route
          path="client/projects/:projectId"
          element={<ClientProjectView />}
        />
        <Route
          path="client/projects/:projectId/publications/:publicationId"
          element={<ClientPublicationView />}
        />
      </Route>
    </Routes>
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

  return (
    <AuthenticatedRoutes
      user={identity.data.user}
      landingPath={identity.data.landing_path || "/react"}
      canonicalCatalogRead={identity.data.ts_next_canonical_read}
    />
  );
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
