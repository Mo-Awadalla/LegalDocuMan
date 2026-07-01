import { useEffect, useState } from "react";
import { Link } from "react-router";
import PageMeta from "../../components/common/PageMeta";
import Badge from "../../components/ui/badge/Badge";
import { AngleLeftIcon, AngleRightIcon, EyeIcon } from "../../icons";
import { getReviewQueue, type Document } from "../../services/api";

export default function ReviewQueue() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getReviewQueue({ page, per_page: 15 })
      .then((res) => {
        setDocuments(res.documents);
        setPages(res.pages || 1);
      })
      .catch((err) => {
        setDocuments([]);
        setError(err instanceof Error ? err.message : "Unable to load review queue");
      })
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <>
      <PageMeta title="Review Queue | LegalDocuMan" description="Documents needing human review" />
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800 dark:text-white/90">Review Queue</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Prioritize documents flagged for manual quality control.</p>
        </div>

        {error && <div className="rounded-lg border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-600 dark:border-error-500/20 dark:bg-error-500/10">{error}</div>}

        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              <p className="p-6 text-sm text-gray-500">Loading...</p>
            ) : documents.length === 0 ? (
              <p className="p-6 text-sm text-gray-500">No documents need review right now.</p>
            ) : documents.map((doc) => (
              <div key={doc.id} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <Link to={`/documents/${doc.id}`} className="font-medium text-gray-800 hover:text-brand-500 dark:text-white/90">{doc.original_name}</Link>
                  <p className="mt-1 text-xs text-gray-500">{doc.vendor || "Unknown vendor"} · {doc.document_type || "Unclassified"}</p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge color={doc.review_status === "needs_review" ? "warning" : "light"} variant="light">{doc.review_status.replace("_", " ")}</Badge>
                  <Link to={`/documents/${doc.id}`} className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-2 text-xs font-medium text-white hover:bg-brand-600"><EyeIcon className="h-4 w-4" /> Review</Link>
                </div>
              </div>
            ))}
          </div>
          {pages > 1 && (
            <div className="flex items-center justify-between border-t border-gray-200 px-5 py-3 dark:border-gray-800">
              <span className="text-sm text-gray-500">Page {page} of {pages}</span>
              <div className="flex gap-2">
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="rounded-lg border border-gray-300 p-2 text-gray-500 disabled:opacity-40 dark:border-gray-700"><AngleLeftIcon className="h-4 w-4" /></button>
                <button onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page === pages} className="rounded-lg border border-gray-300 p-2 text-gray-500 disabled:opacity-40 dark:border-gray-700"><AngleRightIcon className="h-4 w-4" /></button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
