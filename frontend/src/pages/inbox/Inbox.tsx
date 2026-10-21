/**
 * Inbox screen displaying received replies with classification override and response conversion (R6, G8, G9).
 */

import { Fragment, useState } from "react";
import { Link, useNavigate } from "react-router";
import {
  useConvertSuggestedReply,
  useInbox,
  useOverrideClassification,
  type InboxItem,
} from "../../api/inbox";
import styles from "./Inbox.module.css";

const CLASSIFICATION_OPTIONS = [
  { value: "interested", label: "Interested", shape: "●", styleClass: styles.statusInterested },
  { value: "question", label: "Question", shape: "▲", styleClass: styles.statusQuestion },
  { value: "declined", label: "Declined", shape: "■", styleClass: styles.statusDeclined },
  { value: "auto_reply", label: "Auto-reply", shape: "◆", styleClass: styles.statusAutoReply },
  { value: "bounce", label: "Bounce", shape: "×", styleClass: styles.statusBounce },
  { value: "other", label: "Other", shape: "○", styleClass: styles.statusOther },
];

function formatDate(isoDate: string): string {
  try {
    const d = new Date(isoDate);
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return isoDate;
  }
}

interface DetailViewerProps {
  item: InboxItem;
  onClose: () => void;
}

function DetailViewer({ item, onClose }: DetailViewerProps) {
  const [editedSuggestion, setEditedSuggestion] = useState(item.suggested_reply || "");
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const convertMutation = useConvertSuggestedReply();
  const navigate = useNavigate();

  const handleConvert = () => {
    convertMutation.mutate(
      {
        messageId: item.id,
        body: editedSuggestion,
      },
      {
        onSuccess: () => {
          setStatusNotice("Draft created in queue.");
          setTimeout(() => {
            navigate("/queue");
          }, 800);
        },
      }
    );
  };

  return (
    <div className={styles.detailPanel} data-testid={`inbox-detail-${item.id}`}>
      <div className={styles.detailHeader}>
        <div>
          <div className={styles.detailTitle}>{item.subject || "(No subject)"}</div>
          <div className={styles.contactInfo}>
            From: {item.contact_name || "Unknown"} ({item.contact_email || "no email"}) &middot; Target:{" "}
            <Link to={`/targets/${item.target_id}`}>{item.company_name}</Link>
          </div>
        </div>
        <button type="button" onClick={onClose} className={styles.closeButton}>
          Close
        </button>
      </div>

      <div>
        <div className={styles.suggestionLabel}>Message Body</div>
        <div className={styles.messageBodyBox}>{item.body || "(Empty message body)"}</div>
      </div>

      {(item.suggested_reply || item.classification === "interested" || item.classification === "question") && (
        <div className={styles.suggestionSection}>
          <div className={styles.suggestionLabel}>Suggested Response</div>
          <textarea
            className={styles.suggestionTextarea}
            value={editedSuggestion}
            onChange={(e) => setEditedSuggestion(e.target.value)}
            placeholder="Edit suggested response before creating a draft..."
          />
          <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
            <button
              type="button"
              onClick={handleConvert}
              disabled={convertMutation.isPending || !editedSuggestion.trim()}
              className={styles.convertButton}
            >
              {convertMutation.isPending ? "Creating draft..." : "Create queue draft"}
            </button>
            {statusNotice && <span className={styles.summaryText}>{statusNotice}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export function Inbox() {
  const [selectedFilter, setSelectedFilter] = useState<string | undefined>(undefined);
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);
  const [localOverrides, setLocalOverrides] = useState<Record<number, string>>({});

  const { data: items, isLoading, isError } = useInbox(selectedFilter);
  const overrideMutation = useOverrideClassification();

  const handleClassChange = (messageId: number, newClass: string) => {
    setLocalOverrides((prev) => ({ ...prev, [messageId]: newClass }));
    overrideMutation.mutate({ messageId, classification: newClass });
  };

  if (isLoading) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <h1 className={styles.title}>Inbox</h1>
          <div className={styles.subtitle}>Incoming sponsor replies and notifications</div>
        </div>
        <div className={styles.loadingText}>Loading inbox.</div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <h1 className={styles.title}>Inbox</h1>
          <div className={styles.subtitle}>Incoming sponsor replies and notifications</div>
        </div>
        <div className={styles.emptyState}>Failed to load inbox replies.</div>
      </div>
    );
  }

  const filters = [
    { label: "All", value: undefined },
    { label: "Interested", value: "interested" },
    { label: "Question", value: "question" },
    { label: "Declined", value: "declined" },
    { label: "Auto-reply", value: "auto_reply" },
    { label: "Bounce", value: "bounce" },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.headerCard}>
        <h1 className={styles.title}>Inbox</h1>
        <div className={styles.subtitle}>
          Incoming replies newest first with classification, summary, and suggested responses
        </div>
      </div>

      <div className={styles.filterCard}>
        <div className={styles.filterBar}>
          {filters.map((f) => (
            <button
              key={f.label}
              type="button"
              className={`${styles.filterButton} ${selectedFilter === f.value ? styles.filterActive : ""}`}
              onClick={() => setSelectedFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {(!items || items.length === 0) ? (
        <div className={styles.emptyState}>
          No replies yet. We check the mailbox every 5 minutes.
        </div>
      ) : (
        <div className={styles.tableCard}>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
            <thead>
              <tr>
                <th style={{ width: "100px" }}>Date</th>
                <th style={{ width: "220px" }}>Company</th>
                <th>Subject & Summary</th>
                <th style={{ width: "160px" }}>Classification</th>
                <th style={{ width: "120px" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const isSelected = selectedItemId === item.id;
                const activeClass = localOverrides[item.id] ?? item.classification ?? "other";
                const opt = CLASSIFICATION_OPTIONS.find((c) => c.value === activeClass);

                return (
                  <Fragment key={item.id}>
                    <tr className={isSelected ? styles.rowSelected : ""}>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
                        {formatDate(item.created_at)}
                      </td>
                      <td>
                        <div className={styles.companyName}>
                          <Link to={`/targets/${item.target_id}`}>{item.company_name}</Link>
                        </div>
                        <div className={styles.domain}>{item.company_domain}</div>
                        {item.contact_email && (
                          <div className={styles.contactInfo}>{item.contact_email}</div>
                        )}
                      </td>
                      <td>
                        <div className={styles.subjectText}>{item.subject || "(No subject)"}</div>
                        {item.summary && <div className={styles.summaryText}>{item.summary}</div>}
                      </td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
                          <span className={`${styles.statusMark} ${opt?.styleClass || styles.statusOther}`}>
                            {opt?.shape || "○"} {opt?.label || activeClass}
                          </span>
                          <select
                            className={styles.classSelect}
                            value={activeClass}
                            onChange={(e) => handleClassChange(item.id, e.target.value)}
                            aria-label={`Change classification for ${item.company_name}`}
                          >
                            {CLASSIFICATION_OPTIONS.map((c) => (
                              <option key={c.value} value={c.value}>
                                {c.shape} {c.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </td>
                      <td>
                        <button
                          type="button"
                          className={styles.actionButton}
                          onClick={() => setSelectedItemId(isSelected ? null : item.id)}
                        >
                          {isSelected ? "Hide" : "Review"}
                        </button>
                      </td>
                    </tr>
                    {isSelected && (
                      <tr>
                        <td colSpan={5} style={{ padding: 0 }}>
                          <DetailViewer
                            item={item}
                            onClose={() => setSelectedItemId(null)}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
        </div>
      )}
    </div>
  );
}
