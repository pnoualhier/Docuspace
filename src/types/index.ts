export type PlanType = 'FREE' | 'PERSONAL' | 'PREMIUM';

export interface Plan {
  id: PlanType;
  name: string;
  maxStorageBytes: number;
  maxFileSizeBytes: number;
  maxMembers: number;
  maxVersionsPerFile: number;
  priceMonthly: number;
  priceYearly?: number;
  features: string[];
}

export type UserRole = 'OWNER' | 'EDITOR' | 'VIEWER' | 'GUEST';

export interface User {
  id: string;
  email: string;
  fullName: string;
  isActive: boolean;
  isVerified: boolean;
  isSuperuser: boolean;
  createdAt: string;
}

export interface Tenant {
  id: string;
  name: string;
  ownerId: string;
  planId: PlanType;
  role: UserRole;
  isActive: boolean;
  createdAt: string;
  usedBytes: number;
  reservedBytes: number;
  documentCount: number;
  maxStorageBytes?: number;
  subscriptionStatus?: 'ACTIVE' | 'PAST_DUE' | 'CANCELED' | 'TRIALING';
  isRestrictedReadOnly?: boolean;
}

export interface TenantMemberItem {
  id: string;
  userId: string;
  email: string;
  fullName: string;
  role: UserRole;
  joinedAt: string;
}

export interface Folder {
  id: string;
  tenantId: string;
  parentId: string | null;
  name: string;
  color: string;
  isFavorite: boolean;
  isTrashed: boolean;
  trashedAt?: string | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export type DocumentStatus =
  | 'INITIATED'
  | 'UPLOADING'
  | 'PENDING_SCAN'
  | 'READY'
  | 'REJECTED'
  | 'FAILED'
  | 'QUARANTINED';
export type AntivirusStatus = 'PENDING' | 'CLEAN' | 'INFECTED' | 'SCAN_ERROR';

export interface DocumentVersion {
  id: string;
  documentId: string;
  versionNumber: number;
  storageKey?: string;
  sizeBytes: number;
  mimeType: string;
  sha256Hash: string;
  changeSummary?: string | null;
  createdAt: string;
}

export interface DocumentItem {
  id: string;
  tenantId: string;
  folderId: string | null;
  originalName: string;
  storageKey?: string;
  mimeType: string;
  extension: string;
  sizeBytes: number;
  sha256Hash: string;
  status: DocumentStatus;
  antivirusStatus: AntivirusStatus;
  antivirusDetails?: string;
  isFavorite: boolean;
  isTrashed: boolean;
  trashedAt?: string | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  versions: DocumentVersion[];
}

export interface DocumentPreviewData {
  documentId: string;
  originalName: string;
  mimeType: string;
  extension: string;
  sizeBytes: number;
  mode: 'text' | 'markdown' | 'csv' | 'svg' | 'binary_url' | 'unsupported';
  textContent?: string | null;
  htmlContent?: string | null;
  svgContent?: string | null;
  csvData?: {
    headers: string[];
    rows: string[][];
    total_rows_parsed: number;
    delimiter: string;
  } | null;
  downloadUrl?: string | null;
  message?: string | null;
}

export interface ShareRecipientItem {
  id: string;
  recipientEmail: string;
  recipientUserId?: string | null;
  role: UserRole;
  createdAt: string;
}

export interface Share {
  id: string;
  tenantId: string;
  documentId?: string | null;
  folderId?: string | null;
  createdBy: string;
  shareType: 'INTERNAL_USER' | 'SECURE_LINK';
  role: UserRole;
  token?: string | null;
  publicUrl?: string | null;
  hasPassword?: boolean;
  documentName?: string;
  maxDownloads?: number | null;
  downloadCount: number;
  expiresAt?: string | null;
  recipientEmail?: string;
  recipients?: ShareRecipientItem[];
  isActive: boolean;
  isExpired?: boolean;
  createdAt: string;
}

export interface PublicShareDetails {
  token: string;
  resourceType: 'DOCUMENT' | 'FOLDER';
  resourceName: string;
  mimeType?: string | null;
  extension?: string | null;
  sizeBytes?: number | null;
  sha256Hash?: string | null;
  hasPassword: boolean;
  isPasswordRequired: boolean;
  expiresAt?: string | null;
  downloadCount: number;
  maxDownloads?: number | null;
  canDownload: boolean;
  isActive: boolean;
}

export interface AuditLogItem {
  id: string;
  tenantId: string | null;
  userId: string | null;
  userEmail: string;
  action: string;
  resourceType: string;
  resourceId?: string | null;
  resourceName?: string;
  details?: Record<string, unknown>;
  ipAddress: string | null;
  userAgent?: string | null;
  timestamp: string;
  status?: 'SUCCESS' | 'WARNING' | 'BLOCKED' | 'FAILED' | 'DENIED';
}

export interface SessionInfo {
  id: string;
  userAgent: string | null;
  ipAddress: string | null;
  isRevoked: boolean;
  isCurrent: boolean;
  expiresAt: string;
  createdAt: string;
  lastActiveAt: string;
}

export type NotificationCategory = 'STORAGE' | 'SECURITY' | 'BILLING' | 'SHARING';
export type NotificationLevel = 'INFO' | 'WARNING' | 'CRITICAL' | 'SUCCESS';

export interface NotificationItem {
  id: string;
  tenantId: string;
  userId: string;
  category: NotificationCategory;
  title: string;
  message: string;
  level: NotificationLevel;
  actionUrl?: string | null;
  isRead: boolean;
  createdAt: string;
}

export interface InvoiceItem {
  id: string;
  createdAt: string | null;
  eventType: string;
  planId: string;
  planName: string;
  amountEur: number;
  status: string;
}
