import { type TargetDetail } from "../../../api/targets";
import styles from "../TargetDetail.module.css";

interface TargetRecommendationCardProps {
  target: TargetDetail;
}

export function TargetRecommendationCard({ target }: TargetRecommendationCardProps) {
  const renderPriority = (priority: string | null) => {
    switch (priority) {
      case "high":
        return <span className={styles.priorityHigh}>High</span>;
      case "medium":
        return <span className={styles.priorityMed}>Medium</span>;
      case "low":
        return <span className={styles.priorityLow}>Low</span>;
      default:
        return <span className={styles.priorityLow}>-</span>;
    }
  };

  return (
    <section className={styles.section}>
      <div className={styles.sectionTitle}>
        <span>Recommendation</span>
        {target.ask_basis === "assumption" && (
          <span className={styles.badgeAssumption}>Assumption, not evidence</span>
        )}
      </div>

      {target.researched_at ? (
        <div className={styles.recGrid}>
          <div className={styles.recRow}>
            <span className={styles.recLabel}>Priority</span>
            <div
              className={styles.recValue}
              style={{ display: "flex", gap: "8px", alignItems: "center" }}
            >
              {renderPriority(target.priority)}
              <span>Score {target.priority_score}</span>
            </div>
          </div>

          <div className={styles.recRow}>
            <span className={styles.recLabel}>Recommended Tier</span>
            <span className={styles.recValue} style={{ textTransform: "capitalize" }}>
              {target.tier || "None"}
            </span>
          </div>

          <div className={styles.recRow}>
            <span className={styles.recLabel}>Ask Summary</span>
            <span className={styles.recValue}>
              {target.ask_summary || "No ask generated."}
            </span>
          </div>

          <div className={styles.recRow}>
            <span className={styles.recLabel}>Reasoning</span>
            <div className={styles.recValue}>
              <p>{target.ask_reasoning}</p>
              {target.ask_fact_ids && target.ask_fact_ids.length > 0 && (
                <div style={{ marginTop: "6px", fontSize: "12px", color: "var(--ink-2)" }}>
                  Cites facts: {target.ask_fact_ids.join(", ")}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className={styles.emptyBox}>
          Target has not been researched yet. Click &quot;Prepare target&quot; to research.
        </div>
      )}
    </section>
  );
}
