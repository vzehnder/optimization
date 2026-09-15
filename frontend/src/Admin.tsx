import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  ApiError,
  createAdminUser,
  createRunSchedule,
  deactivateAdminUser,
  listAdminUsers,
  listProjectExternalAccess,
  listRunSchedules,
  revokeProjectExternalAccess,
  runDueSchedules,
  setProjectExternalAccess,
  type AdminUser,
  type ExternalProjectAccess,
  type RunSchedule,
  type RunScheduleCreatePayload,
  type RunScheduleTick,
  type UserCreatePayload,
} from "./api/client";

const adminUsersQueryKey = ["admin-users"] as const;
const runSchedulesQueryKey = ["run-schedules"] as const;
const projectExternalAccessQueryKey = (projectId: number) =>
  ["project-external-access", projectId] as const;
const cadenceLabels: Record<string, string> = {
  hourly: "Cada hora",
  daily: "Diaria",
  weekly: "Semanal",
};
const tickLabels: Record<string, string> = {
  queued: "En cola",
  failed: "Fallido",
  pending: "Pendiente",
};
const userRoles: UserCreatePayload["role"][] = ["admin", "analyst", "external"];
const roleLabels = {
  admin: "Administrador",
  analyst: "Analista",
  external: "Usuario externo",
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "No se pudo completar la accion.";
}

function isUserRole(value: string): value is UserCreatePayload["role"] {
  return userRoles.includes(value as UserCreatePayload["role"]);
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

function replaceAssignment(
  assignments: ExternalProjectAccess[] | undefined,
  assignment: ExternalProjectAccess,
) {
  if (!assignments) return [assignment];
  if (
    !assignments.some((candidate) => candidate.user_id === assignment.user_id)
  )
    return [...assignments, assignment];
  return assignments.map((candidate) =>
    candidate.user_id === assignment.user_id ? assignment : candidate,
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
    return <p className="empty-state">No hay programaciones configuradas.</p>;
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
        const rangeRule =
          schedule.range_mode === "rolling"
            ? `Horizonte móvil | desplazamiento ${schedule.rolling_start_offset_hours ?? 0} h | duración ${schedule.rolling_duration_hours ?? 0} h`
            : "Período fijo";
        return (
          <li key={schedule.id}>
            <div className="admin-resource-row">
              <div>
                <strong>{schedule.display_name}</strong>
                <p>
                  Escenario {schedule.scenario_id} | Variante{" "}
                  {schedule.case_input_variant_id} |{" "}
                  {cadenceLabels[schedule.cadence] || schedule.cadence} |
                  Próxima ejecución {schedule.next_run_at}
                </p>
                <p>
                  Período {schedule.range_start} - {schedule.range_end}
                </p>
                <p>{rangeRule}</p>
                {latestTick ? (
                  <p>
                    Último intento{" "}
                    {tickLabels[latestTick.status] || latestTick.status}
                    {latestTick.run_id
                      ? ` | ejecución ${latestTick.run_id}`
                      : ""}
                    {latestTick.error_message
                      ? ` | ${latestTick.error_message}`
                      : ""}
                  </p>
                ) : null}
                {ticksBySchedule.get(schedule.id)?.length ? (
                  <ul aria-label={`Historial ${schedule.display_name}`}>
                    {ticksBySchedule.get(schedule.id)?.map((tick) => (
                      <li key={tick.id}>
                        Intento {tick.id}{" "}
                        {tickLabels[tick.status] || tick.status} | período{" "}
                        {tick.range_start} - {tick.range_end}
                        {tick.run_id ? ` | ejecución ${tick.run_id}` : ""}
                        {tick.error_message ? ` | ${tick.error_message}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <span className="status-pill">
                {schedule.is_active ? "Activa" : "Inactiva"}
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
  const formRef = useRef<HTMLFormElement>(null);
  const [errorField, setErrorField] = useState("");
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
      setErrorField("");
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
    onError: (mutationError) => {
      const message = errorMessage(mutationError);
      for (const [field, label] of [
        ["next_run_at", "Próxima ejecución"],
        ["range_start", "Inicio del período"],
        ["range_end", "Fin del período"],
      ]) {
        const missingOffset =
          message === `${field} must include a timezone offset`;
        if (missingOffset || message === `${field} must be ISO-8601`) {
          setError(
            missingOffset
              ? `${label} debe incluir un offset horario, por ejemplo -03:00.`
              : `${label} debe ser una fecha ISO-8601 válida.`,
          );
          setErrorField(field);
          (
            formRef.current?.elements.namedItem(
              field,
            ) as HTMLInputElement | null
          )?.focus();
          return;
        }
      }
      setError(message);
    },
  });
  const runDueMutation = useMutation({
    mutationFn: runDueSchedules,
    onSuccess: (report) => {
      setError("");
      setStatus(`${report.due_count} programación(es) evaluadas.`);
      void queryClient.invalidateQueries({ queryKey: runSchedulesQueryKey });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setErrorField("");
    setStatus("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload: RunScheduleCreatePayload = {
      scenario_id: Number(form.get("scenario_id") || 0),
      case_input_variant_id: Number(form.get("case_input_variant_id") || 0),
      display_name: String(form.get("display_name") || ""),
      range_start: String(form.get("range_start") || ""),
      range_end: String(form.get("range_end") || ""),
      range_mode: String(form.get("range_mode") || "fixed"),
      rolling_start_offset_hours:
        form.get("rolling_start_offset_hours") === ""
          ? null
          : Number(form.get("rolling_start_offset_hours") || 0),
      rolling_duration_hours:
        form.get("rolling_duration_hours") === ""
          ? null
          : Number(form.get("rolling_duration_hours") || 0),
      cadence: String(form.get("cadence") || "daily"),
      next_run_at: String(form.get("next_run_at") || ""),
    };
    createMutation.mutate(payload, {
      onSuccess: () => formElement.reset(),
    });
  }

  return (
    <section className="workspace-section" aria-labelledby="admin-schedules">
      <h2 id="admin-schedules">Programación de ejecuciones</h2>
      <p>
        Define el escenario, la variante y el período. Ejecutar vencidos evalúa
        las programaciones activas cuya fecha ya llegó; cada ejecución conserva
        la validación y el registro del servidor.
      </p>
      {error ? (
        <p role="alert" id="schedule-error">
          {error}
        </p>
      ) : null}
      {status ? (
        <p className="inline-status" role="status">
          {status}
        </p>
      ) : null}
      {schedules.isPending ? (
        <p role="status">Cargando programación</p>
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
      <form
        ref={formRef}
        className="workspace-form nested-form"
        onSubmit={submit}
      >
        <h3>Nueva programación</h3>
        <label htmlFor="schedule-name">Nombre de la programación</label>
        <input id="schedule-name" name="display_name" required />
        <label htmlFor="schedule-scenario">Escenario (ID)</label>
        <input
          id="schedule-scenario"
          name="scenario_id"
          type="number"
          min="1"
          required
        />
        <label htmlFor="schedule-variant">Variante (ID)</label>
        <input
          id="schedule-variant"
          name="case_input_variant_id"
          type="number"
          min="1"
          required
        />
        <label htmlFor="schedule-range-start">Inicio del período</label>
        <input
          id="schedule-range-start"
          name="range_start"
          required
          aria-invalid={errorField === "range_start" || undefined}
          aria-describedby={
            errorField === "range_start"
              ? "schedule-error"
              : "schedule-period-help"
          }
        />
        <label htmlFor="schedule-range-end">Fin del período</label>
        <input
          id="schedule-range-end"
          name="range_end"
          required
          aria-invalid={errorField === "range_end" || undefined}
          aria-describedby={
            errorField === "range_end"
              ? "schedule-error"
              : "schedule-period-help"
          }
        />
        <p id="schedule-period-help">
          Inicio incluido y fin excluido. Usa fechas ISO con offset explícito,
          por ejemplo 2026-09-15T00:00:00-03:00.
        </p>
        <label htmlFor="schedule-range-mode">Modo de rango</label>
        <select id="schedule-range-mode" name="range_mode" defaultValue="fixed">
          <option value="fixed">Fijo</option>
          <option value="rolling">Horizonte móvil</option>
        </select>
        <p>
          Fijo repite el mismo período. Horizonte móvil calcula el inicio desde
          la fecha programada más el desplazamiento, y el fin según la duración
          indicada.
        </p>
        <label htmlFor="schedule-rolling-offset">
          Desplazamiento del inicio (horas)
        </label>
        <input
          id="schedule-rolling-offset"
          name="rolling_start_offset_hours"
          type="number"
          step="0.25"
        />
        <label htmlFor="schedule-rolling-duration">
          Duración del horizonte (horas)
        </label>
        <input
          id="schedule-rolling-duration"
          name="rolling_duration_hours"
          type="number"
          min="0.25"
          step="0.25"
        />
        <label htmlFor="schedule-cadence">Frecuencia</label>
        <select id="schedule-cadence" name="cadence" defaultValue="daily">
          <option value="hourly">Cada hora</option>
          <option value="daily">Diaria</option>
          <option value="weekly">Semanal</option>
        </select>
        <label htmlFor="schedule-next-run">Próxima ejecución</label>
        <input
          id="schedule-next-run"
          name="next_run_at"
          required
          aria-invalid={errorField === "next_run_at" || undefined}
          aria-describedby={
            errorField === "next_run_at"
              ? "schedule-error"
              : "schedule-period-help"
          }
        />
        <button type="submit" disabled={createMutation.isPending}>
          Crear programación
        </button>
      </form>
    </section>
  );
}

function CreateUserForm() {
  const queryClient = useQueryClient();
  const emailRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [emailError, setEmailError] = useState(false);
  const [status, setStatus] = useState("");
  const mutation = useMutation({
    mutationFn: createAdminUser,
    onSuccess: (created) => {
      setError("");
      setEmailError(false);
      setStatus(`${created.email} creado.`);
      queryClient.setQueryData<AdminUser[]>(adminUsersQueryKey, (users) =>
        appendUser(users, created),
      );
      void queryClient.invalidateQueries({ queryKey: adminUsersQueryKey });
      emailRef.current?.focus();
    },
    onError: (mutationError) => {
      const message = errorMessage(mutationError);
      const emailMessage =
        message === "email already exists"
          ? "Ya existe un usuario con este email."
          : message === "valid email is required"
            ? "Introduce un email válido."
            : "";
      setError(emailMessage || message);
      setEmailError(!!emailMessage);
      if (emailMessage) emailRef.current?.focus();
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setEmailError(false);
    setStatus("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const role = String(form.get("role") || "");
    if (!isUserRole(role)) {
      setError("Rol de usuario no soportado.");
      return;
    }
    const payload: UserCreatePayload = {
      email: String(form.get("email") || ""),
      display_name: String(form.get("display_name") || ""),
      password: String(form.get("password") || ""),
      role,
    };
    mutation.mutate(payload, {
      onSuccess: () => formElement.reset(),
    });
  }

  return (
    <form className="workspace-form" onSubmit={submit}>
      <h2>Nuevo usuario</h2>
      {error ? (
        <p role="alert" id="admin-user-error">
          {error}
        </p>
      ) : null}
      {status ? <p className="inline-status">{status}</p> : null}
      <label htmlFor="admin-user-email">Email</label>
      <input
        id="admin-user-email"
        ref={emailRef}
        name="email"
        type="email"
        aria-invalid={emailError || undefined}
        aria-describedby={emailError ? "admin-user-error" : undefined}
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
      <label htmlFor="admin-user-password">Contraseña</label>
      <input
        id="admin-user-password"
        name="password"
        type="password"
        autoComplete="new-password"
        required
      />
      <label htmlFor="admin-user-role">Rol</label>
      <select id="admin-user-role" name="role" defaultValue="analyst" required>
        <option value="analyst">Analista</option>
        <option value="external">Usuario externo</option>
        <option value="admin">Administrador</option>
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

  if (!user.is_active) return <span className="status-pill">Desactivado</span>;

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
      <p>
        Perderá el acceso a todos sus proyectos en su siguiente solicitud.
        Desactivar la cuenta no cancela ejecuciones ya iniciadas.
      </p>
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
        disabled={mutation.isPending}
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
                {user.display_name || "Sin nombre"} | {roleLabels[user.role]} |{" "}
                {user.is_active ? "Activo" : "Desactivado"}
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
  const [searchParams] = useSearchParams();
  const section =
    searchParams.get("section") === "schedules" ? "schedules" : "users";
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

  return (
    <section className="workspace-view admin-view">
      <header className="workspace-heading">
        <p className="eyebrow">Gestión del espacio de trabajo</p>
        <h1>Administración</h1>
      </header>
      <nav className="workspace-nav" aria-label="Secciones de administración">
        {[
          ["users", "Usuarios y accesos"],
          ["schedules", "Programación"],
        ].map(([key, label]) => {
          const params = new URLSearchParams(searchParams);
          params.set("section", key);
          return (
            <Link
              key={key}
              to={`?${params}`}
              aria-current={section === key ? "page" : undefined}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      <div hidden={section !== "users"}>
        <h2>Usuarios y accesos</h2>
        <p>
          Las cuentas definen la identidad. Los permisos de un usuario externo
          se conceden por separado en Accesos de cada proyecto.
        </p>
        <Link to="/projects">
          Elegir un proyecto para administrar sus accesos
        </Link>
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
            {users.isPending ? (
              <p role="status">Cargando usuarios</p>
            ) : users.isError ? (
              <div>
                <p role="alert">{errorMessage(users.error)}</p>
                <button type="button" onClick={() => void users.refetch()}>
                  Reintentar usuarios
                </button>
              </div>
            ) : (
              <AdminUserList
                users={users.data}
                onDeactivated={acceptDeactivated}
              />
            )}
          </section>
          <CreateUserForm />
        </div>
      </div>
      <div hidden={section !== "schedules"}>
        <RunSchedulesPanel />
      </div>
    </section>
  );
}

function ExternalCapabilityEditor({
  assignment,
  projectId,
  projectName,
  onChanged,
}: {
  assignment: ExternalProjectAccess;
  projectId: number;
  projectName: string;
  onChanged: (assignment: ExternalProjectAccess) => void;
}) {
  const reviewRef = useRef<HTMLHeadingElement>(null);
  const permissionsRef = useRef<HTMLInputElement>(null);
  const returnToPermissions = useRef(false);
  const [portalView, setPortalView] = useState(assignment.portal_view);
  const [operate, setOperate] = useState(assignment.operate);
  const [reviewing, setReviewing] = useState(false);
  const [confirmingRemoval, setConfirmingRemoval] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (reviewing || confirmingRemoval) reviewRef.current?.focus();
    else if (returnToPermissions.current) {
      permissionsRef.current?.focus();
      returnToPermissions.current = false;
    }
  }, [reviewing, confirmingRemoval]);
  const saveMutation = useMutation({
    mutationFn: () =>
      setProjectExternalAccess(projectId, assignment.user_id, {
        portal_view: portalView,
        operate,
      }),
    onSuccess: (updated) => {
      setError("");
      setReviewing(false);
      onChanged(updated);
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });
  const removeMutation = useMutation({
    mutationFn: () =>
      revokeProjectExternalAccess(projectId, assignment.user_id),
    onSuccess: (revoked) => {
      setError("");
      setConfirmingRemoval(false);
      onChanged(revoked);
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  return (
    <div>
      <div className="admin-resource-row">
        <div>
          <strong>{assignment.email}</strong>
          <p>
            {assignment.display_name || "Sin nombre"} |{" "}
            {assignment.is_active ? "Activo" : "Desactivado"} | actualizado por{" "}
            {assignment.updated_by}
          </p>
        </div>
        <fieldset
          disabled={
            reviewing ||
            confirmingRemoval ||
            saveMutation.isPending ||
            removeMutation.isPending
          }
        >
          <legend>Permisos en {projectName}</legend>
          <label>
            <input
              type="checkbox"
              checked={portalView}
              ref={permissionsRef}
              aria-label={`Ver informes para ${assignment.email}`}
              onChange={(event) => setPortalView(event.target.checked)}
            />
            Ver informes
          </label>
          <label>
            <input
              type="checkbox"
              checked={operate}
              aria-label={`Operar consolas para ${assignment.email}`}
              onChange={(event) => setOperate(event.target.checked)}
            />
            Operar consolas
          </label>
        </fieldset>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {!reviewing ? (
        <button
          type="button"
          disabled={
            confirmingRemoval ||
            saveMutation.isPending ||
            removeMutation.isPending ||
            (portalView === assignment.portal_view &&
              operate === assignment.operate)
          }
          onClick={() => {
            setError("");
            setReviewing(true);
          }}
        >
          Guardar capacidades de {assignment.email}
        </button>
      ) : (
        <section
          className="remove-confirmation"
          aria-label={`Revisar cambios de ${assignment.email}`}
        >
          <h3 ref={reviewRef} tabIndex={-1}>
            Revisar cambios de {assignment.email}
          </h3>
          <p>Proyecto: {projectName}.</p>
          <p>
            Ver informes: {assignment.portal_view ? "Permitido" : "Sin acceso"}{" "}
            → {portalView ? "Permitido" : "Sin acceso"}.
          </p>
          <p>
            Operar consolas: {assignment.operate ? "Permitido" : "Sin acceso"} →{" "}
            {operate ? "Permitido" : "Sin acceso"}.
          </p>
          {(assignment.portal_view && !portalView) ||
          (assignment.operate && !operate) ? (
            <p>
              Los permisos retirados dejarán de estar disponibles en la
              siguiente solicitud. Este cambio no cancela ejecuciones ya
              iniciadas.
            </p>
          ) : null}
          <button
            type="button"
            disabled={saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
          >
            Confirmar cambios
          </button>
          <button
            type="button"
            className="secondary-action"
            disabled={saveMutation.isPending}
            onClick={() => {
              returnToPermissions.current = true;
              setReviewing(false);
            }}
          >
            Volver a editar permisos
          </button>
        </section>
      )}
      {!confirmingRemoval ? (
        <button
          type="button"
          className="danger-button"
          disabled={
            reviewing ||
            saveMutation.isPending ||
            removeMutation.isPending ||
            (!assignment.portal_view && !assignment.operate)
          }
          onClick={() => {
            setError("");
            setConfirmingRemoval(true);
          }}
        >
          Revocar {assignment.email}
        </button>
      ) : (
        <div className="remove-confirmation">
          <h3 ref={reviewRef} tabIndex={-1}>
            Confirma revocar a {assignment.email} de {projectName}
          </h3>
          <p>
            Se retirarán Ver informes y Operar consolas en este proyecto. Los
            demás proyectos conservan sus permisos. La revocación se aplica en
            la siguiente solicitud y no cancela ejecuciones ya iniciadas.
          </p>
          <button
            type="button"
            className="danger-button"
            disabled={removeMutation.isPending}
            onClick={() => removeMutation.mutate()}
          >
            Confirmar revocar {assignment.email}
          </button>
          <button
            type="button"
            className="secondary-action"
            disabled={removeMutation.isPending}
            onClick={() => {
              returnToPermissions.current = true;
              setConfirmingRemoval(false);
            }}
          >
            Cancelar
          </button>
        </div>
      )}
    </div>
  );
}

function AssignmentList({
  assignments,
  projectId,
  projectName,
  onChanged,
}: {
  assignments: ExternalProjectAccess[];
  projectId: number;
  projectName: string;
  onChanged: (assignment: ExternalProjectAccess) => void;
}) {
  if (!assignments.length) {
    return <p className="empty-state">No hay usuarios externos asignados.</p>;
  }

  return (
    <ul className="resource-list">
      {assignments.map((assignment) => (
        <li
          key={`${assignment.user_id}:${assignment.updated_at}:${assignment.portal_view}:${assignment.operate}`}
        >
          <ExternalCapabilityEditor
            assignment={assignment}
            projectId={projectId}
            projectName={projectName}
            onChanged={onChanged}
          />
        </li>
      ))}
    </ul>
  );
}

export function ProjectExternalAccessSection({
  projectId,
  projectName,
}: {
  projectId: number;
  projectName: string;
}) {
  const queryClient = useQueryClient();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const reviewRef = useRef<HTMLHeadingElement>(null);
  const userRef = useRef<HTMLSelectElement>(null);
  const returnToUser = useRef(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [grantPortalView, setGrantPortalView] = useState(false);
  const [grantOperate, setGrantOperate] = useState(false);
  const [grantReview, setGrantReview] = useState<{
    userId: number;
    email: string;
    portal_view: boolean;
    operate: boolean;
  } | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const users = useQuery({
    queryKey: adminUsersQueryKey,
    queryFn: ({ signal }) => listAdminUsers(signal),
    retry: false,
  });
  const access = useQuery({
    queryKey: projectExternalAccessQueryKey(projectId),
    queryFn: ({ signal }) => listProjectExternalAccess(projectId, signal),
    retry: false,
  });
  const assignedIds = useMemo(
    () => new Set((access.data || []).map((assignment) => assignment.user_id)),
    [access.data],
  );
  const eligibleExternalUsers = useMemo(
    () =>
      (users.data || []).filter(
        (user) =>
          user.role === "external" &&
          user.is_active &&
          !assignedIds.has(user.id),
      ),
    [assignedIds, users.data],
  );
  const selectedUserAvailable = eligibleExternalUsers.some(
    (user) => String(user.id) === selectedUserId,
  );
  const effectiveSelectedUserId = selectedUserAvailable
    ? selectedUserId
    : eligibleExternalUsers[0]
      ? String(eligibleExternalUsers[0].id)
      : "";
  const assignMutation = useMutation({
    mutationFn: (review: NonNullable<typeof grantReview>) =>
      setProjectExternalAccess(projectId, review.userId, {
        portal_view: review.portal_view,
        operate: review.operate,
      }),
    onSuccess: (assignment) => {
      setError("");
      setStatus(
        `Capacidades de ${assignment.email} otorgadas en ${projectName}.`,
      );
      setGrantPortalView(false);
      setGrantOperate(false);
      setGrantReview(null);
      queryClient.setQueryData<ExternalProjectAccess[]>(
        projectExternalAccessQueryKey(projectId),
        (assignments) => replaceAssignment(assignments, assignment),
      );
      void queryClient.invalidateQueries({
        queryKey: projectExternalAccessQueryKey(projectId),
      });
    },
    onError: (mutationError) => setError(errorMessage(mutationError)),
  });

  useEffect(() => {
    if (status) statusRef.current?.focus();
  }, [status]);

  useEffect(() => {
    if (grantReview) reviewRef.current?.focus();
    else if (returnToUser.current) {
      userRef.current?.focus();
      returnToUser.current = false;
    }
  }, [grantReview]);

  function changeAccepted(assignment: ExternalProjectAccess) {
    queryClient.setQueryData<ExternalProjectAccess[]>(
      projectExternalAccessQueryKey(projectId),
      (assignments) => replaceAssignment(assignments, assignment),
    );
    setError("");
    setStatus(`Capacidades de ${assignment.email} actualizadas.`);
  }

  if (users.isPending || access.isPending) {
    return (
      <section
        className="workspace-section external-access"
        aria-labelledby="project-access"
      >
        <h2 id="project-access">Capacidades externas</h2>
        <p role="status">Cargando capacidades externas</p>
      </section>
    );
  }
  if (users.isError || access.isError) {
    return (
      <section
        className="workspace-section external-access"
        aria-labelledby="project-access"
      >
        <h2 id="project-access">Capacidades externas</h2>
        <p role="alert">{errorMessage(users.error || access.error)}</p>
        <button
          type="button"
          onClick={() => {
            void users.refetch();
            void access.refetch();
          }}
        >
          Reintentar accesos
        </button>
      </section>
    );
  }

  return (
    <section
      className="workspace-section external-access"
      aria-labelledby="project-access"
    >
      <h2 id="project-access">Capacidades externas</h2>
      <p>
        Elige el acceso a {projectName} para cada usuario. Ver informes permite
        consultar publicaciones y descargar sus archivos autorizados. Operar
        consolas permite ajustar los datos habilitados y ejecutar las consolas
        de este proyecto.
      </p>
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
        onChanged={(assignment) => {
          changeAccepted(assignment);
          if (!assignment.portal_view && !assignment.operate) {
            setStatus(
              `Capacidades de ${assignment.email} revocadas en ${projectName}.`,
            );
          }
        }}
      />
      <form
        className="workspace-form nested-form"
        onSubmit={(event) => {
          event.preventDefault();
          setError("");
          setStatus("");
          const selected = eligibleExternalUsers.find(
            (user) => String(user.id) === effectiveSelectedUserId,
          );
          if (selected)
            setGrantReview({
              userId: selected.id,
              email: selected.email,
              portal_view: grantPortalView,
              operate: grantOperate,
            });
        }}
      >
        <h3>Otorgar capacidades</h3>
        {error ? <p role="alert">{error}</p> : null}
        <fieldset disabled={!!grantReview || assignMutation.isPending}>
          <legend>Nuevo acceso a {projectName}</legend>
          <label htmlFor="eligible-external-user">Usuario externo</label>
          <select
            id="eligible-external-user"
            ref={userRef}
            value={effectiveSelectedUserId}
            disabled={!eligibleExternalUsers.length}
            onChange={(event) => setSelectedUserId(event.target.value)}
          >
            {eligibleExternalUsers.length ? (
              eligibleExternalUsers.map((externalUser) => (
                <option key={externalUser.id} value={externalUser.id}>
                  {externalUser.email}
                </option>
              ))
            ) : (
              <option value="">Sin usuarios externos elegibles</option>
            )}
          </select>
          <label>
            <input
              type="checkbox"
              checked={grantPortalView}
              onChange={(event) => setGrantPortalView(event.target.checked)}
            />
            Ver informes
          </label>
          <label>
            <input
              type="checkbox"
              checked={grantOperate}
              onChange={(event) => setGrantOperate(event.target.checked)}
            />
            Operar consolas
          </label>
        </fieldset>
        {!grantReview ? (
          <button
            type="submit"
            disabled={
              !effectiveSelectedUserId ||
              (!grantPortalView && !grantOperate) ||
              assignMutation.isPending
            }
          >
            Revisar acceso
          </button>
        ) : (
          <section aria-label="Revisar acceso" className="remove-confirmation">
            <h3 ref={reviewRef} tabIndex={-1}>
              Revisar acceso
            </h3>
            <p>
              Usuario: {grantReview.email}. Proyecto: {projectName}.
            </p>
            <p>
              Ver informes:{" "}
              {grantReview.portal_view ? "Permitido" : "Sin acceso"}.
            </p>
            <p>
              Operar consolas:{" "}
              {grantReview.operate ? "Permitido" : "Sin acceso"}.
            </p>
            <button
              type="button"
              disabled={assignMutation.isPending}
              onClick={() => assignMutation.mutate(grantReview)}
            >
              Otorgar capacidades
            </button>
            <button
              type="button"
              className="secondary-action"
              disabled={assignMutation.isPending}
              onClick={() => {
                returnToUser.current = true;
                setGrantReview(null);
              }}
            >
              Volver a editar acceso
            </button>
          </section>
        )}
      </form>
    </section>
  );
}
