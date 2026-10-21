import { useState, type FormEvent } from "react";
import {
  type useCreateTemplate,
  type useDeleteTemplate,
  type useTemplates,
} from "../../../api/admin";
import styles from "../Admin.module.css";

interface AdminTemplatesTabProps {
  templatesQuery: ReturnType<typeof useTemplates>;
  createTemplate: ReturnType<typeof useCreateTemplate>;
  deleteTemplate: ReturnType<typeof useDeleteTemplate>;
}

export function AdminTemplatesTab({
  templatesQuery,
  createTemplate,
  deleteTemplate,
}: AdminTemplatesTabProps) {
  const [tplName, setTplName] = useState("");
  const [tplKind, setTplKind] = useState<"first" | "followup" | "meeting">("first");
  const [tplBody, setTplBody] = useState("");
  const [tplError, setTplError] = useState<string | null>(null);

  const handleAddTemplate = async (e: FormEvent) => {
    e.preventDefault();
    setTplError(null);
    if (!tplName.trim() || !tplBody.trim()) {
      setTplError("Template name and body are required.");
      return;
    }
    try {
      await createTemplate.mutateAsync({
        name: tplName.trim(),
        kind: tplKind,
        body: tplBody.trim(),
      });
      setTplName("");
      setTplBody("");
    } catch (err: unknown) {
      setTplError(err instanceof Error ? err.message : "Failed to create template.");
    }
  };

  const handleDeleteTemplate = async (id: number) => {
    if (!window.confirm("Delete this template?")) return;
    try {
      await deleteTemplate.mutateAsync(id);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete template.");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div className={styles.sectionCard}>
        <h2 className={styles.sectionTitle}>Email outreach templates</h2>
        {templatesQuery.isLoading ? (
          <div className={styles.loading}>Loading templates...</div>
        ) : (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Kind</th>
                  <th>Name</th>
                  <th>Body preview</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {templatesQuery.data && templatesQuery.data.length > 0 ? (
                  templatesQuery.data.map((tpl) => (
                    <tr key={tpl.id}>
                      <td>{tpl.kind}</td>
                      <td>{tpl.name}</td>
                      <td className={styles.previewText}>{tpl.body}</td>
                      <td>
                        <button
                          type="button"
                          onClick={() => handleDeleteTemplate(tpl.id)}
                          className={styles.secondaryButton}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className={styles.loading}>
                      No templates created yet. Templates provide a structural base that drafting personalizes.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className={styles.sectionCard}>
        <h2 className={styles.sectionTitle}>Add template</h2>
        <form onSubmit={handleAddTemplate} className={styles.form}>
          {tplError && <div className={styles.errorBanner}>{tplError}</div>}

          <div className={styles.field}>
            <label htmlFor="tpl-name" className={styles.label}>
              Template name
            </label>
            <input
              id="tpl-name"
              type="text"
              required
              value={tplName}
              onChange={(e) => setTplName(e.target.value)}
              className={styles.input}
              placeholder="e.g. Standard First Outreach"
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="tpl-kind" className={styles.label}>
              Outreach stage
            </label>
            <select
              id="tpl-kind"
              value={tplKind}
              onChange={(e) => setTplKind(e.target.value as "first" | "followup" | "meeting")}
              className={styles.select}
            >
              <option value="first">First outreach</option>
              <option value="followup">Follow-up</option>
              <option value="meeting">Meeting reply</option>
            </select>
          </div>

          <div className={styles.field}>
            <label htmlFor="tpl-body" className={styles.label}>
              Template body
            </label>
            <textarea
              id="tpl-body"
              required
              rows={5}
              value={tplBody}
              onChange={(e) => setTplBody(e.target.value)}
              className={styles.textarea}
              placeholder="Base email text that the model personalizes with verified facts..."
            />
          </div>

          <button
            type="submit"
            disabled={createTemplate.isPending}
            className={styles.primaryButton}
          >
            {createTemplate.isPending ? "Adding template..." : "Add template"}
          </button>
        </form>
      </div>
    </div>
  );
}
