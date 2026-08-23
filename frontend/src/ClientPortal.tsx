import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ReactNode, useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  getClientPublication,
  listClientProjectPublications,
  listClientProjects,
  type ClientPortalProject,
  type PortalBranding,
  type Publication,
} from "./api/client";
import {
  PortalPublicationHeader,
  PortalPublicationReport,
} from "./PortalResults";

const clientProjectsQueryKey = ["client-projects"] as const;
const clientProjectPublicationsQueryKey = (projectId: number) =>
  ["client-project-publications", projectId] as const;
const clientPublicationQueryKey = (projectId: number, publicationId: number) =>
  ["client-publication", projectId, publicationId] as const;

function useNumericParam(name: string): number | null {
  const params = useParams();
  const rawValue = params[name];
  const value = Number(rawValue);
  if (!rawValue || !Number.isInteger(value) || value < 1) return null;
  return value;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "No se pudo completar la accion.";
}

function isAuthorizationFailure(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 401 || error.status === 403 || error.status === 404)
  );
}

function useClearClientCacheOnAuthorizationFailure(error: unknown) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!isAuthorizationFailure(error)) return;
    queryClient.removeQueries({
      predicate: (query) =>
        String(query.queryKey[0] || "").startsWith("client-"),
    });
  }, [error, queryClient]);
}

function LoadingView({ label }: { label: string }) {
  return <p role="status">{label}</p>;
}

function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty-state">{children}</p>;
}

function Breadcrumbs({ children }: { children: ReactNode }) {
  return (
    <nav className="breadcrumbs" aria-label="Ruta">
      {children}
    </nav>
  );
}

function usePortalDocumentTitle(displayName?: string) {
  useEffect(() => {
    if (!displayName) return undefined;
    const previousTitle = document.title;
    document.title = displayName;
    return () => {
      document.title = previousTitle;
    };
  }, [displayName]);
}

function PortalProjectBrand({ branding }: { branding: PortalBranding }) {
  return (
    <>
      {branding.logo_url ? (
        <img
          className="portal-logo"
          src={branding.logo_url}
          alt={`Logo de ${branding.display_name}`}
        />
      ) : null}
      <h1>{branding.display_name}</h1>
    </>
  );
}

function ClientErrorView({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <section className="content-panel">
        <h1>No encontrado</h1>
        <p>El recurso solicitado no existe.</p>
        <Link className="button-link" to="/client">
          Volver al portal
        </Link>
      </section>
    );
  }
  return (
    <section className="content-panel">
      <h1>No se pudo cargar</h1>
      <p>{errorMessage(error)}</p>
      {retry ? (
        <button type="button" onClick={retry}>
          Reintentar
        </button>
      ) : null}
    </section>
  );
}

function ClientProjectList({ projects }: { projects: ClientPortalProject[] }) {
  if (!projects.length) {
    return <EmptyState>No hay proyectos asignados.</EmptyState>;
  }
  return (
    <ul className="resource-list">
      {projects.map((project) => (
        <li key={project.id}>
          {project.branding.logo_url ? (
            <img
              className="portal-logo portal-logo-list"
              src={project.branding.logo_url}
              alt=""
            />
          ) : null}
          <Link to={`/client/projects/${project.id}`}>
            {project.branding.display_name}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ClientPublicationList({
  publications,
}: {
  publications: Publication[];
}) {
  if (!publications.length) {
    return <EmptyState>No hay publicaciones activas.</EmptyState>;
  }
  return (
    <ul className="resource-list publication-list">
      {publications.map((publication) => (
        <li key={publication.id}>
          <Link
            to={`/client/projects/${publication.project_id}/publications/${publication.id}`}
          >
            {publication.public_title}
          </Link>
          <p>{publication.analyst_notes || "Sin notas."}</p>
          <p>{publication.published_at || "Publicado"}</p>
        </li>
      ))}
    </ul>
  );
}

export function ClientPortalHomeView() {
  usePortalDocumentTitle("Portal cliente");
  const projects = useQuery({
    queryKey: clientProjectsQueryKey,
    queryFn: ({ signal }) => listClientProjects(signal),
    staleTime: 0,
    refetchOnMount: "always",
    retry: false,
  });
  useClearClientCacheOnAuthorizationFailure(projects.error);

  if (projects.isPending || (projects.isFetching && projects.data)) {
    return <LoadingView label="Cargando portal cliente" />;
  }
  if (projects.isError) {
    return (
      <ClientErrorView
        error={projects.error}
        retry={() => void projects.refetch()}
      />
    );
  }

  return (
    <section className="workspace-view">
      <header className="workspace-heading">
        <p className="eyebrow">Cliente</p>
        <h1>Portal cliente</h1>
      </header>
      <section className="workspace-section" aria-labelledby="client-projects">
        <h2 id="client-projects">Proyectos asignados</h2>
        <ClientProjectList projects={projects.data} />
      </section>
    </section>
  );
}

export function ClientProjectView() {
  const projectId = useNumericParam("projectId");
  const publications = useQuery({
    queryKey: clientProjectPublicationsQueryKey(projectId || 0),
    queryFn: ({ signal }) =>
      listClientProjectPublications(projectId || 0, signal),
    enabled: projectId !== null,
    staleTime: 0,
    refetchOnMount: "always",
    retry: false,
  });
  useClearClientCacheOnAuthorizationFailure(publications.error);
  usePortalDocumentTitle(publications.data?.branding.display_name);

  if (projectId === null) {
    return (
      <ClientErrorView error={new ApiError("not found", 404, "not_found")} />
    );
  }
  if (
    publications.isPending ||
    (publications.isFetching && publications.data)
  ) {
    return <LoadingView label="Cargando publicaciones" />;
  }
  if (publications.isError) {
    return (
      <ClientErrorView
        error={publications.error}
        retry={() => void publications.refetch()}
      />
    );
  }

  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/client">Portal cliente</Link>
        <span aria-hidden="true">/</span>
        <span>{publications.data.branding.display_name}</span>
      </Breadcrumbs>
      <header className="workspace-heading">
        <p className="eyebrow">Proyecto</p>
        <PortalProjectBrand branding={publications.data.branding} />
      </header>
      <section
        className="workspace-section"
        aria-labelledby="client-publications"
      >
        <h2 id="client-publications">Publicaciones</h2>
        <ClientPublicationList publications={publications.data.publications} />
      </section>
    </section>
  );
}

export function ClientPublicationView() {
  const projectId = useNumericParam("projectId");
  const publicationId = useNumericParam("publicationId");
  const publication = useQuery({
    queryKey: clientPublicationQueryKey(projectId || 0, publicationId || 0),
    queryFn: ({ signal }) =>
      getClientPublication(projectId || 0, publicationId || 0, signal),
    enabled: projectId !== null && publicationId !== null,
    staleTime: 0,
    refetchOnMount: "always",
    retry: false,
  });
  useClearClientCacheOnAuthorizationFailure(publication.error);
  usePortalDocumentTitle(publication.data?.branding.display_name);

  if (projectId === null || publicationId === null) {
    return (
      <ClientErrorView error={new ApiError("not found", 404, "not_found")} />
    );
  }
  if (publication.isPending || (publication.isFetching && publication.data)) {
    return <LoadingView label="Cargando publicacion" />;
  }
  if (publication.isError) {
    return (
      <ClientErrorView
        error={publication.error}
        retry={() => void publication.refetch()}
      />
    );
  }

  const detail = publication.data;
  return (
    <section className="workspace-view">
      <Breadcrumbs>
        <Link to="/client">Portal cliente</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/client/projects/${detail.publication.project_id}`}>
          {detail.branding.display_name}
        </Link>
        <span aria-hidden="true">/</span>
        <span>{detail.publication.public_title}</span>
      </Breadcrumbs>
      <PortalPublicationHeader detail={detail} />
      <PortalPublicationReport detail={detail} />
    </section>
  );
}
