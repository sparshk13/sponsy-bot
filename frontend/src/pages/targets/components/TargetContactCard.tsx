import { useState, type FormEvent } from "react";
import { type TargetDetail, useFindContact, useUpdateContact } from "../../../api/targets";
import styles from "../TargetDetail.module.css";

interface TargetContactCardProps {
  target: TargetDetail;
  isOwnerOrAdmin: boolean;
}

export function TargetContactCard({ target, isOwnerOrAdmin }: TargetContactCardProps) {
  const findContactMutation = useFindContact();
  const updateContactMutation = useUpdateContact();

  const [showContactForm, setShowContactForm] = useState(false);
  const [contactName, setContactName] = useState("");
  const [contactRole, setContactRole] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactFeedback, setContactFeedback] = useState<string | null>(null);

  const handleFindContact = async () => {
    setContactFeedback(null);
    try {
      const res = await findContactMutation.mutateAsync(target.id);
      if (res.found && res.contact?.email) {
        setContactFeedback(
          `Found ${res.contact.name || "contact"} (${res.contact.role || "role"}): ${res.contact.email}. Saved to target.`
        );
      } else {
        setContactFeedback("No verified contact found for this domain on Hunter.");
      }
    } catch (err: unknown) {
      setContactFeedback(err instanceof Error ? err.message : "Failed to find contact on Hunter.");
    }
  };

  const handleSaveContact = async (e: FormEvent) => {
    e.preventDefault();
    setContactFeedback(null);
    try {
      await updateContactMutation.mutateAsync({
        targetId: target.id,
        payload: {
          name: contactName.trim() || undefined,
          role: contactRole.trim() || undefined,
          email: contactEmail.trim().toLowerCase(),
        },
      });
      setShowContactForm(false);
      setContactFeedback("Contact updated.");
    } catch (err: unknown) {
      setContactFeedback(err instanceof Error ? err.message : "Failed to save contact.");
    }
  };

  return (
    <div className={styles.statusCard}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div>
          <span className={styles.recLabel}>Contact:</span>{" "}
          {target.contact?.email ? (
            <span>
              <strong>{target.contact.name || "Unnamed"}</strong>
              {target.contact.role && ` (${target.contact.role})`},{" "}
              <span className={styles.monoCol}>{target.contact.email}</span>{" "}
              <span
                style={{
                  fontSize: "11px",
                  color: "var(--ink-2)",
                  textTransform: "uppercase",
                }}
              >
                [{target.contact.source}]
              </span>
            </span>
          ) : (
            <span style={{ color: "var(--ink-2)" }}>No contact on file.</span>
          )}
        </div>
        {isOwnerOrAdmin && (
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={handleFindContact}
              disabled={findContactMutation.isPending}
            >
              {findContactMutation.isPending ? "Searching Hunter..." : "Find contact (Hunter)"}
            </button>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => {
                if (!showContactForm && target.contact) {
                  setContactName(target.contact.name || "");
                  setContactRole(target.contact.role || "");
                  setContactEmail(target.contact.email || "");
                }
                setShowContactForm(!showContactForm);
              }}
            >
              {showContactForm
                ? "Cancel"
                : target.contact?.email
                ? "Edit contact"
                : "Add contact"}
            </button>
          </div>
        )}
      </div>

      {contactFeedback && (
        <div style={{ fontSize: "12px", marginTop: "6px", color: "var(--ink-2)" }}>
          {contactFeedback}
        </div>
      )}

      {showContactForm && isOwnerOrAdmin && (
        <form
          onSubmit={handleSaveContact}
          style={{
            marginTop: "12px",
            display: "flex",
            gap: "8px",
            flexWrap: "wrap",
            alignItems: "flex-end",
          }}
        >
          <div>
            <label htmlFor="contact-name" style={{ fontSize: "12px", display: "block" }}>
              Name
            </label>
            <input
              id="contact-name"
              type="text"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              placeholder="Contact name"
              className={styles.draftInput}
            />
          </div>
          <div>
            <label htmlFor="contact-role" style={{ fontSize: "12px", display: "block" }}>
              Role
            </label>
            <input
              id="contact-role"
              type="text"
              value={contactRole}
              onChange={(e) => setContactRole(e.target.value)}
              placeholder="e.g. Sponsorship Lead"
              className={styles.draftInput}
            />
          </div>
          <div>
            <label htmlFor="contact-email" style={{ fontSize: "12px", display: "block" }}>
              Email *
            </label>
            <input
              id="contact-email"
              type="email"
              required
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              placeholder="contact@domain.com"
              className={styles.draftInput}
            />
          </div>
          <button
            type="submit"
            disabled={updateContactMutation.isPending}
            className={styles.primaryButton}
          >
            {updateContactMutation.isPending ? "Saving..." : "Save contact"}
          </button>
        </form>
      )}
    </div>
  );
}
