import { useState } from "react";
import {
  useAdminAudit,
  useAdminUsers,
  useBrochures,
  useCreateTemplate,
  useCreateUser,
  useDeleteTemplate,
  useResetUser2FA,
  useRevokeAllSessions,
  useSystemStatus,
  useTemplates,
  useUpdateUser,
  useUploadBrochure,
} from "../../api/admin";
import { useSession } from "../../api/auth";
import styles from "./Admin.module.css";
import { AdminAuditTab } from "./components/AdminAuditTab";
import { AdminBrochuresTab } from "./components/AdminBrochuresTab";
import { AdminSystemTab } from "./components/AdminSystemTab";
import { AdminTemplatesTab } from "./components/AdminTemplatesTab";
import { AdminUsersTab } from "./components/AdminUsersTab";

export function Admin() {
  const sessionQuery = useSession();
  const currentUser = sessionQuery.data?.user;

  const [activeTab, setActiveTab] = useState<
    "users" | "templates" | "brochures" | "audit" | "system"
  >("users");

  const usersQuery = useAdminUsers();
  const auditQuery = useAdminAudit();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const resetUser2FA = useResetUser2FA();
  const templatesQuery = useTemplates();
  const createTemplate = useCreateTemplate();
  const deleteTemplate = useDeleteTemplate();
  const brochuresQuery = useBrochures();
  const uploadBrochure = useUploadBrochure();
  const systemQuery = useSystemStatus();
  const revokeSessions = useRevokeAllSessions();

  if (currentUser?.role !== "admin") {
    return (
      <div>
        <h1 className={styles.title}>Admin</h1>
        <p className={styles.subtitle}>You do not have permission to view this page.</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.headerCard}>
        <h1 className={styles.title}>Admin</h1>
        <p className={styles.subtitle}>User accounts, outreach templates, tier brochures, and audit log.</p>
      </div>

      <div className={styles.tabCard}>
        <div className={styles.tabs}>
          <button
            type="button"
            onClick={() => setActiveTab("users")}
            className={`${styles.tabButton} ${activeTab === "users" ? styles.activeTab : ""}`}
          >
            Users
          </button>
        <button
          type="button"
          onClick={() => setActiveTab("templates")}
          className={`${styles.tabButton} ${activeTab === "templates" ? styles.activeTab : ""}`}
        >
          Templates
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("brochures")}
          className={`${styles.tabButton} ${activeTab === "brochures" ? styles.activeTab : ""}`}
        >
          Brochures
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("audit")}
          className={`${styles.tabButton} ${activeTab === "audit" ? styles.activeTab : ""}`}
        >
          Audit Log
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("system")}
          className={`${styles.tabButton} ${activeTab === "system" ? styles.activeTab : ""}`}
        >
          System
        </button>
      </div>
      </div>

      {activeTab === "users" && (
        <AdminUsersTab
          currentUser={currentUser}
          usersQuery={usersQuery}
          createUser={createUser}
          updateUser={updateUser}
          resetUser2FA={resetUser2FA}
        />
      )}

      {activeTab === "templates" && (
        <AdminTemplatesTab
          templatesQuery={templatesQuery}
          createTemplate={createTemplate}
          deleteTemplate={deleteTemplate}
        />
      )}

      {activeTab === "brochures" && (
        <AdminBrochuresTab
          brochuresQuery={brochuresQuery}
          uploadBrochure={uploadBrochure}
        />
      )}

      {activeTab === "audit" && <AdminAuditTab auditQuery={auditQuery} />}

      {activeTab === "system" && (
        <AdminSystemTab
          systemQuery={systemQuery}
          revokeSessions={revokeSessions}
        />
      )}
    </div>
  );
}
