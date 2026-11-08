import { User, Tenant, Folder, DocumentItem, Plan, AuditLogItem, SessionInfo } from '../types';

export const PLANS: Record<string, Plan> = {
  FREE: {
    id: 'FREE',
    name: 'Gratuit',
    maxStorageBytes: 524288000, // 500 MB
    maxFileSizeBytes: 26214400, // 25 MB
    maxMembers: 1,
    maxVersionsPerFile: 3,
    priceMonthly: 0,
    features: [
      '500 Mo de stockage sécurisé',
      'Fichier max 25 Mo',
      'Scan antivirus ClamAV temps réel',
      'Partage par liens sécurisés',
      'Conservation 3 versions par fichier',
      'Corbeille 15 jours'
    ]
  },
  PERSONAL: {
    id: 'PERSONAL',
    name: 'Personnel',
    maxStorageBytes: 21474836480, // 20 GB
    maxFileSizeBytes: 262144000, // 250 MB
    maxMembers: 1,
    maxVersionsPerFile: 10,
    priceMonthly: 4.99,
    features: [
      '20 Go de stockage cloud chiffré',
      'Fichier max 250 Mo',
      'Conversions LibreOffice automatiques',
      'Historique étendu (10 versions)',
      'Liens avec mot de passe & date d’expiration',
      'Corbeille 30 jours',
      'Support prioritaire par e-mail'
    ]
  },
  PREMIUM: {
    id: 'PREMIUM',
    name: 'Premium',
    maxStorageBytes: 107374182400, // 100 GB
    maxFileSizeBytes: 1073741824, // 1 GB
    maxMembers: 3,
    maxVersionsPerFile: 30,
    priceMonthly: 12.99,
    features: [
      '100 Go de stockage haute disponibilité',
      'Fichier max 1 Go',
      'Audit de sécurité complet & logs RGPD',
      'Jusqu’à 3 utilisateurs dans l’espace',
      'Protection anti-ransomware & rollback 30 versions',
      'Extraction & indexation de métadonnées',
      'Sauvegarde snapshot journalière'
    ]
  }
};

export const INITIAL_USERS: User[] = [
  {
    id: 'usr-alice-101',
    email: 'alice.dupont@example.com',
    fullName: 'Alice Dupont',
    isActive: true,
    isVerified: true,
    isSuperuser: false,
    createdAt: '2026-01-15T09:00:00Z'
  },
  {
    id: 'usr-bob-202',
    email: 'bob.martin@example.com',
    fullName: 'Bob Martin',
    isActive: true,
    isVerified: true,
    isSuperuser: false,
    createdAt: '2026-02-10T14:30:00Z'
  },
  {
    id: 'usr-admin-001',
    email: 'admin@docuspace.io',
    fullName: 'Administrateur DocuSpace',
    isActive: true,
    isVerified: true,
    isSuperuser: true,
    createdAt: '2025-12-01T08:00:00Z'
  }
];

export const INITIAL_TENANTS: Tenant[] = [
  {
    id: 'tnt-alice-main',
    name: 'Espace Personnel d’Alice',
    ownerId: 'usr-alice-101',
    planId: 'FREE',
    role: 'OWNER',
    isActive: true,
    createdAt: '2026-01-15T09:05:00Z',
    usedBytes: 142600000, // ~142.6 MB
    reservedBytes: 0,
    documentCount: 6
  },
  {
    id: 'tnt-alice-family',
    name: 'Famille Dupont & Patrimoine',
    ownerId: 'usr-alice-101',
    planId: 'PERSONAL',
    role: 'OWNER',
    isActive: true,
    createdAt: '2026-03-01T11:00:00Z',
    usedBytes: 384000000,
    reservedBytes: 0,
    documentCount: 4
  },
  {
    id: 'tnt-bob-main',
    name: 'Espace Personnel de Bob',
    ownerId: 'usr-bob-202',
    planId: 'PERSONAL',
    role: 'OWNER',
    isActive: true,
    createdAt: '2026-02-10T14:35:00Z',
    usedBytes: 671000000,
    reservedBytes: 0,
    documentCount: 3
  }
];

export const INITIAL_FOLDERS: Folder[] = [
  {
    id: 'fld-impots',
    tenantId: 'tnt-alice-main',
    parentId: null,
    name: 'Fiscalité & Impôts',
    color: '#3B82F6',
    isFavorite: true,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-01-16T10:00:00Z',
    updatedAt: '2026-01-16T10:00:00Z'
  },
  {
    id: 'fld-sante',
    tenantId: 'tnt-alice-main',
    parentId: null,
    name: 'Santé & Assurances',
    color: '#10B981',
    isFavorite: false,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-01-20T14:15:00Z',
    updatedAt: '2026-01-20T14:15:00Z'
  },
  {
    id: 'fld-contrats',
    tenantId: 'tnt-alice-main',
    parentId: null,
    name: 'Logement & Contrats',
    color: '#F59E0B',
    isFavorite: true,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-02-01T09:30:00Z',
    updatedAt: '2026-02-01T09:30:00Z'
  },
  {
    id: 'fld-sous-2025',
    tenantId: 'tnt-alice-main',
    parentId: 'fld-impots',
    name: 'Déclarations 2025',
    color: '#6366F1',
    isFavorite: false,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-02-15T16:00:00Z',
    updatedAt: '2026-02-15T16:00:00Z'
  }
];

export const INITIAL_DOCUMENTS: DocumentItem[] = [
  {
    id: 'doc-avis-impot-2025',
    tenantId: 'tnt-alice-main',
    folderId: 'fld-sous-2025',
    originalName: 'Avis_Situation_Fiscale_2025.pdf',
    storageKey: 'tenants/tnt-alice-main/8b628ff3-e189-40ad-a2df-95d4ea547d02.pdf',
    mimeType: 'application/pdf',
    extension: 'pdf',
    sizeBytes: 1245000, // 1.2 MB
    sha256Hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
    status: 'READY',
    antivirusStatus: 'CLEAN',
    isFavorite: true,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-03-02T10:12:00Z',
    updatedAt: '2026-03-02T10:12:00Z',
    versions: [
      {
        id: 'ver-01',
        documentId: 'doc-avis-impot-2025',
        versionNumber: 1,
        storageKey: 'tenants/tnt-alice-main/8b628ff3-e189-40ad-a2df-95d4ea547d02.pdf',
        sizeBytes: 1245000,
        mimeType: 'application/pdf',
        sha256Hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        changeSummary: 'Version initiale certifiée par la DGFIP',
        createdAt: '2026-03-02T10:12:00Z'
      }
    ],
    contentPreview: 'DOCUMENT OFFICIEL RÉPUBLIQUE FRANÇAISE\nDirection Générale des Finances Publiques\n\nAvis de Situation Déclarative à l’Impôt sur le Revenu 2025\nBénéficiaire : Alice Dupont\nNuméro Fiscal : 18 42 75 92 11 04\nRevenu Brut Global : 42 500 €\nStatut : Déclaration validée sans anomalie'
  },
  {
    id: 'doc-bail-locatif',
    tenantId: 'tnt-alice-main',
    folderId: 'fld-contrats',
    originalName: 'Bail_Location_Appartement_Paris11.docx',
    storageKey: 'tenants/tnt-alice-main/2c45ae28-64ff-4bb2-b69c-097bc2713f88.docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    extension: 'docx',
    sizeBytes: 840000,
    sha256Hash: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
    status: 'READY',
    antivirusStatus: 'CLEAN',
    isFavorite: false,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-02-05T14:20:00Z',
    updatedAt: '2026-02-12T11:00:00Z',
    versions: [
      {
        id: 'ver-02',
        documentId: 'doc-bail-locatif',
        versionNumber: 2,
        storageKey: 'tenants/tnt-alice-main/2c45ae28-64ff-4bb2-b69c-097bc2713f88.docx',
        sizeBytes: 840000,
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        sha256Hash: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
        changeSummary: 'Ajout avenant stationnement vélo et cave',
        createdAt: '2026-02-12T11:00:00Z'
      },
      {
        id: 'ver-01-old',
        documentId: 'doc-bail-locatif',
        versionNumber: 1,
        storageKey: 'tenants/tnt-alice-main/2c45ae28-old-ver.docx',
        sizeBytes: 812000,
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        sha256Hash: '4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a',
        changeSummary: 'Version initiale signée chez le notaire',
        createdAt: '2026-02-05T14:20:00Z'
      }
    ],
    contentPreview: 'CONTRAT DE BAIL D’HABITATION NON MEUBLÉE\nLoi n° 89-462 du 6 juillet 1989\n\nEntre les soussignés :\nBailleur : SCI Le Marais\nLocataire : Mme Alice Dupont\nDésignation : 3 pièces, 68m², 75011 Paris\nLoyer mensuel : 1 450,00 € charges comprises\nDépôt de garantie : 1 300,00 €\nDurée : 3 années reconductibles tacitement'
  },
  {
    id: 'doc-budget-2026',
    tenantId: 'tnt-alice-main',
    folderId: null,
    originalName: 'Suivi_Budget_Familial_2026.csv',
    storageKey: 'tenants/tnt-alice-main/01bf2803-b54c-47bc-bb39-b9ee0fa6c391.csv',
    mimeType: 'text/csv',
    extension: 'csv',
    sizeBytes: 154000,
    sha256Hash: '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae',
    status: 'READY',
    antivirusStatus: 'CLEAN',
    isFavorite: true,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-01-18T18:00:00Z',
    updatedAt: '2026-03-01T09:15:00Z',
    versions: [],
    contentPreview: 'Mois,Revenus (€),Logement (€),Alimentation (€),Santé (€),Épargne (€)\nJanvier 2026,3500.00,1450.00,450.00,65.00,750.00\nFévrier 2026,3500.00,1450.00,420.00,45.00,800.00\nMars 2026,3650.00,1450.00,480.00,110.00,720.00\nAvril 2026,3500.00,1450.00,440.00,30.00,850.00'
  },
  {
    id: 'doc-carte-identite',
    tenantId: 'tnt-alice-main',
    folderId: null,
    originalName: 'CNI_Alice_Dupont_RectoVerso.jpg',
    storageKey: 'tenants/tnt-alice-main/78de2819-0941-4322-834c-687f893cbcd1.jpg',
    mimeType: 'image/jpeg',
    extension: 'jpg',
    sizeBytes: 2450000,
    sha256Hash: 'fcde2b2edba56bf408601fb721fe9b5c338d10ee429ea04fae5511b68fbf8fb9',
    status: 'READY',
    antivirusStatus: 'CLEAN',
    isFavorite: false,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-01-16T11:45:00Z',
    updatedAt: '2026-01-16T11:45:00Z',
    versions: [],
    contentPreview: 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="600" height="380" viewBox="0 0 600 380"><rect width="600" height="380" rx="16" fill="%231E293B"/><rect x="20" y="20" width="560" height="340" rx="12" fill="%230F172A" stroke="%2338BDF8" stroke-width="2"/><circle cx="110" cy="150" r="50" fill="%2338BDF8" opacity="0.3"/><text x="110" y="160" font-family="sans-serif" font-size="28" fill="%2338BDF8" text-anchor="middle">PHOTO</text><text x="200" y="120" font-family="sans-serif" font-size="22" font-weight="bold" fill="%23F8FAFC">RÉPUBLIQUE FRANÇAISE</text><text x="200" y="150" font-family="sans-serif" font-size="16" fill="%2394A3B8">CARTE NATIONALE D’IDENTITÉ</text><text x="200" y="190" font-family="sans-serif" font-size="15" fill="%23E2E8F0">Nom : DUPONT</text><text x="200" y="220" font-family="sans-serif" font-size="15" fill="%23E2E8F0">Prénoms : Alice Marie</text><text x="200" y="250" font-family="sans-serif" font-size="15" fill="%23E2E8F0">Née le : 14/07/1992 à Lyon (69)</text><rect x="40" y="300" width="520" height="35" rx="4" fill="%230284C7" opacity="0.2"/><text x="50" y="323" font-family="monospace" font-size="14" fill="%2338BDF8">IDFRADUPONT&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;9207144F2911244FRA&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;6</text></svg>'
  },
  {
    id: 'doc-note-medecin',
    tenantId: 'tnt-alice-main',
    folderId: 'fld-sante',
    originalName: 'Ordonnance_Ophtalmologie_2026.pdf',
    storageKey: 'tenants/tnt-alice-main/3412abef-8899-4411-b2c3-998877665544.pdf',
    mimeType: 'application/pdf',
    extension: 'pdf',
    sizeBytes: 680000,
    sha256Hash: 'a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e',
    status: 'READY',
    antivirusStatus: 'CLEAN',
    isFavorite: false,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-02-28T09:30:00Z',
    updatedAt: '2026-02-28T09:30:00Z',
    versions: [],
    contentPreview: 'CENTRE MÉDICAL SAINT-ANTOINE\nDr. Philippe Mercier — Ophtalmologiste\nRPPS : 1000349821\n\nPrescription de verres correcteurs :\nOD : -1.75 (+0.50 à 90°)\nOG : -2.00 (+0.25 à 85°)\nVerres antireflet et amincis recommandés.\nValidité : 3 ans'
  },
  {
    id: 'doc-code-projet',
    tenantId: 'tnt-alice-main',
    folderId: null,
    originalName: 'Notes_Securite_Debian.md',
    storageKey: 'tenants/tnt-alice-main/11223344-5566-7788-99aa-bbccddeeff00.md',
    mimeType: 'text/markdown',
    extension: 'md',
    sizeBytes: 42000,
    sha256Hash: 'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9',
    status: 'READY',
    antivirusStatus: 'CLEAN',
    isFavorite: false,
    isTrashed: false,
    createdBy: 'usr-alice-101',
    createdAt: '2026-02-14T15:20:00Z',
    updatedAt: '2026-02-14T15:20:00Z',
    versions: [],
    contentPreview: '# Procédure de Durcissement Serveur Debian 12\n\n1. Désactiver la connexion root SSH\n2. Installer fail2ban avec jail sur le port 22 et Nginx\n3. Configurer les sauvegardes chiffrées automatiques\n4. Vérifier la santé du conteneur ClamAV avec `clamdscan --ping`\n5. Valider l’isolation PostgreSQL Row-Level Security'
  }
];

export const INITIAL_AUDIT_LOGS: AuditLogItem[] = [
  {
    id: 'log-01',
    tenantId: 'tnt-alice-main',
    userId: 'usr-alice-101',
    userEmail: 'alice.dupont@example.com',
    action: 'AUTH_LOGIN_SUCCESS',
    resourceType: 'AUTH',
    resourceName: 'Session Web',
    ipAddress: '192.168.1.45',
    userAgent: 'Mozilla/5.0 (Debian; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
    timestamp: '2026-11-08T08:30:12Z',
    status: 'SUCCESS'
  },
  {
    id: 'log-02',
    tenantId: 'tnt-alice-main',
    userId: 'usr-alice-101',
    userEmail: 'alice.dupont@example.com',
    action: 'DOC_UPLOAD_VERIFIED',
    resourceType: 'DOCUMENT',
    resourceName: 'Avis_Situation_Fiscale_2025.pdf',
    ipAddress: '192.168.1.45',
    userAgent: 'Firefox/128.0',
    timestamp: '2026-11-08T08:32:44Z',
    status: 'SUCCESS'
  },
  {
    id: 'log-03',
    tenantId: 'tnt-alice-main',
    userId: 'usr-alice-101',
    userEmail: 'alice.dupont@example.com',
    action: 'CLAMAV_SCAN_PASSED',
    resourceType: 'DOCUMENT',
    resourceName: 'SHA256: 9f86d081884c...',
    ipAddress: '127.0.0.1 (Docker internal)',
    userAgent: 'ClamAV-Daemon 1.3',
    timestamp: '2026-11-08T08:32:45Z',
    status: 'SUCCESS'
  },
  {
    id: 'log-04',
    tenantId: 'tnt-alice-main',
    userId: 'usr-alice-101',
    userEmail: 'alice.dupont@example.com',
    action: 'TENANT_RLS_CONTEXT_SET',
    resourceType: 'TENANT',
    resourceName: 'tnt-alice-main',
    ipAddress: '192.168.1.45',
    userAgent: 'FastAPI/0.111',
    timestamp: '2026-11-08T08:33:00Z',
    status: 'SUCCESS'
  }
];

export const INITIAL_SESSIONS: SessionInfo[] = [
  {
    id: 'ses-cur',
    device: 'Linux PC (Debian Bookworm)',
    browser: 'Firefox 128.0',
    ipAddress: '192.168.1.45 (Localhost)',
    lastActive: 'À l’instant',
    isCurrent: true
  },
  {
    id: 'ses-mob',
    device: 'iPhone 15 Pro (iOS 18)',
    browser: 'Safari Mobile',
    ipAddress: '88.162.204.12',
    lastActive: 'Hier à 22:15',
    isCurrent: false
  }
];
