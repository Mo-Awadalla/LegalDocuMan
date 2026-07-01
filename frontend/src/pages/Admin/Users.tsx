import { useEffect, useState } from "react";
import PageMeta from "../../components/common/PageMeta";
import Badge from "../../components/ui/badge/Badge";
import { createUser, listUsers, updateUser, type UserAccount, type UserPayload } from "../../services/api";

const emptyForm: UserPayload = { email: "", name: "", role: "user", password: "", is_active: true };

export default function Users() {
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [form, setForm] = useState<UserPayload>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    listUsers()
      .then((data) => setUsers(data.users))
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load users"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const submit = async () => {
    setMessage(null);
    setError(null);
    if (!form.email || !form.name) {
      setError("Name and email are required.");
      return;
    }
    try {
      await createUser({ ...form, password: form.password || undefined });
      setForm(emptyForm);
      setMessage("User created.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create user");
    }
  };

  const toggleActive = async (user: UserAccount) => {
    await updateUser(user.id, { is_active: !user.is_active }).then(load).catch((err) => setError(err instanceof Error ? err.message : "Unable to update user"));
  };

  return (
    <>
      <PageMeta title="Users | LegalDocuMan" description="User administration" />
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800 dark:text-white/90">Users</h1>
          <p className="text-sm text-gray-500">Invite and manage tenant users.</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <h2 className="text-lg font-medium text-gray-800 dark:text-white/90">Create User</h2>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-5">
            <input placeholder="Name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
            <input placeholder="Email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} className="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
            <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as UserPayload["role"] }))} className="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"><option value="user">User</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option></select>
            <input placeholder="Temp password" type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} className="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
            <button onClick={submit} className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600">Create</button>
          </div>
          {message && <p className="mt-3 text-sm text-success-600">{message}</p>}
          {error && <p className="mt-3 text-sm text-error-600">{error}</p>}
        </div>

        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          {loading ? <p className="p-5 text-sm text-gray-500">Loading...</p> : users.length === 0 ? <p className="p-5 text-sm text-gray-500">No users found.</p> : users.map((user) => (
            <div key={user.id} className="flex flex-col gap-3 border-b border-gray-100 p-5 last:border-0 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between">
              <div><p className="font-medium text-gray-800 dark:text-white/90">{user.name}</p><p className="text-sm text-gray-500">{user.email}</p></div>
              <div className="flex items-center gap-3"><Badge color={user.role === "admin" ? "success" : user.role === "reviewer" ? "warning" : "light"} variant="light">{user.role}</Badge><button onClick={() => toggleActive(user)} className="rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300">{user.is_active === false ? "Activate" : "Deactivate"}</button></div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
