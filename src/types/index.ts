export type PlanType = 'FREE' | 'PERSONAL' | 'PREMIUM';

export interface Plan {
  id: PlanType;
  name: string;
  maxStorageBytes: number;
  maxFileSizeBytes: number;
  maxMembers: number;
  maxVersionsPerFile: number;
  priceMonthly: number;
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
}

export interface Folder {
  id: string;
  tenantId: string;
  parentId: string | null;
  name: string;
  color: string;
  isFavorite: boolean;
  isTrashed: boolean;
  trashedAt?: string;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export type DocumentStatus = 'INITIATED' | 'UPLOADING' | 'PENDING_SCAN' | 'READY' | 'REJECTED' | 'FAILED';
export type AntivirusStatus = 'PENDING' | 'CLEAN' | 'INFECTED' | 'SCAN_ERROR';

export interface DocumentVersion {
  id: string;
  documentId: string;
  versionNumber: number;
  storageKey: string;
  sizeBytes: number;
  mimeType: string;
  sha256Hash: string;
  changeSummary?: string;
  createdAt: string;
}

export interface DocumentItem {
  id: string;
  tenantId: string;
  folderId: string | null;
  originalName: string;
  storageKey: string;
  mimeType: string;
  extension: string;
  sizeBytes: number;
  sha256Hash: string;
  status: DocumentStatus;
  antivirusStatus: AntivirusStatus;
  antivirusDetails?: string;
  isFavorite: boolean;
  isTrashed: boolean;
  trashedAt?: string;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  versions: DocumentVersion[];
  contentPreview?: string; // sample textual or image data URI for preview
}

export interface Share {
  id: string;
  tenantId: string;
  documentId?: string;
  folderId?: string;
  createdBy: string;
  shareType: 'INTERNAL_USER' | 'SECURE_LINK';
  role: UserRole;
  token?: string;
  hasPassword?: boolean;
  maxDownloads?: number;
  downloadCount: number;
  expiresAt?: string;
  recipientEmail?: string;
  isActive: boolean;
  createdAt: string;
}

export interface AuditLogItem {
  id: string;
  tenantId: string;
  userId: string;
  userEmail: string;
  action: string;
  resourceType: 'DOCUMENT' | 'FOLDER' | 'SHARE' | 'AUTH' | 'TENANT';
  resourceName: string;
  ipAddress: string;
  userAgent: string;
  timestamp: string;
  status: 'SUCCESS' | 'WARNING' | 'BLOCKED';
}

export interface SessionInfo {
  id: string;
  device: string;
  browser: string;
  ipAddress: string;
  lastActive: string;
  isCurrent: boolean;
}
