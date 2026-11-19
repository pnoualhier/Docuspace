export interface ApiErrorPayload {
  detail?: string;
  message?: string;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export interface ApiTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  tenant_id: string;
  refresh_token?: string;
}

export interface ApiUser {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface ApiTenant {
  id: string;
  name: string;
  owner_id: string;
  plan_id: string;
  role?: string;
  is_active: boolean;
  used_bytes?: number;
  reserved_bytes?: number;
  document_count?: number;
  subscription_status?: string;
  restricted_read_only?: boolean;
  created_at?: string;
}

export interface ApiFolder {
  id: string;
  tenant_id: string;
  parent_id: string | null;
  name: string;
  color: string;
  is_favorite: boolean;
  is_trashed: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ApiDocument {
  id: string;
  tenant_id: string;
  folder_id: string | null;
  original_name: string;
  storage_key: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  sha256_hash: string;
  status: string;
  antivirus_status: string;
  is_favorite: boolean;
  is_trashed: boolean;
  trashed_at?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ApiUploadCompleteResponse {
  document: ApiDocument;
  antivirus_status: string;
  threat_detected?: string | null;
  details: string;
}

export interface ApiShare {
  id: string;
  tenant_id: string;
  document_id?: string | null;
  folder_id?: string | null;
  target_name: string;
  share_type: 'INTERNAL_USER' | 'SECURE_LINK';
  role: string;
  token?: string | null;
  public_url?: string | null;
  has_password: boolean;
  max_downloads?: number | null;
  download_count: number;
  expires_at?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

const DEFAULT_BASE_URL =
  (typeof import.meta !== 'undefined' &&
    (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL) ||
  '/api/v1';

class DocuSpaceApiClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private onUnauthorized: (() => void) | null = null;

  constructor(baseUrl: string = DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  setAccessToken(token: string | null) {
    this.accessToken = token;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setUnauthorizedHandler(handler: (() => void) | null) {
    this.onUnauthorized = handler;
  }

  private buildHeaders(tenantId?: string, extra?: Record<string, string>): Record<string, string> {
    const headers: Record<string, string> = { ...(extra || {}) };
    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }
    if (tenantId) {
      headers['X-Tenant-ID'] = tenantId;
    }
    return headers;
  }

  private async request<T>(
    path: string,
    options: RequestInit & { tenantId?: string; skipAuthCallback?: boolean } = {}
  ): Promise<T> {
    const { tenantId, skipAuthCallback, headers, ...fetchOpts } = options;
    const mergedHeaders = this.buildHeaders(tenantId, headers as Record<string, string> | undefined);
    if (fetchOpts.body && !(fetchOpts.body instanceof FormData) && !mergedHeaders['Content-Type']) {
      mergedHeaders['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...fetchOpts,
      headers: mergedHeaders,
      credentials: 'include',
    });

    if (!response.ok) {
      let detail = `Erreur HTTP ${response.status}`;
      try {
        const body = (await response.json()) as ApiErrorPayload;
        if (body && typeof body.detail === 'string') {
          detail = body.detail;
        } else if (body && typeof body.message === 'string') {
          detail = body.message;
        }
      } catch {
        // Non-JSON error body
      }
      if (response.status === 401 && !skipAuthCallback && this.onUnauthorized) {
        this.accessToken = null;
        this.onUnauthorized();
      }
      throw new ApiError(response.status, detail);
    }

    if (response.status === 204) {
      return undefined as unknown as T;
    }

    return (await response.json()) as T;
  }

  health = {
    check: () =>
      this.request<{
        status: string;
        database: string;
        redis?: string;
        storage: string;
        antivirus: string;
      }>('/health', { skipAuthCallback: true }),
  };

  auth = {
    login: async (email: string, password: string): Promise<ApiTokenResponse> => {
      const res = await this.request<ApiTokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
        skipAuthCallback: true,
      });
      this.accessToken = res.access_token;
      return res;
    },
    register: (fullName: string, email: string, password: string) =>
      this.request<ApiUser>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ full_name: fullName, email, password }),
        skipAuthCallback: true,
      }),
    logout: async () => {
      try {
        await this.request('/auth/logout', { method: 'POST', skipAuthCallback: true });
      } finally {
        this.accessToken = null;
      }
    },
    me: () => this.request<ApiUser>('/auth/me'),
  };

  tenants = {
    list: () => this.request<ApiTenant[]>('/tenants/my-tenants'),
    current: (tenantId: string) => this.request<ApiTenant>('/tenants/current', { tenantId }),
    quota: (tenantId: string) =>
      this.request<{
        tenant_id: string;
        used_bytes: number;
        reserved_bytes: number;
        max_storage_bytes: number;
        available_bytes: number;
        document_count: number;
        usage_percent: number;
      }>('/storage/quota', { tenantId }),
  };

  documents = {
    listFolders: (
      tenantId: string,
      params: { parentId?: string | null; trashed?: boolean; limit?: number; offset?: number } = {}
    ) => {
      const qs = new URLSearchParams();
      if (params.parentId) qs.set('parent_id', params.parentId);
      if (params.trashed !== undefined) qs.set('is_trashed', String(params.trashed));
      if (params.limit !== undefined) qs.set('limit', String(params.limit));
      if (params.offset !== undefined) qs.set('offset', String(params.offset));
      const query = qs.toString() ? `?${qs.toString()}` : '';
      return this.request<ApiFolder[]>(`/documents/folders${query}`, { tenantId });
    },
    createFolder: (tenantId: string, name: string, parentId: string | null = null, color: string = '#3b82f6') =>
      this.request<ApiFolder>('/documents/folders', {
        method: 'POST',
        tenantId,
        body: JSON.stringify({ name, parent_id: parentId, color }),
      }),
    deleteFolder: (tenantId: string, folderId: string) =>
      this.request<void>(`/documents/folders/${folderId}`, { method: 'DELETE', tenantId }),
    list: (
      tenantId: string,
      params: { folderId?: string | null; trashed?: boolean; limit?: number; offset?: number } = {}
    ) => {
      const qs = new URLSearchParams();
      if (params.folderId) qs.set('folder_id', params.folderId);
      if (params.trashed !== undefined) qs.set('is_trashed', String(params.trashed));
      if (params.limit !== undefined) qs.set('limit', String(params.limit));
      if (params.offset !== undefined) qs.set('offset', String(params.offset));
      const query = qs.toString() ? `?${qs.toString()}` : '';
      return this.request<ApiDocument[]>(`/documents/documents${query}`, { tenantId });
    },
    search: (tenantId: string, query: string, limit: number = 50, offset: number = 0) =>
      this.request<ApiDocument[]>(
        `/documents/documents/search?query=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`,
        { tenantId }
      ),
    rename: (tenantId: string, documentId: string, name: string) =>
      this.request<ApiDocument>(`/documents/documents/${documentId}`, {
        method: 'PATCH',
        tenantId,
        body: JSON.stringify({ original_name: name }),
      }),
    move: (tenantId: string, documentId: string, targetFolderId: string | null) =>
      this.request<ApiDocument>(`/documents/documents/${documentId}`, {
        method: 'PATCH',
        tenantId,
        body: JSON.stringify({ folder_id: targetFolderId }),
      }),
    copy: (tenantId: string, documentId: string, targetFolderId: string | null = null) =>
      this.request<ApiDocument>(`/documents/documents/${documentId}/copy`, {
        method: 'POST',
        tenantId,
        body: JSON.stringify({ target_folder_id: targetFolderId }),
      }),
    trash: (tenantId: string, documentId: string) =>
      this.request<void>(`/documents/documents/${documentId}`, { method: 'DELETE', tenantId }),
    restore: (tenantId: string, documentId: string) =>
      this.request<ApiDocument>(`/documents/documents/${documentId}/restore`, {
        method: 'POST',
        tenantId,
      }),
    purge: (tenantId: string, documentId: string) =>
      this.request<{ message: string }>(`/documents/documents/${documentId}/purge`, {
        method: 'DELETE',
        tenantId,
      }),
    emptyTrash: (tenantId: string) =>
      this.request<{ purged_documents: number; reclaimed_bytes: number }>('/documents/trash/empty', {
        method: 'POST',
        tenantId,
      }),
  };

  storage = {
    uploadWithProgress: (
      tenantId: string,
      file: File,
      folderId: string | null,
      onProgress?: (percent: number) => void
    ): Promise<ApiDocument> => {
      return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('file', file);
        if (folderId) {
          formData.append('folder_id', folderId);
        }

        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${this.baseUrl}/storage/upload/direct`, true);
        xhr.withCredentials = true;
        if (this.accessToken) {
          xhr.setRequestHeader('Authorization', `Bearer ${this.accessToken}`);
        }
        if (tenantId) {
          xhr.setRequestHeader('X-Tenant-ID', tenantId);
        }

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable && onProgress) {
            const pct = Math.min(100, Math.round((event.loaded / event.total) * 100));
            onProgress(pct);
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const parsed = JSON.parse(xhr.responseText) as ApiUploadCompleteResponse;
              resolve(parsed.document);
            } catch {
              reject(new ApiError(xhr.status, 'Réponse JSON invalide lors de l’upload.'));
            }
          } else {
            let detail = `Échec du téléversement (HTTP ${xhr.status})`;
            try {
              const parsed = JSON.parse(xhr.responseText) as ApiErrorPayload;
              if (parsed.detail) detail = parsed.detail;
            } catch {
              // ignore
            }
            if (xhr.status === 401 && this.onUnauthorized) {
              this.accessToken = null;
              this.onUnauthorized();
            }
            reject(new ApiError(xhr.status, detail));
          }
        };

        xhr.onerror = () => {
          reject(new ApiError(0, 'Erreur réseau lors du transfert vers le serveur DocuSpace.'));
        };

        xhr.send(formData);
      });
    },
    getDownloadUrl: (tenantId: string, documentId: string) =>
      this.request<{ document_id: string; filename: string; download_url: string; expires_in_seconds: number }>(
        `/storage/download/${documentId}`,
        { tenantId }
      ),
  };

  shares = {
    list: (tenantId: string) => this.request<ApiShare[]>('/shares', { tenantId }),
    createLink: (
      tenantId: string,
      payload: {
        document_id?: string;
        folder_id?: string;
        password?: string;
        expires_in_hours?: number;
        max_downloads?: number;
      }
    ) =>
      this.request<ApiShare>('/shares/link', {
        method: 'POST',
        tenantId,
        body: JSON.stringify(payload),
      }),
    update: (
      tenantId: string,
      shareId: string,
      payload: { role?: string; is_active?: boolean; max_downloads?: number; expires_in_hours?: number }
    ) =>
      this.request<ApiShare>(`/shares/${shareId}`, {
        method: 'PATCH',
        tenantId,
        body: JSON.stringify(payload),
      }),
    revoke: (tenantId: string, shareId: string) =>
      this.request<void>(`/shares/${shareId}`, { method: 'DELETE', tenantId }),
  };

  gdpr = {
    exportData: () => this.request<Record<string, unknown>>('/gdpr/export'),
    deleteAccount: (confirmationPhrase: string = 'SUPPRIMER') =>
      this.request<{ message: string }>('/gdpr/delete-account', {
        method: 'POST',
        body: JSON.stringify({ confirmation_phrase: confirmationPhrase }),
      }),
  };
}

export const apiClient = new DocuSpaceApiClient();
