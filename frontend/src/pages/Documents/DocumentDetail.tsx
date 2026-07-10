import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import PageMeta from "../../components/common/PageMeta";
import Badge from "../../components/ui/badge/Badge";
import {
  AngleLeftIcon,
  FileIcon,
  CheckCircleIcon,
  TimeIcon,
  AlertIcon,
  FolderIcon,
  DownloadIcon,
} from "../../icons";
import { useAuth } from "../../auth/AuthContext";
import { createDocumentDownloadUrl, getDocument, getDocumentAudit, updateDocument, type AuditEvent, type DocumentDetail as DocDetail } from "../../services/api";

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircleIcon className="h-6 w-6 text-success-500" />;
    case "processing":
    case "pending":
      return <TimeIcon className="h-6 w-6 text-warning-500" />;
    case "failed":
      return <AlertIcon className="h-6 w-6 text-error-500" />;
    default:
      return null;
  }
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between border-b border-gray-100 dark:border-gray-800 last:border-0">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-sm font-medium text-gray-800 dark:text-white/90">
        {value || <span className="text-gray-400">-</span>}
      </span>
    </div>
  );
}

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const { hasRole } = useAuth();
  const canReview = hasRole(["admin", "reviewer"]);
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [form, setForm] = useState({
    document_type: "",
    vendor: "",
    execution_status: "",
    retention_category: "",
    effective_date: "",
    expiration_date: "",
    renewal_date: "",
    review_date: "",
    termination_date: "",
    review_notes: "",
  });

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getDocument(Number(id))
      .then((loaded) => {
        setDoc(loaded);
        setForm({
          document_type: loaded.document_type || "",
          vendor: loaded.vendor || "",
          execution_status: loaded.execution_status || "",
          retention_category: loaded.retention_category || "",
          effective_date: loaded.effective_date || "",
          expiration_date: loaded.expiration_date || "",
          renewal_date: loaded.renewal_date || "",
          review_date: loaded.review_date || "",
          termination_date: loaded.termination_date || "",
          review_notes: loaded.review_notes || "",
        });
        if (canReview) {
          getDocumentAudit(Number(id)).then((data) => setAuditEvents(data.events)).catch(() => {});
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, canReview]);

  useEffect(() => {
    if (!doc || !id) return;
    if (doc.status === "processing" || doc.status === "pending") {
      const timer = setTimeout(() => {
        getDocument(Number(id)).then(setDoc).catch(() => {});
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [doc, id]);


  const saveReview = async (markReviewed = false) => {
    if (!doc) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateDocument(doc.id, { ...form, mark_reviewed: markReviewed });
      setDoc(updated);
      const audit = await getDocumentAudit(doc.id).catch(() => ({ events: [] }));
      setAuditEvents(audit.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save review");
    } finally {
      setSaving(false);
    }
  };

  const downloadDocument = async () => {
    if (!doc) return;
    setError(null);
    try {
      window.location.href = await createDocumentDownloadUrl(doc.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create download link");
    }
  };

  const setField = (field: keyof typeof form, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  if (loading) {
    return (
      <>
        <PageMeta title="Document | LegalDocuMan" description="Document details" />
        <div className="flex items-center justify-center py-20">
          <p className="text-gray-500">Loading...</p>
        </div>
      </>
    );
  }

  if (error || !doc) {
    return (
      <>
        <PageMeta title="Not Found | LegalDocuMan" description="Document not found" />
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <p className="text-error-500">{error || "Document not found"}</p>
          <Link to="/documents" className="text-brand-500 hover:text-brand-600 text-sm">
            Back to Documents
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <PageMeta title={`${doc.original_name} | LegalDocuMan`} description="Document details" />
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-3">
          <Link
            to="/documents"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-300 dark:border-gray-700 text-gray-500 hover:bg-gray-50 dark:hover:bg-white/5"
          >
            <AngleLeftIcon className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-semibold text-gray-800 dark:text-white/90">
              Document Details
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              ID: {doc.id}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 flex flex-col gap-6">
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <div className="flex items-center gap-4 mb-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-500/15">
                  <FileIcon className="h-6 w-6 text-brand-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 dark:text-white/90 truncate">
                    {doc.original_name}
                  </p>
                  {doc.generated_filename && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {doc.generated_filename}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {doc.status === "completed" && (
                    <button
                      type="button"
                      onClick={downloadDocument}
                      className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
                    >
                      <DownloadIcon className="h-4 w-4" />
                      Download
                    </button>
                  )}
                  <StatusIcon status={doc.status} />
                  <Badge
                    color={
                      doc.status === "completed"
                        ? "success"
                        : doc.status === "failed"
                        ? "error"
                        : "warning"
                    }
                    variant="light"
                  >
                    {doc.status}
                  </Badge>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                <InfoRow label="Document Type" value={doc.document_type} />
                <InfoRow label="Vendor" value={doc.vendor} />
                <InfoRow
                  label="Execution Status"
                  value={
                    doc.execution_status ? (
                      <Badge
                        color={doc.execution_status === "final" ? "success" : "warning"}
                        variant={doc.execution_status === "final" ? "solid" : "light"}
                      >
                        {doc.execution_status}
                      </Badge>
                    ) : null
                  }
                />
                <InfoRow label="Retention Category" value={doc.retention_category} />
                <InfoRow label="Effective Date" value={doc.effective_date} />
                <InfoRow label="Expiration Date" value={doc.expiration_date} />
                <InfoRow label="Renewal Date" value={doc.renewal_date} />
                <InfoRow label="Review Date" value={doc.review_date} />
                <InfoRow label="Termination Date" value={doc.termination_date} />
                <InfoRow
                  label="Processed Folder"
                  value={
                    doc.processed_folder ? (
                      <span className="inline-flex items-center gap-1">
                        <FolderIcon className="h-4 w-4" />
                        {doc.processed_folder}
                      </span>
                    ) : null
                  }
                />
                <InfoRow
                  label="File Size"
                  value={doc.file_size ? `${(doc.file_size / 1024).toFixed(1)} KB` : null}
                />
                <InfoRow label="Created" value={doc.created_at ? new Date(doc.created_at).toLocaleString() : null} />
                <InfoRow label="Updated" value={doc.updated_at ? new Date(doc.updated_at).toLocaleString() : null} />
              </div>
            </div>


            {canReview && (
              <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-medium text-gray-800 dark:text-white/90">Manual Review</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Correct extracted fields and mark the document reviewed.</p>
                </div>
                <Badge color={doc.review_status === "reviewed" ? "success" : doc.review_status === "needs_review" ? "warning" : "light"} variant="light">
                  {doc.review_status.replace("_", " ")}
                </Badge>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {([
                  ["document_type", "Document Type"],
                  ["vendor", "Vendor"],
                  ["execution_status", "Execution Status"],
                  ["retention_category", "Retention Category"],
                  ["effective_date", "Effective Date"],
                  ["expiration_date", "Expiration Date"],
                  ["renewal_date", "Renewal Date"],
                  ["review_date", "Review Date"],
                  ["termination_date", "Termination Date"],
                ] as [keyof typeof form, string][]).map(([field, label]) => (
                  <label key={field} className="flex flex-col gap-1 text-xs text-gray-500 dark:text-gray-400">
                    {label}
                    <input
                      value={form[field]}
                      onChange={(e) => setField(field, e.target.value)}
                      placeholder={field.endsWith("date") ? "YYYY-MM-DD" : ""}
                      className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-brand-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    />
                  </label>
                ))}
              </div>
              <label className="mt-3 flex flex-col gap-1 text-xs text-gray-500 dark:text-gray-400">
                Review Notes
                <textarea
                  value={form.review_notes}
                  onChange={(e) => setField("review_notes", e.target.value)}
                  rows={3}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-brand-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                />
              </label>
              <div className="mt-4 flex gap-2">
                <button onClick={() => saveReview(false)} disabled={saving} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300">
                  Save Corrections
                </button>
                <button onClick={() => saveReview(true)} disabled={saving} className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50">
                  Mark Reviewed
                </button>
              </div>
              </div>
            )}

            {doc.error_message && (
              <div className="rounded-xl border border-error-200 bg-error-50 p-5 dark:border-error-500/20 dark:bg-error-500/10">
                <div className="flex items-center gap-2 mb-2">
                  <AlertIcon className="h-5 w-5 text-error-500" />
                  <p className="text-sm font-medium text-error-600 dark:text-error-500">Error</p>
                </div>
                <p className="text-sm text-error-600 dark:text-error-400">{doc.error_message}</p>
              </div>
            )}
            {doc.extracted_text && (
              <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
                <h3 className="mb-3 text-sm font-medium text-gray-800 dark:text-white/90">Extracted Text</h3>
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-4 text-xs leading-5 text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                  {doc.extracted_text}
                </pre>
              </div>
            )}
          </div>


            {canReview && (
              <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
                <h3 className="text-sm font-medium text-gray-800 dark:text-white/90 mb-4">Audit Trail</h3>
              {auditEvents.length ? (
                <div className="flex flex-col gap-3">
                  {auditEvents.slice(0, 8).map((event) => (
                    <div key={event.id} className="border-b border-gray-100 pb-2 text-xs dark:border-gray-800">
                      <p className="font-medium text-gray-800 dark:text-white/90">{event.action}</p>
                      <p className="text-gray-500 dark:text-gray-400">{event.created_at ? new Date(event.created_at).toLocaleString() : ""}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No audit events visible</p>
              )}
              </div>
            )}

          {doc.metadata_json && (
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <h3 className="text-sm font-medium text-gray-800 dark:text-white/90 mb-4">
                Signature Analysis
              </h3>
              {doc.metadata_json.signature_analysis ? (
                <div className="flex flex-col gap-3">
                  <InfoRow
                    label="Signatures Found"
                    value={String((doc.metadata_json.signature_analysis as Record<string, unknown>).has_signatures ? "Yes" : "No")}
                  />
                  <InfoRow
                    label="Confidence"
                    value={String((doc.metadata_json.signature_analysis as Record<string, unknown>).confidence || "-")}
                  />
                  <InfoRow
                    label="Detection Source"
                    value={String((doc.metadata_json.signature_analysis as Record<string, unknown>).detection_source || "-")}
                  />
                  <InfoRow
                    label="Review Required"
                    value={String((doc.metadata_json.signature_analysis as Record<string, unknown>).review_required ? "Yes" : "No")}
                  />
                </div>
              ) : (
                <p className="text-sm text-gray-500">No signature data available</p>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

