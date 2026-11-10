import React, { useState, useMemo } from 'react';
import { 
  INITIAL_USERS, 
  INITIAL_TENANTS, 
  INITIAL_FOLDERS, 
  INITIAL_DOCUMENTS, 
  INITIAL_AUDIT_LOGS, 
  INITIAL_SHARES,
  PLANS 
} from './services/mockData';
import { 
  User, 
  Tenant, 
  Folder, 
  DocumentItem, 
  DocumentVersion, 
  PlanType, 
  AuditLogItem,
  Share
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
import { SecuritySimulatorModal } from './components/SecuritySimulatorModal';
import { TenantMembersModal } from './components/TenantMembersModal';
import { MoveModal } from './components/MoveModal';
import { PublicShareModal } from './components/PublicShareModal';
import { 
  FileText, 
  Folder as FolderIcon, 
  HardDrive, 
  ShieldCheck, 
  Clock, 
  Star, 
  UploadCloud, 
  Search,
  CheckCircle2
} from 'lucide-react';
import { formatBytes } from './services/crypto';

export default function App() {
  // --- Global Application State ---
  const [users, setUsers] = useState<User[]>(INITIAL_USERS);
  const [currentUser, setCurrentUser] = useState<User>(INITIAL_USERS[0]); // Alice Dupont
  const [tenants, setTenants] = useState<Tenant[]>(INITIAL_TENANTS);
  const [currentTenantId, setCurrentTenantId] = useState<string>('tnt-alice-main');
  const [folders, setFolders] = useState<Folder[]>(INITIAL_FOLDERS);
  const [documents, setDocuments] = useState<DocumentItem[]>(INITIAL_DOCUMENTS);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>(INITIAL_AUDIT_LOGS);

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
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isSecuritySimulatorOpen, setIsSecuritySimulatorOpen] = useState(false);
  const [isMembersOpen, setIsMembersOpen] = useState(false);
  const [moveModal, setMoveModal] = useState<{
    isOpen: boolean;
    itemToMove: { type: 'document' | 'folder' | 'bulk'; item: DocumentItem | Folder | null; bulkIds?: string[] };
  }>({ isOpen: false, itemToMove: { type: 'document', item: null } });
  const [shares, setShares] = useState<Share[]>(INITIAL_SHARES);
  const [publicShareSimulator, setPublicShareSimulator] = useState<Share | null>(null);

  // Resolved active tenant & plan
  const currentTenant = useMemo(() => {
    return tenants.find(t => t.id === currentTenantId) || tenants[0];
  }, [tenants, currentTenantId]);

  const currentPlan = useMemo(() => {
    return PLANS[currentTenant.planId] || PLANS.FREE;
  }, [currentTenant.planId]);

  const userTenants = useMemo(() => {
    return tenants.filter(t => t.ownerId === currentUser.id || currentUser.isSuperuser);
  }, [tenants, currentUser]);

  // Active folder object
  const currentFolder = useMemo(() => {
    if (!currentFolderId) return null;
    return folders.find(f => f.id === currentFolderId) || null;
  }, [folders, currentFolderId]);

  // Breadcrumbs
  const breadcrumbs = useMemo(() => {
    const crumbs: Folder[] = [];
    let cur = currentFolder;
    while (cur) {
      crumbs.unshift(cur);
      cur = cur.parentId ? folders.find(f => f.id === cur?.parentId) || null : null;
    }
    return crumbs;
  }, [currentFolder, folders]);

  // Filtered documents & folders scoped to active tenant
  const tenantDocs = useMemo(() => {
    return documents.filter(d => d.tenantId === currentTenant.id);
  }, [documents, currentTenant.id]);

  const tenantFolders = useMemo(() => {
    return folders.filter(f => f.tenantId === currentTenant.id);
  }, [folders, currentTenant.id]);

  // Trashed items count
  const trashedCount = useMemo(() => {
    return tenantDocs.filter(d => d.isTrashed).length + tenantFolders.filter(f => f.isTrashed).length;
  }, [tenantDocs, tenantFolders]);

  // Filter items based on active Tab
  const displayedItems = useMemo(() => {
    let docs = tenantDocs;
    let flds = tenantFolders;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      docs = docs.filter(d => 
        !d.isTrashed && (
          d.originalName.toLowerCase().includes(q) ||
          d.extension.toLowerCase().includes(q) ||
          d.sha256Hash.toLowerCase().includes(q) ||
          d.mimeType.toLowerCase().includes(q)
        )
      );
      flds = flds.filter(f => !f.isTrashed && f.name.toLowerCase().includes(q));
      return { docs, flds };
    }

    switch (currentTab) {
      case 'dashboard':
        // Top 8 recent files
        docs = docs.filter(d => !d.isTrashed).slice(0, 8);
        flds = flds.filter(f => !f.isTrashed && f.parentId === null);
        break;

      case 'documents':
        docs = docs.filter(d => !d.isTrashed && d.folderId === currentFolderId);
        flds = flds.filter(f => !f.isTrashed && f.parentId === currentFolderId);
        break;

      case 'folders':
        docs = docs.filter(d => !d.isTrashed && d.folderId === currentFolderId);
        flds = flds.filter(f => !f.isTrashed && f.parentId === currentFolderId);
        break;

      case 'favorites':
        docs = docs.filter(d => !d.isTrashed && d.isFavorite);
        flds = flds.filter(f => !f.isTrashed && f.isFavorite);
        break;

      case 'recents':
        docs = [...docs.filter(d => !d.isTrashed)].sort(
          (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
        flds = [];
        break;

      case 'trash':
        docs = docs.filter(d => d.isTrashed);
        flds = flds.filter(f => f.isTrashed);
        break;

      case 'shared-by-me': {
        const sharedDocIds = shares
          .filter(s => s.tenantId === currentTenant.id && s.isActive && s.documentId)
          .map(s => s.documentId);
        docs = docs.filter(d => !d.isTrashed && sharedDocIds.includes(d.id));
        flds = [];
        break;
      }

      case 'shared-with-me': {
        const incomingDocIds = shares
          .filter(s => s.recipientEmail === currentUser.email && s.isActive && s.documentId)
          .map(s => s.documentId);
        // Include any document shared with this user's email
        docs = documents.filter(d => !d.isTrashed && (incomingDocIds.includes(d.id) || d.id === 'doc-bail-locatif'));
        flds = [];
        break;
      }

      default:
        docs = docs.filter(d => !d.isTrashed && d.folderId === currentFolderId);
        flds = flds.filter(f => !f.isTrashed && f.parentId === currentFolderId);
        break;
    }

    return { docs, flds };
  }, [tenantDocs, tenantFolders, currentTab, currentFolderId, searchQuery]);

  // --- Handlers ---
  const handleSelectTenant = (tenantId: string) => {
    setCurrentTenantId(tenantId);
    setCurrentFolderId(null);
    logAction('TENANT_SWITCH_RLS', 'TENANT', tenantId, `Basculement vers l'espace ${tenantId}`);
  };

  const handleSwitchUser = (userId: string) => {
    const user = users.find(u => u.id === userId);
    if (!user) return;
    setCurrentUser(user);

    // Auto-select user's owned tenant
    const userTenant = tenants.find(t => t.ownerId === user.id) || tenants[0];
    setCurrentTenantId(userTenant.id);
    setCurrentFolderId(null);
    logAction('AUTH_USER_SWITCH', 'AUTH', user.email, `Changement d'utilisateur : ${user.fullName}`);
  };

  const handleUploadSuccess = (newDoc: DocumentItem) => {
    setDocuments(prev => [newDoc, ...prev]);

    // Update tenant storage usage
    setTenants(prev => prev.map(t => {
      if (t.id === currentTenant.id) {
        return {
          ...t,
          usedBytes: (t.usedBytes || 0) + newDoc.sizeBytes,
          documentCount: (t.documentCount || 0) + 1
        };
      }
      return t;
    }));

    logAction('DOC_UPLOAD_VERIFIED', 'DOCUMENT', newDoc.originalName, `Fichier importé avec succès (${formatBytes(newDoc.sizeBytes)})`);
  };

  const handleSaveFolder = (name: string, color: string) => {
    if (folderModal.folderToEdit) {
      // Rename folder
      setFolders(prev => prev.map(f => {
        if (f.id === folderModal.folderToEdit?.id) {
          return { ...f, name, color, updatedAt: new Date().toISOString() };
        }
        return f;
      }));
      logAction('FOLDER_RENAME', 'FOLDER', name, `Dossier renommé en "${name}"`);
    } else {
      // Create folder
      const newFolder: Folder = {
        id: `fld-${crypto.randomUUID()}`,
        tenantId: currentTenant.id,
        parentId: currentFolderId,
        name,
        color,
        isFavorite: false,
        isTrashed: false,
        createdBy: currentUser.id,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      setFolders(prev => [...prev, newFolder]);
      logAction('FOLDER_CREATE', 'FOLDER', name, `Dossier "${name}" créé dans l'espace ${currentTenant.name}`);
    }
  };

  const handleToggleFavoriteDoc = (docId: string) => {
    setDocuments(prev => prev.map(d => {
      if (d.id === docId) {
        return { ...d, isFavorite: !d.isFavorite };
      }
      return d;
    }));
  };

  const handleTrashDoc = (docId: string) => {
    setDocuments(prev => prev.map(d => {
      if (d.id === docId) {
        return { ...d, isTrashed: true, trashedAt: new Date().toISOString() };
      }
      return d;
    }));
    logAction('DOC_TRASH', 'DOCUMENT', docId, 'Fichier déplacé vers la corbeille');
  };

  const handleRestoreDoc = (docId: string) => {
    setDocuments(prev => prev.map(d => {
      if (d.id === docId) {
        return { ...d, isTrashed: false, trashedAt: undefined };
      }
      return d;
    }));
    logAction('DOC_RESTORE', 'DOCUMENT', docId, 'Fichier restauré de la corbeille');
  };

  const handlePurgeDoc = (docId: string) => {
    const docToDelete = documents.find(d => d.id === docId);
    if (docToDelete) {
      setDocuments(prev => prev.filter(d => d.id !== docId));
      // Reclaim tenant storage quota
      setTenants(prev => prev.map(t => {
        if (t.id === docToDelete.tenantId) {
          return {
            ...t,
            usedBytes: Math.max(0, (t.usedBytes || 0) - docToDelete.sizeBytes),
            documentCount: Math.max(0, (t.documentCount || 0) - 1)
          };
        }
        return t;
      }));
      logAction('DOC_PERMANENT_PURGE', 'DOCUMENT', docToDelete.originalName, 'Fichier définitivement purgé du stockage MinIO');
    }
  };

  const handleRenameDoc = (doc: DocumentItem) => {
    const newName = window.prompt('Nouveau nom du document :', doc.originalName);
    if (!newName || !newName.trim()) return;
    setDocuments(prev => prev.map(d => {
      if (d.id === doc.id) {
        return { ...d, originalName: newName.trim(), updatedAt: new Date().toISOString() };
      }
      return d;
    }));
    logAction('DOC_RENAME', 'DOCUMENT', newName.trim(), `Fichier renommé`);
  };

  const handleTrashFolder = (folderId: string) => {
    setFolders(prev => prev.map(f => {
      if (f.id === folderId) {
        return { ...f, isTrashed: true, trashedAt: new Date().toISOString() };
      }
      return f;
    }));
  };

  // --- Folder & Document Advanced Operations (Phase 3) ---
  const handleMoveDocument = (doc: DocumentItem) => {
    setMoveModal({
      isOpen: true,
      itemToMove: { type: 'document', item: doc }
    });
  };

  const handleCopyDocument = (doc: DocumentItem) => {
    const copyId = `doc-${crypto.randomUUID()}`;
    const copyName = `${doc.originalName.replace(/\.[^/.]+$/, '')} - Copie.${doc.extension}`;
    const newDoc: DocumentItem = {
      ...doc,
      id: copyId,
      originalName: copyName,
      storageKey: `tenants/${doc.tenantId}/${copyId}.${doc.extension}`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      versions: [
        {
          id: `ver-${crypto.randomUUID()}`,
          documentId: copyId,
          versionNumber: 1,
          sizeBytes: doc.sizeBytes,
          sha256Hash: doc.sha256Hash,
          storageKey: `tenants/${doc.tenantId}/${copyId}.${doc.extension}`,
          mimeType: doc.mimeType,
          changeSummary: 'Duplication initiale',
          createdAt: new Date().toISOString()
        }
      ]
    };

    setDocuments(prev => [newDoc, ...prev]);

    // Update tenant storage quota
    setTenants(prev => prev.map(t => {
      if (t.id === doc.tenantId) {
        return {
          ...t,
          usedBytes: (t.usedBytes || 0) + doc.sizeBytes,
          documentCount: (t.documentCount || 0) + 1
        };
      }
      return t;
    }));

    logAction('DOC_COPY', 'DOCUMENT', copyName, `Duplication du document (${formatBytes(doc.sizeBytes)})`);
  };

  const handleMoveFolder = (folder: Folder) => {
    setMoveModal({
      isOpen: true,
      itemToMove: { type: 'folder', item: folder }
    });
  };

  const handleCopyFolder = (folder: Folder) => {
    const copyId = `fld-${crypto.randomUUID()}`;
    const copyName = `${folder.name} - Copie`;
    const newFolder: Folder = {
      ...folder,
      id: copyId,
      name: copyName,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    setFolders(prev => [...prev, newFolder]);
    logAction('FOLDER_COPY', 'FOLDER', copyName, `Duplication du dossier "${folder.name}"`);
  };

  const handleBulkMove = (docIds: string[]) => {
    setMoveModal({
      isOpen: true,
      itemToMove: { type: 'bulk', item: null, bulkIds: docIds }
    });
  };

  const handleConfirmMove = (targetFolderId: string | null) => {
    const { type, item, bulkIds } = moveModal.itemToMove;

    if (type === 'document' && item) {
      setDocuments(prev => prev.map(d => {
        if (d.id === (item as DocumentItem).id) {
          return { ...d, folderId: targetFolderId, updatedAt: new Date().toISOString() };
        }
        return d;
      }));
      logAction('DOC_MOVE', 'DOCUMENT', (item as DocumentItem).originalName, `Déplacement vers dossier ${targetFolderId || 'Racine'}`);
    } else if (type === 'folder' && item) {
      setFolders(prev => prev.map(f => {
        if (f.id === (item as Folder).id) {
          return { ...f, parentId: targetFolderId, updatedAt: new Date().toISOString() };
        }
        return f;
      }));
      logAction('FOLDER_MOVE', 'FOLDER', (item as Folder).name, `Déplacement vers parent ${targetFolderId || 'Racine'}`);
    } else if (type === 'bulk' && bulkIds && bulkIds.length > 0) {
      setDocuments(prev => prev.map(d => {
        if (bulkIds.includes(d.id)) {
          return { ...d, folderId: targetFolderId, updatedAt: new Date().toISOString() };
        }
        return d;
      }));
      logAction('BULK_DOC_MOVE', 'DOCUMENT', `${bulkIds.length} fichiers`, `Déplacement groupé vers dossier ${targetFolderId || 'Racine'}`);
    }
  };

  const handleBulkTrash = (docIds: string[]) => {
    setDocuments(prev => prev.map(d => {
      if (docIds.includes(d.id)) {
        return { ...d, isTrashed: true, trashedAt: new Date().toISOString() };
      }
      return d;
    }));
    logAction('BULK_DOC_TRASH', 'DOCUMENT', `${docIds.length} fichiers`, 'Mise en corbeille groupée');
  };

  const handleBulkRestore = (docIds: string[]) => {
    setDocuments(prev => prev.map(d => {
      if (docIds.includes(d.id)) {
        return { ...d, isTrashed: false, trashedAt: undefined };
      }
      return d;
    }));
    logAction('BULK_DOC_RESTORE', 'DOCUMENT', `${docIds.length} fichiers`, 'Restauration groupée depuis la corbeille');
  };

  const handleBulkPurge = (docIds: string[]) => {
    const docsToPurge = documents.filter(d => docIds.includes(d.id));
    const totalBytesFreed = docsToPurge.reduce((acc, curr) => acc + curr.sizeBytes, 0);

    setDocuments(prev => prev.filter(d => !docIds.includes(d.id)));

    // Reclaim storage
    setTenants(prev => prev.map(t => {
      if (t.id === currentTenant.id) {
        return {
          ...t,
          usedBytes: Math.max(0, (t.usedBytes || 0) - totalBytesFreed),
          documentCount: Math.max(0, (t.documentCount || 0) - docsToPurge.length)
        };
      }
      return t;
    }));

    logAction('BULK_DOC_PURGE', 'DOCUMENT', `${docIds.length} fichiers`, `Purge définitive (${formatBytes(totalBytesFreed)} libérés)`);
  };

  // --- Secure Sharing Handlers (Phase 5) ---
  const handleSaveShare = (newShare: Share) => {
    setShares(prev => [newShare, ...prev]);
    logAction(
      newShare.shareType === 'SECURE_LINK' ? 'SHARE_LINK_CREATE' : 'SHARE_INTERNAL_CREATE',
      'SHARE',
      newShare.documentName || 'Document',
      newShare.shareType === 'SECURE_LINK'
        ? `Lien généré (Token: ...${newShare.token?.slice(-6)}, MDP: ${newShare.hasPassword})`
        : `Partagé avec ${newShare.recipientEmail} (${newShare.role})`
    );
  };

  const handleToggleShare = (shareId: string) => {
    setShares(prev => prev.map(s => {
      if (s.id === shareId) {
        const nextState = !s.isActive;
        logAction('SHARE_TOGGLE', 'SHARE', s.documentName || 'Document', `Lien ${nextState ? 'activé' : 'désactivé'}`);
        return { ...s, isActive: nextState };
      }
      return s;
    }));
  };

  const handleRevokeShare = (shareId: string) => {
    setShares(prev => prev.filter(s => s.id !== shareId));
    logAction('SHARE_REVOKE', 'SHARE', shareId, 'Partage définitivement révoqué');
  };

  const handleDownloadIncrement = (shareId: string) => {
    setShares(prev => prev.map(s => {
      if (s.id === shareId) {
        const newCount = s.downloadCount + 1;
        logAction('PUBLIC_SHARE_DOWNLOAD', 'SHARE', s.documentName || 'Document', `Téléchargement public n°${newCount}`);
        return { ...s, downloadCount: newCount };
      }
      return s;
    }));
  };

  const handleRestoreVersion = (doc: DocumentItem, version: DocumentVersion) => {
    setDocuments(prev => prev.map(d => {
      if (d.id === doc.id) {
        return {
          ...d,
          sizeBytes: version.sizeBytes,
          sha256Hash: version.sha256Hash,
          mimeType: version.mimeType,
          updatedAt: new Date().toISOString()
        };
      }
      return d;
    }));
    setVersionsDoc(null);
    logAction('DOC_VERSION_RESTORE', 'DOCUMENT', doc.originalName, `Restauration de la version ${version.versionNumber}`);
  };

  const handleCreateVersion = (doc: DocumentItem, newVersion: DocumentVersion) => {
    setDocuments(prev => prev.map(d => {
      if (d.id === doc.id) {
        return {
          ...d,
          sizeBytes: newVersion.sizeBytes,
          sha256Hash: newVersion.sha256Hash,
          mimeType: newVersion.mimeType,
          updatedAt: new Date().toISOString(),
          versions: [newVersion, ...d.versions]
        };
      }
      return d;
    }));

    // Update tenant storage quota
    setTenants(prev => prev.map(t => {
      if (t.id === doc.tenantId) {
        return {
          ...t,
          usedBytes: (t.usedBytes || 0) + newVersion.sizeBytes,
        };
      }
      return t;
    }));

    // Keep active modal in sync
    setVersionsDoc(prev => prev ? {
      ...prev,
      sizeBytes: newVersion.sizeBytes,
      sha256Hash: newVersion.sha256Hash,
      mimeType: newVersion.mimeType,
      versions: [newVersion, ...prev.versions]
    } : null);

    logAction('DOC_VERSION_CREATE', 'DOCUMENT', doc.originalName, `Nouvelle révision v${newVersion.versionNumber} (${formatBytes(newVersion.sizeBytes)})`);
  };

  const handlePurgeVersion = (doc: DocumentItem, versionId: string) => {
    const versionToPurge = doc.versions.find(v => v.id === versionId);
    if (!versionToPurge) return;

    setDocuments(prev => prev.map(d => {
      if (d.id === doc.id) {
        return {
          ...d,
          versions: d.versions.filter(v => v.id !== versionId)
        };
      }
      return d;
    }));

    // Reclaim storage quota
    setTenants(prev => prev.map(t => {
      if (t.id === doc.tenantId) {
        return {
          ...t,
          usedBytes: Math.max(0, (t.usedBytes || 0) - versionToPurge.sizeBytes)
        };
      }
      return t;
    }));

    setVersionsDoc(prev => prev ? {
      ...prev,
      versions: prev.versions.filter(v => v.id !== versionId)
    } : null);

    logAction('DOC_VERSION_PURGE', 'DOCUMENT', doc.originalName, `Purge de la version v${versionToPurge.versionNumber} (${formatBytes(versionToPurge.sizeBytes)} libérés)`);
  };

  const handleEmptyTrash = () => {
    const trashedDocs = tenantDocs.filter(d => d.isTrashed);
    const trashedFlds = tenantFolders.filter(f => f.isTrashed);
    if (trashedDocs.length === 0 && trashedFlds.length === 0) return;

    if (!window.confirm(`Êtes-vous sûr de vouloir vider la corbeille ? ${trashedDocs.length} fichier(s) et ${trashedFlds.length} dossier(s) seront définitivement purgés.`)) {
      return;
    }

    const totalBytesFreed = trashedDocs.reduce((acc, curr) => acc + curr.sizeBytes, 0);

    // Remove trashed documents & folders
    setDocuments(prev => prev.filter(d => !(d.tenantId === currentTenant.id && d.isTrashed)));
    setFolders(prev => prev.filter(f => !(f.tenantId === currentTenant.id && f.isTrashed)));

    // Reclaim storage quota
    setTenants(prev => prev.map(t => {
      if (t.id === currentTenant.id) {
        return {
          ...t,
          usedBytes: Math.max(0, (t.usedBytes || 0) - totalBytesFreed),
          documentCount: Math.max(0, (t.documentCount || 0) - trashedDocs.length)
        };
      }
      return t;
    }));

    logAction('TRASH_EMPTY', 'TENANT', currentTenant.name, `Corbeille entièrement vidée (${formatBytes(totalBytesFreed)} libérés)`);
  };

  const handleUpgradePlan = (planId: PlanType) => {
    setTenants(prev => prev.map(t => {
      if (t.id === currentTenant.id) {
        return { ...t, planId };
      }
      return t;
    }));
    logAction('PLAN_UPGRADE', 'TENANT', planId, `Mise à niveau vers le forfait ${planId}`);
    alert(`Votre espace est désormais associé au forfait ${planId} (${formatBytes(PLANS[planId].maxStorageBytes)}) !`);
  };

  const handleRegister = (fullName: string, email: string) => {
    const newUser: User = {
      id: `usr-${crypto.randomUUID()}`,
      email: email.toLowerCase(),
      fullName,
      isActive: true,
      isVerified: true,
      isSuperuser: false,
      createdAt: new Date().toISOString()
    };

    // Auto-create personal tenant
    const newTenant: Tenant = {
      id: `tnt-${crypto.randomUUID()}`,
      name: `Espace de ${fullName}`,
      ownerId: newUser.id,
      planId: 'FREE',
      role: 'OWNER',
      isActive: true,
      createdAt: new Date().toISOString(),
      usedBytes: 0,
      reservedBytes: 0,
      documentCount: 0
    };

    setUsers(prev => [...prev, newUser]);
    setTenants(prev => [...prev, newTenant]);
    setCurrentUser(newUser);
    setCurrentTenantId(newTenant.id);
    setIsAuthOpen(false);
    logAction('AUTH_REGISTER', 'USER', email, `Création du compte et initialisation de l'espace personnel.`);
  };

  const handleLogin = (email: string) => {
    const user = users.find(u => u.email.toLowerCase() === email.toLowerCase());
    if (user) {
      setCurrentUser(user);
      const userTenant = tenants.find(t => t.ownerId === user.id) || tenants[0];
      setCurrentTenantId(userTenant.id);
      setIsAuthOpen(false);
      logAction('AUTH_LOGIN', 'USER', email, `Connexion réussie.`);
    } else {
      alert("Identifiants non reconnus. Veuillez vérifier l'adresse saisie.");
    }
  };

  const logAction = (action: string, resourceType: any, resourceName: string, details: string) => {
    const log: AuditLogItem = {
      id: `log-${crypto.randomUUID()}`,
      tenantId: currentTenant.id,
      userId: currentUser.id,
      userEmail: currentUser.email,
      action,
      resourceType,
      resourceName,
      ipAddress: '192.168.1.45',
      userAgent: 'Mozilla/5.0 (Debian 12)',
      timestamp: new Date().toISOString(),
      status: 'SUCCESS'
    };
    setAuditLogs(prev => [log, ...prev]);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none antialiased">
      {/* Top Header */}
      <Header
        currentUser={currentUser}
        currentTenant={currentTenant}
        userTenants={userTenants}
        currentPlan={currentPlan}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSelectTenant={handleSelectTenant}
        onSwitchUser={handleSwitchUser}
        onOpenArchitecture={() => setIsArchitectureOpen(true)}
        onOpenUpload={() => {
          if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
            alert("Action refusée : votre rôle est LECTEUR seul dans cet espace documentaire (politique RBAC appliquée).");
            return;
          }
          setIsUploadOpen(true);
        }}
        onOpenSecuritySimulator={() => setIsSecuritySimulatorOpen(true)}
        onOpenMembers={() => setIsMembersOpen(true)}
        onLogout={() => setIsAuthOpen(true)}
        allUsers={users}
      />

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
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
              alert("Action refusée : votre rôle est LECTEUR seul dans cet espace documentaire (politique RBAC appliquée).");
              return;
            }
            setIsUploadOpen(true);
          }}
          onOpenNewFolder={() => {
            if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
              alert("Action refusée : votre rôle est LECTEUR seul dans cet espace documentaire (politique RBAC appliquée).");
              return;
            }
            setFolderModal({ isOpen: true, folderToEdit: null, parentFolder: currentFolder });
          }}
          trashedCount={trashedCount}
        />

        {/* Dynamic Center Stage */}
        <main className="flex-1 flex flex-col overflow-hidden bg-slate-950/60">
          {/* Dashboard Summary Top Banner (when in dashboard tab) */}
          {currentTab === 'dashboard' && !searchQuery && (
            <div className="p-6 pb-2 border-b border-slate-800/80 bg-slate-900/40">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center space-x-3.5">
                  <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-white">{tenantDocs.length}</div>
                    <div className="text-[11px] text-slate-400">Documents actifs</div>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center space-x-3.5">
                  <div className="p-3 rounded-xl bg-purple-500/10 text-purple-400">
                    <FolderIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-white">{tenantFolders.length}</div>
                    <div className="text-[11px] text-slate-400">Dossiers organisés</div>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex items-center space-x-3.5">
                  <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-emerald-400">100% Sain</div>
                    <div className="text-[11px] text-slate-400">Contrôle ClamAV actif</div>
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
                      sur {formatBytes(currentPlan.maxStorageBytes)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Conditional Views */}
          {currentTab === 'storage' || currentTab === 'billing' ? (
            <StorageGauge
              currentTenant={currentTenant}
              currentPlan={currentPlan}
              documents={tenantDocs}
              onUpgradePlan={handleUpgradePlan}
            />
          ) : currentTab === 'admin' && currentUser.isSuperuser ? (
            <AdminConsole
              tenants={tenants}
              users={users}
              auditLogs={auditLogs}
            />
          ) : (
            <FileExplorer
              currentFolder={currentFolder}
              breadcrumbs={breadcrumbs}
              folders={displayedItems.flds}
              documents={displayedItems.docs}
              allFolders={tenantFolders}
              viewMode={viewMode}
              onToggleViewMode={() => setViewMode(prev => prev === 'grid' ? 'list' : 'grid')}
              onNavigateFolder={(fId) => setCurrentFolderId(fId)}
              onPreviewDocument={(doc) => setPreviewDoc(doc)}
              onShareDocument={(doc) => setShareDoc(doc)}
              onViewVersions={(doc) => setVersionsDoc(doc)}
              onToggleFavoriteDoc={handleToggleFavoriteDoc}
              onTrashDoc={handleTrashDoc}
              onRestoreDoc={handleRestoreDoc}
              onPurgeDoc={handlePurgeDoc}
              onRenameDoc={handleRenameDoc}
              onMoveDocument={handleMoveDocument}
              onCopyDocument={handleCopyDocument}
              onOpenUpload={() => {
                if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
                  alert("Action refusée : votre rôle est LECTEUR seul dans cet espace documentaire (politique RBAC appliquée).");
                  return;
                }
                setIsUploadOpen(true);
              }}
              onOpenNewFolder={() => {
                if (currentTenant.role === 'VIEWER' || currentTenant.role === 'GUEST') {
                  alert("Action refusée : votre rôle est LECTEUR seul dans cet espace documentaire (politique RBAC appliquée).");
                  return;
                }
                setFolderModal({ isOpen: true, folderToEdit: null, parentFolder: currentFolder });
              }}
              onRenameFolder={(f) => setFolderModal({ isOpen: true, folderToEdit: f, parentFolder: currentFolder })}
              onMoveFolder={handleMoveFolder}
              onCopyFolder={handleCopyFolder}
              onTrashFolder={handleTrashFolder}
              onBulkMove={handleBulkMove}
              onBulkTrash={handleBulkTrash}
              onBulkRestore={handleBulkRestore}
              onBulkPurge={handleBulkPurge}
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
        onUploadSuccess={handleUploadSuccess}
      />

      <FilePreviewModal
        document={previewDoc}
        onClose={() => setPreviewDoc(null)}
        onShare={(doc) => {
          setPreviewDoc(null);
          setShareDoc(doc);
        }}
      />

      <ShareModal
        document={shareDoc}
        onClose={() => setShareDoc(null)}
        shares={shares}
        onSaveShare={handleSaveShare}
        onToggleShare={handleToggleShare}
        onRevokeShare={handleRevokeShare}
        onOpenPublicSimulator={(share) => setPublicShareSimulator(share)}
      />

      <VersionsModal
        document={versionsDoc}
        onClose={() => setVersionsDoc(null)}
        onRestoreVersion={handleRestoreVersion}
        onCreateVersion={handleCreateVersion}
        onPurgeVersion={handlePurgeVersion}
      />

      <FolderModal
        isOpen={folderModal.isOpen}
        onClose={() => setFolderModal({ isOpen: false, folderToEdit: null, parentFolder: null })}
        folderToEdit={folderModal.folderToEdit}
        parentFolder={folderModal.parentFolder}
        onSave={handleSaveFolder}
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
        documents={tenantDocs}
        onDeleteAccount={() => {
          alert('Votre compte a été purgé conformément au RGPD.');
          setIsAuthOpen(true);
        }}
      />

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onLogin={handleLogin}
        onRegister={handleRegister}
        availableUsers={users}
      />

      <SecuritySimulatorModal
        isOpen={isSecuritySimulatorOpen}
        onClose={() => setIsSecuritySimulatorOpen(false)}
        currentUser={currentUser}
        currentTenant={currentTenant}
        allTenants={tenants}
        allDocs={documents}
      />

      <TenantMembersModal
        isOpen={isMembersOpen}
        onClose={() => setIsMembersOpen(false)}
        currentTenant={currentTenant}
        currentUser={currentUser}
      />

      <MoveModal
        isOpen={moveModal.isOpen}
        onClose={() => setMoveModal({ isOpen: false, itemToMove: { type: 'document', item: null } })}
        itemToMove={moveModal.itemToMove}
        folders={tenantFolders}
        onConfirmMove={handleConfirmMove}
      />

      <PublicShareModal
        isOpen={publicShareSimulator !== null}
        onClose={() => setPublicShareSimulator(null)}
        share={publicShareSimulator}
        document={documents.find(d => d.id === publicShareSimulator?.documentId) || null}
        onDownloadIncrement={handleDownloadIncrement}
      />
    </div>
  );
}
