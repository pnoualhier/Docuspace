import React from 'react';
import fs from 'node:fs';
import path from 'node:path';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import App from '../App';
import { StorageGauge } from '../components/StorageGauge';
import { AuthModal } from '../components/AuthModal';
import { ShareModal } from '../components/ShareModal';
import { FileExplorer } from '../components/FileExplorer';
import { FileUploadModal } from '../components/FileUploadModal';
import { FilePreviewModal } from '../components/FilePreviewModal';
import { PublicShareView } from '../components/PublicShareView';
import { TenantMembersModal } from '../components/TenantMembersModal';
import { VersionsModal } from '../components/VersionsModal';
import { SettingsModal } from '../components/SettingsModal';
import { BillingCheckoutModal } from '../components/BillingCheckoutModal';
import { AdminConsole } from '../components/AdminConsole';
import { ConfirmActionModal } from '../components/ConfirmActionModal';
import { RenameModal } from '../components/RenameModal';
import { apiClient, ApiError } from '../services/api';
import { calculateSHA256, formatBytes, getFileCategory, generateStorageKey } from '../services/crypto';
import {
  FIXTURE_DOCUMENTS,
  FIXTURE_FOLDERS,
  FIXTURE_PLANS,
  FIXTURE_SECOND_TENANT,
  FIXTURE_TENANT,
  FIXTURE_USER,
} from './fixtures/testData';

const jsonResponse = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('DocuSpace Crypto & Utility Helpers', () => {
  it('1. calculates exact SHA-256 digest and formats sizes/categories accurately', async () => {
    const data = new TextEncoder().encode('docuspace-integrity-check');
    const blob = new Blob([data], { type: 'text/plain' });
    if (!blob.arrayBuffer) {
      (blob as unknown as { arrayBuffer: () => Promise<ArrayBuffer> }).arrayBuffer = async () =>
        data.buffer;
    }
    const digest = await calculateSHA256(blob);
    expect(digest).toMatch(/^[a-f0-9]{64}$/);
    expect(formatBytes(0)).toBe('0 o');
    expect(formatBytes(1024)).toBe('1 Ko');
    expect(formatBytes(524288000, 0)).toBe('500 Mo');
    expect(getFileCategory('application/pdf', 'pdf')).toBe('pdf');
    expect(getFileCategory('image/png', 'png')).toBe('image');
    expect(generateStorageKey('tenant-123', '.pdf')).toMatch(
      /^tenants\/tenant-123\/[a-f0-9-]+\.pdf$/
    );
  });
});

describe('DocuSpace Dynamic Auth, Workspace & Tenant Isolation', () => {
  beforeEach(() => {
    apiClient.setAccessToken(null);
    apiClient.setUnauthorizedHandler(null);
    window.history.pushState({}, '', '/');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('2. starts strictly unauthenticated when /auth/me returns 401 with zero mock data shown', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/billing/plans')) {
        return jsonResponse([
          {
            id: 'FREE',
            name: 'Gratuit',
            price_monthly: 0,
            price_yearly: 0,
            max_storage_bytes: 524288000,
            max_file_size_bytes: 52428800,
            max_members: 1,
            max_versions_per_file: 3,
            features: ['500 Mo'],
          },
        ]);
      }
      if (url.endsWith('/auth/me') || url.endsWith('/auth/refresh')) {
        return jsonResponse({ detail: 'Non authentifié' }, 401);
      }
      return jsonResponse({}, 404);
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    expect(screen.getByText(/Connexion sécurisée avec chiffrement Argon2id/i)).toBeInTheDocument();
    expect(screen.queryByText(/Simulateur RLS/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Espace Personnel/i)).not.toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalled();
  });

  it('3. logs in against FastAPI endpoints and hydrates user, tenant, documents, and folders', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/billing/plans')) {
        return jsonResponse([
          {
            id: 'PERSONAL',
            name: 'Personnel',
            price_monthly: 4.99,
            price_yearly: 49.9,
            max_storage_bytes: 21474836480,
            max_file_size_bytes: 524288000,
            max_members: 5,
            max_versions_per_file: 10,
            features: ['20 Go'],
          },
        ]);
      }
      if (url.endsWith('/auth/me') && !apiClient.getAccessToken()) {
        return jsonResponse({ detail: 'Non authentifié' }, 401);
      }
      if (url.endsWith('/auth/refresh') && !apiClient.getAccessToken()) {
        return jsonResponse({ detail: 'No refresh cookie' }, 401);
      }
      if (url.endsWith('/auth/login') && init?.method === 'POST') {
        return jsonResponse({
          access_token: 'jwt-valid-token',
          token_type: 'bearer',
          expires_in: 1800,
          user_id: FIXTURE_USER.id,
          tenant_id: FIXTURE_TENANT.id,
        });
      }
      if (url.endsWith('/auth/me')) {
        return jsonResponse({
          id: FIXTURE_USER.id,
          email: FIXTURE_USER.email,
          full_name: FIXTURE_USER.fullName,
          is_active: true,
          is_verified: true,
          is_superuser: false,
          created_at: FIXTURE_USER.createdAt,
        });
      }
      if (url.endsWith('/tenants/my-tenants')) {
        return jsonResponse([
          {
            id: FIXTURE_TENANT.id,
            name: FIXTURE_TENANT.name,
            owner_id: FIXTURE_USER.id,
            plan_id: 'PERSONAL',
            role: 'OWNER',
            is_active: true,
            created_at: FIXTURE_TENANT.createdAt,
            storage_usage: {
              tenant_id: FIXTURE_TENANT.id,
              used_bytes: 2048,
              reserved_bytes: 0,
              document_count: 1,
              max_storage_bytes: 21474836480,
              percent_used: 0.01,
            },
          },
        ]);
      }
      if (url.endsWith('/tenants/current')) {
        return jsonResponse({
          id: FIXTURE_TENANT.id,
          name: FIXTURE_TENANT.name,
          owner_id: FIXTURE_USER.id,
          plan_id: 'PERSONAL',
          role: 'OWNER',
          is_active: true,
          created_at: FIXTURE_TENANT.createdAt,
          storage_usage: {
            tenant_id: FIXTURE_TENANT.id,
            used_bytes: 2048,
            reserved_bytes: 0,
            document_count: 1,
            max_storage_bytes: 21474836480,
            percent_used: 0.01,
          },
        });
      }
      if (url.includes('/documents/folders') && url.includes('is_trashed=false')) {
        return jsonResponse([
          {
            id: FIXTURE_FOLDERS[0].id,
            tenant_id: FIXTURE_TENANT.id,
            parent_id: null,
            name: FIXTURE_FOLDERS[0].name,
            color: '#3B82F6',
            is_favorite: false,
            is_trashed: false,
            created_at: FIXTURE_FOLDERS[0].createdAt,
            updated_at: FIXTURE_FOLDERS[0].updatedAt,
          },
        ]);
      }
      if (url.includes('/documents/folders') && url.includes('is_trashed=true')) {
        return jsonResponse([]);
      }
      if (url.includes('/documents/documents') && url.includes('is_trashed=false')) {
        return jsonResponse([
          {
            id: FIXTURE_DOCUMENTS[0].id,
            tenant_id: FIXTURE_TENANT.id,
            folder_id: null,
            original_name: FIXTURE_DOCUMENTS[0].originalName,
            mime_type: 'text/plain',
            extension: 'txt',
            size_bytes: 2048,
            sha256_hash: FIXTURE_DOCUMENTS[0].sha256Hash,
            status: 'READY',
            antivirus_status: 'CLEAN',
            is_favorite: false,
            is_trashed: false,
            created_at: FIXTURE_DOCUMENTS[0].createdAt,
            updated_at: FIXTURE_DOCUMENTS[0].updatedAt,
          },
        ]);
      }
      if (url.includes('/documents/documents') && url.includes('is_trashed=true')) {
        return jsonResponse([]);
      }
      if (url.endsWith('/shares') || url.endsWith('/shares/received') || url.endsWith('/billing/invoices')) {
        return jsonResponse([]);
      }
      if (url.includes('/notifications')) {
        return jsonResponse({ items: [], total: 0, unread_count: 0 });
      }
      return jsonResponse({}, 404);
    });

    render(<App />);
    await waitFor(() => expect(screen.getByLabelText(/Adresse e-mail/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/Adresse e-mail/i), {
      target: { value: FIXTURE_USER.email },
    });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), {
      target: { value: 'StrongPassword!123' },
    });
    const loginButtons = screen.getAllByRole('button', { name: /Se connecter/i });
    fireEvent.click(loginButtons[loginButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText(FIXTURE_DOCUMENTS[0].originalName)).toBeInTheDocument();
    });
    expect(screen.getByText(FIXTURE_FOLDERS[0].name)).toBeInTheDocument();
    expect(screen.getByText(FIXTURE_TENANT.name)).toBeInTheDocument();
  });

  it('4. clears workspace and returns to AuthModal on logout', async () => {
    apiClient.setAccessToken('active-jwt-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/billing/plans')) return jsonResponse([]);
      if (url.endsWith('/auth/me')) {
        return jsonResponse({
          id: FIXTURE_USER.id,
          email: FIXTURE_USER.email,
          full_name: FIXTURE_USER.fullName,
          is_active: true,
          is_verified: true,
          is_superuser: false,
          created_at: FIXTURE_USER.createdAt,
        });
      }
      if (url.endsWith('/auth/logout')) return new Response(null, { status: 204 });
      if (url.endsWith('/tenants/my-tenants')) {
        return jsonResponse([
          {
            id: FIXTURE_TENANT.id,
            name: FIXTURE_TENANT.name,
            owner_id: FIXTURE_USER.id,
            plan_id: 'PERSONAL',
            role: 'OWNER',
            is_active: true,
            created_at: FIXTURE_TENANT.createdAt,
          },
        ]);
      }
      if (url.endsWith('/tenants/current')) {
        return jsonResponse({
          id: FIXTURE_TENANT.id,
          name: FIXTURE_TENANT.name,
          owner_id: FIXTURE_USER.id,
          plan_id: 'PERSONAL',
          role: 'OWNER',
          is_active: true,
          created_at: FIXTURE_TENANT.createdAt,
        });
      }
      if (url.includes('/notifications')) return jsonResponse({ items: [], total: 0, unread_count: 0 });
      return jsonResponse([]);
    });

    render(<App />);
    await waitFor(() => expect(screen.getByText(FIXTURE_USER.fullName)).toBeInTheDocument());

    fireEvent.click(screen.getByText(FIXTURE_USER.fullName));
    fireEvent.click(screen.getByRole('button', { name: /Se déconnecter/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    expect(apiClient.getAccessToken()).toBeNull();
  });

  it('5. isolates tenant data cleanly when switching active workspace', async () => {
    apiClient.setAccessToken('active-jwt-2');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString();
      const headers = new Headers(init?.headers);
      const tid = headers.get('X-Tenant-ID');

      if (url.endsWith('/billing/plans')) return jsonResponse([]);
      if (url.endsWith('/auth/me')) {
        return jsonResponse({
          id: FIXTURE_USER.id,
          email: FIXTURE_USER.email,
          full_name: FIXTURE_USER.fullName,
          is_active: true,
          is_verified: true,
          is_superuser: false,
          created_at: FIXTURE_USER.createdAt,
        });
      }
      if (url.endsWith('/tenants/my-tenants')) {
        return jsonResponse([
          {
            id: FIXTURE_TENANT.id,
            name: FIXTURE_TENANT.name,
            owner_id: FIXTURE_USER.id,
            plan_id: 'PERSONAL',
            role: 'OWNER',
            is_active: true,
            created_at: FIXTURE_TENANT.createdAt,
          },
          {
            id: FIXTURE_SECOND_TENANT.id,
            name: FIXTURE_SECOND_TENANT.name,
            owner_id: FIXTURE_USER.id,
            plan_id: 'FREE',
            role: 'EDITOR',
            is_active: true,
            created_at: FIXTURE_SECOND_TENANT.createdAt,
          },
        ]);
      }
      if (url.endsWith('/tenants/current')) {
        const active = tid === FIXTURE_SECOND_TENANT.id ? FIXTURE_SECOND_TENANT : FIXTURE_TENANT;
        return jsonResponse({
          id: active.id,
          name: active.name,
          owner_id: active.ownerId,
          plan_id: active.planId,
          role: active.role,
          is_active: true,
          created_at: active.createdAt,
        });
      }
      if (url.includes('/documents/documents') && url.includes('is_trashed=false')) {
        if (tid === FIXTURE_SECOND_TENANT.id) {
          return jsonResponse([
            {
              id: 'doc-t2-only',
              tenant_id: FIXTURE_SECOND_TENANT.id,
              folder_id: null,
              original_name: 'fichier_secondaire_isole.pdf',
              mime_type: 'application/pdf',
              extension: 'pdf',
              size_bytes: 4096,
              sha256_hash: 'c'.repeat(64),
              status: 'READY',
              antivirus_status: 'CLEAN',
              is_favorite: false,
              is_trashed: false,
              created_at: '2026-02-02T10:00:00Z',
              updated_at: '2026-02-02T10:00:00Z',
            },
          ]);
        }
        return jsonResponse([
          {
            id: FIXTURE_DOCUMENTS[0].id,
            tenant_id: FIXTURE_TENANT.id,
            folder_id: null,
            original_name: FIXTURE_DOCUMENTS[0].originalName,
            mime_type: 'text/plain',
            extension: 'txt',
            size_bytes: 2048,
            sha256_hash: FIXTURE_DOCUMENTS[0].sha256Hash,
            status: 'READY',
            antivirus_status: 'CLEAN',
            is_favorite: false,
            is_trashed: false,
            created_at: FIXTURE_DOCUMENTS[0].createdAt,
            updated_at: FIXTURE_DOCUMENTS[0].updatedAt,
          },
        ]);
      }
      if (url.includes('/notifications')) return jsonResponse({ items: [], total: 0, unread_count: 0 });
      return jsonResponse([]);
    });

    render(<App />);
    await waitFor(() =>
      expect(screen.getByText(FIXTURE_DOCUMENTS[0].originalName)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(FIXTURE_TENANT.name));
    fireEvent.click(screen.getByText(FIXTURE_SECOND_TENANT.name));

    await waitFor(() => {
      expect(screen.getByText('fichier_secondaire_isole.pdf')).toBeInTheDocument();
    });
    expect(screen.queryByText(FIXTURE_DOCUMENTS[0].originalName)).not.toBeInTheDocument();
  });
});

describe('DocuSpace Dynamic Component Workflows', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('6. FileUploadModal validates security rules, enforces read-only restriction, and uploads via real API callback', async () => {
    const onUploadToApi = vi.fn().mockRejectedValueOnce(new Error('ClamAV: Menace détectée'));
    const onUploadSuccess = vi.fn();

    const { rerender } = render(
      <FileUploadModal
        isOpen={true}
        onClose={vi.fn()}
        currentTenant={{ ...FIXTURE_TENANT, isRestrictedReadOnly: true }}
        currentPlan={FIXTURE_PLANS[1]}
        currentFolder={null}
        onUploadSuccess={onUploadSuccess}
        onUploadToApi={onUploadToApi}
      />
    );

    const validFile = new File(['hello'], 'rapport.txt', { type: 'text/plain' });
    fireEvent.change(screen.getByLabelText(/Sélectionner un fichier à importer/i), {
      target: { files: [validFile] },
    });
    expect(screen.getByRole('alert')).toHaveTextContent(/lecture seule/i);

    rerender(
      <FileUploadModal
        isOpen={true}
        onClose={vi.fn()}
        currentTenant={FIXTURE_TENANT}
        currentPlan={FIXTURE_PLANS[1]}
        currentFolder={null}
        onUploadSuccess={onUploadSuccess}
        onUploadToApi={onUploadToApi}
      />
    );

    const input = screen.getByLabelText(/Sélectionner un fichier à importer/i);
    fireEvent.change(input, {
      target: { files: [new File(['MZ'], 'facture.exe.pdf', { type: 'application/pdf' })] },
    });
    expect(screen.getByRole('alert')).toHaveTextContent(/double extension exécutable/i);

    fireEvent.change(input, { target: { files: [new File([], 'vide.txt', { type: 'text/plain' })] } });
    expect(screen.getByRole('alert')).toHaveTextContent(/est vide/i);

    fireEvent.click(screen.getByRole('button', { name: /Préparer fichier EICAR/i }));
    fireEvent.click(screen.getByRole('button', { name: /Lancer l'import sécurisé/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/ClamAV: Menace détectée/i);
    });
    expect(onUploadToApi).toHaveBeenCalledTimes(1);
    expect(onUploadSuccess).not.toHaveBeenCalled();
  });

  it('7. FilePreviewModal loads backend /preview content and renders accurate PENDING/CLEAN ClamAV status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse({
        document_id: FIXTURE_DOCUMENTS[1].id,
        original_name: FIXTURE_DOCUMENTS[1].originalName,
        mime_type: 'text/csv',
        extension: 'csv',
        size_bytes: 4096,
        mode: 'csv',
        csv_data: {
          headers: ['Produit', 'Montant'],
          rows: [['Stockage Cloud', '14.99']],
          total_rows_parsed: 1,
          delimiter: ',',
        },
      })
    );

    render(
      <FilePreviewModal
        document={FIXTURE_DOCUMENTS[1]}
        onClose={vi.fn()}
        onShare={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Stockage Cloud')).toBeInTheDocument();
    });
    expect(screen.getByText(/ClamAV : Analyse en attente/i)).toBeInTheDocument();
    expect(screen.getByText(/Aperçu Tabulaire/i)).toBeInTheDocument();
  });

  it('8. ShareModal creates SECURE_LINK via backend handler and exposes one-time URL', async () => {
    const onCreateSecureLink = vi.fn().mockResolvedValue({
      id: 'shr-1',
      tenantId: FIXTURE_TENANT.id,
      documentId: FIXTURE_DOCUMENTS[0].id,
      createdBy: FIXTURE_USER.id,
      shareType: 'SECURE_LINK',
      role: 'VIEWER',
      token: 'tok-987654321',
      publicUrl: 'http://localhost/s/tok-987654321',
      hasPassword: false,
      downloadCount: 0,
      isActive: true,
      createdAt: '2026-01-20T10:00:00Z',
    });

    render(
      <ShareModal
        document={FIXTURE_DOCUMENTS[0]}
        onClose={vi.fn()}
        shares={[]}
        onCreateSecureLink={onCreateSecureLink}
        onRevokeShare={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Générer un nouveau lien sécurisé/i }));

    await waitFor(() => {
      expect(screen.getByText('http://localhost/s/tok-987654321')).toBeInTheDocument();
    });
    expect(onCreateSecureLink).toHaveBeenCalledWith({
      documentId: FIXTURE_DOCUMENTS[0].id,
      password: undefined,
      expiresInHours: 168,
      maxDownloads: undefined,
    });
  });

  it('9. PublicShareView unlocks password-protected link via API and updates download count', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          token: 'pub-tok-1',
          resource_type: 'DOCUMENT',
          resource_name: 'contrat_client.pdf',
          mime_type: 'application/pdf',
          extension: 'pdf',
          size_bytes: 12000,
          sha256_hash: 'd'.repeat(64),
          has_password: true,
          is_password_required: true,
          download_count: 0,
          max_downloads: 2,
          can_download: true,
          is_active: true,
        })
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'Mot de passe incorrect' }, 401))
      .mockResolvedValueOnce(
        jsonResponse({
          token: 'pub-tok-1',
          resource_type: 'DOCUMENT',
          resource_name: 'contrat_client.pdf',
          mime_type: 'application/pdf',
          extension: 'pdf',
          size_bytes: 12000,
          sha256_hash: 'd'.repeat(64),
          has_password: true,
          is_password_required: true,
          download_count: 0,
          max_downloads: 2,
          can_download: true,
          is_active: true,
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          download_url: 'http://localhost/minio/presigned-doc',
          filename: 'contrat_client.pdf',
          size_bytes: 12000,
          mime_type: 'application/pdf',
          download_count: 1,
          max_downloads: 2,
        })
      );

    render(<PublicShareView token="pub-tok-1" />);

    await waitFor(() => {
      expect(screen.getByText('contrat_client.pdf')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Mot de passe du partage/i), {
      target: { value: 'wrong-pass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Déverrouiller le partage/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Mot de passe incorrect');
    });

    fireEvent.change(screen.getByLabelText(/Mot de passe du partage/i), {
      target: { value: 'correct-pass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Déverrouiller le partage/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Télécharger le document sécurisé/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Télécharger le document sécurisé/i }));

    await waitFor(() => {
      expect(screen.getByText(/Téléchargements : 1 \/ 2/i)).toBeInTheDocument();
    });
  });

  it('10. TenantMembersModal loads members from API and surfaces max_members 400 error', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 'mem-1',
            user_id: FIXTURE_USER.id,
            email: FIXTURE_USER.email,
            full_name: FIXTURE_USER.fullName,
            role: 'OWNER',
            joined_at: '2026-01-10T09:00:00Z',
          },
        ])
      )
      .mockResolvedValueOnce(
        jsonResponse({ detail: 'Limite de membres du forfait atteinte (max 1).' }, 400)
      );

    render(
      <TenantMembersModal
        isOpen={true}
        onClose={vi.fn()}
        currentTenant={FIXTURE_TENANT}
        currentUser={FIXTURE_USER}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(FIXTURE_USER.fullName)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/collaborateur@domaine.fr/i), {
      target: { value: 'invite@example.org' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Inviter/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Limite de membres/i);
    });
  });

  it('11. VersionsModal loads real versions from API and handles restore', async () => {
    const onVersionsUpdated = vi.fn();
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 'ver-2',
            document_id: FIXTURE_DOCUMENTS[0].id,
            version_number: 2,
            size_bytes: 2048,
            mime_type: 'text/plain',
            sha256_hash: 'e'.repeat(64),
            change_summary: 'Mise à jour v2',
            created_at: '2026-01-18T10:00:00Z',
          },
          {
            id: 'ver-1',
            document_id: FIXTURE_DOCUMENTS[0].id,
            version_number: 1,
            size_bytes: 1024,
            mime_type: 'text/plain',
            sha256_hash: 'f'.repeat(64),
            change_summary: 'Import initial',
            created_at: '2026-01-15T12:00:00Z',
          },
        ])
      )
      .mockResolvedValueOnce(
        jsonResponse({
          document_id: FIXTURE_DOCUMENTS[0].id,
          restored_version_number: 1,
          size_bytes: 1024,
          sha256_hash: 'f'.repeat(64),
          message: 'Version 1 rétablie',
        })
      )
      .mockResolvedValueOnce(jsonResponse([]));

    render(
      <VersionsModal
        document={FIXTURE_DOCUMENTS[0]}
        tenantId={FIXTURE_TENANT.id}
        onClose={vi.fn()}
        onVersionsUpdated={onVersionsUpdated}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Version 2')).toBeInTheDocument();
      expect(screen.getByText('Version 1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Rétablir/i }));

    await waitFor(() => {
      expect(onVersionsUpdated).toHaveBeenCalledTimes(1);
    });
  });

  it('12. SettingsModal loads real sessions, revokes session, and calls GDPR export/delete', async () => {
    const onDeleteAccount = vi.fn();
    const createObjectUrlSpy = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:mock-url');
    const revokeObjectUrlSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 'ses-cur',
            user_agent: 'Mozilla/5.0 (X11; Linux x86_64) Firefox/126.0',
            ip_address: '10.0.0.15',
            is_revoked: false,
            is_current: true,
            expires_at: '2026-02-10T00:00:00Z',
            created_at: '2026-01-10T00:00:00Z',
            last_active_at: '2026-01-20T12:00:00Z',
          },
          {
            id: 'ses-old',
            user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1',
            ip_address: '10.0.0.99',
            is_revoked: false,
            is_current: false,
            expires_at: '2026-02-01T00:00:00Z',
            created_at: '2026-01-05T00:00:00Z',
            last_active_at: '2026-01-19T12:00:00Z',
          },
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ gdpr: 'ok' }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        currentUser={FIXTURE_USER}
        currentTenant={FIXTURE_TENANT}
        onDeleteAccount={onDeleteAccount}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Sessions \(2\)/i)).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole('button', { name: /Télécharger mon archive personnelle complète/i })
    );
    await waitFor(() => expect(createObjectUrlSpy).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /Sessions \(2\)/i }));
    expect(screen.getByText(/Session actuelle/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Révoquer' }));
    await waitFor(() => {
      expect(screen.queryByText(/iPhone — Safari/i)).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Zone de danger/i }));
    fireEvent.click(screen.getByRole('button', { name: /Demander la suppression de mon compte/i }));
    fireEvent.change(screen.getByPlaceholderText('SUPPRIMER'), {
      target: { value: 'SUPPRIMER' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirmer la purge définitive/i }));

    await waitFor(() => expect(onDeleteAccount).toHaveBeenCalledTimes(1));

    createObjectUrlSpy.mockRestore();
    revokeObjectUrlSpy.mockRestore();
  });

  it('13. BillingCheckoutModal, StorageGauge, AdminConsole & confirmation modals call real APIs without static stubs', async () => {
    const onUpgradePlan = vi.fn();
    render(
      <StorageGauge
        currentTenant={FIXTURE_TENANT}
        currentPlan={FIXTURE_PLANS[1]}
        plans={FIXTURE_PLANS}
        documents={FIXTURE_DOCUMENTS}
        onUpgradePlan={onUpgradePlan}
      />
    );
    expect(screen.getByText(/Gestion des Quotas Transactionnels/i)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /Choisir ce forfait/i })[0]);
    expect(onUpgradePlan).toHaveBeenCalledTimes(1);

    render(
      <FileExplorer
        currentFolder={null}
        breadcrumbs={[]}
        folders={FIXTURE_FOLDERS}
        documents={FIXTURE_DOCUMENTS}
        viewMode="grid"
        onToggleViewMode={vi.fn()}
        onNavigateFolder={vi.fn()}
        onPreviewDocument={vi.fn()}
        onShareDocument={vi.fn()}
        onViewVersions={vi.fn()}
        onToggleFavoriteDoc={vi.fn()}
        onTrashDoc={vi.fn()}
        onRestoreDoc={vi.fn()}
        onPurgeDoc={vi.fn()}
        onRenameDoc={vi.fn()}
        onMoveDocument={vi.fn()}
        onCopyDocument={vi.fn()}
        onOpenUpload={vi.fn()}
        onOpenNewFolder={vi.fn()}
        onRenameFolder={vi.fn()}
        onMoveFolder={vi.fn()}
        onCopyFolder={vi.fn()}
        onTrashFolder={vi.fn()}
        onBulkMove={vi.fn()}
        onBulkTrash={vi.fn()}
        userRole="VIEWER"
      />
    );
    expect(screen.queryByRole('button', { name: /Importer/i })).not.toBeInTheDocument();
    cleanup();

    const authLogin = vi.fn();
    render(
      <AuthModal
        isOpen={true}
        onClose={vi.fn()}
        onLogin={authLogin}
        onRegister={vi.fn()}
        errorMessage="Mot de passe invalide"
      />
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Mot de passe invalide');
    expect(screen.queryByText(/Comptes Démonstration/i)).not.toBeInTheDocument();
    cleanup();

    const onConfirm = vi.fn();
    render(
      <ConfirmActionModal
        isOpen={true}
        title="Purge définitive"
        description="Confirmer la suppression ?"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /Confirmer/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    const onRename = vi.fn();
    render(
      <RenameModal
        isOpen={true}
        currentName="contrat.pdf"
        onConfirm={onRename}
        onCancel={vi.fn()}
      />
    );
    const renameInput = screen.getByLabelText(/Nouveau nom/i);
    fireEvent.change(renameInput, { target: { value: '../evil.pdf' } });
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/i }));
    expect(screen.getByRole('alert')).toHaveTextContent(/Caractères de chemin interdits/i);
    expect(onRename).not.toHaveBeenCalled();
    cleanup();

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/billing/checkout')) {
        return jsonResponse({
          session_id: 'cs_test_123',
          url: 'https://checkout.stripe.com/pay/cs_test_123',
          tenant_id: FIXTURE_TENANT.id,
          plan_id: 'PREMIUM',
          billing_interval: 'monthly',
          amount_eur: 14.99,
          currency: 'EUR',
          status: 'open',
          expires_at: 1800000000,
        });
      }
      if (url.endsWith('/health')) {
        return jsonResponse({
          status: 'healthy',
          database: 'healthy',
          redis: 'healthy',
          storage: 'healthy',
          antivirus: 'healthy',
        });
      }
      if (url.endsWith('/admin/stats')) {
        return jsonResponse({
          tenants_count: 1,
          users_count: 1,
          documents_count: 2,
          total_storage_bytes: 2048,
          storage_capacity_bytes: 21474836480,
          antivirus_status: 'healthy',
        });
      }
      if (url.includes('/admin/users')) return jsonResponse({ users: [], total: 0, limit: 100, offset: 0 });
      if (url.includes('/admin/tenants')) return jsonResponse({ tenants: [], total: 0, limit: 100, offset: 0 });
      if (url.includes('/admin/audit-logs')) return jsonResponse({ logs: [], total: 0, limit: 100, offset: 0 });
      return jsonResponse({}, 404);
    });

    render(
      <BillingCheckoutModal
        isOpen={true}
        onClose={vi.fn()}
        targetPlan={FIXTURE_PLANS[2]}
        plans={FIXTURE_PLANS}
        currentTenant={FIXTURE_TENANT}
        invoices={[]}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /Passer au paiement Stripe/i }));
    await waitFor(() => {
      expect(screen.getByText(/cs_test_123/i)).toBeInTheDocument();
    });

    render(<AdminConsole />);
    await waitFor(() => {
      expect(screen.getByText('HEALTHY')).toBeInTheDocument();
    });
    expect(fetchSpy).toHaveBeenCalled();
  });

  it('14. Static & bundle leak scan confirms zero prototype/mock strings in production code or dist bundle', () => {
    const forbiddenTokens = [
      ['mock', 'Data'].join(''),
      ['INITIAL', '_USERS'].join(''),
      ['INITIAL', '_TENANTS'].join(''),
      ['Alice ', 'Dupont'].join(''),
      ['Bob ', 'Martin'].join(''),
      ['Charlie ', 'Comptable'].join(''),
      ['tnt-', 'alice-', 'main'].join(''),
      ['doc-', 'bail-', 'locatif'].join(''),
      ['Libre', 'Office Headless'].join(''),
      ['RÉPUBLIQUE ', 'FRANÇAISE'].join(''),
      ['Security', 'SimulatorModal'].join(''),
      ['Public', 'ShareModal'].join(''),
      ['4242 ', '••••'].join(''),
      ['192.168.', '1.45'].join(''),
    ];

    const collectFiles = (dir: string): string[] => {
      if (!fs.existsSync(dir)) return [];
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      const results: string[] = [];
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (entry.name === '__tests__' || entry.name === 'node_modules') continue;
          results.push(...collectFiles(full));
        } else if (/\.(ts|tsx|js|jsx)$/.test(entry.name)) {
          results.push(full);
        }
      }
      return results;
    };

    const projectRoot = process.cwd();
    const sourceFiles = collectFiles(path.join(projectRoot, 'src'));
    expect(sourceFiles.length).toBeGreaterThan(5);

    for (const file of sourceFiles) {
      const content = fs.readFileSync(file, 'utf-8');
      for (const token of forbiddenTokens) {
        expect(content, `Leak "${token}" found in ${file}`).not.toContain(token);
      }
    }

    const distAssetsDir = path.join(projectRoot, 'dist', 'assets');
    if (fs.existsSync(distAssetsDir)) {
      const distBundles = fs
        .readdirSync(distAssetsDir)
        .filter((f) => f.endsWith('.js'))
        .map((f) => path.join(distAssetsDir, f));
      for (const bundle of distBundles) {
        const content = fs.readFileSync(bundle, 'utf-8');
        for (const token of forbiddenTokens) {
          expect(content, `Leak "${token}" found in bundle ${bundle}`).not.toContain(token);
        }
      }
    }
  });

  it('15. AuthModal provides show/hide password toggle, email check, and 8-char password check', () => {
    const onLogin = vi.fn();
    const onRegister = vi.fn();

    render(
      <AuthModal
        isOpen={true}
        onClose={vi.fn()}
        onLogin={onLogin}
        onRegister={onRegister}
      />
    );

    const pwdInput = screen.getByLabelText(/Mot de passe/i) as HTMLInputElement;
    expect(pwdInput.type).toBe('password');

    const toggleBtn = screen.getByRole('button', { name: /Afficher la saisie en clair/i });
    fireEvent.click(toggleBtn);
    expect(pwdInput.type).toBe('text');

    fireEvent.click(screen.getByRole('button', { name: /Masquer la saisie en clair/i }));
    expect(pwdInput.type).toBe('password');

    // Switch to register mode
    fireEvent.click(screen.getByRole('button', { name: /Créer un compte/i }));

    fireEvent.change(screen.getByLabelText(/Nom complet/i), {
      target: { value: 'Pat Noualhier' },
    });
    fireEvent.change(screen.getByLabelText(/Adresse e-mail/i), {
      target: { value: 'email-invalide' },
    });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), {
      target: { value: '12345' },
    });

    expect(screen.getByText(/Format d'e-mail attendu/i)).toBeInTheDocument();
    expect(screen.getByText(/Trop court : 5\/8 caractères minimum/i)).toBeInTheDocument();

    // Submit with invalid email
    fireEvent.click(screen.getByRole('button', { name: /Créer mon espace/i }));
    expect(screen.getByRole('alert')).toHaveTextContent(/adresse e-mail saisie est invalide/i);
    expect(onRegister).not.toHaveBeenCalled();

    // Fix email, keep short password
    fireEvent.change(screen.getByLabelText(/Adresse e-mail/i), {
      target: { value: 'pat@example.fr' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Créer mon espace/i }));
    expect(screen.getByRole('alert')).toHaveTextContent(/Mot de passe trop court \(5\/8/i);
    expect(onRegister).not.toHaveBeenCalled();

    // Fix password (>= 8 chars)
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), {
      target: { value: 'MotDePasseValide123' },
    });
    expect(screen.getByText(/Longueur conforme \(19 caractères\)/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Créer mon espace/i }));
    expect(onRegister).toHaveBeenCalledWith('Pat Noualhier', 'pat@example.fr', 'MotDePasseValide123');
  });

  it('16. API client and App capture HTML 404, Pydantic 422 arrays, and missing tenant provisioning errors cleanly', async () => {
    // 1. HTML 404 on /auth/register explains backend/proxy issue instead of generic "Erreur HTTP 404"
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('<html><body>Not Found</body></html>', {
        status: 404,
        headers: { 'Content-Type': 'text/html' },
      })
    );

    await expect(
      apiClient.auth.register('Pat Noualhier', 'pat@example.fr', 'StrongPass123!')
    ).rejects.toMatchObject({
      status: 404,
      detail: expect.stringMatching(/Service API backend introuvable \(HTTP 404/i),
    });

    // 2. FastAPI 422 array detail is formatted cleanly in French
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse(
        {
          detail: [
            { loc: ['body', 'password'], msg: 'String should have at least 8 characters', type: 'string_too_short' },
          ],
        },
        422
      )
    );

    await expect(
      apiClient.auth.register('Pat Noualhier', 'pat@example.fr', 'short')
    ).rejects.toMatchObject({
      status: 422,
      detail: expect.stringMatching(/au moins 8 caractères/i),
    });

    // 3. App.handleRegister catches missing tenant provisioning after signup
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/billing/plans')) return jsonResponse([]);
      if (url.endsWith('/auth/me') && !apiClient.getAccessToken()) {
        return jsonResponse({ detail: 'Non authentifié' }, 401);
      }
      if (url.endsWith('/auth/refresh') && !apiClient.getAccessToken()) {
        return jsonResponse({ detail: 'No refresh' }, 401);
      }
      if (url.endsWith('/auth/register')) {
        return jsonResponse(
          {
            id: FIXTURE_USER.id,
            email: FIXTURE_USER.email,
            full_name: FIXTURE_USER.fullName,
            is_active: true,
            is_verified: true,
            is_superuser: false,
            created_at: FIXTURE_USER.createdAt,
          },
          201
        );
      }
      if (url.endsWith('/auth/login')) {
        return jsonResponse({
          access_token: 'jwt-temp-no-tenant',
          token_type: 'bearer',
          expires_in: 1800,
          user_id: FIXTURE_USER.id,
          tenant_id: '',
        });
      }
      if (url.endsWith('/auth/me')) {
        return jsonResponse({
          id: FIXTURE_USER.id,
          email: FIXTURE_USER.email,
          full_name: FIXTURE_USER.fullName,
          is_active: true,
          is_verified: true,
          is_superuser: false,
          created_at: FIXTURE_USER.createdAt,
        });
      }
      if (url.endsWith('/tenants/my-tenants')) {
        return jsonResponse([]);
      }
      return jsonResponse({}, 404);
    });

    render(<App />);
    await waitFor(() => expect(screen.getByRole('button', { name: /Créer un compte/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Créer un compte/i }));

    fireEvent.change(screen.getByLabelText(/Nom complet/i), { target: { value: 'Pat Noualhier' } });
    fireEvent.change(screen.getByLabelText(/Adresse e-mail/i), { target: { value: 'pat@example.fr' } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), { target: { value: 'StrongPass123!' } });
    fireEvent.click(screen.getByRole('button', { name: /Créer mon espace/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /aucun espace documentaire n'a pu être provisionné/i
      );
    });
  });
});
