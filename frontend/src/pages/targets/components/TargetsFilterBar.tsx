import styles from "../Targets.module.css";

interface TargetsFilterBarProps {
  campaigns?: Array<{ id: number; name: string }>;
  activeCampaignId?: number;
  onSelectCampaign: (id: number) => void;
  searchTerm: string;
  onSearchChange: (val: string) => void;
  statusFilter: string;
  onStatusChange: (val: string) => void;
  tierFilter: string;
  onTierChange: (val: string) => void;
  ownerFilter: string;
  onOwnerChange: (val: string) => void;
}

export function TargetsFilterBar({
  campaigns,
  activeCampaignId,
  onSelectCampaign,
  searchTerm,
  onSearchChange,
  statusFilter,
  onStatusChange,
  tierFilter,
  onTierChange,
  ownerFilter,
  onOwnerChange,
}: TargetsFilterBarProps) {
  return (
    <div className={styles.filterRow}>
      {campaigns && campaigns.length > 1 && (
        <select
          value={activeCampaignId ?? ""}
          onChange={(e) => onSelectCampaign(Number(e.target.value))}
          className={styles.selectFilter}
        >
          {campaigns.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      )}

      <input
        type="search"
        placeholder="Search companies..."
        value={searchTerm}
        onChange={(e) => onSearchChange(e.target.value)}
        className={styles.searchInput}
      />

      <select
        value={statusFilter}
        onChange={(e) => onStatusChange(e.target.value)}
        className={styles.selectFilter}
      >
        <option value="">All statuses</option>
        <option value="not_contacted">Not contacted</option>
        <option value="contacted">Contacted</option>
        <option value="follow_up">Follow-up</option>
        <option value="interested">Interested</option>
        <option value="meeting_booked">Meeting booked</option>
        <option value="secured">Secured</option>
        <option value="declined">Declined</option>
        <option value="closed_no_reply">Closed (no reply)</option>
      </select>

      <select
        value={tierFilter}
        onChange={(e) => onTierChange(e.target.value)}
        className={styles.selectFilter}
      >
        <option value="">All tiers</option>
        <option value="cash">Cash</option>
        <option value="goodies">Goodies</option>
        <option value="credits">Credits</option>
      </select>

      <select
        value={ownerFilter}
        onChange={(e) => onOwnerChange(e.target.value)}
        className={styles.selectFilter}
      >
        <option value="">All owners</option>
        <option value="mine">Assigned to me</option>
      </select>
    </div>
  );
}
