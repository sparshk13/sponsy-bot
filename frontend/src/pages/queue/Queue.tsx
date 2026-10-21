/**
 * Approval queue screen for reviewing and approving drafts.
 */

import { Fragment, useState } from "react";
import { Link } from "react-router";
import {
  useApproveMessage,
  useDiscardMessage,
  useQueue,
  useUpdateMessage,
  type QueueItem,
} from "../../api/queue";
import styles from "./Queue.module.css";

function countWords(text: string): number {
  if (!text || !text.trim()) return 0;
  return text.trim().split(/\s+/).length;
}

interface DraftEditorProps {
  item: QueueItem;
  onClose: () => void;
}

function DraftEditor({ item, onClose }: DraftEditorProps) {
  const [subject, setSubject] = useState(item.subject || "");
  const [body, setBody] = useState(item.body || "");
  const [hasEdited, setHasEdited] = useState(false);

  const updateMessage = useUpdateMessage();
  const approveMessage = useApproveMessage();
  const discardMessage = useDiscardMessage();

  const isFollowUp = item.kind === "followup" || item.kind === "follow_up";
  const minWords = isFollowUp ? 40 : 80;
  const maxWords = isFollowUp ? 100 : 160;
  const words = countWords(body);
  const isWordCountValid = words >= minWords && words <= maxWords;



  const handleSubjectChange = (val: string) => {
    setSubject(val);
    setHasEdited(true);
  };

  const handleBodyChange = (val: string) => {
    setBody(val);
    setHasEdited(true);
  };

  const handleSave = () => {
    updateMessage.mutate(
      {
        messageId: item.id,
        payload: { subject, body },
      },
      {
        onSuccess: () => {
          setHasEdited(false);
        },
      }
    );
  };

  const handleApprove = () => {
    if (!item.is_owner) return;
    approveMessage.mutate(item.id, {
      onSuccess: () => {
        onClose();
      },
    });
  };

  const handleDiscard = () => {
    if (!item.is_owner) return;
    discardMessage.mutate(item.id, {
      onSuccess: () => {
        onClose();
      },
    });
  };

  const isApproved = item.status === "approved";

  return (
    <div className={styles.reviewPanel} data-testid={`draft-editor-${item.id}`}>
      {isApproved && (
        <div className={styles.voidNotice}>
          Notice: Message is currently approved. Any edit will void approval and return status to draft.
        </div>
      )}
      {!item.contact_email && (
        <div className={styles.voidNotice}>
          Target has no valid contact email. Add contact details on Target page before approving.
        </div>
      )}

      <div className={styles.editorGroup}>
        <label htmlFor={`subj-${item.id}`} className={styles.editorLabel}>
          Subject Line
        </label>
        <input
          id={`subj-${item.id}`}
          className={styles.input}
          value={subject}
          onChange={(e) => handleSubjectChange(e.target.value)}
        />
      </div>

      <div className={styles.editorGroup}>
        <div className={styles.metaRow}>
          <label htmlFor={`body-${item.id}`} className={styles.editorLabel}>
            Email Body (Plain Text)
          </label>
          <span className={isWordCountValid ? styles.wordCountValid : styles.wordCountInvalid}>
            {words} words{" "}
            {isWordCountValid
              ? `(Valid ${minWords}-${maxWords})`
              : `(Required: ${minWords}-${maxWords} words)`}
          </span>
        </div>
        <textarea
          id={`body-${item.id}`}
          className={styles.textarea}
          rows={10}
          value={body}
          onChange={(e) => handleBodyChange(e.target.value)}
        />
      </div>

      <div className={styles.actionRow}>
        <button
          type="button"
          className={styles.btnSecondary}
          disabled={!hasEdited || updateMessage.isPending}
          onClick={handleSave}
        >
          {updateMessage.isPending ? "Saving..." : "Save Edit"}
        </button>

        {item.is_owner && (
          <button
            type="button"
            className={styles.btnPrimary}
            data-testid={`approve-btn-${item.id}`}
            disabled={
              isApproved ||
              hasEdited ||
              !item.contact_email ||
              !isWordCountValid ||
              approveMessage.isPending
            }
            onClick={handleApprove}
          >
            {approveMessage.isPending ? "Approving..." : isApproved ? "Approved" : "Approve Draft"}
          </button>
        )}

        {item.is_owner && (
          <button
            type="button"
            className={styles.btnDanger}
            disabled={discardMessage.isPending}
            onClick={handleDiscard}
          >
            Discard
          </button>
        )}

        <button type="button" className={styles.btnSecondary} onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

export function Queue() {
  const { data: queue, isLoading, error } = useQueue();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <h1 className={styles.title}>Approval queue</h1>
          <p className={styles.subtitle}>Draft outreach messages awaiting human review and approval.</p>
        </div>
        <div className={styles.loading}>Loading drafts...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <h1 className={styles.title}>Approval queue</h1>
          <p className={styles.subtitle}>Draft outreach messages awaiting human review and approval.</p>
        </div>
        <div className={styles.voidNotice}>{error.message}</div>
      </div>
    );
  }

  const items = queue || [];

  return (
    <div className={styles.container}>
      <div className={styles.headerCard}>
        <h1 className={styles.title}>Approval queue</h1>
        <p className={styles.subtitle}>
          Draft outreach messages awaiting human review. Only manual review and approval can release emails to the send queue.
        </p>
      </div>

      <div className={styles.statusNotice}>
        Sending window: Weekdays, randomized gap. Max 40 emails/day cap enforced.
      </div>

      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
          <thead>
            <tr>
              <th>Company</th>
              <th>Campaign</th>
              <th>Tier</th>
              <th>Recipient</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={6} className={styles.emptyState}>
                  No drafts awaiting approval in the queue.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <Fragment key={item.id}>
                  <tr
                    className={selectedId === item.id ? styles.rowSelected : undefined}
                  >
                    <td>
                      <div className={styles.companyName}>
                        <Link to={`/targets/${item.target_id}`}>{item.company_name}</Link>
                      </div>
                      <div className={styles.domain}>{item.company_domain}</div>
                    </td>
                    <td>{item.campaign_name}</td>
                    <td>
                      <span className={styles.tag}>{item.tier || "Unspecified"}</span>
                    </td>
                    <td>
                      <div>{item.contact_name || "Unassigned"}</div>
                      <div className={styles.domain}>{item.contact_email || "No email"}</div>
                    </td>
                    <td>
                      <span
                        className={
                          item.status === "approved"
                            ? styles.statusApproved
                            : styles.statusDraft
                        }
                      >
                        {item.status === "approved" ? "Approved" : "Draft"}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className={styles.btnSecondary}
                        onClick={() => setSelectedId(selectedId === item.id ? null : item.id)}
                      >
                        {selectedId === item.id ? "Hide" : "Inspect / Edit"}
                      </button>
                    </td>
                  </tr>
                  {selectedId === item.id && (
                    <tr key={`editor-${item.id}`}>
                      <td colSpan={6} style={{ padding: 0 }}>
                        <DraftEditor item={item} onClose={() => setSelectedId(null)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
      </div>
    </div>
  );
}
