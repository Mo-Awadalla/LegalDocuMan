const BASE_URL = "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getAuthToken(): string {
  return localStorage.getItem("legaldocuman_token") || "";
}

function authHeaders(): HeadersInit {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface CurrentUser {
  id: number;
  email: string;
  name: string;
  role: "admin" | "reviewer" | "user";
  tenant_id: number;
}

export interface CurrentUserResponse {
  user: CurrentUser | null;
  auth_mode?: string;
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
  job_id: number;
  status: string;
  job_status: string;
}

export interface DocumentJob {
  id: number;
  document_id: number;
  tenant_id: number | null;
  status: "pending" | "queued" | "processing" | "completed" | "failed";
  backend: string;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  document: Document | null;
}

export interface PublicConfig {
  max_upload_mb?: number;
  allowed_extensions?: string[];
  app_name?: string;
  [key: string]: unknown;
}

export interface Tenant {
  id: number;
  name: string;
  slug?: string;
  plan?: string;
  status?: string;
  max_upload_mb?: number;
  allowed_extensions?: string[];
  created_at?: string | null;
  updated_at?: string | null;
  [key: string]: unknown;
}

export interface UserAccount {
  id: number;
  email: string;
  name: string;
  role: "admin" | "reviewer" | "user";
  tenant_id?: number;
  is_active?: boolean;
  created_at?: string | null;
}

export interface UserPayload {
  email: string;
  name: string;
  role: "admin" | "reviewer" | "user";
  password?: string;
  is_active?: boolean;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new ApiError(error.error || `HTTP ${response.status}`, response.status);
  }
  return response.json();
}

export async function login(email: string, password: string) {
  const response = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse<{ token: string; user: CurrentUser }>(response);
  localStorage.setItem("legaldocuman_token", data.token);
  return data;
}

export function logout() {
  localStorage.removeItem("legaldocuman_token");
}

export async function getCurrentUser(): Promise<CurrentUserResponse> {
  const response = await fetch(`${BASE_URL}/auth/me`, { headers: authHeaders() });
  return handleResponse<CurrentUserResponse>(response);
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

export async function getJobStatus(id: number): Promise<DocumentJob> {
  const response = await fetch(`${BASE_URL}/jobs/${id}`, { headers: authHeaders() });
  return handleResponse<DocumentJob>(response);
}

export async function createDocumentDownloadUrl(id: number): Promise<string> {
  const response = await fetch(`${BASE_URL}/documents/${id}/download-token`, {
    method: "POST",
    headers: authHeaders(),
  });
  const data = await handleResponse<{ download_token: string; expires_in: number }>(response);
  return `${BASE_URL}/documents/${id}/download?download_token=${encodeURIComponent(data.download_token)}`;
}

function documentExportQuery(params?: { status?: string; search?: string; type?: string }): string {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.search) searchParams.set("search", params.search);
  if (params?.type) searchParams.set("type", params.type);
  return searchParams.toString();
}

export function getDocumentsExportUrl(params?: { status?: string; search?: string; type?: string }): string {
  const query = documentExportQuery(params);
  return `${BASE_URL}/documents/export.csv${query ? `?${query}` : ""}`;
}

export async function downloadDocumentsExport(params?: { status?: string; search?: string; type?: string }): Promise<void> {
  const response = await fetch(getDocumentsExportUrl(params), { headers: authHeaders() });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new ApiError(error.error || `HTTP ${response.status}`, response.status);
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "legaldocuman-documents.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function getPublicConfig(): Promise<PublicConfig> {
  const response = await fetch(`${BASE_URL}/config/public`);
  return handleResponse<PublicConfig>(response);
}

export async function getTenant(): Promise<Tenant> {
  const response = await fetch(`${BASE_URL}/tenant`, { headers: authHeaders() });
  return handleResponse<Tenant>(response);
}

export async function updateTenant(payload: Partial<Tenant>): Promise<Tenant> {
  const response = await fetch(`${BASE_URL}/tenant`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<Tenant>(response);
}

export async function listUsers(): Promise<{ users: UserAccount[] }> {
  const response = await fetch(`${BASE_URL}/users`, { headers: authHeaders() });
  return handleResponse<{ users: UserAccount[] }>(response);
}

export async function createUser(payload: UserPayload): Promise<UserAccount> {
  const response = await fetch(`${BASE_URL}/users`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<UserAccount>(response);
}

export async function updateUser(id: number, payload: Partial<UserPayload>): Promise<UserAccount> {
  const response = await fetch(`${BASE_URL}/users/${id}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<UserAccount>(response);
}

export async function getReviewQueue(params?: { page?: number; per_page?: number }): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.per_page) searchParams.set("per_page", String(params.per_page));
  const response = await fetch(`${BASE_URL}/documents/review-queue?${searchParams}`, { headers: authHeaders() });
  return handleResponse<DocumentListResponse>(response);
}
