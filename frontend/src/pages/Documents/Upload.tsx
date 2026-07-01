import { useCallback, useEffect, useMemo, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Link } from "react-router";
import PageMeta from "../../components/common/PageMeta";
import { FileIcon, CheckCircleIcon, AlertIcon, TimeIcon } from "../../icons";
import { uploadDocument, getJobStatus, getPublicConfig, type Document, type PublicConfig } from "../../services/api";

interface UploadResult {
  id: number;
  jobId?: number;
  status: string;
  document?: Document;
  error?: string;
}

export default function Upload() {
  const [results, setResults] = useState<UploadResult[]>([]);
  const [uploading, setUploading] = useState(false);
  const [config, setConfig] = useState<PublicConfig | null>(null);

  useEffect(() => {
    getPublicConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  const allowedExtensions = useMemo(
    () => (config?.allowed_extensions?.length ? config.allowed_extensions : [".pdf", ".docx", ".doc", ".txt"]),
    [config?.allowed_extensions]
  );
  const accept = useMemo(() => allowedExtensions.reduce<Record<string, string[]>>((acc, ext) => {
    const normalized = ext.startsWith(".") ? ext : `.${ext}`;
    acc["application/octet-stream"] = [...(acc["application/octet-stream"] || []), normalized];
    return acc;
  }, {}), [allowedExtensions]);

  const pollStatus = useCallback(async (jobId: number) => {
    const poll = async () => {
      try {
        const job = await getJobStatus(jobId);
        setResults((prev) =>
          prev.map((r) =>
            r.jobId === jobId ? { ...r, status: job.status, document: job.document || r.document } : r
          )
        );
        if (job.status === "queued" || job.status === "processing" || job.status === "pending") {
          setTimeout(poll, 3000);
        }
      } catch {
        setResults((prev) =>
          prev.map((r) =>
            r.jobId === jobId ? { ...r, error: "Failed to check status" } : r
          )
        );
      }
    };
    poll();
  }, []);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      setUploading(true);
      const newResults: UploadResult[] = acceptedFiles.map(() => ({
        id: 0,
        status: "uploading",
      }));
      setResults((prev) => [...prev, ...newResults]);

      for (let i = 0; i < acceptedFiles.length; i++) {
        try {
          if (config?.max_upload_mb && acceptedFiles[i].size > config.max_upload_mb * 1024 * 1024) {
            throw new Error(`File exceeds ${config.max_upload_mb} MB limit`);
          }
          const res = await uploadDocument(acceptedFiles[i]);
          setResults((prev) => {
            const updated = [...prev];
            const idx = updated.length - acceptedFiles.length + i;
            updated[idx] = { id: res.id, jobId: res.job_id, status: res.job_status || res.status };
            return updated;
          });
          pollStatus(res.job_id);
        } catch (err) {
          setResults((prev) => {
            const updated = [...prev];
            const idx = updated.length - acceptedFiles.length + i;
            updated[idx] = {
              id: 0,
              status: "error",
              error: err instanceof Error ? err.message : "Upload failed",
            };
            return updated;
          });
        }
      }
      setUploading(false);
    },
    [pollStatus, config?.max_upload_mb]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    multiple: true,
  });

  return (
    <>
      <PageMeta title="Upload Documents | LegalDocuMan" description="Upload documents for processing" />
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-gray-800 dark:text-white/90">
            Upload Documents
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Drop your contracts, agreements, and supporting documents for automatic classification and organization.
          </p>
        </div>

        <div
          {...getRootProps()}
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors cursor-pointer ${
            isDragActive
              ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
              : "border-gray-300 dark:border-gray-700 hover:border-brand-400 dark:hover:border-brand-500"
          }`}
        >
          <input {...getInputProps()} />
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-50 dark:bg-brand-500/15">
            <FileIcon className="h-8 w-8 text-brand-500" />
          </div>
          {isDragActive ? (
            <p className="text-lg font-medium text-brand-500">Drop files here...</p>
          ) : (
            <>
              <p className="text-lg font-medium text-gray-800 dark:text-white/90">
                Drag & drop files here
              </p>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                or click to browse ({allowedExtensions.join(", ")})
              </p>
              {config?.max_upload_mb && (
                <p className="mt-1 text-xs text-gray-400">Maximum file size: {config.max_upload_mb} MB. Multiple files upload sequentially.</p>
              )}
            </>
          )}
        </div>

        {uploading && (
          <div className="flex items-center gap-2 rounded-lg bg-brand-50 dark:bg-brand-500/15 px-4 py-3">
            <TimeIcon className="h-5 w-5 text-brand-500 animate-spin" />
            <span className="text-sm text-brand-500">Uploading and processing...</span>
          </div>
        )}

        {results.length > 0 && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
            <div className="border-b border-gray-200 dark:border-gray-800 px-5 py-4">
              <h2 className="text-lg font-medium text-gray-800 dark:text-white/90">
                Upload Results
              </h2>
            </div>
            <div className="divide-y divide-gray-200 dark:divide-gray-800">
              {results.map((result, idx) => (
                <div key={idx} className="flex items-center justify-between px-5 py-4">
                  <div className="flex items-center gap-3">
                    {result.status === "completed" && (
                      <CheckCircleIcon className="h-5 w-5 text-success-500" />
                    )}
                    {(result.status === "pending" || result.status === "queued" || result.status === "processing" || result.status === "uploading") && (
                      <TimeIcon className="h-5 w-5 text-warning-500 animate-spin" />
                    )}
                    {(result.status === "failed" || result.status === "error") && (
                      <AlertIcon className="h-5 w-5 text-error-500" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-gray-800 dark:text-white/90">
                        {result.document?.original_name || `Document #${result.id || idx + 1}`}
                      </p>
                      {result.document?.document_type && (
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {result.document.document_type} &middot; {result.document.vendor} &middot;{" "}
                          <span className={result.document.execution_status === "final" ? "text-success-500" : "text-warning-500"}>
                            {result.document.execution_status}
                          </span>
                        </p>
                      )}
                      {result.error && (
                        <p className="text-xs text-error-500">{result.error}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        result.status === "completed"
                          ? "bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
                          : result.status === "failed" || result.status === "error"
                          ? "bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500"
                          : "bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-500"
                      }`}
                    >
                      {result.status}
                    </span>
                    {result.id > 0 && (
                      <Link
                        to={`/documents/${result.id}`}
                        className="text-xs text-brand-500 hover:text-brand-600"
                      >
                        View
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
