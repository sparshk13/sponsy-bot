import {
  type useRevokeAllSessions,
  type useSystemStatus,
} from "../../../api/admin";
import styles from "../Admin.module.css";

interface AdminSystemTabProps {
  systemQuery: ReturnType<typeof useSystemStatus>;
  revokeSessions: ReturnType<typeof useRevokeAllSessions>;
}

export function AdminSystemTab({
  systemQuery,
  revokeSessions,
}: AdminSystemTabProps) {
  const handleRevokeSessions = async () => {
    if (
      !confirm(
        "Are you sure you want to revoke all active sessions? All users will be signed out immediately."
      )
    ) {
      return;
    }
    try {
      await revokeSessions.mutateAsync();
      alert("All user sessions have been revoked.");
    } catch (err: unknown) {
      if (err instanceof Error) {
        alert(err.message);
      }
    }
  };

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>System status and maintenance</h2>
      {systemQuery.isLoading ? (
        <div className={styles.loading}>Loading system status...</div>
      ) : (
        <div className={styles.systemGrid}>
          <div className={styles.systemCard}>
            <span className={styles.systemLabel}>Last mail check</span>
            <span className={styles.systemValue}>
              {systemQuery.data?.last_mail_check || "Never"}
            </span>
          </div>
          <div className={styles.systemCard}>
            <span className={styles.systemLabel}>Last email sent</span>
            <span className={styles.systemValue}>
              {systemQuery.data?.last_send || "Never"}
            </span>
          </div>
          <div className={styles.systemCard}>
            <span className={styles.systemLabel}>Last backup file</span>
            <span className={styles.systemValue}>
              {systemQuery.data?.last_backup || "None recorded"}
            </span>
          </div>
          <div className={styles.systemCard}>
            <span className={styles.systemLabel}>Database size</span>
            <span className={styles.systemValue}>
              {systemQuery.data?.db_size_bytes
                ? `${Math.round(systemQuery.data.db_size_bytes / (1024 * 1024))} MB`
                : "0 MB"}
            </span>
          </div>
          <div className={styles.systemCard}>
            <span className={styles.systemLabel}>Free disk space</span>
            <span className={styles.systemValue}>
              {systemQuery.data?.disk_free_bytes
                ? `${Math.round(systemQuery.data.disk_free_bytes / (1024 * 1024 * 1024))} GB`
                : "0 GB"}
            </span>
          </div>
        </div>
      )}

      <div className={styles.dangerZone}>
        <h3 className={styles.dangerTitle}>Session management</h3>
        <p className={styles.dangerDesc}>
          Revoke all active user sessions across the entire system. All organizers and
          administrators will be signed out immediately.
        </p>
        <button
          type="button"
          onClick={handleRevokeSessions}
          disabled={revokeSessions.isPending}
          className={styles.dangerButton}
        >
          {revokeSessions.isPending ? "Revoking sessions..." : "Revoke all sessions"}
        </button>
      </div>
    </div>
  );
}
