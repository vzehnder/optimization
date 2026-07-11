import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  assignProjectClientAccess,
  createAdminUser,
  createRunSchedule,
  deactivateAdminUser,
  listAdminUsers,
  listProjectClientAccess,
  listRunSchedules,
  removeProjectClientAccess,
  runDueSchedules,
  type AdminUser,
  type ProjectClientAccess,
  type RunSchedule,
  type RunScheduleCreatePayload,
  type RunScheduleTick,
  type UserCreatePayload,
} from "./api/client";

const adminUsersQueryKey = ["admin-users"] as const;
const runSchedulesQueryKey = ["run-schedules"] as const;
const projectClientAccessQueryKey = (projectId: number) =>
  ["project-client-access", projectId] as const;

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "No se pudo completar la accion.";
}

function appendUser(users: AdminUser[] | undefined, user: AdminUser) {
  if (!users) return [user];
  if (users.some((candidate) => candidate.id === user.id)) return users;
  return [...users, user];
}

function replaceUser(users: AdminUser[] | undefined, user: AdminUser) {
  if (!users) return [user];
  return users.map((candidate) =>
    candidate.id === user.id ? user : candidate,
  );
}

function appendAssignment(
  assignments: ProjectClientAccess[] | undefined,
  assignment: ProjectClientAccess,
) {
  if (!assignments) return [assignment];
  if (assignments.some((candidate) => candidate.user_id === assignment.user_id))
    return assignments;
  return [...assignments, assignment];
}

function removeAssignment(
  assignments: ProjectClientAccess[] | undefined,
  userId: number,
) {
  return (assignments || []).filter(
    (assignment) => assignment.user_id !== userId,
  );
}

function appendSchedule(
  schedules: RunSchedule[] | undefined,
  schedule: RunSchedule,
) {
  if (!schedules) return [schedule];
  if (schedules.some((candidate) => candidate.id === schedule.id))
    return schedules;
  return [...schedules, schedule];
}

function RunScheduleList({
  schedules,
  ticks,
}: {
  schedules: RunSchedule[];
  ticks: RunScheduleTick[];
}) {
  if (!schedules.length) {
    return <p className="empty-state">No hay schedules configurados.</p>;
  }

  const ticksBySchedule = new Map<number, RunScheduleTick[]>();
  for (const tick of ticks) {
    const current = ticksBySchedule.get(tick.schedule_id) || [];
    current.push(tick);
    ticksBySchedule.set(tick.schedule_id, current);
  }

  return (
    <ul className="resource-list">
      {schedules.map((schedule) => {
        const latestTick = ticksBySchedule.get(schedule.id)?.[0];
        return (
          <li key={schedule.id}>
            <div className="admin-resource-row">
              <div>
                <strong>{schedule.display_name}</strong>
                <p>
                  scenario {schedule.scenario_id} | variant{" "}
                  {schedule.case_input_variant_id} | {schedule.cadence} | next{" "}
                  {schedule.next_run_at}
                </p>
                <p>
                  rango {schedule.range_start} - {schedule.range_end}
                </p>
                {latestTick ? (
                  <p>
                    ultimo tick {latestTick.status}
                    {latestTick.run_id ? ` | run ${latestTick.run_id}` : ""}
                    {latestTick.error_message
                      ? ` | ${latestTick.error_message}`
                      : ""}
                  </p>
                ) : null}
              </div>
              <span className="status-pill">
                {schedule.is_active ? "active" : "inactive"}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function RunSchedulesPanel() {
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const schedules = useQuery({
    queryKey: runSchedulesQueryKey,
    queryFn: ({ signal }) => listRunSchedules(signal),
    retry: false,
  });
  const createMutation = useMutation({
    mutationFn: createRunSchedule,
    onSuccess: (schedule) => {
      setError("");
      setStatus(`${schedule.display_name} creado.`);
      queryClient.setQueryData<{
        schedules: RunSchedule[];
        ticks: RunScheduleTick[];
      }>(runSchedulesQueryKey, (current) => ({
        schedules: appendSchedule(current?.schedules, schedule),
        ticks: current?.ticks || [],
      }));
      void queryClient.invalidateQueries({ queryKey: runSchedulesQueryKey });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });
  const runDueMutation = useMutation({
    mutationFn: runDueSchedules,
    onSuccess: (report) => {
      setError("");
      setStatus(`${report.due_count} schedule(s) evaluados.`);
      void queryClient.invalidateQueries({ queryKey: runSchedulesQueryKey });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload: RunScheduleCreatePayload = {
      scenario_id: Number(form.get("scenario_id") || 0),
      case_input_variant_id: Number(form.get("case_input_variant_id") || 0),
      display_name: String(form.get("display_name") || ""),
      range_start: String(form.get("range_start") || ""),
      range_end: String(form.get("range_end") || ""),
      cadence: String(form.get("cadence") || "daily"),
      next_run_at: String(form.get("next_run_at") || ""),
    };
    createMutation.mutate(payload, {
      onSuccess: () => formElement.reset(),
    });
  }

  return (
    <section className="workspace-section" aria-labelledby="admin-schedules">
      <h2 id="admin-schedules">Schedules</h2>
      {error ? <p role="alert">{error}</p> : null}
      {status ? <p className="inline-status">{status}</p> : null}
      {schedules.isPending ? (
        <p role="status">Cargando schedules</p>
      ) : schedules.isError ? (
        <p role="alert">{errorMessage(schedules.error)}</p>
      ) : (
        <RunScheduleList
          schedules={schedules.data.schedules}
          ticks={schedules.data.ticks}
        />
      )}
      <div className="action-row">
        <button
          type="button"
          className="secondary-action"
          disabled={runDueMutation.isPending}
          onClick={() => runDueMutation.mutate({})}
        >
          Ejecutar vencidos
        </button>
        <button
          type="button"
          className="secondary-action"
          onClick={() => void schedules.refetch()}
        >
          Refrescar
        </button>
      </div>
      <form className="workspace-form nested-form" onSubmit={submit}>
        <h3>Nuevo schedule</h3>
        <label htmlFor="schedule-name">Nombre schedule</label>
        <input id="schedule-name" name="display_name" required />
        <label htmlFor="schedule-scenario">Scenario ID</label>
        <input
          id="schedule-scenario"
          name="scenario_id"
          type="number"
          min="1"
          required
        />
        <label htmlFor="schedule-variant">Variant ID</label>
        <input
          id="schedule-variant"
          name="case_input_variant_id"
          type="number"
          min="1"
          required
        />
        <label htmlFor="schedule-range-start">Rango inicio</label>
        <input id="schedule-range-start" name="range_start" required />
        <label htmlFor="schedule-range-end">Rango termino</label>
        <input id="schedule-range-end" name="range_end" required />
        <label htmlFor="schedule-cadence">Cadencia</label>
        <select id="schedule-cadence" name="cadence" defaultValue="daily">
          <option value="hourly">hourly</option>
          <option value="daily">daily</option>
          <option value="weekly">weekly</option>
        </select>
        <label htmlFor="schedule-next-run">Proxima ejecucion</label>
        <input id="schedule-next-run" name="next_run_at" required />
        <button type="submit" disabled={createMutation.isPending}>
          Crear schedule
        </button>
      </form>
    </section>
  );
}

function CreateUserForm() {
  const queryClient = useQueryClient();
  const emailRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const mutation = useMutation({
    mutationFn: createAdminUser,
    onSuccess: (created) => {
      setError("");
      setStatus(`${created.email} creado.`);
      queryClient.setQueryData<AdminUser[]>(adminUsersQueryKey, (users) =>
        appendUser(users, created),
      );
      void queryClient.invalidateQueries({ queryKey: adminUsersQueryKey });
      emailRef.current?.focus();
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload: UserCreatePayload = {
      email: String(form.get("email") || ""),
      display_name: String(form.get("display_name") || ""),
      password: String(form.get("password") || ""),
      role: String(form.get("role") || ""),
    };
    mutation.mutate(payload, {
      onSuccess: () => formElement.reset(),
    });
  }

  return (
    <form className="workspace-form" onSubmit={submit}>
      <h2>Nuevo usuario</h2>
      {error ? <p role="alert">{error}</p> : null}
      {status ? <p className="inline-status">{status}</p> : null}
      <label htmlFor="admin-user-email">Email</label>
      <input
        id="admin-user-email"
        ref={emailRef}
        name="email"
        type="email"
        autoComplete="username"
        required
      />
      <label htmlFor="admin-user-name">Nombre</label>
      <input
        id="admin-user-name"
        name="display_name"
        type="text"
        autoComplete="name"
        required
      />
      <label htmlFor="admin-user-password">Password</label>
      <input
        id="admin-user-password"
        name="password"
        type="password"
        autoComplete="new-password"
        required
      />
      <label htmlFor="admin-user-role">Rol</label>
      <select id="admin-user-role" name="role" defaultValue="analyst" required>
        <option value="analyst">analyst</option>
        <option value="client">client</option>
        <option value="admin">admin</option>
      </select>
      <button type="submit" disabled={mutation.isPending}>
        Crear usuario
      </button>
    </form>
  );
}

function DeactivateUserControl({
  user,
  onDeactivated,
}: {
  user: AdminUser;
  onDeactivated: (user: AdminUser) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () => deactivateAdminUser(user.id),
    onSuccess: (updated) => {
      setConfirming(false);
      setError("");
      onDeactivated(updated);
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  if (!user.is_active) return <span className="status-pill">deactivated</span>;

  if (!confirming) {
    return (
      <button
        type="button"
        className="danger-button"
        onClick={() => setConfirming(true)}
      >
        Desactivar {user.email}
      </button>
    );
  }

  return (
    <div className="remove-confirmation">
      <p>Confirma desactivar {user.email}</p>
      {error ? <p role="alert">{error}</p> : null}
      <button
        type="button"
        className="danger-button"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Confirmar desactivar {user.email}
      </button>
      <button
        type="button"
        className="secondary-action"
        onClick={() => {
          setConfirming(false);
          setError("");
        }}
      >
        Cancelar
      </button>
    </div>
  );
}

function AdminUserList({
  users,
  onDeactivated,
}: {
  users: AdminUser[];
  onDeactivated: (user: AdminUser) => void;
}) {
  if (!users.length) {
    return <p className="empty-state">No hay usuarios registrados.</p>;
  }

  return (
    <ul className="resource-list admin-user-list">
      {users.map((user) => (
        <li key={user.id}>
          <div className="admin-resource-row">
            <div>
              <strong>{user.email}</strong>
              <p>
                {user.display_name || "Sin nombre"} | {user.role} |{" "}
                {user.is_active ? "active" : "deactivated"}
              </p>
            </div>
            <DeactivateUserControl user={user} onDeactivated={onDeactivated} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function AdminUsersView() {
  const queryClient = useQueryClient();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [deactivationStatus, setDeactivationStatus] = useState("");
  const users = useQuery({
    queryKey: adminUsersQueryKey,
    queryFn: ({ signal }) => listAdminUsers(signal),
    retry: false,
  });

  useEffect(() => {
    if (deactivationStatus) statusRef.current?.focus();
  }, [deactivationStatus]);

  function acceptDeactivated(user: AdminUser) {
    queryClient.setQueryData<AdminUser[]>(adminUsersQueryKey, (current) =>
      replaceUser(current, user),
    );
    void queryClient.invalidateQueries({ queryKey: adminUsersQueryKey });
    setDeactivationStatus(`${user.email} desactivado.`);
  }

  if (users.isPending) {
    return <p role="status">Cargando usuarios</p>;
  }
  if (users.isError) {
    return (
      <section className="content-panel">
        <h1>No se pudo cargar</h1>
        <p>{errorMessage(users.error)}</p>
        <button type="button" onClick={() => void users.refetch()}>
          Reintentar
        </button>
      </section>
    );
  }

  return (
    <section className="workspace-view">
      <header className="workspace-heading">
        <p className="eyebrow">Admin</p>
        <h1>Administracion</h1>
      </header>
      <div className="workspace-grid">
        <section className="workspace-section" aria-labelledby="admin-users">
          <h2 id="admin-users">Cuentas locales</h2>
          {deactivationStatus ? (
            <p
              ref={statusRef}
              className="inline-status"
              tabIndex={-1}
              aria-live="polite"
            >
              {deactivationStatus}
            </p>
          ) : null}
          <AdminUserList users={users.data} onDeactivated={acceptDeactivated} />
        </section>
        <CreateUserForm />
        <RunSchedulesPanel />
      </div>
    </section>
  );
}

function RemoveProjectAccessControl({
  assignment,
  projectId,
  projectName,
  onRemoved,
}: {
  assignment: ProjectClientAccess;
  projectId: number;
  projectName: string;
  onRemoved: (assignment: ProjectClientAccess) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () => removeProjectClientAccess(projectId, assignment.user_id),
    onSuccess: () => {
      setConfirming(false);
      setError("");
      onRemoved(assignment);
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  if (!confirming) {
    return (
      <button
        type="button"
        className="danger-button"
        onClick={() => setConfirming(true)}
      >
        Quitar {assignment.email}
      </button>
    );
  }

  return (
    <div className="remove-confirmation">
      <p>Confirma quitar {assignment.email}</p>
      <p className="source-note">
        Esto revoca acceso a {projectName} de inmediato.
      </p>
      {error ? <p role="alert">{error}</p> : null}
      <button
        type="button"
        className="danger-button"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Confirmar quitar {assignment.email}
      </button>
      <button
        type="button"
        className="secondary-action"
        onClick={() => {
          setConfirming(false);
          setError("");
        }}
      >
        Cancelar
      </button>
    </div>
  );
}

function AssignmentList({
  assignments,
  projectId,
  projectName,
  onRemoved,
}: {
  assignments: ProjectClientAccess[];
  projectId: number;
  projectName: string;
  onRemoved: (assignment: ProjectClientAccess) => void;
}) {
  if (!assignments.length) {
    return <p className="empty-state">No hay clientes asignados.</p>;
  }

  return (
    <ul className="resource-list">
      {assignments.map((assignment) => (
        <li key={assignment.user_id}>
          <div className="admin-resource-row">
            <div>
              <strong>{assignment.email}</strong>
              <p>
                {assignment.display_name || "Sin nombre"} |{" "}
                {assignment.is_active ? "active" : "deactivated"} | assigned by{" "}
                {assignment.assigned_by}
              </p>
            </div>
            <RemoveProjectAccessControl
              assignment={assignment}
              projectId={projectId}
              projectName={projectName}
              onRemoved={onRemoved}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ProjectClientAccessSection({
  projectId,
  projectName,
}: {
  projectId: number;
  projectName: string;
}) {
  const queryClient = useQueryClient();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const users = useQuery({
    queryKey: adminUsersQueryKey,
    queryFn: ({ signal }) => listAdminUsers(signal),
    retry: false,
  });
  const access = useQuery({
    queryKey: projectClientAccessQueryKey(projectId),
    queryFn: ({ signal }) => listProjectClientAccess(projectId, signal),
    retry: false,
  });
  const assignedIds = useMemo(
    () => new Set((access.data || []).map((assignment) => assignment.user_id)),
    [access.data],
  );
  const eligibleClients = useMemo(
    () =>
      (users.data || []).filter(
        (user) =>
          user.role === "client" && user.is_active && !assignedIds.has(user.id),
      ),
    [assignedIds, users.data],
  );
  const selectedClientAvailable = eligibleClients.some(
    (client) => String(client.id) === selectedUserId,
  );
  const effectiveSelectedUserId = selectedClientAvailable
    ? selectedUserId
    : eligibleClients[0]
      ? String(eligibleClients[0].id)
      : "";
  const assignMutation = useMutation({
    mutationFn: (userId: number) =>
      assignProjectClientAccess(projectId, userId),
    onSuccess: (assignment) => {
      setError("");
      setStatus(`${assignment.email} asignado a ${projectName}.`);
      queryClient.setQueryData<ProjectClientAccess[]>(
        projectClientAccessQueryKey(projectId),
        (assignments) => appendAssignment(assignments, assignment),
      );
      void queryClient.invalidateQueries({
        queryKey: projectClientAccessQueryKey(projectId),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  useEffect(() => {
    if (status) statusRef.current?.focus();
  }, [status]);

  function removeAccepted(assignment: ProjectClientAccess) {
    queryClient.setQueryData<ProjectClientAccess[]>(
      projectClientAccessQueryKey(projectId),
      (assignments) => removeAssignment(assignments, assignment.user_id),
    );
    void queryClient.invalidateQueries({
      queryKey: projectClientAccessQueryKey(projectId),
    });
    setError("");
    setStatus(`${assignment.email} sin acceso a ${projectName}.`);
  }

  if (users.isPending || access.isPending) {
    return (
      <section className="workspace-section" aria-labelledby="project-access">
        <h2 id="project-access">Acceso cliente</h2>
        <p role="status">Cargando acceso cliente</p>
      </section>
    );
  }
  if (users.isError || access.isError) {
    return (
      <section className="workspace-section" aria-labelledby="project-access">
        <h2 id="project-access">Acceso cliente</h2>
        <p role="alert">{errorMessage(users.error || access.error)}</p>
      </section>
    );
  }

  return (
    <section className="workspace-section" aria-labelledby="project-access">
      <h2 id="project-access">Acceso cliente</h2>
      {status ? (
        <p
          ref={statusRef}
          className="inline-status"
          tabIndex={-1}
          aria-live="polite"
        >
          {status}
        </p>
      ) : null}
      <AssignmentList
        assignments={access.data}
        projectId={projectId}
        projectName={projectName}
        onRemoved={removeAccepted}
      />
      <form
        className="workspace-form nested-form"
        onSubmit={(event) => {
          event.preventDefault();
          setError("");
          setStatus("");
          if (effectiveSelectedUserId)
            assignMutation.mutate(Number(effectiveSelectedUserId));
        }}
      >
        <h3>Asignar cliente</h3>
        {error ? <p role="alert">{error}</p> : null}
        <label htmlFor="eligible-client">Cliente elegible</label>
        <select
          id="eligible-client"
          value={effectiveSelectedUserId}
          disabled={!eligibleClients.length}
          onChange={(event) => setSelectedUserId(event.target.value)}
        >
          {eligibleClients.length ? (
            eligibleClients.map((client) => (
              <option key={client.id} value={client.id}>
                {client.email}
              </option>
            ))
          ) : (
            <option value="">Sin clientes elegibles</option>
          )}
        </select>
        <button
          type="submit"
          disabled={!effectiveSelectedUserId || assignMutation.isPending}
        >
          Asignar cliente
        </button>
      </form>
    </section>
  );
}
