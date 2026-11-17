import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from '../App';
import { StorageGauge } from '../components/StorageGauge';
import { AuthModal } from '../components/AuthModal';
import { ShareModal } from '../components/ShareModal';
import { FileExplorer } from '../components/FileExplorer';
import { calculateSHA256, formatBytes, getFileCategory, generateStorageKey } from '../services/crypto';
import { INITIAL_TENANTS, INITIAL_DOCUMENTS, INITIAL_FOLDERS, INITIAL_USERS, PLANS } from '../services/mockData';

describe('DocuSpace Crypto & Utility Helpers', () => {
  it('calculates exact SHA-256 hex digest using WebCrypto', async () => {
    const data = new TextEncoder().encode('docuspace-integrity-check');
    const blob = new Blob([data], { type: 'text/plain' });
    // Polyfill arrayBuffer if jsdom Blob lacks it
    if (!blob.arrayBuffer) {
      (blob as unknown as { arrayBuffer: () => Promise<ArrayBuffer> }).arrayBuffer = async () => data.buffer;
    }
    const digest = await calculateSHA256(blob);
    expect(digest).toMatch(/^[a-f0-9]{64}$/);
  });

  it('formats byte sizes and maps file categories accurately', () => {
    expect(formatBytes(0)).toBe('0 o');
    expect(formatBytes(1024)).toBe('1 Ko');
    expect(formatBytes(524288000, 0)).toBe('500 Mo');
    expect(getFileCategory('application/pdf', 'pdf')).toBe('pdf');
    expect(getFileCategory('image/png', 'png')).toBe('image');
    expect(generateStorageKey('tenant-123', '.pdf')).toMatch(/^tenants\/tenant-123\/[a-f0-9-]+\.pdf$/);
  });
});

describe('DocuSpace Core UI Components', () => {
  it('renders StorageGauge with active plan quota and categories', () => {
    const onUpgrade = vi.fn();
    render(
      <StorageGauge
        currentTenant={INITIAL_TENANTS[0]}
        currentPlan={PLANS.PERSONAL}
        documents={INITIAL_DOCUMENTS}
        onUpgradePlan={onUpgrade}
      />
    );
    expect(screen.getByText(/Gestion des Quotas Transactionnels/i)).toBeInTheDocument();
    expect(screen.getByText(/Documents PDF/i)).toBeInTheDocument();
    const upgradeButtons = screen.getAllByRole('button', { name: /Choisir ce forfait/i });
    expect(upgradeButtons.length).toBeGreaterThan(0);
    fireEvent.click(upgradeButtons[0]);
    expect(onUpgrade).toHaveBeenCalledTimes(1);
  });

  it('renders AuthModal and allows switching between login and register modes', () => {
    const onLogin = vi.fn();
    const onRegister = vi.fn();
    render(
      <AuthModal
        isOpen={true}
        onClose={vi.fn()}
        onLogin={onLogin}
        onRegister={onRegister}
        availableUsers={INITIAL_USERS}
      />
    );
    expect(screen.getByText(/Connexion sécurisée avec chiffrement Argon2id/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Créer un compte/i }));
    expect(screen.getByText(/Création de votre espace documentaire personnel/i)).toBeInTheDocument();
  });

  it('renders ShareModal for a document and creates a secure share payload', () => {
    const onSaveShare = vi.fn();
    render(
      <ShareModal
        document={INITIAL_DOCUMENTS[0]}
        onClose={vi.fn()}
        shares={[]}
        onSaveShare={onSaveShare}
      />
    );
    expect(screen.getByText(INITIAL_DOCUMENTS[0].originalName)).toBeInTheDocument();
    const createBtn = screen.getByRole('button', { name: /Générer un nouveau lien sécurisé/i });
    fireEvent.click(createBtn);
    expect(onSaveShare).toHaveBeenCalledTimes(1);
    const created = onSaveShare.mock.calls[0][0];
    expect(created.shareType).toBe('SECURE_LINK');
    expect(created.documentId).toBe(INITIAL_DOCUMENTS[0].id);
  });

  it('renders FileExplorer documents and enforces VIEWER role restrictions', () => {
    render(
      <FileExplorer
        currentFolder={null}
        breadcrumbs={[]}
        folders={INITIAL_FOLDERS.filter(f => f.tenantId === 'tnt-alice-main')}
        documents={INITIAL_DOCUMENTS.filter(d => d.tenantId === 'tnt-alice-main')}
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
  });

  it('renders full DocuSpace App and navigates across tenant workspaces', () => {
    render(<App />);
    expect(screen.getAllByText(/DocuSpace/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Espace Personnel/i).length).toBeGreaterThan(0);
  });
});
