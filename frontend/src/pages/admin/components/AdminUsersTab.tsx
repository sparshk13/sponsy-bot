import { useState, type FormEvent } from "react";
import {
  type AdminUser,
  type useAdminUsers,
  type useCreateUser,
  type useResetUser2FA,
  type useUpdateUser,
} from "../../../api/admin";
import styles from "../Admin.module.css";

interface AdminUsersTabProps {
  currentUser: { id: number; email: string; role: string };
  usersQuery: ReturnType<typeof useAdminUsers>;
  createUser: ReturnType<typeof useCreateUser>;
  updateUser: ReturnType<typeof useUpdateUser>;
  resetUser2FA: ReturnType<typeof useResetUser2FA>;
}

export function AdminUsersTab({
  currentUser,
  usersQuery,
  createUser,
  updateUser,
  resetUser2FA,
}: AdminUsersTabProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"organizer" | "admin">("organizer");
  const [formError, setFormError] = useState<string | null>(null);

  const handleAddUser = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (password.length < 12) {
      setFormError("Password must be at least 12 characters long.");
      return;
    }

    try {
      await createUser.mutateAsync({ name, email, password, role });
      setName("");
      setEmail("");
      setPassword("");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to create user.");
      }
    }
  };

  const handleToggleActive = async (user: AdminUser) => {
    try {
      await updateUser.mutateAsync({
        userId: user.id,
        payload: {
          is_active: !user.is_active,
        },
      });
    } catch (err: unknown) {
      if (err instanceof Error) {
        alert(err.message);
      }
    }
  };

  const handleReset2FA = async (user: AdminUser) => {
    if (
      !confirm(
        `Reset two-factor authentication for ${user.email}? They will need to set up an authenticator again.`
      )
    ) {
      return;
    }
    try {
      await resetUser2FA.mutateAsync(user.id);
    } catch (err: unknown) {
      if (err instanceof Error) {
        alert(err.message);
      }
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div className={styles.sectionCard}>
        <h2 className={styles.sectionTitle}>User accounts</h2>
        {usersQuery.isLoading ? (
          <div className={styles.loading}>Loading users...</div>
        ) : (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>2FA</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {usersQuery.data?.map((user) => (
                  <tr key={user.id}>
                    <td>{user.name}</td>
                    <td className={styles.monoCol}>{user.email}</td>
                    <td style={{ textTransform: "capitalize" }}>{user.role}</td>
                    <td>
                      <span
                        className={
                          user.totp_enabled ? styles.tagActive : styles.tagInactive
                        }
                      >
                        {user.totp_enabled ? "Enabled" : "Not set"}
                      </span>
                    </td>
                    <td>
                      <span
                        className={
                          user.is_active ? styles.tagActive : styles.tagInactive
                        }
                      >
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                        {user.id === currentUser.id ? (
                          <span className={styles.tagInactive}>Current account</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleToggleActive(user)}
                            className={styles.secondaryButton}
                          >
                            {user.is_active ? "Deactivate" : "Activate"}
                          </button>
                        )}
                        {user.totp_enabled && (
                          <button
                            type="button"
                            onClick={() => handleReset2FA(user)}
                            disabled={resetUser2FA.isPending}
                            className={styles.secondaryButton}
                          >
                            Reset 2FA
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className={styles.sectionCard}>
        <h2 className={styles.sectionTitle}>Add user</h2>
        <form onSubmit={handleAddUser} className={styles.form}>
          {formError && <div className={styles.errorBanner}>{formError}</div>}

          <div className={styles.field}>
            <label htmlFor="user-name" className={styles.label}>
              Full name
            </label>
            <input
              id="user-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={styles.input}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="user-email" className={styles.label}>
              Email address
            </label>
            <input
              id="user-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={styles.input}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="user-password" className={styles.label}>
              Password
            </label>
            <input
              id="user-password"
              type="password"
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={styles.input}
            />
            <span className={styles.hint}>Minimum 12 characters</span>
          </div>

          <div className={styles.field}>
            <label htmlFor="user-role" className={styles.label}>
              Role
            </label>
            <select
              id="user-role"
              value={role}
              onChange={(e) => setRole(e.target.value as "organizer" | "admin")}
              className={styles.select}
            >
              <option value="organizer">Organizer</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={createUser.isPending}
            className={styles.primaryButton}
          >
            {createUser.isPending ? "Adding user..." : "Add user"}
          </button>
        </form>
      </div>
    </div>
  );
}
