import { useEffect, useState } from "react";
import PageMeta from "../../components/common/PageMeta";
import { getTenant, updateTenant, type Tenant } from "../../services/api";

export default function TenantSettings() {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [form, setForm] = useState({ name: "", slug: "" });
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTenant()
      .then((data) => {
        setTenant(data);
        setForm({ name: data.name || "", slug: data.slug || "" });
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load tenant"))
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setMessage(null);
    setError(null);
    try {
      const updated = await updateTenant({ name: form.name, slug: form.slug });
      setTenant(updated);
      setForm({ name: updated.name || "", slug: updated.slug || "" });
      setMessage("Tenant settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save tenant");
    }
  };

  return (
    <>
      <PageMeta title="Tenant Settings | LegalDocuMan" description="Tenant administration" />
      <div className="max-w-3xl rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <h1 className="text-2xl font-semibold text-gray-800 dark:text-white/90">Tenant Settings</h1>
        <p className="mt-1 text-sm text-gray-500">Manage the tenant profile stored by the backend.</p>
        {loading ? <p className="mt-6 text-sm text-gray-500">Loading...</p> : (
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="text-sm text-gray-600 dark:text-gray-300">Tenant Name
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-brand-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
            </label>
            <label className="text-sm text-gray-600 dark:text-gray-300">Tenant Slug
              <input value={form.slug} onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))} className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-brand-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
            </label>
          </div>
        )}
        {tenant?.created_at && <p className="mt-4 text-xs text-gray-500">Created: {new Date(tenant.created_at).toLocaleString()}</p>}
        {message && <p className="mt-4 text-sm text-success-600">{message}</p>}
        {error && <p className="mt-4 text-sm text-error-600">{error}</p>}
        <button onClick={save} disabled={loading} className="mt-6 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50">Save Settings</button>
      </div>
    </>
  );
}
