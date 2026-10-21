import { useState, type RefObject } from "react";
import styles from "./GoogleSheetsModal.module.css";

interface GoogleSheetsModalProps {
  dialogRef: RefObject<HTMLDialogElement | null>;
}

export function GoogleSheetsModal({ dialogRef }: GoogleSheetsModalProps) {
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleCopyTsv = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/export/tracker.csv");
      if (!res.ok) {
        throw new Error("Failed to export tracker data");
      }
      const csvText = await res.text();
      // Convert CSV commas to tabs for standard Google Sheets / Excel clipboard pasting
      const rows = csvText.split("\n").map((line) => {
        // Quick parse for basic CSV lines
        return line
          .split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/)
          .map((cell) => cell.replace(/^"|"$/g, "").replace(/""/g, '"'))
          .join("\t");
      });
      const tsvText = rows.join("\n");
      await navigator.clipboard.writeText(tsvText);
      setCopied(true);
      setTimeout(() => setCopied(false), 4000);
    } catch {
      alert("Could not copy to clipboard. You can download the CSV directly.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    dialogRef.current?.close();
  };

  return (
    <dialog ref={dialogRef} className={styles.dialog}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div>
            <h2 className={styles.title}>Google Sheets Sync</h2>
            <p className={styles.subtitle}>
              Export and sync the live sponsor tracker into Google Sheets
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className={styles.closeButton}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className={styles.instructionsBox}>
          <strong>Fastest 1-Click Sync:</strong>
          <ol className={styles.stepList}>
            <li>Click <strong>Copy Sheet Data</strong> below.</li>
            <li>Open a new or existing Google Sheet.</li>
            <li>Press <strong>Ctrl + V</strong> (or <strong>Cmd + V</strong> on Mac) in cell A1. All 16 tracker columns will format instantly.</li>
          </ol>
        </div>

        <div className={styles.optionsGrid}>
          {copied ? (
            <div className={styles.copiedNotice}>
              ✓ Copied to clipboard! Paste into Google Sheets (Cmd + V)
            </div>
          ) : (
            <button
              type="button"
              onClick={handleCopyTsv}
              disabled={loading}
              className={styles.copyButton}
            >
              {loading ? "Generating..." : "Copy Sheet Data (for Google Sheets)"}
            </button>
          )}

          <a
            href="https://docs.google.com/spreadsheets/d/create"
            target="_blank"
            rel="noopener noreferrer"
            className={styles.secondaryLink}
          >
            Open New Google Sheet ↗
          </a>

          <a
            href="/api/export/tracker.csv"
            download="tracker.csv"
            className={styles.secondaryLink}
          >
            Download CSV File
          </a>
        </div>
      </div>
    </dialog>
  );
}
