"use client";

import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { portalApi, type AdminDestination } from "@/lib/portal";
import { PortalIcon } from "./PortalIcon";
import { PortalError, PortalLoading, usePortalResource } from "./PortalShell";

export function AdminDashboard({
  navigate,
}: {
  navigate: (destination: AdminDestination) => void;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const resource = usePortalResource(portalApi.overview);
  const data = resource.data;
  const number = (value: number) => value.toLocaleString(locale);
  const roleLabels = {
    student: c.student,
    instructor: c.instructor,
    admin: c.administrator,
  };
  const stateLabels = {
    published: c.published,
    unpublished: c.unpublished,
    suspended: c.suspended,
  };
  const metrics = data
    ? [
        {
          label: c.totalUsers,
          count: data.users,
          action: c.viewUsers,
          target: { section: "users" } as const,
        },
        {
          label: c.totalCourses,
          count: data.courses,
          action: c.viewCourses,
          target: { section: "courses" } as const,
        },
        {
          label: c.publishedCourses,
          count: data.publishedCourses,
          action: c.viewPublished,
          target: { section: "courses", courseFilter: "published" } as const,
        },
        {
          label: c.enrollments,
          count: data.enrollments,
          action: c.viewEnrollments,
          target: { section: "courses", courseFilter: "enrolled" } as const,
        },
      ]
    : [];
  const enrolled =
    data?.courseEnrollments.filter((course) => course.count > 0).slice(0, 5) ??
    [];
  const maxEnrollment = Math.max(1, ...enrolled.map((course) => course.count));
  return (
    <section className="portal-dashboard">
      <div className="portal-section-heading">
        <h2>{c.overview}</h2>
        <button
          type="button"
          disabled={resource.loading}
          onClick={resource.reload}
        >
          {resource.loading ? c.loading : c.refresh}
        </button>
      </div>
      <PortalError error={resource.error} retry={resource.reload} />
      {resource.loading ? (
        <PortalLoading />
      ) : data ? (
        <>
          <div className="portal-metrics">
            {metrics.map((metric) => (
              <button
                className="portal-metric"
                type="button"
                key={metric.label}
                onClick={() => navigate(metric.target)}
              >
                <span>{metric.label}</span>
                <strong>{number(metric.count)}</strong>
                <span className="portal-metric-action">
                  {metric.action}
                  <PortalIcon name="arrow" />
                </span>
              </button>
            ))}
          </div>
          <div className="portal-analytics-grid">
            <section
              className="portal-chart-panel"
              aria-labelledby="admin-role-chart"
            >
              <h3 id="admin-role-chart">{c.userDistribution}</h3>
              <div className="portal-role-chart">
                <div className="portal-donut">
                  <svg viewBox="0 0 42 42" aria-hidden="true" focusable="false">
                    <circle
                      className="portal-donut-track"
                      cx="21"
                      cy="21"
                      r="15.915494"
                    />
                    {data.userRoles.map((item, index) => {
                      const share = data.users
                        ? (item.count / data.users) * 100
                        : 0;
                      const offset = data.users
                        ? (data.userRoles
                            .slice(0, index)
                            .reduce((sum, row) => sum + row.count, 0) /
                            data.users) *
                          -100
                        : 0;
                      return share > 0 ? (
                        <circle
                          key={item.role}
                          className={`portal-series--${item.role}`}
                          cx="21"
                          cy="21"
                          r="15.915494"
                          strokeDasharray={`${share} ${100 - share}`}
                          strokeDashoffset={offset}
                        />
                      ) : null;
                    })}
                  </svg>
                  <div>
                    <strong>{number(data.users)}</strong>
                    <span>{c.users}</span>
                  </div>
                </div>
                <ul className="portal-chart-legend">
                  {data.userRoles.map((item) => (
                    <li key={item.role}>
                      <button
                        type="button"
                        onClick={() =>
                          navigate({ section: "users", role: item.role })
                        }
                      >
                        <span
                          className={`portal-chart-key portal-series--${item.role}`}
                          aria-hidden="true"
                        />
                        <span>{roleLabels[item.role]}</span>
                        <strong>{number(item.count)}</strong>
                        <span className="portal-chart-share">
                          {data.users
                            ? Math.round((item.count / data.users) * 100)
                            : 0}
                          %
                        </span>
                        <PortalIcon name="arrow" />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
              {!data.users ? (
                <p className="portal-chart-note">{c.noUsers}</p>
              ) : null}
            </section>
            <section
              className="portal-chart-panel"
              aria-labelledby="admin-course-chart"
            >
              <h3 id="admin-course-chart">{c.courseDistribution}</h3>
              <div className="portal-course-chart-total">
                <strong>{number(data.courses)}</strong>
                <span>{c.totalCourses}</span>
              </div>
              <div className="portal-stacked-bar" aria-hidden="true">
                {data.courseStates.map((item) => (
                  <span
                    key={item.state}
                    className={`portal-series--${item.state}`}
                    style={{
                      width: `${data.courses ? (item.count / data.courses) * 100 : 0}%`,
                    }}
                  />
                ))}
              </div>
              <ul className="portal-chart-legend">
                {data.courseStates.map((item) => (
                  <li key={item.state}>
                    <button
                      type="button"
                      onClick={() =>
                        navigate({
                          section: "courses",
                          courseFilter: item.state,
                        })
                      }
                    >
                      <span
                        className={`portal-chart-key portal-series--${item.state}`}
                        aria-hidden="true"
                      />
                      <span>{stateLabels[item.state]}</span>
                      <strong>{number(item.count)}</strong>
                      <span className="portal-chart-share">
                        {data.courses
                          ? Math.round((item.count / data.courses) * 100)
                          : 0}
                        %
                      </span>
                      <PortalIcon name="arrow" />
                    </button>
                  </li>
                ))}
              </ul>
              {!data.courses ? (
                <p className="portal-chart-note">{c.noCourseStats}</p>
              ) : null}
            </section>
            <section
              className="portal-chart-panel portal-enrollment-panel"
              aria-labelledby="admin-enrollment-chart"
            >
              <div className="portal-chart-heading">
                <div>
                  <h3 id="admin-enrollment-chart">
                    {c.enrollmentDistribution}
                  </h3>
                  <p className="portal-chart-note">{c.enrollmentHint}</p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    navigate({ section: "courses", courseFilter: "enrolled" })
                  }
                >
                  {c.viewCourses}
                  <PortalIcon name="arrow" />
                </button>
              </div>
              {enrolled.length ? (
                <ol className="portal-enrollment-chart">
                  {enrolled.map((course) => (
                    <li key={course.courseId}>
                      <button
                        type="button"
                        onClick={() =>
                          navigate({
                            section: "courses",
                            courseId: course.courseId,
                          })
                        }
                      >
                        <span className="portal-enrollment-label">
                          <span>{course.title}</span>
                          {course.courseCode ? (
                            <small>{course.courseCode}</small>
                          ) : null}
                        </span>
                        <span
                          className="portal-enrollment-track"
                          aria-hidden="true"
                        >
                          <span
                            style={{
                              width: `${(course.count / maxEnrollment) * 100}%`,
                            }}
                          />
                        </span>
                        <strong>{number(course.count)}</strong>
                        <PortalIcon name="arrow" />
                      </button>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="portal-chart-empty">{c.noEnrollments}</p>
              )}
            </section>
          </div>
          <div className="portal-review-inbox">
            <span className="portal-review-mark">
              <PortalIcon name="applications" />
            </span>
            <div>
              <h3>{c.applications}</h3>
              <p>
                {c.pendingApplications}:{" "}
                <strong>{number(data.pendingApplications)}</strong>
              </p>
            </div>
            <button
              className="portal-button"
              type="button"
              onClick={() => navigate({ section: "applications" })}
            >
              {c.reviewApplications}
              <PortalIcon name="arrow" />
            </button>
          </div>
        </>
      ) : null}
    </section>
  );
}
