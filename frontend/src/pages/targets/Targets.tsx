import { useRef, useState } from "react";
import { Link } from "react-router";
import { useSession } from "../../api/auth";
import {
  useCampaigns,
  useClaimTarget,
  useTargets,
  useUnlockCooldown,
  type TargetItem,
} from "../../api/targets";
import { GoogleSheetsModal } from "../../components/GoogleSheetsModal";
import styles from "./Targets.module.css";
import { AddCompanyDialog } from "./components/AddCompanyDialog";
import { ImportCsvDialog } from "./components/ImportCsvDialog";
import { TargetsFilterBar } from "./components/TargetsFilterBar";

export function Targets() {
  const sessionQuery = useSession();
  const currentUser = sessionQuery.data?.user;

  const [selectedCampaignId, setSelectedCampaignId] = useState<number | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [tierFilter, setTierFilter] = useState<string>("");
  const [ownerFilter, setOwnerFilter] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState<string>("");

  const campaignsQuery = useCampaigns();
  const activeCampaignId =
    selectedCampaignId ??
    (campaignsQuery.data && campaignsQuery.data.length > 0
      ? campaignsQuery.data[0].id
      : undefined);

  const filterOwnerId =
    ownerFilter === "mine" && currentUser ? currentUser.id : undefined;

  const targetsQuery = useTargets({
    campaign_id: activeCampaignId,
    status: statusFilter || undefined,
    tier: tierFilter || undefined,
    owner_id: filterOwnerId,
    search: searchTerm || undefined,
  });

  const claimTarget = useClaimTarget();
  const unlockCooldown = useUnlockCooldown();

  const addDialogRef = useRef<HTMLDialogElement>(null);
  const importDialogRef = useRef<HTMLDialogElement>(null);
  const sheetsDialogRef = useRef<HTMLDialogElement>(null);

  const targets = targetsQuery.data || [];
  const myTargetsCount = currentUser
    ? targets.filter((t) => t.owner_id === currentUser.id).length
    : 0;

  const handleClaim = async (targetId: number) => {
    try {
      await claimTarget.mutateAsync(targetId);
    } catch (err: unknown) {
      if (err instanceof Error) {
        alert(err.message);
      }
    }
  };

  const handleUnlock = async (targetId: number) => {
    try {
      await unlockCooldown.mutateAsync(targetId);
    } catch (err: unknown) {
      if (err instanceof Error) {
        alert(err.message);
      }
    }
  };

  const renderPriority = (priority: string | null) => {
    switch (priority) {
      case "high":
      case "A":
        return <span className={`${styles.priorityBadge} ${styles.priorityA}`}>A</span>;
      case "medium":
      case "B":
        return <span className={`${styles.priorityBadge} ${styles.priorityB}`}>B</span>;
      case "low":
      case "C":
        return <span className={`${styles.priorityBadge} ${styles.priorityC}`}>C</span>;
      default:
        return <span className={`${styles.priorityBadge} ${styles.priorityC}`}>-</span>;
    }
  };

  const renderStatus = (status: string) => {
    let dotColor = "var(--ink-muted)";
    if (status === "interested" || status === "secured") dotColor = "var(--online)";
    else if (status === "meeting_booked" || status === "follow_up") dotColor = "var(--brand-peach)";
    else if (status === "declined") dotColor = "var(--stop)";
    else if (status === "contacted") dotColor = "var(--brand)";

    return (
      <span className={styles.statusPill}>
        <span className={styles.statusDot} style={{ backgroundColor: dotColor }} />
        <span>{status.replace(/_/g, " ")}</span>
      </span>
    );
  };

  const renderOwnerAction = (target: TargetItem) => {
    if (!currentUser) return null;
    if (target.owner_id === currentUser.id) {
      return <span className={styles.myTargetTag}>Claimed by you</span>;
    }
    if (target.owner_id) {
      return (
        <span className={styles.claimedTag}>
          Owned by <span>{target.owner_name || "organizer"}</span>
        </span>
      );
    }
    return (
      <button
        type="button"
        onClick={() => handleClaim(target.id)}
        disabled={claimTarget.isPending}
        className={styles.claimButton}
      >
        Claim
      </button>
    );
  };

  return (
    <div className={styles.container}>
      <div className={styles.headerCard}>
        <div className={styles.titleCol}>
          <h1 className={styles.title}>Targets</h1>
          <p className={styles.subtitle}>
            {targets.length} companies tracked across active campaigns.{" "}
            {currentUser && `You own ${myTargetsCount}.`}
          </p>
        </div>
        <div className={styles.actions}>
          <button
            type="button"
            onClick={() => sheetsDialogRef.current?.showModal()}
            className={styles.secondaryButton}
          >
            Google Sheets
          </button>
          <button
            type="button"
            onClick={() => importDialogRef.current?.showModal()}
            className={styles.secondaryButton}
          >
            Import CSV
          </button>
          <button
            type="button"
            onClick={() => addDialogRef.current?.showModal()}
            className={styles.primaryButton}
          >
            Add company
          </button>
        </div>
      </div>

      <div className={styles.filterCard}>
        <TargetsFilterBar
          campaigns={campaignsQuery.data}
          activeCampaignId={activeCampaignId}
          onSelectCampaign={setSelectedCampaignId}
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          statusFilter={statusFilter}
          onStatusChange={setStatusFilter}
          tierFilter={tierFilter}
          onTierChange={setTierFilter}
          ownerFilter={ownerFilter}
          onOwnerChange={setOwnerFilter}
        />
      </div>

      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Company</th>
                <th>Tier</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Owner</th>
                <th>Contact</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {targetsQuery.isLoading ? (
                <tr>
                  <td colSpan={7} className={styles.loading}>
                    Loading targets...
                  </td>
                </tr>
              ) : targets.length === 0 ? (
                <tr>
                  <td colSpan={7} className={styles.emptyState}>
                    No companies yet. Import a CSV or add one by hand.
                  </td>
                </tr>
              ) : (
                targets.map((target) => (
                  <tr key={target.id}>
                    <td>
                      <Link to={`/targets/${target.id}`} className={styles.companyLink}>
                        {target.company_name}
                      </Link>
                      <span className={styles.domain}>{target.domain}</span>
                      {target.cooldown_active && (
                        <span className={styles.cooldownBadge} title="Contacted within 90 days">
                          Cooldown
                        </span>
                      )}
                    </td>
                    <td>
                      {target.tier ? (
                        <span className={styles.tierPill}>{target.tier}</span>
                      ) : (
                        <span style={{ color: "var(--ink-muted)" }}>-</span>
                      )}
                    </td>
                    <td>{renderPriority(target.priority)}</td>
                    <td>{renderStatus(target.status)}</td>
                    <td>
                      {currentUser && target.owner_id === currentUser.id
                        ? "You"
                        : target.owner_name || "-"}
                    </td>
                    <td>
                      {target.contact?.email ? (
                        <div>
                          <div style={{ fontWeight: 500 }}>{target.contact.name || "Contact"}</div>
                          <div className={styles.domain}>{target.contact.email}</div>
                        </div>
                      ) : (
                        <span style={{ color: "var(--ink-muted)" }}>No contact</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                        {renderOwnerAction(target)}
                        {target.cooldown_active && currentUser?.role === "admin" && (
                          <button
                            type="button"
                            onClick={() => handleUnlock(target.id)}
                            disabled={unlockCooldown.isPending}
                            className={styles.secondaryButton}
                          >
                            Unlock
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <AddCompanyDialog
        dialogRef={addDialogRef}
        activeCampaignId={activeCampaignId}
      />

      <ImportCsvDialog
        dialogRef={importDialogRef}
        activeCampaignId={activeCampaignId}
      />

      <GoogleSheetsModal dialogRef={sheetsDialogRef} />
    </div>
  );
}
