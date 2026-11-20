export interface ApiValidationDetailItem {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
}

export interface ApiErrorPayload {
  detail?: string | ApiValidationDetailItem[];
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

export interface ApiStorageUsage {
  tenant_id: string;
  used_bytes: number;
  reserved_bytes: number;
  document_count: number;
  max_storage_bytes: number;
  percent_used: number;
}

export interface ApiTenant {
  id: string;
  name: string;
  owner_id: string;
  plan_id: string;
  role?: string;
  is_active: boolean;
  subscription_status?: string;
  restricted_read_only?: boolean;
  created_at?: string;
  storage_usage?: ApiStorageUsage | null;
}

export interface ApiTenantMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  joined_at: string;
}

export interface ApiFolder {
  id: string;
  tenant_id: string;
  parent_id: string | null;
  name: string;
  color: string;
  is_favorite: boolean;
  is_trashed: boolean;
  trashed_at?: string | null;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface ApiDocument {
  id: string;
  tenant_id: string;
  folder_id: string | null;
  original_name: string;
  storage_key?: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  sha256_hash: string;
  status: string;
  antivirus_status: string;
  antivirus_details?: string;
  is_favorite: boolean;
  is_trashed: boolean;
  trashed_at?: string | null;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface ApiDocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  size_bytes: number;
  mime_type: string;
  sha256_hash: string;
  change_summary?: string | null;
  created_at: string;
}

export interface ApiDocumentPreview {
  document_id: string;
  original_name: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  mode: 'text' | 'markdown' | 'csv' | 'svg' | 'binary_url' | 'unsupported';
  text_content?: string | null;
  html_content?: string | null;
  svg_content?: string | null;
  csv_data?: {
    headers: string[];
    rows: string[][];
    total_rows_parsed: number;
    delimiter: string;
  } | null;
  download_url?: string | null;
  message?: string | null;
}

export interface ApiUploadCompleteResponse {
  document: ApiDocument;
  antivirus_status: string;
  threat_detected?: string | null;
  details: string;
}

export interface ApiShareRecipient {
  id: string;
  recipient_email: string;
  recipient_user_id?: string | null;
  role: string;
  created_at: string;
}

export interface ApiShare {
  id: string;
  tenant_id: string;
  document_id?: string | null;
  folder_id?: string | null;
  created_by?: string | null;
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
  is_expired?: boolean;
  recipients?: ApiShareRecipient[];
  created_at: string;
  updated_at: string;
}

export interface ApiPublicShareDetails {
  token: string;
  resource_type: 'DOCUMENT' | 'FOLDER';
  resource_name: string;
  mime_type?: string | null;
  extension?: string | null;
  size_bytes?: number | null;
  sha256_hash?: string | null;
  has_password: boolean;
  is_password_required: boolean;
  expires_at?: string | null;
  download_count: number;
  max_downloads?: number | null;
  can_download: boolean;
  is_active: boolean;
}

export interface ApiPublicShareDownload {
  download_url: string;
  filename: string;
  size_bytes: number;
  mime_type: string;
  download_count: number;
  max_downloads?: number | null;
}

export interface ApiSession {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  is_revoked: boolean;
  is_current: boolean;
  expires_at: string;
  created_at: string;
  last_active_at: string;
}

export interface ApiNotification {
  id: string;
  tenant_id: string;
  user_id: string;
  category: string;
  level: string;
  title: string;
  message: string;
  action_url?: string | null;
  is_read: boolean;
  created_at: string;
}

export interface ApiPlan {
  id: string;
  name: string;
  price_monthly: number;
  price_yearly?: number;
  max_storage_bytes: number;
  max_file_size_bytes: number;
  max_members: number;
  max_versions_per_file: number;
  features: string[] | Record<string, unknown>;
}

export interface ApiInvoice {
  id: string;
  created_at: string | null;
  event_type: string;
  plan_id: string;
  plan_name: string;
  amount_eur: number;
  status: string;
}

export interface ApiAdminStats {
  tenants_count: number;
  users_count: number;
  documents_count: number;
  total_storage_bytes: number;
  storage_capacity_bytes: number;
  antivirus_status: string;
}

export interface ApiAdminTenant {
  id: string;
  name: string;
  owner_id: string;
  owner_email: string | null;
  plan_id: string;
  plan_name: string;
  subscription_status: string;
  restricted_read_only: boolean;
  is_active: boolean;
  used_bytes: number;
  reserved_bytes: number;
  document_count: number;
  max_storage_bytes: number;
  created_at: string | null;
}

export interface ApiAuditLog {
  id: string;
  timestamp: string | null;
  tenant_id: string | null;
  user_id: string | null;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  user_agent?: string | null;
}

const DEFAULT_BASE_URL =
  (typeof import.meta !== 'undefined' &&
    (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL) ||
  '/api/v1';

class DocuSpaceApiClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private onUnauthorized: (() => void) | null = null;
  private refreshPromise: Promise<boolean> | null = null;

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

  private async tryRefreshSession(): Promise<boolean> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }
    this.refreshPromise = (async () => {
      try {
        const res = await fetch(`${this.baseUrl}/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
        if (!res.ok) {
          return false;
        }
        const data = (await res.json()) as ApiTokenResponse;
        if (data?.access_token) {
          this.accessToken = data.access_token;
          return true;
        }
        return false;
      } catch {
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();
    return this.refreshPromise;
  }

  private formatValidationErrors(items: ApiValidationDetailItem[]): string {
    const messages = items
      .map((item) => {
        const field = String(item.loc?.[item.loc.length - 1] ?? '').toLowerCase();
        const rawMsg = (item.msg || '').toLowerCase();
        if (field === 'email' || rawMsg.includes('email')) {
          return 'Adresse e-mail invalide. Vérifiez le format (ex. nom@domaine.fr).';
        }
        if (field === 'password' || field === 'new_password') {
          if (rawMsg.includes('at least') || rawMsg.includes('min_length') || rawMsg.includes('8')) {
            return 'Le mot de passe est trop court : il doit contenir au moins 8 caractères.';
          }
          return 'Mot de passe non conforme aux exigences de sécurité.';
        }
        if (field === 'full_name') {
          return 'Le nom complet doit contenir au moins 2 caractères.';
        }
        return item.msg || null;
      })
      .filter((m): m is string => Boolean(m));

    if (messages.length > 0) {
      return Array.from(new Set(messages)).join(' ');
    }
    return 'Les informations saisies sont invalides ou incomplètes (erreur de validation 422).';
  }

  private buildFallbackHttpErrorMessage(status: number, path: string): string {
    if (status === 404) {
      return `Service API backend introuvable (HTTP 404 sur ${this.baseUrl}${path}). Le serveur FastAPI ou le proxy Nginx n'est pas actif sur cet environnement ; démarrez la pile complète (backend FastAPI + PostgreSQL) pour créer ou ouvrir un espace.`;
    }
    if (status === 405) {
      return `Méthode HTTP non autorisée sur ${this.baseUrl}${path} (HTTP 405). Vérifiez le routage du proxy API.`;
    }
    if (status === 429) {
      return 'Trop de tentatives effectuées. Veuillez patienter quelques minutes avant de réessayer (HTTP 429).';
    }
    if (status === 502 || status === 503 || status === 504) {
      return `Le serveur backend DocuSpace ou PostgreSQL est temporairement indisponible (HTTP ${status}).`;
    }
    if (status >= 500) {
      return `Erreur interne du serveur lors du traitement de la requête (HTTP ${status}).`;
    }
    return `Erreur HTTP ${status}`;
  }

  private async request<T>(
    path: string,
    options: RequestInit & {
      tenantId?: string;
      skipAuthCallback?: boolean;
      skipRefreshRetry?: boolean;
      rawResponse?: boolean;
    } = {}
  ): Promise<T> {
    const { tenantId, skipAuthCallback, skipRefreshRetry, rawResponse, headers, ...fetchOpts } = options;
    const mergedHeaders = this.buildHeaders(tenantId, headers as Record<string, string> | undefined);
    if (fetchOpts.body && !(fetchOpts.body instanceof FormData) && !mergedHeaders['Content-Type']) {
      mergedHeaders['Content-Type'] = 'application/json';
    }

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...fetchOpts,
        headers: mergedHeaders,
        credentials: 'include',
      });
    } catch {
      throw new ApiError(
        0,
        "Impossible de joindre le serveur API DocuSpace. Vérifiez votre connexion réseau et que le backend FastAPI est démarré."
      );
    }

    if (response.status === 401 && !skipRefreshRetry && path !== '/auth/login' && path !== '/auth/refresh') {
      const refreshed = await this.tryRefreshSession();
      if (refreshed) {
        return this.request<T>(path, { ...options, skipRefreshRetry: true });
      }
    }

    if (!response.ok) {
      let detail = this.buildFallbackHttpErrorMessage(response.status, path);
      try {
        const rawText = await response.text();
        if (rawText) {
          const body = JSON.parse(rawText) as ApiErrorPayload;
          if (body && typeof body.detail === 'string' && body.detail.trim()) {
            detail = body.detail;
          } else if (body && Array.isArray(body.detail) && body.detail.length > 0) {
            detail = this.formatValidationErrors(body.detail);
          } else if (body && typeof body.message === 'string' && body.message.trim()) {
            detail = body.message;
          }
        }
      } catch {
        // Non-JSON error body (e.g. Vite/Nginx HTML 404/502 page): keep explicit status message
      }
      if (response.status === 401 && !skipAuthCallback && this.onUnauthorized) {
        this.accessToken = null;
        this.onUnauthorized();
      }
      throw new ApiError(response.status, detail);
    }

    if (rawResponse) {
      return response as unknown as T;
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
        app?: string;
        version?: string;
        database: string;
        redis?: string;
        storage: string;
        antivirus: string;
      }>('/health', { skipAuthCallback: true, skipRefreshRetry: true }),
  };

  auth = {
    login: async (email: string, password: string): Promise<ApiTokenResponse> => {
      const res = await this.request<ApiTokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
        skipAuthCallback: true,
        skipRefreshRetry: true,
      });
      this.accessToken = res.access_token;
      return res;
    },
    register: (fullName: string, email: string, password: string) =>
      this.request<ApiUser>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ full_name: fullName, email, password }),
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
    refresh: () => this.tryRefreshSession(),
    logout: async () => {
      try {
        await this.request('/auth/logout', { method: 'POST', skipAuthCallback: true, skipRefreshRetry: true });
      } finally {
        this.accessToken = null;
      }
    },
    me: (options: { skipAuthCallback?: boolean } = {}) =>
      this.request<ApiUser>('/auth/me', { skipAuthCallback: options.skipAuthCallback }),
    sessions: () => this.request<ApiSession[]>('/auth/sessions'),
    revokeSession: (sessionId: string) =>
      this.request<void>(`/auth/sessions/${sessionId}`, { method: 'DELETE' }),
    revokeAllSessions: () =>
      this.request<{ message: string }>('/auth/sessions/revoke-all', { method: 'POST' }),
    passwordResetRequest: (email: string) =>
      this.request<{ message: string }>('/auth/password-reset/request', {
        method: 'POST',
        body: JSON.stringify({ email }),
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
    passwordResetConfirm: (token: string, newPassword: string) =>
      this.request<{ message: string }>('/auth/password-reset/confirm', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: newPassword }),
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
    verifyEmail: (token: string) =>
      this.request<{ message: string }>(`/auth/verify-email?token=${encodeURIComponent(token)}`, {
        method: 'GET',
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
    resendVerification: (email: string) =>
      this.request<{ message: string }>('/auth/resend-verification', {
        method: 'POST',
        body: JSON.stringify({ email }),
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
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
    members: (tenantId: string) =>
      this.request<ApiTenantMember[]>('/tenants/current/members', { tenantId }),
    inviteMember: (tenantId: string, email: string, role: string) =>
      this.request<{ message: string }>('/tenants/current/members', {
        method: 'POST',
        tenantId,
        body: JSON.stringify({ email, role }),
      }),
    updateMemberRole: (tenantId: string, userId: string, role: string) =>
      this.request<{ message: string }>(`/tenants/current/members/${userId}`, {
        method: 'PATCH',
        tenantId,
        body: JSON.stringify({ role }),
      }),
    removeMember: (tenantId: string, userId: string) =>
      this.request<void>(`/tenants/current/members/${userId}`, {
        method: 'DELETE',
        tenantId,
      }),
  };

  documents = {
    listFolders: (
      tenantId: string,
      params: { parentId?: string | null; trashed?: boolean; flat?: boolean; limit?: number; offset?: number } = {}
    ) => {
      const qs = new URLSearchParams();
      if (params.parentId) qs.set('parent_id', params.parentId);
      if (params.trashed !== undefined) qs.set('is_trashed', String(params.trashed));
      if (params.flat !== undefined) qs.set('flat', String(params.flat));
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
    updateFolder: (
      tenantId: string,
      folderId: string,
      payload: { name?: string; color?: string; is_favorite?: boolean }
    ) =>
      this.request<ApiFolder>(`/documents/folders/${folderId}`, {
        method: 'PATCH',
        tenantId,
        body: JSON.stringify(payload),
      }),
    moveFolder: (tenantId: string, folderId: string, newParentId: string | null) => {
      const qs = newParentId ? `?new_parent_id=${encodeURIComponent(newParentId)}` : '';
      return this.request<ApiFolder>(`/documents/folders/${folderId}/move${qs}`, {
        method: 'PATCH',
        tenantId,
      });
    },
    copyFolder: (tenantId: string, folderId: string, targetParentId: string | null = null, newName?: string) =>
      this.request<ApiFolder>(`/documents/folders/${folderId}/copy`, {
        method: 'POST',
        tenantId,
        body: JSON.stringify({ target_parent_id: targetParentId, new_name: newName }),
      }),
    deleteFolder: (tenantId: string, folderId: string) =>
      this.request<void>(`/documents/folders/${folderId}`, { method: 'DELETE', tenantId }),
    list: (
      tenantId: string,
      params: { folderId?: string | null; trashed?: boolean; isFavorite?: boolean; limit?: number; offset?: number } = {}
    ) => {
      const qs = new URLSearchParams();
      if (params.folderId) qs.set('folder_id', params.folderId);
      if (params.trashed !== undefined) qs.set('is_trashed', String(params.trashed));
      if (params.isFavorite !== undefined) qs.set('is_favorite', String(params.isFavorite));
      if (params.limit !== undefined) qs.set('limit', String(params.limit));
      if (params.offset !== undefined) qs.set('offset', String(params.offset));
      const query = qs.toString() ? `?${qs.toString()}` : '';
      return this.request<ApiDocument[]>(`/documents/documents${query}`, { tenantId });
    },
    search: (tenantId: string, query: string, limit: number = 100, offset: number = 0) =>
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
    toggleFavorite: (tenantId: string, documentId: string, isFavorite: boolean) =>
      this.request<ApiDocument>(`/documents/documents/${documentId}`, {
        method: 'PATCH',
        tenantId,
        body: JSON.stringify({ is_favorite: isFavorite }),
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
      this.request<{ purged_document_id: string; freed_bytes: number; message: string }>(
        `/documents/documents/${documentId}/purge`,
        {
          method: 'DELETE',
          tenantId,
        }
      ),
    bulkMove: (tenantId: string, documentIds: string[], targetFolderId: string | null) =>
      this.request<{ success_count: number; failed_count: number; message: string; affected_ids: string[] }>(
        '/documents/documents/bulk/move',
        {
          method: 'POST',
          tenantId,
          body: JSON.stringify({ document_ids: documentIds, target_folder_id: targetFolderId }),
        }
      ),
    bulkTrash: (tenantId: string, documentIds: string[]) =>
      this.request<{ success_count: number; failed_count: number; message: string; affected_ids: string[] }>(
        '/documents/documents/bulk/trash',
        {
          method: 'POST',
          tenantId,
          body: JSON.stringify({ document_ids: documentIds }),
        }
      ),
    bulkRestore: (tenantId: string, documentIds: string[]) =>
      this.request<{ success_count: number; failed_count: number; message: string; affected_ids: string[] }>(
        '/documents/documents/bulk/restore',
        {
          method: 'POST',
          tenantId,
          body: JSON.stringify({ document_ids: documentIds }),
        }
      ),
    bulkPurge: (tenantId: string, documentIds: string[]) =>
      this.request<{ success_count: number; failed_count: number; message: string; affected_ids: string[] }>(
        '/documents/documents/bulk/purge',
        {
          method: 'POST',
          tenantId,
          body: JSON.stringify({ document_ids: documentIds }),
        }
      ),
    emptyTrash: (tenantId: string) =>
      this.request<{ purged_documents_count: number; purged_folders_count: number; freed_bytes: number; message: string }>(
        '/documents/trash/empty',
        {
          method: 'POST',
          tenantId,
        }
      ),
    getPreview: (tenantId: string, documentId: string) =>
      this.request<ApiDocumentPreview>(`/documents/documents/${documentId}/preview`, { tenantId }),
    listVersions: (tenantId: string, documentId: string) =>
      this.request<ApiDocumentVersion[]>(`/documents/documents/${documentId}/versions`, { tenantId }),
    uploadVersion: (tenantId: string, documentId: string, file: File, changeSummary?: string) => {
      const formData = new FormData();
      formData.append('file', file);
      if (changeSummary) {
        formData.append('change_summary', changeSummary);
      }
      return this.request<ApiDocumentVersion>(`/documents/documents/${documentId}/versions/upload`, {
        method: 'POST',
        tenantId,
        body: formData,
      });
    },
    restoreVersion: (tenantId: string, documentId: string, versionId: string) =>
      this.request<{
        document_id: string;
        restored_version_number: number;
        size_bytes: number;
        sha256_hash: string;
        message: string;
      }>(`/documents/documents/${documentId}/versions/${versionId}/restore`, {
        method: 'POST',
        tenantId,
      }),
    purgeVersion: (tenantId: string, documentId: string, versionId: string) =>
      this.request<{
        purged_version_id: string;
        freed_bytes: number;
        remaining_version_count: number;
        message: string;
      }>(`/documents/documents/${documentId}/versions/${versionId}`, {
        method: 'DELETE',
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
              if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
                detail = parsed.detail;
              } else if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
                detail = this.formatValidationErrors(parsed.detail);
              } else if (typeof parsed.message === 'string' && parsed.message.trim()) {
                detail = parsed.message;
              }
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
    reconcile: (tenantId: string) =>
      this.request<Record<string, unknown>>('/storage/reconcile', {
        method: 'POST',
        tenantId,
      }),
  };

  shares = {
    list: (tenantId: string) => this.request<ApiShare[]>('/shares', { tenantId }),
    received: () => this.request<ApiShare[]>('/shares/received'),
    downloadReceived: (shareId: string) =>
      this.request<ApiPublicShareDownload>(`/shares/received/${shareId}/download`),
    createLink: (
      tenantId: string,
      payload: {
        document_id?: string;
        folder_id?: string;
        password?: string;
        expires_in_hours?: number;
        max_downloads?: number;
        role?: string;
      }
    ) =>
      this.request<ApiShare>('/shares/link', {
        method: 'POST',
        tenantId,
        body: JSON.stringify(payload),
      }),
    createInternal: (
      tenantId: string,
      payload: {
        document_id?: string;
        folder_id?: string;
        recipient_email: string;
        role: string;
      }
    ) =>
      this.request<ApiShare>('/shares/internal', {
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
    getPublic: (token: string) =>
      this.request<ApiPublicShareDetails>(`/shares/public/${encodeURIComponent(token)}`, {
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
    accessPublic: (token: string, password?: string) =>
      this.request<ApiPublicShareDetails>(`/shares/public/${encodeURIComponent(token)}/access`, {
        method: 'POST',
        body: JSON.stringify({ password: password || null }),
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
    downloadPublic: (token: string, password?: string) =>
      this.request<ApiPublicShareDownload>(`/shares/public/${encodeURIComponent(token)}/download`, {
        method: 'POST',
        body: JSON.stringify({ password: password || null }),
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
  };

  notifications = {
    list: (tenantId: string, params: { unreadOnly?: boolean; category?: string } = {}) => {
      const qs = new URLSearchParams();
      if (params.unreadOnly) qs.set('unread_only', 'true');
      if (params.category && params.category !== 'ALL') qs.set('category', params.category);
      const q = qs.toString() ? `?${qs.toString()}` : '';
      return this.request<{ items: ApiNotification[]; total: number; unread_count: number }>(
        `/notifications${q}`,
        { tenantId }
      );
    },
    markRead: (tenantId: string, notificationId: string) =>
      this.request<{ success: boolean; id: string }>(`/notifications/${notificationId}/read`, {
        method: 'POST',
        tenantId,
      }),
    markAllRead: (tenantId: string) =>
      this.request<{ success: boolean; marked_count: number }>('/notifications/read-all', {
        method: 'POST',
        tenantId,
      }),
    delete: (tenantId: string, notificationId: string) =>
      this.request<void>(`/notifications/${notificationId}`, {
        method: 'DELETE',
        tenantId,
      }),
    checkQuota: (tenantId: string) =>
      this.request<{ alert_created: boolean; notification: ApiNotification | null }>('/notifications/check-quota', {
        method: 'POST',
        tenantId,
        body: JSON.stringify({}),
      }),
  };

  billing = {
    plans: () =>
      this.request<ApiPlan[]>('/billing/plans', {
        skipAuthCallback: true,
        skipRefreshRetry: true,
      }),
    checkout: (
      tenantId: string,
      payload: { plan_id: string; billing_interval: 'monthly' | 'yearly'; success_url?: string; cancel_url?: string }
    ) =>
      this.request<{
        session_id: string;
        url: string;
        tenant_id: string;
        plan_id: string;
        billing_interval: string;
        amount_eur: number;
        currency: string;
        status: string;
        expires_at: number;
      }>('/billing/checkout', {
        method: 'POST',
        tenantId,
        body: JSON.stringify(payload),
      }),
    invoices: (tenantId: string) => this.request<ApiInvoice[]>('/billing/invoices', { tenantId }),
  };

  admin = {
    stats: () => this.request<ApiAdminStats>('/admin/stats'),
    users: (params: { search?: string; limit?: number; offset?: number } = {}) => {
      const qs = new URLSearchParams();
      if (params.search) qs.set('search', params.search);
      if (params.limit !== undefined) qs.set('limit', String(params.limit));
      if (params.offset !== undefined) qs.set('offset', String(params.offset));
      const q = qs.toString() ? `?${qs.toString()}` : '';
      return this.request<{ users: ApiUser[]; total: number; limit: number; offset: number }>(`/admin/users${q}`);
    },
    tenants: (params: { limit?: number; offset?: number } = {}) => {
      const qs = new URLSearchParams();
      if (params.limit !== undefined) qs.set('limit', String(params.limit));
      if (params.offset !== undefined) qs.set('offset', String(params.offset));
      const q = qs.toString() ? `?${qs.toString()}` : '';
      return this.request<{ tenants: ApiAdminTenant[]; total: number; limit: number; offset: number }>(
        `/admin/tenants${q}`
      );
    },
    auditLogs: (params: { action?: string; tenantId?: string; limit?: number; offset?: number } = {}) => {
      const qs = new URLSearchParams();
      if (params.action) qs.set('action', params.action);
      if (params.tenantId) qs.set('tenant_id', params.tenantId);
      if (params.limit !== undefined) qs.set('limit', String(params.limit));
      if (params.offset !== undefined) qs.set('offset', String(params.offset));
      const q = qs.toString() ? `?${qs.toString()}` : '';
      return this.request<{ logs: ApiAuditLog[]; total: number; limit: number; offset: number }>(
        `/admin/audit-logs${q}`
      );
    },
    exportAuditLogsCsv: async (): Promise<Blob> => {
      const response = await this.request<Response>('/admin/audit-logs?format=csv', { rawResponse: true });
      return response.blob();
    },
    updateUserStatus: (userId: string, isActive: boolean) =>
      this.request<{ id: string; is_active: boolean }>(`/admin/users/${userId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      }),
    overrideTenantPlan: (tenantId: string, planId: string) =>
      this.request<{ tenant_id: string; plan_id: string }>(`/admin/tenants/${tenantId}/plan`, {
        method: 'PATCH',
        body: JSON.stringify({ plan_id: planId }),
      }),
  };

  gdpr = {
    exportData: async (): Promise<Blob> => {
      const response = await this.request<Response>('/gdpr/export', { rawResponse: true });
      return response.blob();
    },
    deleteAccount: (confirmationPhrase: string = 'SUPPRIMER') =>
      this.request<{ message: string; status?: string }>('/gdpr/delete-account', {
        method: 'POST',
        body: JSON.stringify({ confirmation_phrase: confirmationPhrase }),
      }),
  };
}

export const apiClient = new DocuSpaceApiClient();
