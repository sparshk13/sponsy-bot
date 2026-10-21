import { useMemory } from "../../api/dashboard";
import { formatDateIst, formatInr } from "../../formatters";
import styles from "./Memory.module.css";

export function Memory() {
  const memoryQuery = useMemory();

  if (memoryQuery.isLoading) {
    return <div className={styles.emptyState}>Loading institutional memory.</div>;
  }

  if (memoryQuery.isError || !memoryQuery.data) {
    return (
      <div className={styles.emptyState}>
        Failed to load memory data. Please try again.
      </div>
    );
  }

  const data = memoryQuery.data;

  return (
    <div className={styles.container}>
      <header className={styles.headerCard}>
        <div className={styles.titleCol}>
          <h1 className={styles.title}>Memory</h1>
          <p className={styles.subtitle}>
            Institutional memory of past sponsors, confirmed outcomes, and the asks that worked across campaigns.
          </p>
        </div>
      </header>

      {/* Summary Ledger */}
      <div className={styles.summaryRow}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Past Sponsors</span>
          <span className={styles.summaryValue}>{data.total_sponsors}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Total Funds Raised</span>
          <span className={styles.summaryValue}>{formatInr(data.total_cash_inr)}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Total Partnerships</span>
          <span className={styles.summaryValue}>{data.entries.length}</span>
        </div>
      </div>

      {/* Cross-campaign History Table */}
      <div className={styles.tableCard}>
        {data.entries.length === 0 ? (
          <div className={styles.emptyState}>
            No confirmed sponsorship outcomes recorded across campaigns yet.
          </div>
        ) : (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Campaign</th>
                  <th>Kind / Tier</th>
                  <th>Outcome Secured</th>
                  <th>Date</th>
                  <th>Ask that worked</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>
                      <div>
                        <strong>{entry.company_name}</strong>
                      </div>
                      <div className={styles.monoCol} style={{ color: "var(--ink-2)", fontSize: "12px" }}>
                        {entry.company_domain}
                      </div>
                    </td>
                    <td>{entry.campaign_name}</td>
                    <td style={{ textTransform: "capitalize" }}>
                      {entry.kind}
                      {entry.tier && ` (${entry.tier})`}
                    </td>
                    <td>
                      {entry.kind === "cash" && entry.amount_inr !== null ? (
                        <span className={styles.monoCol} style={{ fontWeight: 600 }}>
                          {formatInr(entry.amount_inr)}
                        </span>
                      ) : (
                        entry.description || "-"
                      )}
                      {entry.kind === "cash" && entry.description && (
                        <div style={{ fontSize: "12px", color: "var(--ink-2)", marginTop: "2px" }}>
                          {entry.description}
                        </div>
                      )}
                    </td>
                    <td className={styles.monoCol}>
                      {formatDateIst(entry.confirmed_at)}
                    </td>
                    <td>
                      {entry.ask_worked ? (
                        <div style={{ maxWidth: "340px", fontSize: "13px" }}>
                          {entry.ask_worked}
                        </div>
                      ) : (
                        <span style={{ color: "var(--ink-2)" }}>-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
