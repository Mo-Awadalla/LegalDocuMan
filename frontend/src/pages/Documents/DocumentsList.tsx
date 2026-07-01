import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import PageMeta from "../../components/common/PageMeta";
import Badge from "../../components/ui/badge/Badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableCell,
} from "../../components/ui/table";
import { AngleLeftIcon, AngleRightIcon, EyeIcon } from "../../icons";
import { downloadDocumentsExport, listDocuments, type Document } from "../../services/api";

function statusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge color="success" variant="light">Completed</Badge>;
    case "processing":
      return <Badge color="warning" variant="light">Processing</Badge>;
    case "pending":
      return <Badge color="info" variant="light">Pending</Badge>;
    case "failed":
      return <Badge color="error" variant="light">Failed</Badge>;
    default:
      return <Badge color="light" variant="light">{status}</Badge>;
  }
}

function executionBadge(status: string | null) {
  if (!status) return <span className="text-gray-400">-</span>;
  if (status === "final")
    return <Badge color="success" variant="solid">Final</Badge>;
  return <Badge color="warning" variant="light">Supporting</Badge>;
}

export default function DocumentsList() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listDocuments({
        page,
        per_page: 15,
        search: search || undefined,
        status: statusFilter || undefined,
        type: typeFilter || undefined,
      });
      setDocuments(res.documents);
      setTotal(res.total);
      setPages(res.pages);
    } catch (err) {
      setDocuments([]);
      setError(err instanceof Error ? err.message : "Unable to load documents");
    }
    setLoading(false);
  }, [page, search, statusFilter, typeFilter]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  useEffect(() => {
    if (search || statusFilter || typeFilter) {
      setPage(1);
    }
  }, [search, statusFilter, typeFilter]);

  return (
    <>
      <PageMeta title="Documents | LegalDocuMan" description="Browse all processed documents" />
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-800 dark:text-white/90">Documents</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {total} document{total !== 1 ? "s" : ""} total
            </p>
          </div>
          <button
            type="button"
            onClick={() => downloadDocumentsExport({ search: search || undefined, status: statusFilter || undefined, type: typeFilter || undefined }).catch((err) => setError(err instanceof Error ? err.message : "Unable to export documents"))}
            className="inline-flex items-center justify-center rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
          >
            Export CSV
          </button>
        </div>

        {error && <div className="rounded-lg border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-600 dark:border-error-500/20 dark:bg-error-500/10">{error}</div>}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            type="text"
            placeholder="Search by name or vendor..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 rounded-lg border border-gray-300 bg-transparent px-4 text-sm text-gray-800 outline-none focus:border-brand-500 dark:border-gray-700 dark:text-white/90 dark:focus:border-brand-500 sm:w-64"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 outline-none focus:border-brand-500 dark:border-gray-700 dark:text-white/90 dark:bg-gray-900"
          >
            <option value="">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="processing">Processing</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="h-10 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 outline-none focus:border-brand-500 dark:border-gray-700 dark:text-white/90 dark:bg-gray-900"
          >
            <option value="">All Types</option>
            <option value="MSA">MSA</option>
            <option value="SOW">SOW</option>
            <option value="NDA">NDA</option>
            <option value="PO">PO</option>
            <option value="AMD">AMD</option>
            <option value="LICENSE">License</option>
            <option value="CONTRACT">Contract</option>
          </select>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-b border-gray-200 dark:border-gray-800">
                  <TableCell isHeader className="px-5 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">
                    Document
                  </TableCell>
                  <TableCell isHeader className="px-5 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">
                    Type
                  </TableCell>
                  <TableCell isHeader className="px-5 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">
                    Vendor
                  </TableCell>
                  <TableCell isHeader className="px-5 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </TableCell>
                  <TableCell isHeader className="px-5 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">
                    Execution
                  </TableCell>
                  <TableCell isHeader className="px-5 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">
                    Date
                  </TableCell>
                  <TableCell isHeader className="px-5 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">
                    Actions
                  </TableCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell className="px-5 py-8 text-center text-sm text-gray-500" colSpan={7} isHeader={false}>
                      Loading...
                    </TableCell>
                  </TableRow>
                ) : documents.length === 0 ? (
                  <TableRow>
                    <TableCell className="px-5 py-8 text-center text-sm text-gray-500" colSpan={7} isHeader={false}>
                      No documents found
                    </TableCell>
                  </TableRow>
                ) : (
                  documents.map((doc) => (
                    <TableRow
                      key={doc.id}
                      className="border-b border-gray-100 last:border-0 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-white/[0.02]"
                    >
                      <TableCell className="px-5 py-4">
                        <div>
                          <p className="text-sm font-medium text-gray-800 dark:text-white/90 truncate max-w-[200px]">
                            {doc.original_name}
                          </p>
                          {doc.generated_filename && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                              {doc.generated_filename}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="px-5 py-4">
                        <span className="text-sm text-gray-800 dark:text-white/90">
                          {doc.document_type || "-"}
                        </span>
                      </TableCell>
                      <TableCell className="px-5 py-4">
                        <span className="text-sm text-gray-800 dark:text-white/90">
                          {doc.vendor || "-"}
                        </span>
                      </TableCell>
                      <TableCell className="px-5 py-4">
                        {statusBadge(doc.status)}
                      </TableCell>
                      <TableCell className="px-5 py-4">
                        {executionBadge(doc.execution_status)}
                      </TableCell>
                      <TableCell className="px-5 py-4">
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          {doc.effective_date || "-"}
                        </span>
                      </TableCell>
                      <TableCell className="px-5 py-4">
                        <Link
                          to={`/documents/${doc.id}`}
                          className="inline-flex items-center gap-1 text-sm text-brand-500 hover:text-brand-600"
                        >
                          <EyeIcon className="h-4 w-4" />
                          View
                        </Link>
                        {doc.review_status === "needs_review" && (
                          <span className="ml-3 text-xs text-warning-600">Needs review</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {pages > 1 && (
            <div className="flex items-center justify-between border-t border-gray-200 dark:border-gray-800 px-5 py-3">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Page {page} of {pages}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-300 dark:border-gray-700 text-gray-500 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-white/5"
                >
                  <AngleLeftIcon className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(pages, p + 1))}
                  disabled={page === pages}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-300 dark:border-gray-700 text-gray-500 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-white/5"
                >
                  <AngleRightIcon className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
