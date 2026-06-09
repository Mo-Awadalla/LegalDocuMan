const BASE_URL = "/api/v1";

export interface Document {
  id: number;
  original_name: string;
  status: "pending" | "processing" | "completed" | "failed";
  document_type: string | null;
  vendor: string | null;
  execution_status: string | null;
  effective_date: string | null;
  expiration_date: string | null;
  retention_category: string | null;
  generated_filename: string | null;
  processed_folder: string | null;
  file_size: number | null;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DocumentDetail extends Document {
  metadata_json: Record<string, unknown> | null;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface DocumentStats {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  by_execution_status: Record<string, number>;
}

export interface UploadResponse {
  id: number;
  status: string;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(error.error || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<UploadResponse>(response);
}

export async function getDocument(id: number): Promise<DocumentDetail> {
  const response = await fetch(`${BASE_URL}/documents/${id}`);
  return handleResponse<DocumentDetail>(response);
}

export async function listDocuments(params?: {
  page?: number;
  per_page?: number;
  status?: string;
  type?: string;
  vendor?: string;
  search?: string;
}): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.per_page) searchParams.set("per_page", String(params.per_page));
  if (params?.status) searchParams.set("status", params.status);
  if (params?.type) searchParams.set("type", params.type);
  if (params?.vendor) searchParams.set("vendor", params.vendor);
  if (params?.search) searchParams.set("search", params.search);

  const response = await fetch(`${BASE_URL}/documents?${searchParams}`);
  return handleResponse<DocumentListResponse>(response);
}

export async function getDocumentStats(): Promise<DocumentStats> {
  const response = await fetch(`${BASE_URL}/documents/stats`);
  return handleResponse<DocumentStats>(response);
}

export async function getJobStatus(id: number): Promise<Document> {
  const response = await fetch(`${BASE_URL}/jobs/${id}`);
  return handleResponse<Document>(response);
}
