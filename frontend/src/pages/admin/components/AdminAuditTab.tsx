import { type useAdminAudit } from "../../../api/admin";
import styles from "../Admin.module.css";

interface AdminAuditTabProps {
  auditQuery: ReturnType<typeof useAdminAudit>;
}

export function AdminAuditTab({ auditQuery }: AdminAuditTabProps) {
  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>System audit log</h2>
      {auditQuery.isLoading ? (
        <div className={styles.loading}>Loading audit log...</div>
      ) : (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Record ID</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {auditQuery.data?.map((entry) => (
                <tr key={entry.id}>
                  <td className={styles.monoCol}>{entry.at}</td>
                  <td>{entry.action}</td>
                  <td>{entry.entity}</td>
                  <td className={styles.monoCol}>{entry.entity_id || "-"}</td>
                  <td>{entry.detail || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
