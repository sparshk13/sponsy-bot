import { Link } from "react-router";
import styles from "./NotFound.module.css";

export function NotFound() {
  return (
    <div className={styles.card}>
      <h1 className={styles.title}>Page not found</h1>
      <p className={styles.note}>The page you are looking for does not exist or has been moved.</p>
      <Link to="/" className={styles.backButton}>
        Return to Workspace
      </Link>
    </div>
  );
}
