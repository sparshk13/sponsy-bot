import { useState, type FormEvent, type RefObject } from "react";
import { useAddTarget } from "../../../api/targets";
import styles from "../Targets.module.css";

interface AddCompanyDialogProps {
  dialogRef: RefObject<HTMLDialogElement | null>;
  activeCampaignId?: number;
}

export function AddCompanyDialog({ dialogRef, activeCampaignId }: AddCompanyDialogProps) {
  const addTarget = useAddTarget();

  const [addName, setAddName] = useState("");
  const [addWebsite, setAddWebsite] = useState("");
  const [addCategory, setAddCategory] = useState("");
  const [addContactName, setAddContactName] = useState("");
  const [addContactRole, setAddContactRole] = useState("");
  const [addContactEmail, setAddContactEmail] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

  const handleAddSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeCampaignId) return;
    setAddError(null);

    try {
      await addTarget.mutateAsync({
        campaign_id: activeCampaignId,
        name: addName,
        website: addWebsite,
        category: addCategory || undefined,
        contact_name: addContactName || undefined,
        contact_role: addContactRole || undefined,
        contact_email: addContactEmail || undefined,
      });

      setAddName("");
      setAddWebsite("");
      setAddCategory("");
      setAddContactName("");
      setAddContactRole("");
      setAddContactEmail("");
      dialogRef.current?.close();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAddError(err.message);
      } else {
        setAddError("Failed to add target company.");
      }
    }
  };

  return (
    <dialog ref={dialogRef} className={styles.dialog}>
      <h2 className={styles.dialogTitle}>Add company target</h2>
      {addError && <div className={styles.errorBanner}>{addError}</div>}
      <form onSubmit={handleAddSubmit} className={styles.form}>
        <div className={styles.field}>
          <label htmlFor="company-name" className={styles.label}>
            Company name
          </label>
          <input
            id="company-name"
            required
            value={addName}
            onChange={(e) => setAddName(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="company-website" className={styles.label}>
            Website or domain
          </label>
          <input
            id="company-website"
            required
            placeholder="e.g. stripe.com"
            value={addWebsite}
            onChange={(e) => setAddWebsite(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="company-category" className={styles.label}>
            Category
          </label>
          <input
            id="company-category"
            value={addCategory}
            onChange={(e) => setAddCategory(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="contact-name" className={styles.label}>
            Contact name
          </label>
          <input
            id="contact-name"
            value={addContactName}
            onChange={(e) => setAddContactName(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="contact-email" className={styles.label}>
            Contact email
          </label>
          <input
            id="contact-email"
            type="email"
            value={addContactEmail}
            onChange={(e) => setAddContactEmail(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.dialogButtons}>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            className={styles.secondaryButton}
          >
            Cancel
          </button>
          <button type="submit" disabled={addTarget.isPending} className={styles.primaryButton}>
            {addTarget.isPending ? "Adding..." : "Add company"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
