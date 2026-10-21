import { useState } from "react";
import { Link, useParams } from "react-router";
import { useSession } from "../../api/auth";
import {
  usePrepareTarget,
  useRefreshResearch,
  useTargetDetail,
} from "../../api/targets";
import styles from "./TargetDetail.module.css";
import { TargetContactCard } from "./components/TargetContactCard";
import { TargetDraftEditor } from "./components/TargetDraftEditor";
import { TargetEvidenceSection } from "./components/TargetEvidenceSection";
import { TargetRecommendationCard } from "./components/TargetRecommendationCard";
import { TargetStatusCard } from "./components/TargetStatusCard";
import { TargetThreadSection } from "./components/TargetThreadSection";

export function TargetDetail() {
  const { id } = useParams<{ id: string }>();
  const targetId = Number(id);

  const sessionQuery = useSession();
  const currentUser = sessionQuery.data?.user;

  const targetQuery = useTargetDetail(targetId);
  const prepareMutation = usePrepareTarget();
  const refreshMutation = useRefreshResearch();

  const [actionError, setActionError] = useState<string | null>(null);

  if (targetQuery.isLoading) {
    return <div className={styles.emptyBox}>Loading target details.</div>;
  }

  const target = targetQuery.data;
  if (!target) {
    return (
      <div className={styles.emptyBox}>
        Target not found.{" "}
        <Link to="/targets" className={styles.backLink}>
          Back to targets
        </Link>
      </div>
    );
  }

  const isOwnerOrAdmin =
    currentUser?.role === "admin" || (currentUser && target.owner_id === currentUser.id);

  const handlePrepare = async () => {
    setActionError(null);
    try {
      await prepareMutation.mutateAsync(target.id);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setActionError(err.message);
      } else {
        setActionError("Failed to prepare target.");
      }
    }
  };

  const handleRefresh = async () => {
    setActionError(null);
    try {
      await refreshMutation.mutateAsync(target.id);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setActionError(err.message);
      } else {
        setActionError("Failed to refresh research.");
      }
    }
  };

  const facts = target.facts || [];
  const thread = target.thread || [];

  return (
    <div>
      <div className={styles.header}>
        <div>
          <Link to="/targets" className={styles.backLink}>
            ← Back to targets
          </Link>
          <h1 className={styles.title}>{target.company_name}</h1>
          <div className={styles.subtitle}>
            <span>{target.domain}</span>
            {target.category && ` | ${target.category}`}
            {target.campaign_name && ` | Campaign: ${target.campaign_name}`}
          </div>
        </div>
        <div className={styles.actions}>
          {isOwnerOrAdmin ? (
            <>
              {target.researched_at && (
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={refreshMutation.isPending}
                  className={styles.secondaryButton}
                >
                  {refreshMutation.isPending ? "Refreshing..." : "Refresh research"}
                </button>
              )}
              <button
                type="button"
                onClick={handlePrepare}
                disabled={prepareMutation.isPending}
                className={styles.primaryButton}
              >
                {prepareMutation.isPending
                  ? "Researching..."
                  : target.researched_at
                  ? "Re-prepare target"
                  : "Prepare target"}
              </button>
            </>
          ) : (
            <span className={styles.subtitle}>
              Owned by {target.owner_name || "another organizer"}
            </span>
          )}
        </div>
      </div>

      {actionError && <div className={styles.errorBanner}>{actionError}</div>}

      <TargetContactCard
        target={target}
        isOwnerOrAdmin={Boolean(isOwnerOrAdmin)}
      />

      <TargetStatusCard
        target={target}
        isOwnerOrAdmin={Boolean(isOwnerOrAdmin)}
        onActionError={setActionError}
      />

      <div className={styles.layout}>
        <div className={styles.leftCol}>
          <TargetRecommendationCard target={target} />
          <TargetEvidenceSection facts={facts} />
        </div>

        <div className={styles.rightCol}>
          <section className={styles.section}>
            <div className={styles.sectionTitle}>
              <span>Outreach draft</span>
              {target.draft && (
                <span
                  className={
                    target.draft.status === "approved"
                      ? styles.badgeVerified
                      : styles.badgeUnverified
                  }
                >
                  {target.draft.status === "approved" ? "Approved" : "Draft"}
                </span>
              )}
            </div>

            {!target.draft ? (
              <div className={styles.emptyBox}>
                No draft prepared yet. Click "Prepare target" above to run research and generate an outreach draft.
              </div>
            ) : (
              <TargetDraftEditor
                draft={target.draft}
                isOwnerOrAdmin={Boolean(isOwnerOrAdmin)}
                contactEmail={target.contact?.email}
              />
            )}
          </section>
        </div>
      </div>

      <TargetThreadSection thread={thread} />
    </div>
  );
}
