import { useContext } from "react";
import { QueryClientContext } from "@tanstack/react-query";
import { Link } from "react-router";
import { useToday, type TodayMetrics } from "../../api/inbox";
import styles from "./Today.module.css";

interface TodayViewProps {
  data?: TodayMetrics;
}

function TodayView({ data }: TodayViewProps) {
  const pendingApprovals = data?.pending_approvals ?? 0;
  const unreadReplies = data?.unread_replies ?? 0;
  const dueFollowups = data?.due_followups ?? 0;
  const sentToday = data?.sent_today ?? 0;
  const sendCap = data?.send_cap ?? 30;

  return (
    <div className={styles.container}>
      <header className={styles.headerCard}>
        <div className={styles.titleArea}>
          <h1 className={styles.title}>Today</h1>
          <p className={styles.subtitle}>
            {pendingApprovals} targets waiting for approval
          </p>
        </div>
        <div className={styles.statsPill}>
          <span>Sent today: {sentToday} of {sendCap}</span>
        </div>
      </header>

      <div className={styles.grid}>
        <section className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.sectionHeading}>Waiting for your approval</h2>
            <span className={styles.countBadge}>{pendingApprovals}</span>
          </div>
          {pendingApprovals > 0 ? (
            <div className={styles.itemList}>
              <Link to="/queue" className={styles.itemRow}>
                <div>
                  <div className={styles.itemTitle}>{pendingApprovals} outreach draft(s) ready</div>
                  <div className={styles.itemSub}>Click to review and dispatch from queue</div>
                </div>
                <span>&rarr;</span>
              </Link>
            </div>
          ) : (
            <div className={styles.emptyBox}>Nothing is waiting for your approval.</div>
          )}
        </section>

        <section className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.sectionHeading}>Replies to read</h2>
            <span className={styles.countBadge}>{unreadReplies}</span>
          </div>
          {unreadReplies > 0 ? (
            <div className={styles.itemList}>
              <Link to="/inbox" className={styles.itemRow}>
                <div>
                  <div className={styles.itemTitle}>{unreadReplies} new sponsor response(s)</div>
                  <div className={styles.itemSub}>Click to view inbox and suggested replies</div>
                </div>
                <span>&rarr;</span>
              </Link>
            </div>
          ) : (
            <div className={styles.emptyBox}>
              No replies yet. We check the mailbox every 5 minutes.
            </div>
          )}
        </section>

        <section className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.sectionHeading}>Follow-ups due</h2>
            <span className={styles.countBadge}>{dueFollowups}</span>
          </div>
          {dueFollowups > 0 ? (
            <div className={styles.itemList}>
              <Link to="/targets" className={styles.itemRow}>
                <div>
                  <div className={styles.itemTitle}>{dueFollowups} target(s) due for follow-up</div>
                  <div className={styles.itemSub}>Paced automatically during sending window</div>
                </div>
                <span>&rarr;</span>
              </Link>
            </div>
          ) : (
            <div className={styles.emptyBox}>No follow-ups due.</div>
          )}
        </section>
      </div>
    </div>
  );
}

function TodayWithQuery() {
  const todayQuery = useToday();
  return <TodayView data={todayQuery.data} />;
}

export function Today() {
  const client = useContext(QueryClientContext);
  if (!client) {
    return <TodayView />;
  }
  return <TodayWithQuery />;
}
