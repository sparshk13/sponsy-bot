import type { ReactNode } from "react";
import { Navigate, NavLink, useNavigate } from "react-router";
import { useLogout, useSession } from "../api/auth";
import { useToday } from "../api/inbox";
import styles from "./Shell.module.css";

interface ShellProps {
  children: ReactNode;
}

interface NavEntry {
  to: string;
  label: string;
  badge?: number;
  adminOnly?: boolean;
}

const NAV_ENTRIES: NavEntry[] = [
  { to: "/", label: "Today" },
  { to: "/targets", label: "Targets" },
  { to: "/queue", label: "Approvals" },
  { to: "/inbox", label: "Inbox" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/memory", label: "Memory" },
  { to: "/usage", label: "Usage" },
  { to: "/admin", label: "Admin", adminOnly: true },
];

const AVATAR_GRADIENTS = [
  "linear-gradient(135deg, #E0C3FC 0%, #8EC5FC 100%)",
  "linear-gradient(135deg, #FFD1FF 0%, #FAD0C4 100%)",
  "linear-gradient(135deg, #D4FC79 0%, #96E6A1 100%)",
  "linear-gradient(135deg, #FFA8A8 0%, #FCFF00 100%)",
];

function getAvatarStyle(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash << 5) - hash + id.charCodeAt(i);
  }
  return {
    background: AVATAR_GRADIENTS[Math.abs(hash) % AVATAR_GRADIENTS.length],
  };
}

export function Shell({ children }: ShellProps) {
  const sessionQuery = useSession();
  const todayQuery = useToday();
  const logoutMutation = useLogout();
  const navigate = useNavigate();

  if (sessionQuery.isLoading) {
    return <div className={styles.loading}>Loading...</div>;
  }

  if (sessionQuery.isError || !sessionQuery.data?.user) {
    return <Navigate to="/login" replace />;
  }

  const user = sessionQuery.data.user;

  const handleSignOut = async () => {
    await logoutMutation.mutateAsync();
    navigate("/login", { replace: true });
  };

  const pendingApprovals = todayQuery.data?.pending_approvals ?? 0;
  const unreadReplies = todayQuery.data?.unread_replies ?? 0;

  const navItems = NAV_ENTRIES.filter(
    (item) => !item.adminOnly || user.role === "admin"
  ).map((entry) => {
    if (entry.to === "/queue" && pendingApprovals > 0) {
      return { ...entry, badge: pendingApprovals };
    }
    if (entry.to === "/inbox" && unreadReplies > 0) {
      return { ...entry, badge: unreadReplies };
    }
    return entry;
  });

  const initials = user.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className={styles.layout}>
      <aside className={styles.rail}>
        <div className={styles.brand}>
          <span>Sponsy</span>
          <span className={styles.brandDot} />
        </div>
        <nav className={styles.nav}>
          {navItems.map((entry) => (
            <NavLink
              key={entry.to}
              to={entry.to}
              end={entry.to === "/"}
              className={({ isActive }) =>
                `${styles.navItem} ${isActive ? styles.activeItem : ""}`
              }
            >
              <span>{entry.label}</span>
              {entry.badge !== undefined && (
                <span className={styles.badge}>{entry.badge}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className={styles.userInfo}>
          <div className={styles.userHeader}>
            <div
              className={styles.avatar}
              style={getAvatarStyle(String(user.id))}
            >
              {initials}
            </div>
            <div className={styles.userMeta}>
              <span className={styles.userName}>{user.name}</span>
              <span className={styles.userRole}>{user.role}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleSignOut}
            className={styles.signOutButton}
          >
            Sign out
          </button>
        </div>

        <footer className={styles.footer}>keys: j k enter esc /</footer>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
