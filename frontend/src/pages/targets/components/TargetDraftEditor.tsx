import { useState } from "react";
import { Link } from "react-router";
import {
  useApproveMessage,
  useDiscardMessage,
  useUpdateMessage,
} from "../../../api/queue";
import styles from "../TargetDetail.module.css";

interface TargetDraftEditorProps {
  draft: NonNullable<import("../../../api/targets").TargetDetail["draft"]>;
  isOwnerOrAdmin: boolean;
  contactEmail?: string | null;
}

export function TargetDraftEditor({
  draft,
  isOwnerOrAdmin,
  contactEmail,
}: TargetDraftEditorProps) {
  const [subject, setSubject] = useState(draft.subject || "");
  const [body, setBody] = useState(draft.body || "");
  const [hasEdited, setHasEdited] = useState(false);

  const updateMessage = useUpdateMessage();
  const approveMessage = useApproveMessage();
  const discardMessage = useDiscardMessage();

  const words = body.trim() ? body.trim().split(/\s+/).length : 0;
  const isFollowUp = draft.kind === "followup" || draft.kind === "follow_up";
  const minWords = isFollowUp ? 40 : 80;
  const maxWords = isFollowUp ? 100 : 160;
  const isWordCountValid = words >= minWords && words <= maxWords;
  const isApproved = draft.status === "approved";

  const handleSave = () => {
    updateMessage.mutate(
      {
        messageId: draft.id,
        payload: { subject, body },
      },
      {
        onSuccess: () => setHasEdited(false),
      }
    );
  };

  const handleApprove = () => {
    if (!isOwnerOrAdmin) return;
    approveMessage.mutate(draft.id);
  };

  const handleDiscard = () => {
    if (!isOwnerOrAdmin) return;
    discardMessage.mutate(draft.id);
  };

  return (
    <div className={styles.draftBox}>
      {isApproved && (
        <div className={styles.badgeAssumption}>
          Message approved. Any edit will void approval and return status to draft.
        </div>
      )}
      {!contactEmail && (
        <div className={styles.errorBanner}>
          No valid contact email found. Add a contact before approving.
        </div>
      )}

      <div>
        <label htmlFor={`target-subj-${draft.id}`} className={styles.recLabel}>
          Subject
        </label>
        <input
          id={`target-subj-${draft.id}`}
          className={styles.draftInput}
          style={{ width: "100%", marginTop: "4px" }}
          value={subject}
          onChange={(e) => {
            setSubject(e.target.value);
            setHasEdited(true);
          }}
        />
      </div>

      <div>
        <div className={styles.draftMeta}>
          <label htmlFor={`target-body-${draft.id}`} className={styles.recLabel}>
            Body
          </label>
          <span style={{ color: isWordCountValid ? "var(--approve)" : "var(--stop)" }}>
            {words} words ({isWordCountValid ? "Valid" : `${minWords}-${maxWords} required`})
          </span>
        </div>
        <textarea
          id={`target-body-${draft.id}`}
          className={styles.draftTextarea}
          style={{ width: "100%", marginTop: "4px" }}
          rows={10}
          value={body}
          onChange={(e) => {
            setBody(e.target.value);
            setHasEdited(true);
          }}
        />
      </div>

      {draft.attachment_id && (
        <div style={{ fontSize: "12px", color: "var(--go)", marginTop: "4px" }}>
          Brochure attached:{" "}
          <a
            href={`/api/brochures/${draft.attachment_id}`}
            download
            style={{ textDecoration: "underline", color: "inherit" }}
          >
            Download PDF
          </a>
        </div>
      )}

      <div className={styles.draftActions}>
        <button
          type="button"
          className={styles.secondaryButton}
          disabled={!hasEdited || updateMessage.isPending}
          onClick={handleSave}
        >
          {updateMessage.isPending ? "Saving..." : "Save Edit"}
        </button>

        {isOwnerOrAdmin && (
          <button
            type="button"
            className={styles.primaryButton}
            disabled={
              isApproved ||
              hasEdited ||
              !contactEmail ||
              !isWordCountValid ||
              approveMessage.isPending
            }
            onClick={handleApprove}
          >
            {approveMessage.isPending ? "Approving..." : isApproved ? "Approved" : "Approve Draft"}
          </button>
        )}

        {isOwnerOrAdmin && (
          <button
            type="button"
            className={styles.secondaryButton}
            style={{ color: "var(--stop)", borderColor: "var(--stop)" }}
            disabled={discardMessage.isPending}
            onClick={handleDiscard}
          >
            Discard
          </button>
        )}

        <Link to="/queue" className={styles.backLink} style={{ marginLeft: "auto" }}>
          View in Queue →
        </Link>
      </div>
    </div>
  );
}
