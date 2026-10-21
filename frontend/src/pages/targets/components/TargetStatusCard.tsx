import { useState, type FormEvent } from "react";
import { type TargetDetail, useRecordOutcome, useUpdateTargetStatus } from "../../../api/targets";
import { formatDateIst, formatDateTimeIst, formatInr } from "../../../formatters";
import styles from "../TargetDetail.module.css";

interface TargetStatusCardProps {
  target: TargetDetail;
  isOwnerOrAdmin: boolean;
  onActionError: (err: string | null) => void;
}

export function TargetStatusCard({
  target,
  isOwnerOrAdmin,
  onActionError,
}: TargetStatusCardProps) {
  const statusMutation = useUpdateTargetStatus();
  const outcomeMutation = useRecordOutcome();

  const [outcomeKind, setOutcomeKind] = useState<"cash" | "goodies" | "credits">("cash");
  const [outcomeAmount, setOutcomeAmount] = useState<string>("");
  const [outcomeNotes, setOutcomeNotes] = useState<string>("");

  const outcomes = target.outcomes || [];

  const handleStatusChange = async (
    newStatus: "meeting_booked" | "closed_no_reply" | "declined"
  ) => {
    onActionError(null);
    try {
      await statusMutation.mutateAsync({
        targetId: target.id,
        payload: { status: newStatus },
      });
    } catch (err: unknown) {
      if (err instanceof Error) {
        onActionError(err.message);
      } else {
        onActionError("Failed to update status.");
      }
    }
  };

  const handleRecordOutcome = async (e: FormEvent) => {
    e.preventDefault();
    onActionError(null);
    try {
      const parsedAmount = outcomeAmount.trim() ? parseInt(outcomeAmount.trim(), 10) : undefined;
      await outcomeMutation.mutateAsync({
        targetId: target.id,
        payload: {
          kind: outcomeKind,
          amount_inr: parsedAmount,
          description: outcomeNotes.trim() || undefined,
        },
      });
      setOutcomeAmount("");
      setOutcomeNotes("");
    } catch (err: unknown) {
      if (err instanceof Error) {
        onActionError(err.message);
      } else {
        onActionError("Failed to record outcome.");
      }
    }
  };

  return (
    <div className={styles.statusCard}>
      <div className={styles.stageBar}>
        <span className={styles.recLabel}>Stage & Status:</span>
        <span style={{ fontWeight: 600, textTransform: "capitalize" }}>
          {target.status.replace("_", " ")}
        </span>

        {target.status === "interested" && isOwnerOrAdmin && (
          <button
            type="button"
            className={styles.primaryButton}
            onClick={() => handleStatusChange("meeting_booked")}
            disabled={statusMutation.isPending}
          >
            {statusMutation.isPending ? "Updating..." : "Mark meeting booked"}
          </button>
        )}

        {(target.status === "contacted" || target.status === "follow_up") && (
          <div style={{ display: "flex", gap: "8px", alignItems: "center", marginLeft: "auto" }}>
            <span style={{ fontSize: "12px", color: "var(--ink-2)" }}>
              Follow-up: {target.followup_count} of 2 sent.{" "}
              {target.next_followup_at
                ? `Next due: ${formatDateTimeIst(target.next_followup_at)}`
                : "No follow-up scheduled."}
            </span>
            {isOwnerOrAdmin && (
              <>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => handleStatusChange("closed_no_reply")}
                  disabled={statusMutation.isPending}
                >
                  Close (no reply)
                </button>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  style={{ color: "var(--stop)", borderColor: "var(--stop)" }}
                  onClick={() => handleStatusChange("declined")}
                  disabled={statusMutation.isPending}
                >
                  Declined
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {(target.status === "meeting_booked" ||
        target.status === "interested" ||
        target.status === "secured") && (
        <div className={styles.outcomeForm}>
          <div style={{ fontWeight: 600, fontSize: "14px" }}>
            {target.status === "secured" ? "Secured Sponsorship" : "Record Outcome"}
          </div>

          {outcomes.length > 0 && (
            <div className={styles.tableWrapper} style={{ marginTop: "4px" }}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Amount</th>
                    <th>Notes</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {outcomes.map((o) => (
                    <tr key={o.id}>
                      <td style={{ textTransform: "capitalize" }}>{o.kind}</td>
                      <td>{formatInr(o.amount_inr)}</td>
                      <td>{o.description || "-"}</td>
                      <td>{formatDateIst(o.confirmed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {isOwnerOrAdmin && (
            <form
              onSubmit={handleRecordOutcome}
              style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "4px" }}
            >
              <div className={styles.formGrid}>
                <div>
                  <label htmlFor="outcome-kind" className={styles.recLabel}>
                    Tier / Kind
                  </label>
                  <select
                    id="outcome-kind"
                    className={styles.draftInput}
                    style={{ width: "100%", marginTop: "4px" }}
                    value={outcomeKind}
                    onChange={(e) =>
                      setOutcomeKind(e.target.value as "cash" | "goodies" | "credits")
                    }
                  >
                    <option value="cash">Cash</option>
                    <option value="goodies">Goodies</option>
                    <option value="credits">Credits</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="outcome-amount" className={styles.recLabel}>
                    Amount in INR (if cash)
                  </label>
                  <input
                    id="outcome-amount"
                    type="number"
                    placeholder="e.g. 150000"
                    className={styles.draftInput}
                    style={{ width: "100%", marginTop: "4px" }}
                    value={outcomeAmount}
                    onChange={(e) => setOutcomeAmount(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <label htmlFor="outcome-notes" className={styles.recLabel}>
                  Outcome Notes
                </label>
                <input
                  id="outcome-notes"
                  type="text"
                  placeholder="Details about deliverables, booths, or credits"
                  className={styles.draftInput}
                  style={{ width: "100%", marginTop: "4px" }}
                  value={outcomeNotes}
                  onChange={(e) => setOutcomeNotes(e.target.value)}
                />
              </div>
              <div>
                <button
                  type="submit"
                  className={styles.primaryButton}
                  disabled={outcomeMutation.isPending}
                >
                  {outcomeMutation.isPending ? "Saving..." : "Confirm outcome & mark secured"}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
