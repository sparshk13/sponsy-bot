import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { useLogin, useLoginCode, useSession } from "../../api/auth";
import styles from "./Login.module.css";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const sessionQuery = useSession();
  const loginMutation = useLogin();
  const loginCodeMutation = useLoginCode();

  if (sessionQuery.data?.user) {
    return <Navigate to="/" replace />;
  }

  const isExpired = searchParams.get("reason") === "expired";

  const handleCredentialsSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    try {
      const res = await loginMutation.mutateAsync({ email, password });
      if (res.requires_2fa && res.pending_token) {
        setPendingToken(res.pending_token);
        return;
      }
      navigate("/", { replace: true });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("That email and password do not match.");
      }
    }
  };

  const handleCodeSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!pendingToken) return;
    setErrorMessage(null);

    try {
      await loginCodeMutation.mutateAsync({ pending_token: pendingToken, code });
      navigate("/", { replace: true });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Invalid authentication code or recovery code.");
      }
    }
  };

  const handleCancel2FA = () => {
    setPendingToken(null);
    setCode("");
    setErrorMessage(null);
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.brandHeader}>
          <span className={styles.brandName}>sponsy</span>
          <span className={styles.brandDot} />
        </div>

        <h1 className={styles.title}>
          {pendingToken ? "Two-factor verification" : "Sign in"}
        </h1>
        <p className={styles.subtitle}>
          {pendingToken
            ? "Enter your authenticator or recovery code to continue."
            : "Sign in to your club account to continue."}
        </p>

        {isExpired && (
          <div className={styles.noticeBanner} role="status">
            You were signed out after being away. Sign in to continue.
          </div>
        )}

        {errorMessage && (
          <div className={styles.errorBanner} role="alert">
            {errorMessage}
          </div>
        )}

        {pendingToken ? (
          <form onSubmit={handleCodeSubmit} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="login-code" className={styles.label}>
                Authentication code or recovery code
              </label>
              <input
                id="login-code"
                type="text"
                required
                autoComplete="one-time-code"
                autoFocus
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="6-digit code or recovery code"
                className={styles.input}
              />
            </div>

            <div className={styles.buttonRow}>
              <button
                type="submit"
                disabled={loginCodeMutation.isPending}
                className={styles.submitButton}
              >
                {loginCodeMutation.isPending ? "Verifying..." : "Verify"}
              </button>
              <button
                type="button"
                onClick={handleCancel2FA}
                className={styles.secondaryButton}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleCredentialsSubmit} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="login-email" className={styles.label}>
                Email
              </label>
              <input
                id="login-email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@domain.com"
                className={styles.input}
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="login-password" className={styles.label}>
                Password
              </label>
              <input
                id="login-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className={styles.input}
              />
            </div>

            <button
              type="submit"
              disabled={loginMutation.isPending}
              className={styles.submitButton}
            >
              {loginMutation.isPending ? "Signing in..." : "Sign in"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
