import { DocumentItem, Folder, Plan, Tenant, User } from '../../types';

export const FIXTURE_USER: User = {
  id: 'usr-test-001',
  email: 'claire.bernard@example.org',
  fullName: 'Claire Bernard',
  isActive: true,
  isVerified: true,
  isSuperuser: false,
  createdAt: '2026-01-10T09:00:00Z',
};

export const FIXTURE_ADMIN_USER: User = {
  id: 'usr-test-admin',
  email: 'ops.admin@example.org',
  fullName: 'Marc Lefevre',
  isActive: true,
  isVerified: true,
  isSuperuser: true,
  createdAt: '2026-01-01T08:00:00Z',
};

export const FIXTURE_PLANS: Plan[] = [
  {
    id: 'FREE',
    name: 'Gratuit',
    maxStorageBytes: 524288000,
    maxFileSizeBytes: 52428800,
    maxMembers: 1,
    maxVersionsPerFile: 3,
    priceMonthly: 0,
    priceYearly: 0,
    features: ['500 Mo de stockage', 'Analyse ClamAV'],
  },
  {
    id: 'PERSONAL',
    name: 'Personnel',
    maxStorageBytes: 21474836480,
    maxFileSizeBytes: 524288000,
    maxMembers: 5,
    maxVersionsPerFile: 10,
    priceMonthly: 4.99,
    priceYearly: 49.9,
    features: ['20 Go de stockage', '5 membres'],
  },
  {
    id: 'PREMIUM',
    name: 'Premium',
    maxStorageBytes: 107374182400,
    maxFileSizeBytes: 2147483648,
    maxMembers: 25,
    maxVersionsPerFile: 50,
    priceMonthly: 14.99,
    priceYearly: 149.9,
    features: ['100 Go de stockage', '25 membres'],
  },
];

export const FIXTURE_TENANT: Tenant = {
  id: 'tnt-test-primary',
  name: 'Espace Principal Test',
  ownerId: FIXTURE_USER.id,
  planId: 'PERSONAL',
  role: 'OWNER',
  isActive: true,
  createdAt: '2026-01-10T09:00:00Z',
  usedBytes: 1048576,
  reservedBytes: 0,
  documentCount: 2,
  maxStorageBytes: 21474836480,
  subscriptionStatus: 'ACTIVE',
  isRestrictedReadOnly: false,
};

export const FIXTURE_SECOND_TENANT: Tenant = {
  id: 'tnt-test-secondary',
  name: 'Espace Secondaire Test',
  ownerId: FIXTURE_USER.id,
  planId: 'FREE',
  role: 'EDITOR',
  isActive: true,
  createdAt: '2026-02-01T10:00:00Z',
  usedBytes: 4096,
  reservedBytes: 0,
  documentCount: 1,
  maxStorageBytes: 524288000,
  subscriptionStatus: 'ACTIVE',
  isRestrictedReadOnly: false,
};

export const FIXTURE_FOLDERS: Folder[] = [
  {
    id: 'fld-test-001',
    tenantId: FIXTURE_TENANT.id,
    parentId: null,
    name: 'Archives Comptables',
    color: '#3B82F6',
    isFavorite: false,
    isTrashed: false,
    createdBy: FIXTURE_USER.id,
    createdAt: '2026-01-12T10:00:00Z',
    updatedAt: '2026-01-12T10:00:00Z',
  },
];

export const FIXTURE_DOCUMENTS: DocumentItem[] = [
  {
    id: 'doc-test-001',
    tenantId: FIXTURE_TENANT.id,
    folderId: null,
    originalName: 'note_synthese.txt',
    mimeType: 'text/plain',
    extension: 'txt',
    sizeBytes: 2048,
    sha256Hash: 'a'.repeat(64),
    status: 'READY',
    antivirusStatus: 'CLEAN',
    isFavorite: false,
    isTrashed: false,
    createdBy: FIXTURE_USER.id,
    createdAt: '2026-01-15T12:00:00Z',
    updatedAt: '2026-01-15T12:00:00Z',
    versions: [],
  },
  {
    id: 'doc-test-002',
    tenantId: FIXTURE_TENANT.id,
    folderId: null,
    originalName: 'tableau_suivi.csv',
    mimeType: 'text/csv',
    extension: 'csv',
    sizeBytes: 4096,
    sha256Hash: 'b'.repeat(64),
    status: 'PENDING_SCAN',
    antivirusStatus: 'PENDING',
    isFavorite: true,
    isTrashed: false,
    createdBy: FIXTURE_USER.id,
    createdAt: '2026-01-16T12:00:00Z',
    updatedAt: '2026-01-16T12:00:00Z',
    versions: [],
  },
];
