import { type TargetDetail } from "../../../api/targets";
import { formatDateTimeIst } from "../../../formatters";
import styles from "../TargetDetail.module.css";

interface TargetThreadSectionProps {
  thread: TargetDetail["thread"];
}

export function TargetThreadSection({ thread }: TargetThreadSectionProps) {
  if (thread.length === 0) {
    return null;
  }

  return (
    <section className={styles.section} style={{ marginTop: "var(--space-4)" }}>
      <div className={styles.sectionTitle}>
        <span>Message thread history</span>
        <span style={{ fontSize: "12px", color: "var(--ink-2)" }}>
          {thread.length} messages
        </span>
      </div>

      <div className={styles.threadList}>
        {thread.map((msg) => (
          <div key={msg.id} className={styles.threadItem}>
            <div className={styles.threadHeader}>
              <span>
                <strong>
                  {msg.direction === "out" ? "Outbound" : "Inbound"}
                </strong>{" "}
                ({msg.kind}), Status: {msg.status}
              </span>
              <span>{formatDateTimeIst(msg.created_at)}</span>
            </div>
            {msg.subject && (
              <div style={{ fontSize: "13px", fontWeight: 600 }}>
                Subject: {msg.subject}
              </div>
            )}
            <div className={styles.threadBody}>{msg.body || "(No text content)"}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
