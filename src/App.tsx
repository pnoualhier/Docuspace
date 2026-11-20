import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import {
  User,
  Tenant,
  Folder,
  DocumentItem,
  PlanType,
  Share,
  NotificationItem,
  NotificationCategory,
  NotificationLevel,
  InvoiceItem,
  Plan,
  UserRole,
} from './types';
import { Header } from './components/Header';
import { Sidebar, NavTab } from './components/Sidebar';
import { FileExplorer } from './components/FileExplorer';
import { FilePreviewModal } from './components/FilePreviewModal';
import { FileUploadModal } from './components/FileUploadModal';
import { ShareModal } from './components/ShareModal';
import { VersionsModal } from './components/VersionsModal';
import { FolderModal } from './components/FolderModal';
import { StorageGauge } from './components/StorageGauge';
import { AdminConsole } from './components/AdminConsole';
import { ArchitectureModal } from './components/ArchitectureModal';
import { SettingsModal } from './components/SettingsModal';
import { AuthModal } from './components/AuthModal';
import { TenantMembersModal } from './components/TenantMembersModal';
import { MoveModal } from './components/MoveModal';
import { NotificationsModal } from './components/NotificationsModal';
import { BillingCheckoutModal } from './components/BillingCheckoutModal';
import { ConfirmActionModal } from './components/ConfirmActionModal';
import { RenameModal } from './components/RenameModal';
import { PublicShareView } from './components/PublicShareView';
import {
  apiClient,
  ApiDocument,
  ApiError,
  ApiFolder,
  ApiInvoice,
  ApiNotification,
  ApiPlan,
  ApiShare,
  ApiTenant,
  ApiUser,
} from './services/api';
import {
  FileText,
  Folder as FolderIcon,
  HardDrive,
  ShieldCheck,
  ShieldAlert,
  Clock,
  AlertTriangle,
  CheckCircle2,
  X,
  Download,
  Users,
  Loader2,
} from 'lucide-react';
import { formatBytes } from './services/crypto';

const extractPublicShareToken = (pathname: string): string | null => {
  const match = pathname.match(/^\/s\/([^/?#]+)/);
  if (!match || !match[1]) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
};

const mapApiUser = (u: ApiUser): User => ({
  id: u.id,
  email: u.email,
  fullName: u.full_name,
  isActive: u.is_active,
  isVerified: u.is_verified,
  isSuperuser: u.is_superuser,
  createdAt: u.created_at,
});

const mapApiTenant = (t: ApiTenant): Tenant => ({
  id: t.id,
  name: t.name,
  ownerId: t.owner_id,
  planId: (t.plan_id as PlanType) || 'FREE',
  role: (t.role as UserRole) || 'OWNER',
  isActive: t.is_active,
  createdAt: t.created_at || '',
  usedBytes: t.storage_usage?.used_bytes ?? 0,
  reservedBytes: t.storage_usage?.reserved_bytes ?? 0,
  documentCount: t.storage_usage?.document_count ?? 0,
  maxStorageBytes: t.storage_usage?.max_storage_bytes,
  subscriptionStatus: (t.subscription_status as Tenant['subscriptionStatus']) || 'ACTIVE',
  isRestrictedReadOnly: Boolean(t.restricted_read_only),
});

const mapApiPlan = (p: ApiPlan): Plan => ({
  id: (p.id as PlanType) || 'FREE',
  name: p.name,
  maxStorageBytes: p.max_storage_bytes,
  maxFileSizeBytes: p.max_file_size_bytes,
  maxMembers: p.max_members,
  maxVersionsPerFile: p.max_versions_per_file,
  priceMonthly: p.price_monthly,
  priceYearly: p.price_yearly,
  features: Array.isArray(p.features)
    ? p.features.map((f) => String(f))
    : Object.entries(p.features || {}).map(([k, v]) => `${k}: ${String(v)}`),
});

const mapApiFolder = (f: ApiFolder): Folder => ({
  id: f.id,
  tenantId: f.tenant_id,
  parentId: f.parent_id,
  name: f.name,
  color: f.color,
  isFavorite: f.is_favorite,
  isTrashed: f.is_trashed,
  trashedAt: f.trashed_at ?? null,
  createdBy: f.created_by || '',
  createdAt: f.created_at,
  updatedAt: f.updated_at,
});

const mapApiDoc = (d: ApiDocument): DocumentItem => ({
  id: d.id,
  tenantId: d.tenant_id,
  folderId: d.folder_id,
  originalName: d.original_name,
  storageKey: d.storage_key,
  mimeType: d.mime_type,
  extension: d.extension,
  sizeBytes: d.size_bytes,
  sha256Hash: d.sha256_hash,
  status: (d.status as DocumentItem['status']) || 'READY',
  antivirusStatus: (d.antivirus_status as DocumentItem['antivirusStatus']) || 'PENDING',
  antivirusDetails: d.antivirus_details,
  isFavorite: d.is_favorite,
  isTrashed: d.is_trashed,
  trashedAt: d.trashed_at ?? null,
  createdBy: d.created_by || '',
  createdAt: d.created_at,
  updatedAt: d.updated_at,
  versions: [],
});

const mapApiShare = (s: ApiShare): Share => ({
  id: s.id,
  tenantId: s.tenant_id,
  documentId: s.document_id ?? null,
  folderId: s.folder_id ?? null,
  createdBy: s.created_by || '',
  shareType: s.share_type,
  role: (s.role as UserRole) || 'VIEWER',
  token: s.token ?? null,
  publicUrl: s.public_url ?? null,
  hasPassword: s.has_password,
  documentName: s.target_name,
  maxDownloads: s.max_downloads ?? null,
  downloadCount: s.download_count ?? 0,
  expiresAt: s.expires_at ?? null,
  recipientEmail: s.recipients?.[0]?.recipient_email,
  recipients: (s.recipients || []).map((r) => ({
    id: r.id,
    recipientEmail: r.recipient_email,
    recipientUserId: r.recipient_user_id ?? null,
    role: (r.role as UserRole) || 'VIEWER',
    createdAt: r.created_at,
  })),
  isActive: s.is_active,
  isExpired: s.is_expired,
  createdAt: s.created_at,
});

const mapApiNotification = (n: ApiNotification): NotificationItem => ({
  id: n.id,
  tenantId: n.tenant_id,
  userId: n.user_id,
  category: (n.category as NotificationCategory) || 'SECURITY',
  title: n.title,
  message: n.message,
  level: (n.level as NotificationLevel) || 'INFO',
  actionUrl: n.action_url ?? null,
  isRead: n.is_read,
  createdAt: n.created_at,
});

const mapApiInvoice = (inv: ApiInvoice): InvoiceItem => ({
  id: inv.id,
  createdAt: inv.created_at,
  eventType: inv.event_type,
  planId: inv.plan_id,
  planName: inv.plan_name,
  amountEur: inv.amount_eur,
  status: inv.status,
});

const buildStructuralFallbackPlan = (tenant: Tenant): Plan => ({
  id: tenant.planId,
  name: tenant.planId,
  maxStorageBytes: tenant.maxStorageBytes || 524288000,
  maxFileSizeBytes: 52428800,
  maxMembers: 1,
  maxVersionsPerFile: 3,
  priceMonthly: 0,
  features: [],
});

export default function App() {
  // --- Public Share Route State (/s/:token) ---
  const [publicShareToken, setPublicShareToken] = useState<string | null>(() =>
    typeof window !== 'undefined' ? extractPublicShareToken(window.location.pathname) : null
  );

  // --- Authenticated Global State (Unauthenticated-First) ---
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [shares, setShares] = useState<Share[]>([]);
  const [receivedShares, setReceivedShares] = useState<Share[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [searchResultsDocs, setSearchResultsDocs] = useState<DocumentItem[] | null>(null);

  const [isBootstrapping, setIsBootstrapping] = useState<boolean>(true);
  const [isWorkspaceLoading, setIsWorkspaceLoading] = useState<boolean>(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isAuthSubmitting, setIsAuthSubmitting] = useState<boolean>(false);

  // Navigation & View state
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modals state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<DocumentItem | null>(null);
  const [shareDoc, setShareDoc] = useState<DocumentItem | null>(null);
  const [versionsDoc, setVersionsDoc] = useState<DocumentItem | null>(null);
  const [folderModal, setFolderModal] = useState<{
    isOpen: boolean;
    folderToEdit: Folder | null;
    parentFolder: Folder | null;
  }>({ isOpen: false, folderToEdit: null, parentFolder: null });
  const [isArchitectureOpen, setIsArchitectureOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMembersOpen, setIsMembersOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [moveModal, setMoveModal] = useState<{
    isOpen: boolean;
    itemToMove: { type: 'document' | 'folder' | 'bulk'; item: DocumentItem | Folder | null; bulkIds?: string[] };
  }>({ isOpen: false, itemToMove: { type: 'document', item: null } });
  const [billingModal, setBillingModal] = useState<{
    isOpen: boolean;
    targetPlan: Plan | null;
  }>({ isOpen: false, targetPlan: null });
  const [feedbackBanner, setFeedbackBanner] = useState<{
    type: 'success' | 'error' | 'warning' | 'info';
    text: string;
  } | null>(null);
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    confirmLabel: string;
    variant: 'danger' | 'warning';
    onConfirm: () => void | Promise<void>;
  } | null>(null);
  const [renameTarget, setRenameTarget] = useState<DocumentItem | null>(null);

  const syncSeqRef = useRef(0);

  const showFeedback = useCallback(
    (type: 'success' | 'error' | 'warning' | 'info', text: string) => {
      setFeedbackBanner({ type, text });
    },
    []
  );

  const clearWorkspaceState = useCallback(() => {
    setFolders([]);
    setDocuments([]);
    setShares([]);
    setReceivedShares([]);
    setNotifications([]);
    setInvoices([]);
    setSearchResultsDocs(null);
    setCurrentFolderId(null);
    setSearchQuery('');
  }, []);

  const resetSessionState = useCallback(() => {
    syncSeqRef.current += 1;
    apiClient.setAccessToken(null);
    setCurrentUser(null);
    setTenants([]);
    setCurrentTenantId(null);
    clearWorkspaceState();
    setPreviewDoc(null);
    setShareDoc(null);
    setVersionsDoc(null);
    setIsUploadOpen(false);
    setIsSettingsOpen(false);
    setIsMembersOpen(false);
    setIsNotificationsOpen(false);
    setBillingModal({ isOpen: false, targetPlan: null });
    setCurrentTab('dashboard');
  }, [clearWorkspaceState]);

  const syncWorkspaceFromApi = useCallback(
    async (tenantId: string) => {
      const seq = ++syncSeqRef.current;
      setIsWorkspaceLoading(true);
      try {
        const [
          tenantRes,
          activeFoldersRes,
          trashedFoldersRes,
          activeDocsRes,
          trashedDocsRes,
          sharesRes,
          receivedRes,
          notifRes,
          invoicesRes,
        ] = await Promise.allSettled([
          apiClient.tenants.current(tenantId),
          apiClient.documents.listFolders(tenantId, { flat: true, trashed: false, limit: 200 }),
          apiClient.documents.listFolders(tenantId, { flat: true, trashed: true, limit: 200 }),
          apiClient.documents.list(tenantId, { trashed: false, limit: 200 }),
          apiClient.documents.list(tenantId, { trashed: true, limit: 200 }),
          apiClient.shares.list(tenantId),
          apiClient.shares.received(),
          apiClient.notifications.list(tenantId),
          apiClient.billing.invoices(tenantId),
        ]);

        if (seq !== syncSeqRef.current) return;

        if (tenantRes.status === 'fulfilled') {
          const updatedTenant = mapApiTenant(tenantRes.value);
          setTenants((prev) => {
            const exists = prev.some((t) => t.id === updatedTenant.id);
            return exists
              ? prev.map((t) => (t.id === updatedTenant.id ? updatedTenant : t))
              : [updatedTenant, ...prev];
          });
        }

        const mergedFolders: Folder[] = [
          ...(activeFoldersRes.status === 'fulfilled' ? activeFoldersRes.value : []),
          ...(trashedFoldersRes.status === 'fulfilled' ? trashedFoldersRes.value : []),
        ].map(mapApiFolder);
        if (activeFoldersRes.status === 'fulfilled' || trashedFoldersRes.status === 'fulfilled') {
          setFolders(mergedFolders);
        }

        const mergedDocs: DocumentItem[] = [
          ...(activeDocsRes.status === 'fulfilled' ? activeDocsRes.value : []),
          ...(trashedDocsRes.status === 'fulfilled' ? trashedDocsRes.value : []),
        ].map(mapApiDoc);
        if (activeDocsRes.status === 'fulfilled' || trashedDocsRes.status === 'fulfilled') {
          setDocuments(mergedDocs);
        }

        if (sharesRes.status === 'fulfilled') {
          setShares(sharesRes.value.map(mapApiShare));
        }

        if (receivedRes.status === 'fulfilled') {
          setReceivedShares(receivedRes.value.map(mapApiShare));
        }

        if (notifRes.status === 'fulfilled') {
          setNotifications(notifRes.value.items.map(mapApiNotification));
        }

        if (invoicesRes.status === 'fulfilled') {
          setInvoices(invoicesRes.value.map(mapApiInvoice));
        }
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status !== 401) {
          showFeedback('error', err.detail);
        }
      } finally {
        if (seq === syncSeqRef.current) {
          setIsWorkspaceLoading(false);
        }
      }
    },
    [showFeedback]
  );

  // Sync browser back/forward navigation for /s/:token
  useEffect(() => {
    const handlePopState = () => {
      setPublicShareToken(extractPublicShareToken(window.location.pathname));
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Register global 401 handler
  useEffect(() => {
    apiClient.setUnauthorizedHandler(() => {
      resetSessionState();
      setAuthError('Votre session a expiré. Veuillez vous reconnecter.');
      showFeedback('warning', 'Session expirée : veuillez vous reconnecter pour continuer.');
    });
    return () => {
      apiClient.setUnauthorizedHandler(null);
    };
  }, [resetSessionState, showFeedback]);

  // Bootstrap real session & catalog on startup (no mock fallback)
  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      setIsBootstrapping(true);
      try {
        const plansPromise = apiClient.billing.plans().catch(() => []);
        const mePromise = apiClient.auth.me({ skipAuthCallback: true }).catch(() => null);

        const [apiPlans, me] = await Promise.all([plansPromise, mePromise]);
        if (cancelled) return;

        if (apiPlans.length > 0) {
          setPlans(apiPlans.map(mapApiPlan));
        }

        if (!me) {
          resetSessionState();
          return;
        }

        const apiTenants = await apiClient.tenants.list();
        if (cancelled) return;

        const mappedUser = mapApiUser(me);
        const mappedTenants = apiTenants.map(mapApiTenant);

        setCurrentUser(mappedUser);
        setTenants(mappedTenants);

        if (mappedTenants.length > 0) {
          const initialTenantId = mappedTenants[0].id;
          setCurrentTenantId(initialTenantId);
          await syncWorkspaceFromApi(initialTenantId);
        }
      } catch {
        if (!cancelled) {
          resetSessionState();
        }
      } finally {
        if (!cancelled) {
          setIsBootstrapping(false);
        }
      }
    };

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [resetSessionState, syncWorkspaceFromApi]);

  // Resolved active tenant & plan
  const currentTenant = useMemo(() => {
    if (tenants.length === 0) return null;
    return tenants.find((t) => t.id === currentTenantId) || tenants[0];
  }, [tenants, currentTenantId]);

  const currentPlan = useMemo(() => {
    if (!currentTenant) return null;
    return (
      plans.find((p) => p.id === currentTenant.planId) ||
      buildStructuralFallbackPlan(currentTenant)
    );
  }, [plans, currentTenant]);

  // Server-backed search query effect
  useEffect(() => {
    if (!currentTenant || !searchQuery.trim()) {
      setSearchResultsDocs(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      apiClient.documents
        .search(currentTenant.id, searchQuery.trim())
        .then((res) => {
          if (!cancelled) {
            setSearchResultsDocs(res.map(mapApiDoc));
          }
        })
        .catch(() => {
          if (!cancelled) {
            setSearchResultsDocs(null);
          }
        });
    }, 180);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [currentTenant, searchQuery]);

  // Active folder & breadcrumbs
  const currentFolder = useMemo(() => {
    if (!currentFolderId) return null;
    return folders.find((f) => f.id === currentFolderId) || null;
  }, [folders, currentFolderId]);

  const breadcrumbs = useMemo(() => {
    const crumbs: Folder[] = [];
    let cur = currentFolder;
    while (cur) {
      crumbs.unshift(cur);
      cur = cur.parentId ? folders.find((f) => f.id === cur?.parentId) || null : null;
    }
    return crumbs;
  }, [currentFolder, folders]);

  const tenantDocs = useMemo(() => {
    if (!currentTenant) return [];
    return documents.filter((d) => d.tenantId === currentTenant.id);
  }, [documents, currentTenant]);

  const tenantFolders = useMemo(() => {
    if (!currentTenant) return [];
    return folders.filter((f) => f.tenantId === currentTenant.id);
  }, [folders, currentTenant]);

  const trashedCount = useMemo(() => {
    return (
      tenantDocs.filter((d) => d.isTrashed).length +
      tenantFolders.filter((f) => f.isTrashed).length
    );
  }, [tenantDocs, tenantFolders]);

  const clamAvSummary = useMemo(() => {
    const active = tenantDocs.filter((d) => !d.isTrashed);
    const infectedCount = active.filter((d) => d.antivirusStatus === 'INFECTED').length;
    const errorCount = active.filter((d) => d.antivirusStatus === 'SCAN_ERROR').length;
    const pendingCount = active.filter((d) => d.antivirusStatus === 'PENDING').length;

    if (infectedCount > 0) {
      return {
        label: `${infectedCount} Quarantaine`,
        sublabel: 'Menace détectée par ClamAV',
        tone: 'danger' as const,
      };
    }
    if (errorCount > 0) {
      return {
        label: `${errorCount} Erreur Scan`,
        sublabel: 'Contrôle antivirus requis',
        tone: 'warning' as const,
      };
    }
    if (pendingCount > 0) {
      return {
        label: `${pendingCount} En attente`,
        sublabel: 'Scan ClamAV en cours',
        tone: 'warning' as const,
      };
    }
    if (active.length === 0) {
      return {
        label: 'Aucun fichier',
        sublabel: 'Analyse ClamAV prête',
        tone: 'clean' as const,
      };
    }
    return {
      label: '100% Sain',
      sublabel: `${active.length} fichier(s) vérifié(s)`,
      tone: 'clean' as const,
    };
  }, [tenantDocs]);

  // Filter items based on active tab & search
  const displayedItems = useMemo(() => {
    let docs = tenantDocs;
    let flds = tenantFolders;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      docs =
        searchResultsDocs !== null
          ? searchResultsDocs
          : docs.filter(
              (d) =>
                !d.isTrashed &&
                (d.originalName.toLowerCase().includes(q) ||
                  d.extension.toLowerCase().includes(q) ||
                  d.sha256Hash.toLowerCase().includes(q) ||
                  d.mimeType.toLowerCase().includes(q))
            );
      flds = flds.filter((f) => !f.isTrashed && f.name.toLowerCase().includes(q));
      return { docs, flds };
    }

    switch (currentTab) {
      case 'dashboard':
        docs = docs.filter((d) => !d.isTrashed).slice(0, 8);
        flds = flds.filter((f) => !f.isTrashed && f.parentId === null);
        break;

      case 'documents':
      case 'folders':
        docs = docs.filter((d) => !d.isTrashed && d.folderId === currentFolderId);
        flds = flds.filter((f) => !f.isTrashed && f.parentId === currentFolderId);
        break;

      case 'favorites':
        docs = docs.filter((d) => !d.isTrashed && d.isFavorite);
        flds = flds.filter((f) => !f.isTrashed && f.isFavorite);
        break;

      case 'recents':
        docs = [...docs.filter((d) => !d.isTrashed)].sort(
          (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
        flds = [];
        break;

      case 'trash':
        docs = docs.filter((d) => d.isTrashed);
        flds = flds.filter((f) => f.isTrashed);
        break;

      case 'shared-by-me': {
        const sharedDocIds = new Set(
          shares
            .filter((s) => currentTenant && s.tenantId === currentTenant.id && s.isActive && s.documentId)
            .map((s) => s.documentId!)
        );
        docs = docs.filter((d) => !d.isTrashed && sharedDocIds.has(d.id));
        flds = [];
        break;
      }

      default:
        docs = docs.filter((d) => !d.isTrashed && d.folderId === currentFolderId);
        flds = flds.filter((f) => !f.isTrashed && f.parentId === currentFolderId);
        break;
    }

    return { docs, flds };
  }, [tenantDocs, tenantFolders, currentTab, currentFolderId, searchQuery, searchResultsDocs, shares, currentTenant]);

  // --- Auth Handlers ---
  const handleLogin = async (email: string, password: string) => {
    setAuthError(null);
    setIsAuthSubmitting(true);
    try {
      const tokenRes = await apiClient.auth.login(email, password);
      const [me, apiTenants, apiPlans] = await Promise.all([
        apiClient.auth.me(),
        apiClient.tenants.list(),
        apiClient.billing.plans().catch(() => []),
      ]);

      const mappedUser = mapApiUser(me);
      const mappedTenants = apiTenants.map(mapApiTenant);
      if (apiPlans.length > 0) {
        setPlans(apiPlans.map(mapApiPlan));
      }

      clearWorkspaceState();
      setCurrentUser(mappedUser);
      setTenants(mappedTenants);

      const targetTenantId = tokenRes.tenant_id || mappedTenants[0]?.id || null;
      setCurrentTenantId(targetTenantId);

      if (targetTenantId) {
        await syncWorkspaceFromApi(targetTenantId);
      }

      showFeedback('success', `Connexion réussie en tant que ${mappedUser.fullName}.`);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setAuthError(err.detail);
      } else {
        setAuthError('Impossible de joindre le serveur d’authentification.');
      }
    } finally {
      setIsAuthSubmitting(false);
    }
  };

  const handleRegister = async (fullName: string, email: string, password: string) => {
    setAuthError(null);
    setIsAuthSubmitting(true);
    try {
      await apiClient.auth.register(fullName, email, password);
      const tokenRes = await apiClient.auth.login(email, password);
      const [me, apiTenants, apiPlans] = await Promise.all([
        apiClient.auth.me(),
        apiClient.tenants.list(),
        apiClient.billing.plans().catch(() => []),
      ]);

      const mappedUser = mapApiUser(me);
      const mappedTenants = apiTenants.map(mapApiTenant);
      if (apiPlans.length > 0) {
        setPlans(apiPlans.map(mapApiPlan));
      }

      clearWorkspaceState();
      setCurrentUser(mappedUser);
      setTenants(mappedTenants);

      const targetTenantId = tokenRes.tenant_id || mappedTenants[0]?.id || null;
      setCurrentTenantId(targetTenantId);

      if (targetTenantId) {
        await syncWorkspaceFromApi(targetTenantId);
      }

      showFeedback('success', `Compte et espace personnel créés pour ${mappedUser.fullName}.`);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setAuthError(err.detail);
      } else {
        setAuthError('Impossible de créer le compte sur le serveur.');
      }
    } finally {
      setIsAuthSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiClient.auth.logout();
    } catch {
      // Clear local session state even if server logout call failed
    } finally {
      resetSessionState();
      setAuthError(null);
    }
  };

  // --- Tenant Switching ---
  const handleSelectTenant = async (tenantId: string) => {
    if (tenantId === currentTenantId) return;
    setCurrentTenantId(tenantId);
    clearWorkspaceState();
    await syncWorkspaceFromApi(tenantId);
  };

  // --- Document & Folder Handlers (100% Backend Persisted) ---
  const denyReadOnlyAction = () => {
    showFeedback(
      'warning',
      'Action refusée : votre rôle est en lecture seule dans cet espace documentaire (politique RBAC appliquée).'
    );
  };

  const handleUploadSuccess = async (newDoc: DocumentItem) => {
    if (!currentTenant) return;
    showFeedback('success', `Fichier "${newDoc.originalName}" analysé et enregistré.`);
    await syncWorkspaceFromApi(currentTenant.id);
  };

  const handleSaveFolder = async (name: string, color: string) => {
    if (!currentTenant) return;
    try {
      if (folderModal.folderToEdit) {
        await apiClient.documents.updateFolder(currentTenant.id, folderModal.folderToEdit.id, {
          name,
          color,
        });
        showFeedback('success', `Dossier renommé en "${name}".`);
      } else {
        await apiClient.documents.createFolder(currentTenant.id, name, currentFolderId, color);
        showFeedback('success', `Dossier "${name}" créé.`);
      }
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la sauvegarde du dossier.'
      );
    }
  };

  const handleToggleFavoriteDoc = async (docId: string) => {
    if (!currentTenant) return;
    const target = documents.find((d) => d.id === docId);
    if (!target) return;
    try {
      await apiClient.documents.toggleFavorite(currentTenant.id, docId, !target.isFavorite);
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la mise à jour du favori.'
      );
    }
  };

  const handleTrashDoc = async (docId: string) => {
    if (!currentTenant) return;
    try {
      await apiClient.documents.trash(currentTenant.id, docId);
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la mise en corbeille.'
      );
    }
  };

  const handleRestoreDoc = async (docId: string) => {
    if (!currentTenant) return;
    try {
      await apiClient.documents.restore(currentTenant.id, docId);
      await syncWorkspaceFromApi(currentTenant.id);
      showFeedback('success', 'Document restauré.');
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la restauration.'
      );
    }
  };

  const handlePurgeDoc = (docId: string) => {
    if (!currentTenant) return;
    const docToDelete = documents.find((d) => d.id === docId);
    if (!docToDelete) return;
    setConfirmModal({
      isOpen: true,
      title: 'Suppression définitive du document',
      description: `Voulez-vous supprimer définitivement "${docToDelete.originalName}" ? L'objet sera effacé de MinIO S3 et cette action est irréversible.`,
      confirmLabel: 'Supprimer définitivement',
      variant: 'danger',
      onConfirm: async () => {
        try {
          await apiClient.documents.purge(currentTenant.id, docId);
          setConfirmModal(null);
          showFeedback('success', `"${docToDelete.originalName}" a été définitivement supprimé.`);
          await syncWorkspaceFromApi(currentTenant.id);
        } catch (err: unknown) {
          setConfirmModal(null);
          showFeedback(
            'error',
            err instanceof ApiError ? err.detail : 'Erreur lors de la suppression définitive.'
          );
        }
      },
    });
  };

  const handleConfirmRename = async (newName: string) => {
    if (!renameTarget || !currentTenant) return;
    const docId = renameTarget.id;
    try {
      await apiClient.documents.rename(currentTenant.id, docId, newName);
      setRenameTarget(null);
      showFeedback('success', `Document renommé en "${newName}".`);
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors du renommage.'
      );
    }
  };

  const handleCopyDocument = async (doc: DocumentItem) => {
    if (!currentTenant) return;
    try {
      await apiClient.documents.copy(currentTenant.id, doc.id, doc.folderId);
      showFeedback('success', `Copie de "${doc.originalName}" créée.`);
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la duplication du document.'
      );
    }
  };

  const handleCopyFolder = async (folder: Folder) => {
    if (!currentTenant) return;
    try {
      await apiClient.documents.copyFolder(currentTenant.id, folder.id, folder.parentId);
      showFeedback('success', `Dossier "${folder.name}" dupliqué.`);
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la duplication du dossier.'
      );
    }
  };

  const handleTrashFolder = async (folderId: string) => {
    if (!currentTenant) return;
    try {
      await apiClient.documents.deleteFolder(currentTenant.id, folderId);
      if (currentFolderId === folderId) {
        setCurrentFolderId(null);
      }
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la suppression du dossier.'
      );
    }
  };

  const handleConfirmMove = async (targetFolderId: string | null) => {
    if (!currentTenant) return;
    const { type, item, bulkIds } = moveModal.itemToMove;
    try {
      if (type === 'document' && item) {
        await apiClient.documents.move(currentTenant.id, (item as DocumentItem).id, targetFolderId);
        showFeedback('success', 'Document déplacé.');
      } else if (type === 'folder' && item) {
        await apiClient.documents.moveFolder(currentTenant.id, (item as Folder).id, targetFolderId);
        showFeedback('success', 'Dossier déplacé.');
      } else if (type === 'bulk' && bulkIds && bulkIds.length > 0) {
        await apiClient.documents.bulkMove(currentTenant.id, bulkIds, targetFolderId);
        showFeedback('success', `${bulkIds.length} document(s) déplacé(s).`);
      }
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors du déplacement.'
      );
    }
  };

  const handleBulkTrash = async (docIds: string[]) => {
    if (!currentTenant || docIds.length === 0) return;
    try {
      await apiClient.documents.bulkTrash(currentTenant.id, docIds);
      showFeedback('info', `${docIds.length} document(s) déplacé(s) vers la corbeille.`);
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la mise en corbeille groupée.'
      );
    }
  };

  const handleBulkRestore = async (docIds: string[]) => {
    if (!currentTenant || docIds.length === 0) return;
    try {
      await apiClient.documents.bulkRestore(currentTenant.id, docIds);
      showFeedback('success', `${docIds.length} document(s) restauré(s).`);
      await syncWorkspaceFromApi(currentTenant.id);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la restauration groupée.'
      );
    }
  };

  const handleBulkPurge = (docIds: string[]) => {
    if (!currentTenant || docIds.length === 0) return;
    setConfirmModal({
      isOpen: true,
      title: 'Purge définitive groupée',
      description: `Vous allez supprimer définitivement ${docIds.length} fichier(s) du stockage MinIO S3. Cette opération est irréversible.`,
      confirmLabel: 'Purger la sélection',
      variant: 'danger',
      onConfirm: async () => {
        try {
          const res = await apiClient.documents.bulkPurge(currentTenant.id, docIds);
          setConfirmModal(null);
          showFeedback('success', res.message || `${res.success_count} fichier(s) purgé(s).`);
          await syncWorkspaceFromApi(currentTenant.id);
        } catch (err: unknown) {
          setConfirmModal(null);
          showFeedback(
            'error',
            err instanceof ApiError ? err.detail : 'Erreur lors de la purge groupée.'
          );
        }
      },
    });
  };

  const handleBulkDownload = async (docIds: string[]) => {
    if (!currentTenant || docIds.length === 0) return;
    let launched = 0;
    for (const id of docIds) {
      try {
        const res = await apiClient.storage.getDownloadUrl(currentTenant.id, id);
        const a = window.document.createElement('a');
        a.href = res.download_url;
        a.download = res.filename;
        a.rel = 'noopener noreferrer';
        a.click();
        launched += 1;
      } catch (err: unknown) {
        showFeedback(
          'error',
          err instanceof ApiError ? err.detail : 'Un ou plusieurs téléchargements ont été refusés.'
        );
      }
    }
    if (launched > 0) {
      showFeedback('success', `${launched} téléchargement(s) sécurisé(s) lancé(s).`);
    }
  };

  const handleEmptyTrash = () => {
    if (!currentTenant) return;
    const trashedDocs = tenantDocs.filter((d) => d.isTrashed);
    const trashedFlds = tenantFolders.filter((f) => f.isTrashed);
    if (trashedDocs.length === 0 && trashedFlds.length === 0) return;

    setConfirmModal({
      isOpen: true,
      title: 'Vider définitivement la corbeille',
      description: `${trashedDocs.length} fichier(s) et ${trashedFlds.length} dossier(s) seront définitivement purgés de la base PostgreSQL et du stockage MinIO S3.`,
      confirmLabel: 'Vider la corbeille',
      variant: 'danger',
      onConfirm: async () => {
        try {
          const res = await apiClient.documents.emptyTrash(currentTenant.id);
          setConfirmModal(null);
          showFeedback(
            'success',
            res.message || `Corbeille vidée (${formatBytes(res.freed_bytes)} libérés).`
          );
          await syncWorkspaceFromApi(currentTenant.id);
        } catch (err: unknown) {
          setConfirmModal(null);
          showFeedback(
            'error',
            err instanceof ApiError ? err.detail : 'Erreur lors du vidage de la corbeille.'
          );
        }
      },
    });
  };

  // --- Share Handlers ---
  const handleCreateSecureLink = async (payload: {
    documentId: string;
    password?: string;
    expiresInHours?: number;
    maxDownloads?: number;
  }): Promise<Share | null> => {
    if (!currentTenant) return null;
    const created = await apiClient.shares.createLink(currentTenant.id, {
      document_id: payload.documentId,
      password: payload.password,
      expires_in_hours: payload.expiresInHours,
      max_downloads: payload.maxDownloads,
    });
    const mapped = mapApiShare(created);
    setShares((prev) => [mapped, ...prev]);
    return mapped;
  };

  const handleCreateInternalShare = async (payload: {
    documentId: string;
    recipientEmail: string;
    role: UserRole;
  }): Promise<Share | null> => {
    if (!currentTenant) return null;
    const created = await apiClient.shares.createInternal(currentTenant.id, {
      document_id: payload.documentId,
      recipient_email: payload.recipientEmail,
      role: payload.role,
    });
    const mapped = mapApiShare(created);
    setShares((prev) => [mapped, ...prev]);
    return mapped;
  };

  const handleToggleShare = async (shareId: string, nextActive: boolean) => {
    if (!currentTenant) return;
    const updated = await apiClient.shares.update(currentTenant.id, shareId, {
      is_active: nextActive,
    });
    const mapped = mapApiShare(updated);
    setShares((prev) => prev.map((s) => (s.id === shareId ? mapped : s)));
  };

  const handleRevokeShare = async (shareId: string) => {
    if (!currentTenant) return;
    await apiClient.shares.revoke(currentTenant.id, shareId);
    setShares((prev) => prev.filter((s) => s.id !== shareId));
  };

  const handleDownloadReceivedShare = async (share: Share) => {
    try {
      const res = await apiClient.shares.downloadReceived(share.id);
      const a = window.document.createElement('a');
      a.href = res.download_url;
      a.download = res.filename;
      a.rel = 'noopener noreferrer';
      a.click();
      showFeedback('success', `Téléchargement lancé pour "${res.filename}".`);
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Impossible de télécharger ce partage reçu.'
      );
    }
  };

  // --- Notification Handlers ---
  const handleMarkNotificationAsRead = async (id: string) => {
    if (!currentTenant) return;
    try {
      await apiClient.notifications.markRead(currentTenant.id, id);
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, isRead: true } : n)));
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la mise à jour de la notification.'
      );
    }
  };

  const handleMarkAllNotificationsAsRead = async () => {
    if (!currentTenant) return;
    try {
      await apiClient.notifications.markAllRead(currentTenant.id);
      setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors du marquage des notifications.'
      );
    }
  };

  const handleDeleteNotification = async (id: string) => {
    if (!currentTenant) return;
    try {
      await apiClient.notifications.delete(currentTenant.id, id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    } catch (err: unknown) {
      showFeedback(
        'error',
        err instanceof ApiError ? err.detail : 'Erreur lors de la suppression de la notification.'
      );
    }
  };

  // --- GDPR Account Deletion ---
  const handleDeleteAccount = async () => {
    if (!currentUser) return;
    const email = currentUser.email;
    await apiClient.gdpr.deleteAccount('SUPPRIMER');
    resetSessionState();
    setAuthError(null);
    showFeedback(
      'success',
      `Le compte (${email}) et toutes ses données ont été définitivement purgés conformément au RGPD.`
    );
  };

  // --- Render 1: Public Share Page (/s/:token) ---
  if (publicShareToken) {
    return (
      <PublicShareView
        token={publicShareToken}
        onExitPublicView={() => {
          window.history.pushState({}, '', '/');
          setPublicShareToken(null);
        }}
      />
    );
  }

  // --- Render 2: Bootstrapping Session Check ---
  if (isBootstrapping) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6">
        <div className="text-center space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500 mx-auto" />
          <h1 className="text-base font-bold text-white">DocuSpace</h1>
          <p className="text-xs text-slate-400">Vérification de la session sécurisée...</p>
        </div>
      </div>
    );
  }

  // --- Render 3: Unauthenticated Gate (No fallback user/workspace ever rendered) ---
  if (!currentUser || !currentTenant || !currentPlan) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        {feedbackBanner && (
          <div
            role={feedbackBanner.type === 'error' || feedbackBanner.type === 'warning' ? 'alert' : 'status'}
            className="fixed top-4 left-1/2 -translate-x-1/2 z-[60] max-w-lg w-full mx-4 px-4 py-2.5 rounded-xl border bg-slate-900/95 border-slate-700 text-xs flex items-center justify-between gap-3 shadow-xl"
          >
            <span>{feedbackBanner.text}</span>
            <button
              type="button"
              onClick={() => setFeedbackBanner(null)}
              aria-label="Fermer la notification"
              className="p-1 rounded-lg hover:bg-slate-800 text-slate-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
        <AuthModal
          isOpen={true}
          canDismiss={false}
          onLogin={handleLogin}
          onRegister={handleRegister}
          errorMessage={authError}
          isSubmitting={isAuthSubmitting}
        />
      </div>
    );
  }

  const maxBytes = currentTenant.maxStorageBytes || currentPlan.maxStorageBytes || 1;
  const activeDocsCount = tenantDocs.filter((d) => !d.isTrashed).length;
  const activeFoldersCount = tenantFolders.filter((f) => !f.isTrashed).length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none antialiased">
      {/* Top Header */}
      <Header
        currentUser={currentUser}
        currentTenant={currentTenant}
        userTenants={tenants}
        currentPlan={currentPlan}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSelectTenant={(id) => void handleSelectTenant(id)}
        onOpenArchitecture={() => setIsArchitectureOpen(true)}
        onOpenUpload={() => {
          if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
            denyReadOnlyAction();
            return;
          }
          setIsUploadOpen(true);
        }}
        onOpenMembers={() => setIsMembersOpen(true)}
        onOpenNotifications={() => setIsNotificationsOpen(true)}
        unreadNotificationsCount={notifications.filter((n) => !n.isRead).length}
        onLogout={() => void handleLogout()}
      />

      {/* Accessible Global Feedback Banner */}
      {feedbackBanner && (
        <div
          role={feedbackBanner.type === 'error' || feedbackBanner.type === 'warning' ? 'alert' : 'status'}
          className={`mx-6 mt-3 px-4 py-2.5 rounded-xl border text-xs flex items-center justify-between gap-3 ${
            feedbackBanner.type === 'error'
              ? 'bg-rose-500/10 border-rose-500/30 text-rose-200'
              : feedbackBanner.type === 'warning'
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
                : feedbackBanner.type === 'success'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                  : 'bg-blue-500/10 border-blue-500/30 text-blue-200'
          }`}
        >
          <div className="flex items-center space-x-2">
            {feedbackBanner.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-4 h-4 shrink-0" />
            )}
            <span>{feedbackBanner.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedbackBanner(null)}
            aria-label="Fermer la notification"
            className="p-1 rounded-lg hover:bg-slate-800/70 text-current"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          currentTab={currentTab}
          onTabChange={(tab) => {
            setCurrentTab(tab);
            if (tab === 'settings') setIsSettingsOpen(true);
            if (tab !== 'documents' && tab !== 'folders') setCurrentFolderId(null);
          }}
          currentUser={currentUser}
          currentTenant={currentTenant}
          currentPlan={currentPlan}
          onOpenUpload={() => {
            if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
              denyReadOnlyAction();
              return;
            }
            setIsUploadOpen(true);
          }}
          onOpenNewFolder={() => {
            if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
              denyReadOnlyAction();
              return;
            }
            setFolderModal({ isOpen: true, folderToEdit: null, parentFolder: currentFolder });
          }}
          trashedCount={trashedCount}
        />

        {/* Dynamic Center Stage */}
        <main className="flex-1 flex flex-col overflow-hidden bg-slate-950/60">
          {currentTab === 'dashboard' && !searchQuery && (
            <div className="p-6 pb-2 border-b border-slate-800/80 bg-slate-900/40">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center space-x-3.5">
                  <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-white">{activeDocsCount}</div>
                    <div className="text-[11px] text-slate-400">Documents actifs</div>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center space-x-3.5">
                  <div className="p-3 rounded-xl bg-purple-500/10 text-purple-400">
                    <FolderIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-white">{activeFoldersCount}</div>
                    <div className="text-[11px] text-slate-400">Dossiers organisés</div>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center space-x-3.5">
                  <div
                    className={`p-3 rounded-xl ${
                      clamAvSummary.tone === 'clean'
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : clamAvSummary.tone === 'warning'
                          ? 'bg-amber-500/10 text-amber-400'
                          : 'bg-rose-500/10 text-rose-400'
                    }`}
                  >
                    {clamAvSummary.tone === 'clean' ? (
                      <ShieldCheck className="w-5 h-5" />
                    ) : clamAvSummary.tone === 'warning' ? (
                      <Clock className="w-5 h-5" />
                    ) : (
                      <ShieldAlert className="w-5 h-5" />
                    )}
                  </div>
                  <div>
                    <div
                      className={`text-xl font-bold ${
                        clamAvSummary.tone === 'clean'
                          ? 'text-emerald-400'
                          : clamAvSummary.tone === 'warning'
                            ? 'text-amber-400'
                            : 'text-rose-400'
                      }`}
                    >
                      {clamAvSummary.label}
                    </div>
                    <div className="text-[11px] text-slate-400">{clamAvSummary.sublabel}</div>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center space-x-3.5">
                  <div className="p-3 rounded-xl bg-sky-500/10 text-sky-400">
                    <HardDrive className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-white font-mono">
                      {formatBytes(currentTenant.usedBytes || 0)}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      sur {formatBytes(maxBytes)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {isWorkspaceLoading && documents.length === 0 && folders.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-xs text-slate-400 space-x-2">
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              <span>Synchronisation avec PostgreSQL & MinIO...</span>
            </div>
          ) : currentTab === 'storage' || currentTab === 'billing' ? (
            <StorageGauge
              currentTenant={currentTenant}
              currentPlan={currentPlan}
              plans={plans}
              documents={tenantDocs}
              onUpgradePlan={(planId) => {
                const target =
                  plans.find((p) => p.id === planId) || buildStructuralFallbackPlan(currentTenant);
                setBillingModal({ isOpen: true, targetPlan: target });
              }}
            />
          ) : currentTab === 'admin' && currentUser.isSuperuser ? (
            <AdminConsole
              onWorkspaceRefresh={() => syncWorkspaceFromApi(currentTenant.id)}
            />
          ) : currentTab === 'shared-with-me' && !searchQuery ? (
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center space-x-2">
                    <Users className="w-4 h-4 text-blue-400" />
                    <span>Documents partagés avec moi ({receivedShares.length})</span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Partages internes directs persistés dans PostgreSQL pour {currentUser.email}.
                  </p>
                </div>
              </div>

              {receivedShares.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {receivedShares.map((s) => (
                    <div
                      key={s.id}
                      className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col justify-between space-y-3"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-white truncate">
                            {s.documentName || 'Document partagé'}
                          </span>
                          <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 text-[10px] font-mono">
                            {s.role}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400">
                          Partagé le {new Date(s.createdAt).toLocaleDateString('fr-FR')}
                        </p>
                      </div>

                      {s.documentId && (
                        <button
                          type="button"
                          onClick={() => void handleDownloadReceivedShare(s)}
                          className="w-full py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center justify-center space-x-1.5 transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Télécharger</span>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-16 text-center border-2 border-dashed border-slate-800 rounded-2xl p-8 space-y-2">
                  <Users className="w-8 h-8 text-slate-600 mx-auto" />
                  <h3 className="text-sm font-semibold text-slate-300">
                    Aucun document partagé avec vous pour le moment
                  </h3>
                  <p className="text-xs text-slate-500">
                    Lorsqu’un autre utilisateur vous partagera un document via son e-mail, il apparaîtra ici.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <FileExplorer
              currentFolder={currentFolder}
              breadcrumbs={breadcrumbs}
              folders={displayedItems.flds}
              documents={displayedItems.docs}
              allFolders={tenantFolders}
              viewMode={viewMode}
              onToggleViewMode={() => setViewMode((prev) => (prev === 'grid' ? 'list' : 'grid'))}
              onNavigateFolder={(fId) => setCurrentFolderId(fId)}
              onPreviewDocument={(doc) => setPreviewDoc(doc)}
              onShareDocument={(doc) => setShareDoc(doc)}
              onViewVersions={(doc) => setVersionsDoc(doc)}
              onToggleFavoriteDoc={(docId) => void handleToggleFavoriteDoc(docId)}
              onTrashDoc={(docId) => void handleTrashDoc(docId)}
              onRestoreDoc={(docId) => void handleRestoreDoc(docId)}
              onPurgeDoc={handlePurgeDoc}
              onRenameDoc={(doc) => setRenameTarget(doc)}
              onMoveDocument={(doc) =>
                setMoveModal({
                  isOpen: true,
                  itemToMove: { type: 'document', item: doc },
                })
              }
              onCopyDocument={(doc) => void handleCopyDocument(doc)}
              onOpenUpload={() => {
                if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
                  denyReadOnlyAction();
                  return;
                }
                setIsUploadOpen(true);
              }}
              onOpenNewFolder={() => {
                if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
                  denyReadOnlyAction();
                  return;
                }
                setFolderModal({ isOpen: true, folderToEdit: null, parentFolder: currentFolder });
              }}
              onRenameFolder={(f) =>
                setFolderModal({ isOpen: true, folderToEdit: f, parentFolder: currentFolder })
              }
              onMoveFolder={(folder) =>
                setMoveModal({
                  isOpen: true,
                  itemToMove: { type: 'folder', item: folder },
                })
              }
              onCopyFolder={(folder) => void handleCopyFolder(folder)}
              onTrashFolder={(folderId) => void handleTrashFolder(folderId)}
              onBulkMove={(docIds) =>
                setMoveModal({
                  isOpen: true,
                  itemToMove: { type: 'bulk', item: null, bulkIds: docIds },
                })
              }
              onBulkTrash={(docIds) => void handleBulkTrash(docIds)}
              onBulkRestore={(docIds) => void handleBulkRestore(docIds)}
              onBulkPurge={handleBulkPurge}
              onBulkDownload={(docIds) => void handleBulkDownload(docIds)}
              onEmptyTrash={handleEmptyTrash}
              isTrashView={currentTab === 'trash'}
              userRole={currentTenant.role}
            />
          )}
        </main>
      </div>

      {/* --- Modals & Overlays --- */}
      <FileUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        currentTenant={currentTenant}
        currentPlan={currentPlan}
        currentFolder={currentFolder}
        onUploadSuccess={(doc) => void handleUploadSuccess(doc)}
        onUploadToApi={async (file, folderId, onProgress) => {
          const uploaded = await apiClient.storage.uploadWithProgress(
            currentTenant.id,
            file,
            folderId,
            onProgress
          );
          return mapApiDoc(uploaded);
        }}
      />

      <FilePreviewModal
        document={previewDoc}
        onClose={() => setPreviewDoc(null)}
        onShare={(doc) => {
          setPreviewDoc(null);
          setShareDoc(doc);
        }}
        onRequestDownload={async (doc) => {
          const res = await apiClient.storage.getDownloadUrl(currentTenant.id, doc.id);
          return res.download_url;
        }}
      />

      <ShareModal
        document={shareDoc}
        onClose={() => setShareDoc(null)}
        shares={shares}
        onCreateSecureLink={handleCreateSecureLink}
        onCreateInternalShare={handleCreateInternalShare}
        onToggleShare={handleToggleShare}
        onRevokeShare={handleRevokeShare}
      />

      <VersionsModal
        document={versionsDoc}
        tenantId={currentTenant.id}
        onClose={() => setVersionsDoc(null)}
        onVersionsUpdated={() => syncWorkspaceFromApi(currentTenant.id)}
      />

      <FolderModal
        isOpen={folderModal.isOpen}
        onClose={() => setFolderModal({ isOpen: false, folderToEdit: null, parentFolder: null })}
        folderToEdit={folderModal.folderToEdit}
        parentFolder={folderModal.parentFolder}
        onSave={(name, color) => void handleSaveFolder(name, color)}
      />

      <ArchitectureModal
        isOpen={isArchitectureOpen}
        onClose={() => setIsArchitectureOpen(false)}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        currentUser={currentUser}
        currentTenant={currentTenant}
        onDeleteAccount={handleDeleteAccount}
        onAllSessionsRevoked={() => {
          resetSessionState();
          showFeedback('info', 'Toutes vos sessions ont été révoquées. Veuillez vous reconnecter.');
        }}
      />

      <TenantMembersModal
        isOpen={isMembersOpen}
        onClose={() => setIsMembersOpen(false)}
        currentTenant={currentTenant}
        currentUser={currentUser}
      />

      <MoveModal
        isOpen={moveModal.isOpen}
        onClose={() =>
          setMoveModal({ isOpen: false, itemToMove: { type: 'document', item: null } })
        }
        itemToMove={moveModal.itemToMove}
        folders={tenantFolders}
        onConfirmMove={(targetFolderId) => void handleConfirmMove(targetFolderId)}
      />

      <NotificationsModal
        isOpen={isNotificationsOpen}
        onClose={() => setIsNotificationsOpen(false)}
        notifications={notifications}
        onMarkAsRead={(id) => void handleMarkNotificationAsRead(id)}
        onMarkAllAsRead={() => void handleMarkAllNotificationsAsRead()}
        onDeleteNotification={(id) => void handleDeleteNotification(id)}
        onNavigateAction={(url) => {
          if (url === '/storage' || url === '/billing') setCurrentTab('storage');
        }}
      />

      <BillingCheckoutModal
        isOpen={billingModal.isOpen}
        onClose={() => setBillingModal({ isOpen: false, targetPlan: null })}
        targetPlan={billingModal.targetPlan}
        plans={plans}
        currentTenant={currentTenant}
        invoices={invoices}
      />

      <ConfirmActionModal
        isOpen={Boolean(confirmModal?.isOpen)}
        title={confirmModal?.title || ''}
        description={confirmModal?.description || ''}
        confirmLabel={confirmModal?.confirmLabel}
        variant={confirmModal?.variant}
        onConfirm={() => void confirmModal?.onConfirm()}
        onCancel={() => setConfirmModal(null)}
      />

      <RenameModal
        isOpen={renameTarget !== null}
        currentName={renameTarget?.originalName || ''}
        onConfirm={(newName) => void handleConfirmRename(newName)}
        onCancel={() => setRenameTarget(null)}
      />
    </div>
  );
}
