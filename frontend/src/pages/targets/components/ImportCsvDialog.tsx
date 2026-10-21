import { useState, type FormEvent, type RefObject } from "react";
import { useImportCSV } from "../../../api/targets";
import styles from "../Targets.module.css";

interface ImportCsvDialogProps {
  dialogRef: RefObject<HTMLDialogElement | null>;
  activeCampaignId?: number;
}

export function ImportCsvDialog({ dialogRef, activeCampaignId }: ImportCsvDialogProps) {
  const importCSV = useImportCSV();

  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [importReport, setImportReport] = useState<string | null>(null);
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [importError, setImportError] = useState<string | null>(null);

  const handleImportSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeCampaignId || !csvFile) return;
    setImportError(null);
    setImportReport(null);
    setImportWarnings([]);

    try {
      const formData = new FormData();
      formData.append("campaign_id", String(activeCampaignId));
      formData.append("file", csvFile);

      const res = await importCSV.mutateAsync(formData);

      const msg = `Import complete: ${res.created} targets created, ${res.skipped} skipped.`;
      setImportReport(msg);
      if (res.near_matches && res.near_matches.length > 0) {
        setImportWarnings(res.near_matches);
      }
      setCsvFile(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setImportError(err.message);
      } else {
        setImportError("Failed to import CSV file.");
      }
    }
  };

  return (
    <dialog ref={dialogRef} className={styles.dialog}>
      <h2 className={styles.dialogTitle}>Import companies from CSV</h2>
      {importError && <div className={styles.errorBanner}>{importError}</div>}
      {importReport && <div className={styles.warningBanner}>{importReport}</div>}
      {importWarnings.length > 0 && (
        <div className={styles.warningBanner}>
          <strong>Near match warnings:</strong>
          <ul>
            {importWarnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      <form onSubmit={handleImportSubmit} className={styles.form}>
        <div className={styles.field}>
          <label htmlFor="csv-file" className={styles.label}>
            CSV file (columns: name, website, category, contact, email)
          </label>
          <input
            id="csv-file"
            type="file"
            accept=".csv"
            required
            onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
            className={styles.input}
          />
        </div>
        <div className={styles.dialogButtons}>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            className={styles.secondaryButton}
          >
            Close
          </button>
          <button type="submit" disabled={importCSV.isPending} className={styles.primaryButton}>
            {importCSV.isPending ? "Importing..." : "Upload and import"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
