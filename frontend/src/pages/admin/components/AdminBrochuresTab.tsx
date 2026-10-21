import { useState, type FormEvent, type ChangeEvent } from "react";
import {
  type useBrochures,
  type useUploadBrochure,
} from "../../../api/admin";
import styles from "../Admin.module.css";

interface AdminBrochuresTabProps {
  brochuresQuery: ReturnType<typeof useBrochures>;
  uploadBrochure: ReturnType<typeof useUploadBrochure>;
}

export function AdminBrochuresTab({
  brochuresQuery,
  uploadBrochure,
}: AdminBrochuresTabProps) {
  const [brochureTier, setBrochureTier] = useState<"cash" | "goodies" | "credits">("cash");
  const [brochureFile, setBrochureFile] = useState<File | null>(null);
  const [brochureError, setBrochureError] = useState<string | null>(null);
  const [brochureSuccess, setBrochureSuccess] = useState<string | null>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      setBrochureFile(files[0]);
    }
  };

  const handleUploadBrochure = async (e: FormEvent) => {
    e.preventDefault();
    setBrochureError(null);
    setBrochureSuccess(null);
    if (!brochureFile) {
      setBrochureError("Please select a PDF brochure file to upload.");
      return;
    }
    if (brochureFile.size > 5 * 1024 * 1024) {
      setBrochureError("Brochure exceeds maximum allowed size of 5 MB.");
      return;
    }
    try {
      await uploadBrochure.mutateAsync({ tier: brochureTier, file: brochureFile });
      setBrochureSuccess(`Brochure for ${brochureTier} tier uploaded.`);
      setBrochureFile(null);
    } catch (err: unknown) {
      setBrochureError(err instanceof Error ? err.message : "Failed to upload brochure.");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div className={styles.sectionCard}>
        <h2 className={styles.sectionTitle}>Tier brochures</h2>
        {brochuresQuery.isLoading ? (
          <div className={styles.loading}>Loading brochures...</div>
        ) : (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Tier</th>
                  <th>Original filename</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {brochuresQuery.data && brochuresQuery.data.length > 0 ? (
                  brochuresQuery.data.map((b) => (
                    <tr key={b.id}>
                      <td>{b.tier}</td>
                      <td>{b.filename}</td>
                      <td>
                        <a
                          href={`/api/brochures/${b.id}`}
                          download
                          className={styles.secondaryButton}
                        >
                          Download
                        </a>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3} className={styles.loading}>
                      No brochures uploaded yet. Uploaded brochures are automatically attached to first outreach emails matching their tier.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className={styles.sectionCard}>
        <h2 className={styles.sectionTitle}>Upload brochure</h2>
        <form onSubmit={handleUploadBrochure} className={styles.form}>
          {brochureError && <div className={styles.errorBanner}>{brochureError}</div>}
          {brochureSuccess && (
            <div style={{ color: "var(--go)", fontSize: "var(--text-sm)", marginBottom: "var(--space-2)" }}>
              {brochureSuccess}
            </div>
          )}

          <div className={styles.field}>
            <label htmlFor="brochure-tier" className={styles.label}>
              Sponsorship tier
            </label>
            <select
              id="brochure-tier"
              value={brochureTier}
              onChange={(e) => setBrochureTier(e.target.value as "cash" | "goodies" | "credits")}
              className={styles.select}
            >
              <option value="cash">Cash tier</option>
              <option value="goodies">Goodies tier</option>
              <option value="credits">Credits tier</option>
            </select>
          </div>

          <div className={styles.field}>
            <label htmlFor="brochure-file" className={styles.label}>
              PDF Document (maximum 5 MB)
            </label>
            <input
              id="brochure-file"
              type="file"
              accept="application/pdf,.pdf"
              required
              onChange={handleFileChange}
              className={styles.input}
            />
            <span className={styles.hint}>PDF files only (max 5 MB).</span>
          </div>

          <button
            type="submit"
            disabled={uploadBrochure.isPending}
            className={styles.primaryButton}
          >
            {uploadBrochure.isPending ? "Uploading brochure..." : "Upload brochure"}
          </button>
        </form>
      </div>
    </div>
  );
}
