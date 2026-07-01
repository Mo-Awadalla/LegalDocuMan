import { useEffect, useState } from "react";
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
import {
  FileIcon,
  CheckCircleIcon,
  AlertIcon,
  BoxIcon,
  EyeIcon,
} from "../../icons";
import {
  getDocumentStats,
  listDocuments,
  type DocumentStats,
  type Document,
} from "../../services/api";

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex items-center gap-4">
        <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${color}`}>
          {icon}
        </div>
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
          <p className="text-2xl font-semibold text-gray-800 dark:text-white/90">{value}</p>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [stats, setStats] = useState<DocumentStats | null>(null);
  const [recentDocs, setRecentDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDocumentStats(), listDocuments({ per_page: 5 })])
      .then(([s, docs]) => {
        setStats(s);
        setRecentDocs(docs.documents);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load dashboard"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <PageMeta title="Dashboard | LegalDocuMan" description="Document management dashboard" />
      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            icon={<BoxIcon className="h-6 w-6 text-brand-500" />}
            label="Total Documents"
            value={loading ? "..." : stats?.total ?? 0}
            color="bg-brand-50 dark:bg-brand-500/15"
          />
          <StatCard
            icon={<CheckCircleIcon className="h-6 w-6 text-success-500" />}
            label="Completed"
            value={loading ? "..." : stats?.by_status?.completed ?? 0}
            color="bg-success-50 dark:bg-success-500/15"
          />
          <StatCard
            icon={<EyeIcon className="h-6 w-6 text-warning-500" />}
            label="Needs Review"
            value={loading ? "..." : stats?.by_review_status?.needs_review ?? 0}
            color="bg-warning-50 dark:bg-warning-500/15"
          />
          <StatCard
            icon={<AlertIcon className="h-6 w-6 text-error-500" />}
            label="Failed"
            value={loading ? "..." : stats?.by_status?.failed ?? 0}
            color="bg-error-50 dark:bg-error-500/15"
          />
        </div>

        {error && <div className="rounded-lg border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-600 dark:border-error-500/20 dark:bg-error-500/10">{error}</div>}

        {!loading && !error && (stats?.total ?? 0) === 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-5 text-sm text-gray-500 dark:border-gray-800 dark:bg-white/[0.03]">
            No documents yet. <Link to="/upload" className="text-brand-500 hover:text-brand-600">Upload your first document</Link> to start processing.
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2 rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
            <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 px-5 py-4">
              <h2 className="text-lg font-medium text-gray-800 dark:text-white/90">
                Recent Documents
              </h2>
              <Link
                to="/documents"
                className="text-sm text-brand-500 hover:text-brand-600"
              >
                View all
              </Link>
            </div>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-b border-gray-100 dark:border-gray-800">
                    <TableCell isHeader className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                      Document
                    </TableCell>
                    <TableCell isHeader className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                      Type
                    </TableCell>
                    <TableCell isHeader className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                      Status
                    </TableCell>
                    <TableCell isHeader className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                      Execution
                    </TableCell>
                    <TableCell isHeader className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                      Action
                    </TableCell>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentDocs.length === 0 ? (
                    <TableRow>
                      <TableCell className="px-5 py-8 text-center text-sm text-gray-500" colSpan={5} isHeader={false}>
                        No documents yet. Upload some to get started.
                      </TableCell>
                    </TableRow>
                  ) : (
                    recentDocs.map((doc) => (
                      <TableRow
                        key={doc.id}
                        className="border-b border-gray-100 last:border-0 dark:border-gray-800"
                      >
                        <TableCell className="px-5 py-3">
                          <div className="flex items-center gap-3">
                            <FileIcon className="h-5 w-5 text-gray-400 shrink-0" />
                            <span className="text-sm text-gray-800 dark:text-white/90 truncate max-w-[180px]">
                              {doc.original_name}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="px-5 py-3">
                          <span className="text-sm text-gray-800 dark:text-white/90">
                            {doc.document_type || "-"}
                          </span>
                        </TableCell>
                        <TableCell className="px-5 py-3">
                          <Badge
                            color={
                              doc.status === "completed"
                                ? "success"
                                : doc.status === "failed"
                                ? "error"
                                : "warning"
                            }
                            size="sm"
                            variant="light"
                          >
                            {doc.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-5 py-3">
                          {doc.execution_status ? (
                            <Badge
                              color={doc.execution_status === "final" ? "success" : "warning"}
                              size="sm"
                              variant={doc.execution_status === "final" ? "solid" : "light"}
                            >
                              {doc.execution_status}
                            </Badge>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </TableCell>
                        <TableCell className="px-5 py-3">
                          <Link
                            to={`/documents/${doc.id}`}
                            className="text-brand-500 hover:text-brand-600"
                          >
                            <EyeIcon className="h-4 w-4" />
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </div>

          <div className="flex flex-col gap-6">
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <h3 className="text-sm font-medium text-gray-800 dark:text-white/90 mb-4">
                By Document Type
              </h3>
              {stats?.by_type && Object.keys(stats.by_type).length > 0 ? (
                <div className="flex flex-col gap-3">
                  {Object.entries(stats.by_type).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between">
                      <span className="text-sm text-gray-600 dark:text-gray-400">{type}</span>
                      <span className="text-sm font-medium text-gray-800 dark:text-white/90">
                        {count}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No data yet</p>
              )}
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <h3 className="text-sm font-medium text-gray-800 dark:text-white/90 mb-4">
                By Execution Status
              </h3>
              {stats?.by_execution_status && Object.keys(stats.by_execution_status).length > 0 ? (
                <div className="flex flex-col gap-3">
                  {Object.entries(stats.by_execution_status).map(([status, count]) => (
                    <div key={status} className="flex items-center justify-between">
                      <Badge
                        color={status === "final" ? "success" : "warning"}
                        variant="light"
                        size="sm"
                      >
                        {status}
                      </Badge>
                      <span className="text-sm font-medium text-gray-800 dark:text-white/90">
                        {count}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No data yet</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
