const BASE_URL = "/api/v1";
const API_KEY = import.meta.env.VITE_API_KEY || "";

export function getAuthToken(): string {
  return localStorage.getItem("legaldocuman_token") || "";
}

function authHeaders(): HeadersInit {
  const token = getAuthToken();
  if (token) return { Authorization: `Bearer ${token}` };
  return API_KEY ? { "X-API-Key": API_KEY } : {};
}

export interface Document {
  id: number;
  tenant_id: number | null;
  uploaded_by_id: number | null;
  reviewed_by_id: number | null;
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
  storage_backend: string | null;
  file_size: number | null;
  checksum: string | null;
  scan_status: "pending" | "clean" | "infected" | "error";
  scan_message: string | null;
  scanned_at: string | null;
  review_status: "not_required" | "needs_review" | "reviewed";
  review_notes: string | null;
  reviewed_at: string | null;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DocumentDetail extends Document {
  metadata_json: Record<string, unknown> | null;
}

export interface AuditEvent {
  id: number;
  action: string;
  document_id: number | null;
  user_id: number | null;
  tenant_id: number | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string | null;
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
  by_review_status: Record<string, number>;
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

export async function login(email: string, password: string) {
  const response = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse<{ token: string; user: { id: number; email: string; name: string; role: string } }>(response);
  localStorage.setItem("legaldocuman_token", data.token);
  return data;
}

export function logout() {
  localStorage.removeItem("legaldocuman_token");
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  return handleResponse<UploadResponse>(response);
}

export async function getDocument(id: number): Promise<DocumentDetail> {
  const response = await fetch(`${BASE_URL}/documents/${id}`, { headers: authHeaders() });
  return handleResponse<DocumentDetail>(response);
}

export async function updateDocument(id: number, payload: Partial<Document> & { mark_reviewed?: boolean }): Promise<DocumentDetail> {
  const response = await fetch(`${BASE_URL}/documents/${id}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<DocumentDetail>(response);
}

export async function getDocumentAudit(id: number): Promise<{ events: AuditEvent[] }> {
  const response = await fetch(`${BASE_URL}/documents/${id}/audit`, { headers: authHeaders() });
  return handleResponse<{ events: AuditEvent[] }>(response);
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

  const response = await fetch(`${BASE_URL}/documents?${searchParams}`, { headers: authHeaders() });
  return handleResponse<DocumentListResponse>(response);
}

export async function getDocumentStats(): Promise<DocumentStats> {
  const response = await fetch(`${BASE_URL}/documents/stats`, { headers: authHeaders() });
  return handleResponse<DocumentStats>(response);
}

export async function getJobStatus(id: number): Promise<Document> {
  const response = await fetch(`${BASE_URL}/jobs/${id}`, { headers: authHeaders() });
  return handleResponse<Document>(response);
}

export function getDocumentDownloadUrl(id: number): string {
  const token = getAuthToken();
  const key = token || API_KEY;
  const query = key ? `?api_key=${encodeURIComponent(key)}` : "";
  return `${BASE_URL}/documents/${id}/download${query}`;
}
