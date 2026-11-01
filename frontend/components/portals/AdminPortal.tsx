"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useAccount } from "@/components/AccountProvider";
import { ApplicationQueue } from "@/components/AccountPages";
import { useI18n } from "@/lib/i18n";
import type { AccountRole } from "@/lib/auth";
import { portalCopy } from "@/lib/portal-copy";
import { PortalIcon } from "./PortalIcon";
import { AdminDashboard } from "./AdminDashboard";
import {
  portalApi,
  replacePortalRecord,
  matchesAdminCourse,
  matchesAdminUser,
  type AdminDestination,
  type AdminCourseFilter,
  type AdminUser,
  type AdminCourse,
} from "@/lib/portal";
import {
  PortalShell,
  PortalError,
  PortalLoading,
  usePortalResource,
  usePortalWrite,
} from "./PortalShell";
export function AdminPortal() {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const [destination, setDestination] = useState<AdminDestination>({
    section: "overview",
  });
  const { section } = destination;
  const contentRef = useRef<HTMLDivElement>(null);
  const hasNavigated = useRef(false);
  const navigate = (next: AdminDestination) => {
    hasNavigated.current = true;
    setDestination(next);
  };
  useEffect(() => {
    if (hasNavigated.current) {
      contentRef.current?.focus({ preventScroll: true });
      contentRef.current?.scrollIntoView({ block: "start" });
    }
  }, [destination]);
  return (
    <PortalShell admin>
      <header className="portal-title">
        <h1>{c.admin}</h1>
      </header>
      <div className="portal-admin">
        <nav className="portal-section-nav" aria-label={c.admin}>
          {(
            [
              "overview",
              "applications",
              "users",
              "courses",
              "activity",
            ] as const
          ).map((key) => (
            <button
              key={key}
              type="button"
              aria-current={section === key ? "page" : undefined}
              onClick={() => navigate({ section: key })}
            >
              <PortalIcon name={key === "courses" ? "book" : key} />
              {c[key]}
            </button>
          ))}
        </nav>
        <div
          className="portal-admin-content"
          ref={contentRef}
          tabIndex={-1}
          role="region"
          aria-label={c[section]}
        >
          {section === "overview" ? (
            <AdminDashboard navigate={navigate} />
          ) : section === "applications" ? (
            <ApplicationQueue />
          ) : section === "users" ? (
            <AdminUsers
              key={destination.role ?? "all"}
              initialRole={destination.role}
            />
          ) : section === "courses" ? (
            <AdminCourses
              key={`${destination.courseFilter ?? "all"}:${destination.courseId ?? ""}`}
              initialFilter={destination.courseFilter}
              initialCourseId={destination.courseId}
            />
          ) : (
            <AdminActivity />
          )}
        </div>
      </div>
    </PortalShell>
  );
}
function AdminUsers({ initialRole }: { initialRole?: AccountRole }) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const { user } = useAccount();
  const resource = usePortalResource(portalApi.users);
  const [updated, setUpdated] = useState(false);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<AccountRole | "all">(
    initialRole ?? "all",
  );
  const visible =
    resource.data?.users.filter(
      (entry) =>
        matchesAdminUser(entry, roleFilter) &&
        `${entry.name} ${entry.email} ${entry.role}`
          .toLocaleLowerCase()
          .includes(search.toLocaleLowerCase()),
    ) ?? [];
  return (
    <section>
      <div className="portal-section-heading">
        <h2>{c.users}</h2>
        <button
          type="button"
          disabled={resource.loading}
          onClick={resource.reload}
        >
          {c.refresh}
        </button>
      </div>
      <p>{c.userHint}</p>
      <div className="portal-admin-filters">
        <label>
          {c.roleFilter}
          <select
            value={roleFilter}
            onChange={(event) =>
              setRoleFilter(event.target.value as AccountRole | "all")
            }
          >
            <option value="all">{c.all}</option>
            <option value="student">{c.student}</option>
            <option value="instructor">{c.instructor}</option>
            <option value="admin">{c.administrator}</option>
          </select>
        </label>
        {roleFilter !== "all" ? (
          <button type="button" onClick={() => setRoleFilter("all")}>
            {c.clearFilters}
          </button>
        ) : null}
      </div>
      <label className="portal-search">
        {c.search}
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <PortalError error={resource.error} retry={resource.reload} />
      {updated ? <p role="status">{c.updated}</p> : null}
      {resource.loading ? (
        <PortalLoading />
      ) : visible.length ? (
        <ul className="portal-operation-list">
          {visible.map((entry) => (
            <UserRow
              key={entry.id}
              entry={entry}
              self={entry.id === user?.id}
              accept={(user) => {
                resource.setData((current) =>
                  current
                    ? { users: replacePortalRecord(current.users, user) }
                    : current,
                );
                setUpdated(true);
              }}
            />
          ))}
        </ul>
      ) : (
        <p className="portal-empty">{c.empty}</p>
      )}
    </section>
  );
}
function UserRow({
  entry,
  self,
  accept,
}: {
  entry: AdminUser;
  self: boolean;
  accept: (user: AdminUser) => void;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const [role, setRole] = useState<AccountRole>(entry.role);
  const [action, setAction] = useState<"role" | "active" | null>(null);
  const write = usePortalWrite();
  const roles = {
    student: c.student,
    instructor: c.instructor,
    admin: c.administrator,
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void write.run(
      (signal) =>
        portalApi.user(
          entry.id,
          action === "role" ? { role } : { active: !entry.active },
          signal,
        ),
      ({ user }) => {
        setAction(null);
        accept(user);
      },
    );
  };
  return (
    <li className="portal-user-row">
      <div className="portal-row-summary">
        <div>
          <h3>{entry.name}</h3>
          <p>{entry.email}</p>
          <p className="portal-meta">
            {roles[entry.role]} · {statusText(entry.status, c)}
          </p>
        </div>
        <span
          className={`portal-status ${entry.active ? "portal-status--complete" : ""}`}
        >
          {entry.active ? c.enabled : c.disabled}
        </span>
      </div>
      {self ? (
        <p className="portal-meta">
          {c.self} · {c.selfHint}
        </p>
      ) : (
        <>
          <div className="portal-row-actions">
            <label>
              {c.role}
              <select
                disabled={write.busy}
                value={role}
                onChange={(event) => {
                  setRole(event.target.value as AccountRole);
                  setAction(null);
                }}
              >
                {(["student", "instructor", "admin"] as const).map((key) => (
                  <option key={key} value={key}>
                    {roles[key]}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={write.busy || role === entry.role}
              onClick={() => setAction("role")}
            >
              {c.changeRole}
            </button>
            <button
              type="button"
              disabled={write.busy}
              onClick={() => setAction("active")}
            >
              {entry.active ? c.disable : c.enable}
            </button>
          </div>
          {action ? (
            <form onSubmit={submit} className="portal-confirm">
              <p>
                {action === "role"
                  ? `${c.changeRole}: ${roles[entry.role]} → ${roles[role]}`
                  : entry.active
                    ? c.disable
                    : c.enable}{" "}
                · {entry.email}
              </p>
              <p>{c.userHint}</p>
              <div className="portal-row-actions">
                <button className="portal-button" disabled={write.busy}>
                  {write.busy ? c.saving : c.confirm}
                </button>
                <button
                  type="button"
                  disabled={write.busy}
                  onClick={() => setAction(null)}
                >
                  {c.cancel}
                </button>
              </div>
            </form>
          ) : null}
        </>
      )}
      <PortalError error={write.error} />
    </li>
  );
}
function AdminCourses({
  initialFilter,
  initialCourseId,
}: {
  initialFilter?: AdminCourseFilter;
  initialCourseId?: string;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const resource = usePortalResource(portalApi.courses);
  const [updated, setUpdated] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<AdminCourseFilter>(
    initialFilter ?? "all",
  );
  const [courseId, setCourseId] = useState(initialCourseId);
  const visible =
    resource.data?.courses.filter(
      (entry) =>
        matchesAdminCourse(entry, filter, courseId) &&
        `${entry.title} ${entry.courseCode} ${entry.ownerName}`
          .toLocaleLowerCase()
          .includes(search.toLocaleLowerCase()),
    ) ?? [];
  return (
    <section>
      <div className="portal-section-heading">
        <h2>{c.courses}</h2>
        <button
          type="button"
          disabled={resource.loading}
          onClick={resource.reload}
        >
          {c.refresh}
        </button>
      </div>
      <p>{c.courseHint}</p>
      <div className="portal-admin-filters">
        <label>
          {c.courseFilter}
          <select
            value={filter}
            onChange={(event) =>
              setFilter(event.target.value as AdminCourseFilter)
            }
          >
            <option value="all">{c.all}</option>
            <option value="published">{c.published}</option>
            <option value="unpublished">{c.unpublished}</option>
            <option value="suspended">{c.suspended}</option>
            <option value="enrolled">{c.enrolledCourses}</option>
          </select>
        </label>
        {courseId ? (
          <span className="portal-meta">
            {c.filteredCourse}:{" "}
            {resource.data?.courses.find((course) => course.id === courseId)
              ?.title ?? courseId}
          </span>
        ) : null}
        {filter !== "all" || courseId ? (
          <button
            type="button"
            onClick={() => {
              setFilter("all");
              setCourseId(undefined);
              setSearch("");
            }}
          >
            {c.clearFilters}
          </button>
        ) : null}
      </div>
      <label className="portal-search">
        {c.search}
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <PortalError error={resource.error} retry={resource.reload} />
      {updated ? <p role="status">{c.updated}</p> : null}
      {resource.loading ? (
        <PortalLoading />
      ) : visible.length ? (
        <ul className="portal-operation-list">
          {visible.map((entry) => (
            <CourseRow
              key={entry.id}
              entry={entry}
              accept={(course) => {
                resource.setData((current) =>
                  current
                    ? { courses: replacePortalRecord(current.courses, course) }
                    : current,
                );
                setUpdated(true);
              }}
            />
          ))}
        </ul>
      ) : (
        <p className="portal-empty">{c.empty}</p>
      )}
    </section>
  );
}
function CourseRow({
  entry,
  accept,
}: {
  entry: AdminCourse;
  accept: (course: AdminCourse) => void;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const [confirm, setConfirm] = useState(false);
  const [reason, setReason] = useState("");
  const write = usePortalWrite();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void write.run(
      (signal) =>
        portalApi.moderate(entry.id, entry.archived, reason.trim(), signal),
      ({ course }) => {
        setConfirm(false);
        accept(course);
      },
    );
  };
  return (
    <li className="portal-course-row">
      <div className="portal-row-summary">
        <div>
          <h3>{entry.title}</h3>
          <p>
            {entry.courseCode} · {c.owner}:{" "}
            {entry.ownerName?.trim() || c.notRecorded}
          </p>
          <p className="portal-meta">
            {statusText(entry.status, c)} · {entry.chapterCount} {c.chapters}
            {" · "}
            {c.enrollments}: {entry.enrollmentCount}
          </p>
        </div>
        <span className="portal-status">
          {entry.archived ? c.suspended : c.notSuspended}
        </span>
      </div>
      {entry.moderationReason ? (
        <p>
          {c.reason}: {entry.moderationReason}
        </p>
      ) : null}
      {confirm ? (
        <form onSubmit={submit} className="portal-confirm">
          {entry.archived ? (
            <p>
              {c.restore} · {entry.title}
            </p>
          ) : (
            <label>
              {c.reason}
              <textarea
                required
                maxLength={1000}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                aria-describedby={`moderation-${entry.id}`}
              />
              <span id={`moderation-${entry.id}`}>{c.reasonHint}</span>
            </label>
          )}
          <div className="portal-row-actions">
            <button
              className="portal-button"
              disabled={write.busy || (!entry.archived && !reason.trim())}
            >
              {write.busy ? c.saving : c.confirm}
            </button>
            <button
              type="button"
              disabled={write.busy}
              onClick={() => setConfirm(false)}
            >
              {c.cancel}
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          disabled={write.busy}
          onClick={() => setConfirm(true)}
        >
          {entry.archived ? c.restore : c.suspend}
        </button>
      )}
      <PortalError error={write.error} />
    </li>
  );
}
function AdminActivity() {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const resource = usePortalResource(portalApi.audit);
  const [search, setSearch] = useState("");
  const visible =
    resource.data?.events.filter((event) =>
      `${event.title} ${event.actor ?? ""} ${event.kind} ${event.status}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
    ) ?? [];
  return (
    <section>
      <div className="portal-section-heading">
        <h2>{c.activity}</h2>
        <button
          type="button"
          onClick={resource.reload}
          disabled={resource.loading}
        >
          {c.refresh}
        </button>
      </div>
      <p>{c.auditHint}</p>
      <label className="portal-search">
        {c.search}
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <PortalError error={resource.error} retry={resource.reload} />
      {resource.loading ? (
        <PortalLoading />
      ) : visible.length ? (
        <ul className="portal-operation-list">
          {visible.map((event) => (
            <li key={event.id}>
              <div className="portal-row-summary">
                <h3>{event.title}</h3>
                <span className="portal-status">
                  {statusText(event.status, c)}
                </span>
              </div>
              <p>
                {event.actor ?? c.unknown} ·{" "}
                {event.at
                  ? new Date(event.at * 1000).toLocaleString(locale)
                  : c.unknown}
              </p>
              <p className="portal-meta">
                {event.kind}
                {event.model ? ` · ${event.model}` : ""}
              </p>
              {event.reason ? <p>{event.reason}</p> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="portal-empty">{c.empty}</p>
      )}
    </section>
  );
}
function statusText(status: string, c: ReturnType<typeof portalCopy>) {
  const known: Record<string, string> = {
    published: c.published,
    draft: c.draft,
    pending: c.pending,
    approved: c.approved,
    rejected: c.rejected,
    active: c.active,
    completed: c.complete,
  };
  return known[status] ?? status;
}
