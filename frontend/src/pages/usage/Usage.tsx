import { useUsage } from "../../api/usage";
import styles from "./Usage.module.css";

export function Usage() {
  const usageQuery = useUsage();

  if (usageQuery.isLoading) {
    return <div className={styles.emptyBox}>Loading usage budgets.</div>;
  }

  const items = usageQuery.data || [];
  const geminiExhausted = items.some((i) => i.provider === "gemini" && i.is_exhausted);
  const anyWarning = items.some((i) => i.is_warning && !i.is_exhausted);

  return (
    <div className={styles.container}>
      <div className={styles.headerCard}>
        <h1 className={styles.title}>Usage and free-tier budgets</h1>
        <p className={styles.subtitle}>
          Monitors daily and monthly free allowance counters across all external APIs.
        </p>
      </div>

      {geminiExhausted && (
        <div className={styles.exhaustedBanner}>
          Gemini&apos;s free quota for today is used up. Drafting resumes tomorrow. Nothing is lost.
        </div>
      )}

      {anyWarning && !geminiExhausted && (
        <div className={styles.warningBanner}>
          One or more free-tier allowances have exceeded 80% usage.
        </div>
      )}

      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
          <thead>
            <tr>
              <th>Provider</th>
              <th>Period</th>
              <th>Used</th>
              <th>Allowance Cap</th>
              <th>Usage %</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const statusCls = item.is_exhausted
                ? styles.statusExhausted
                : item.is_warning
                ? styles.statusWarning
                : styles.statusNormal;

              return (
                <tr key={item.provider}>
                  <td>
                    <span className={styles.providerName}>{item.provider}</span>
                  </td>
                  <td style={{ textTransform: "capitalize" }}>{item.period}</td>
                  <td className={styles.monoCol}>{item.used}</td>
                  <td className={styles.monoCol}>{item.cap}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <div className={styles.progressBarContainer}>
                        <div
                          className={
                            item.is_exhausted
                              ? styles.progressBarExhausted
                              : item.is_warning
                              ? styles.progressBarWarning
                              : styles.progressBar
                          }
                          style={{ width: `${Math.min(100, item.percent)}%` }}
                        />
                      </div>
                      <span className={styles.monoCol}>{item.percent}%</span>
                    </div>
                  </td>
                  <td>
                    <span className={statusCls}>
                      {item.is_exhausted ? "Exhausted" : item.is_warning ? "Near cap" : "Active"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      </div>
    </div>
  );
}
