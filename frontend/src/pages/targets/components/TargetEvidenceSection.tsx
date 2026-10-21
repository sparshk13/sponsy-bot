import { type TargetDetail } from "../../../api/targets";
import styles from "../TargetDetail.module.css";

interface TargetEvidenceSectionProps {
  facts: TargetDetail["facts"];
}

export function TargetEvidenceSection({ facts }: TargetEvidenceSectionProps) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionTitle}>
        <span>Evidence</span>
        <span style={{ fontSize: "12px", fontWeight: "normal", color: "var(--ink-2)" }}>
          {facts.length} facts found
        </span>
      </div>

      {facts.length === 0 ? (
        <div className={styles.emptyBox}>
          No sponsorship history found in the sources searched.
        </div>
      ) : (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th style={{ width: "80px" }}>Kind</th>
                <th>Claim and quote</th>
                <th style={{ width: "120px" }}>Source</th>
                <th style={{ width: "90px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {facts.map((fact) => (
                <tr key={fact.id}>
                  <td style={{ textTransform: "capitalize" }}>
                    {fact.kind.replace("_", " ")}
                  </td>
                  <td>
                    <div>
                      <strong>{fact.claim}</strong>
                    </div>
                    {fact.evidence_quote && (
                      <div
                        style={{
                          fontSize: "12px",
                          color: "var(--ink-2)",
                          marginTop: "4px",
                        }}
                      >
                        &ldquo;{fact.evidence_quote}&rdquo;
                      </div>
                    )}
                  </td>
                  <td>
                    {fact.source_url && fact.source_url.startsWith("https://") ? (
                      <a
                        href={fact.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.sourceLink}
                      >
                        Link
                      </a>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td>
                    {fact.status === "verified" ? (
                      <span className={styles.badgeVerified}>Verified</span>
                    ) : (
                      <span
                        className={styles.badgeUnverified}
                        title="We could not confirm this in the sources we found. Check it before relying on it."
                      >
                        Unverified
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
