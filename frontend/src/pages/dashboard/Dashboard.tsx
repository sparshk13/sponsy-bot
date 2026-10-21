import { useRef } from "react";
import { useSession } from "../../api/auth";
import { useDashboard } from "../../api/dashboard";
import { GoogleSheetsModal } from "../../components/GoogleSheetsModal";
import { formatDateIst, formatInr } from "../../formatters";
import styles from "./Dashboard.module.css";

export function Dashboard() {
  const sessionQuery = useSession();
  const dashboardQuery = useDashboard();
  const sheetsDialogRef = useRef<HTMLDialogElement>(null);

  if (dashboardQuery.isLoading) {
    return <div className={styles.emptyState}>Loading dashboard.</div>;
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return (
      <div className={styles.emptyState}>
        Failed to load dashboard data. Please try again.
      </div>
    );
  }

  const data = dashboardQuery.data;
  const user = sessionQuery.data?.user;
  const isAdmin = user?.role === "admin";

  return (
    <div className={styles.container}>
      <header className={styles.headerCard}>
        <div className={styles.titleCol}>
          <h1 className={styles.title}>Dashboard</h1>
          <p className={styles.subtitle}>
            Outreach pipeline stages, conversion rates, and secured sponsorship outcomes.
          </p>
        </div>
        {isAdmin && (
          <div className={styles.actions}>
            <button
              type="button"
              onClick={() => sheetsDialogRef.current?.showModal()}
              className={styles.exportButton}
            >
              Google Sheets Sync
            </button>
            <a
              href="/api/export/tracker.csv"
              download="tracker.csv"
              className={styles.exportButton}
            >
              Export tracker (CSV)
            </a>
          </div>
        )}
      </header>

      <GoogleSheetsModal dialogRef={sheetsDialogRef} />

      {/* Summary Ledger */}
      <div className={styles.summaryRow}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Total Targets</span>
          <span className={styles.summaryValue}>{data.total_targets}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Contacted</span>
          <span className={styles.summaryValue}>{data.contacted_count}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Response Rate</span>
          <span className={styles.summaryValue}>{data.response_rate}%</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Interest Rate</span>
          <span className={styles.summaryValue}>{data.interest_rate}%</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Secured Cash</span>
          <span className={styles.summaryValue}>{formatInr(data.total_cash_inr)}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Secured Partners</span>
          <span className={styles.summaryValue}>{data.secured_count}</span>
        </div>
      </div>

      {/* Pipeline Breakdown */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Pipeline Stages</h2>
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Stage</th>
                <th style={{ width: "90px" }}>Count</th>
                <th style={{ width: "90px" }}>Share</th>
                <th style={{ width: "200px" }}>Conversion</th>
              </tr>
            </thead>
            <tbody>
              {data.pipeline.map((stage) => {
                const percent =
                  data.total_targets > 0
                    ? Math.round((stage.count / data.total_targets) * 100)
                    : 0;
                const isSecured = stage.stage === "secured";
                return (
                  <tr key={stage.stage}>
                    <td>{stage.label}</td>
                    <td className={styles.monoCol}>{stage.count}</td>
                    <td className={styles.monoCol}>{percent}%</td>
                    <td>
                      <div className={styles.barTrack}>
                        <div
                          className={isSecured ? styles.barFillSecured : styles.barFill}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Non-cash Benefits Section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Non-cash Sponsorship Benefits</h2>
        {data.non_cash_outcomes.length === 0 ? (
          <div className={styles.tableWrapper}>
            <div className={styles.emptyState}>
              No goodies, booths, or credits secured yet.
            </div>
          </div>
        ) : (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Kind</th>
                  <th>Deliverables & Details</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {data.non_cash_outcomes.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.company_name}</strong>
                    </td>
                    <td style={{ textTransform: "capitalize" }}>{item.kind}</td>
                    <td>{item.description || "-"}</td>
                    <td className={styles.monoCol}>
                      {formatDateIst(item.confirmed_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Per-organizer Performance Table */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Organizer Performance</h2>
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Organizer</th>
                <th>Assigned Targets</th>
                <th>Contacted</th>
                <th>Secured Targets</th>
                <th>Cash Raised</th>
              </tr>
            </thead>
            <tbody>
              {data.organizers.map((org) => (
                <tr key={org.user_id}>
                  <td>
                    <strong>{org.name}</strong>
                  </td>
                  <td className={styles.monoCol}>{org.assigned_count}</td>
                  <td className={styles.monoCol}>{org.contacted_count}</td>
                  <td className={styles.monoCol}>{org.secured_count}</td>
                  <td className={styles.monoCol}>
                    {formatInr(org.secured_cash_inr)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
