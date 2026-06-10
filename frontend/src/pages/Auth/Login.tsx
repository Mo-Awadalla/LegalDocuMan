import { useState } from "react";
import { useNavigate } from "react-router";
import PageMeta from "../../components/common/PageMeta";
import { login } from "../../services/api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageMeta title="Login | LegalDocuMan" description="Login" />
      <div className="mx-auto flex max-w-md flex-col gap-6 rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800 dark:text-white/90">Sign in</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Use the admin account bootstrapped for this tenant.</p>
        </div>
        {error && <p className="rounded-lg bg-error-50 p-3 text-sm text-error-600">{error}</p>}
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm text-gray-600 dark:text-gray-300">
            Email
            <input className="rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-700 dark:bg-gray-900" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-600 dark:text-gray-300">
            Password
            <input className="rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-700 dark:bg-gray-900" value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
          </label>
          <button disabled={loading} className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50">
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </>
  );
}
