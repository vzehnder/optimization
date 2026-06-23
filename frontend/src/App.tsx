import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { getCurrentUser } from "./api/client";
import { ErrorBoundary } from "./ErrorBoundary";
import "./styles.css";

function Shell() {
  const identity = useQuery({
    queryKey: ["current-user"],
    queryFn: ({ signal }) => getCurrentUser(signal),
    retry: false,
  });

  if (identity.isPending) {
    return <p role="status">Cargando sesión…</p>;
  }

  if (identity.isError) {
    return (
      <div role="alert">
        <p>No se pudo cargar la sesión.</p>
        <button type="button" onClick={() => void identity.refetch()}>
          Reintentar
        </button>
      </div>
    );
  }

  const user = identity.data.user;
  return (
    <div className="app-frame">
      <header className="topbar">
        <Link className="brand" to="/">
          <span className="brand-mark" aria-hidden="true">
            Z
          </span>
          <span>BESS Workspace</span>
        </Link>
        <div className="identity">
          {user ? (
            <>
              <strong>{user.display_name || user.email}</strong>
              <span className="role-badge">{user.role}</span>
            </>
          ) : (
            <span>Sin sesión activa</span>
          )}
        </div>
      </header>
      <nav className="primary-nav" aria-label="Navegación principal">
        <Link to="/">Inicio</Link>
        <Link to="/system">Sistema</Link>
      </nav>
      <main id="main-content">
        <Routes>
          <Route
            index
            element={
              <section className="hero-panel">
                <p className="eyebrow">Nueva interfaz React</p>
                <h1>Centro de optimización BESS</h1>
                <p>
                  Base lista para migrar flujos sin interrumpir la aplicación
                  actual.
                </p>
              </section>
            }
          />
          <Route
            path="system"
            element={
              <section className="content-panel">
                <h1>Estado del sistema</h1>
                <p>Frontend React conectado al API FastAPI.</p>
              </section>
            }
          />
        </Routes>
      </main>
    </div>
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
