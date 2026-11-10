import React, { useState } from 'react';
import { 
  X, 
  Share2, 
  Link as LinkIcon, 
  Users, 
  Lock, 
  Calendar, 
  DownloadCloud, 
  Copy, 
  Check, 
  ShieldCheck, 
  AlertCircle,
  ExternalLink,
  Power,
  Trash2,
  KeyRound,
  CheckCircle2
} from 'lucide-react';
import { DocumentItem, UserRole, Share } from '../types';

interface ShareModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  shares?: Share[];
  onSaveShare?: (newShare: Share) => void;
  onToggleShare?: (shareId: string) => void;
  onRevokeShare?: (shareId: string) => void;
  onOpenPublicSimulator?: (share: Share) => void;
}

export const ShareModal: React.FC<ShareModalProps> = ({
  document,
  onClose,
  shares = [],
  onSaveShare,
  onToggleShare,
  onRevokeShare,
  onOpenPublicSimulator,
}) => {
  const [activeTab, setActiveTab] = useState<'link' | 'user'>('link');
  const [copiedToken, setCopiedToken] = useState<string | null>(null);
  const [requirePassword, setRequirePassword] = useState(false);
  const [password, setPassword] = useState('');
  const [expiryDays, setExpiryDays] = useState('7');
  const [maxDownloads, setMaxDownloads] = useState('');
  const [linkCreatedSuccess, setLinkCreatedSuccess] = useState(false);

  // User tab
  const [invitedEmail, setInvitedEmail] = useState('');
  const [invitedRole, setInvitedRole] = useState<UserRole>('VIEWER');

  if (!document) return null;

  // Filter existing shares for this document
  const docShares = shares.filter(s => s.documentId === document.id);

  const handleCopyLink = (token: string) => {
    const url = `https://docuspace.io/s/${token}`;
    navigator.clipboard.writeText(url);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  const handleCreateSecureLink = (e: React.FormEvent) => {
    e.preventDefault();
    const token = 'share_' + document.id.substring(4, 14) + '_' + Math.random().toString(36).substring(2, 8);
    
    let expiresAt: string | undefined = undefined;
    if (expiryDays !== 'never') {
      const d = new Date();
      d.setDate(d.getDate() + parseInt(expiryDays, 10));
      expiresAt = d.toISOString();
    }

    const newShare: Share = {
      id: `shr-${crypto.randomUUID()}`,
      tenantId: document.tenantId,
      documentId: document.id,
      documentName: document.originalName,
      createdBy: document.createdBy,
      shareType: 'SECURE_LINK',
      role: 'VIEWER',
      token: token,
      hasPassword: requirePassword,
      password: requirePassword ? password : undefined,
      maxDownloads: maxDownloads ? parseInt(maxDownloads, 10) : undefined,
      downloadCount: 0,
      expiresAt: expiresAt,
      isActive: true,
      createdAt: new Date().toISOString()
    };

    if (onSaveShare) {
      onSaveShare(newShare);
    }
    setLinkCreatedSuccess(true);
    setTimeout(() => setLinkCreatedSuccess(false), 3000);
    setPassword('');
    setRequirePassword(false);
    setMaxDownloads('');
  };

  const handleCreateInternalShare = (e: React.FormEvent) => {
    e.preventDefault();
    if (!invitedEmail.trim()) return;

    const newShare: Share = {
      id: `shr-${crypto.randomUUID()}`,
      tenantId: document.tenantId,
      documentId: document.id,
      documentName: document.originalName,
      createdBy: document.createdBy,
      shareType: 'INTERNAL_USER',
      role: invitedRole,
      recipientEmail: invitedEmail.trim().toLowerCase(),
      downloadCount: 0,
      isActive: true,
      createdAt: new Date().toISOString()
    };

    if (onSaveShare) {
      onSaveShare(newShare);
    }
    setInvitedEmail('');
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <Share2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Partage sécurisé</h3>
              <p className="text-[11px] text-slate-400 truncate max-w-[280px]">
                {document.originalName}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-slate-800">
          <button
            onClick={() => setActiveTab('link')}
            className={`pb-2.5 px-4 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
              activeTab === 'link'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <LinkIcon className="w-3.5 h-3.5" />
            <span>Lien sécurisé (Public / Token)</span>
          </button>
          <button
            onClick={() => setActiveTab('user')}
            className={`pb-2.5 px-4 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
              activeTab === 'user'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Utilisateurs DocuSpace</span>
          </button>
        </div>

        {/* Tab 1: Secure Public Link */}
        {activeTab === 'link' && (
          <div className="space-y-4">
            {/* Creator form */}
            <form onSubmit={handleCreateSecureLink} className="space-y-3">
              <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-3">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Paramètres de sécurité du nouveau lien
                </span>

                {/* Password Protection */}
                <div className="space-y-2">
                  <label className="flex items-center space-x-2 cursor-pointer text-xs">
                    <input
                      type="checkbox"
                      checked={requirePassword}
                      onChange={(e) => setRequirePassword(e.target.checked)}
                      className="rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0"
                    />
                    <span className="text-slate-200 font-medium">Protéger par mot de passe</span>
                  </label>
                  {requirePassword && (
                    <input
                      type="text"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Mot de passe d'accès (Argon2id)"
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono"
                    />
                  )}
                </div>

                {/* Expiry & Download Limit */}
                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">
                      Expiration
                    </label>
                    <select
                      value={expiryDays}
                      onChange={(e) => setExpiryDays(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none cursor-pointer"
                    >
                      <option value="1">1 jour</option>
                      <option value="7">7 jours</option>
                      <option value="30">30 jours</option>
                      <option value="never">Sans expiration</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">
                      Téléchargements max
                    </label>
                    <input
                      type="number"
                      min="1"
                      placeholder="Illimité"
                      value={maxDownloads}
                      onChange={(e) => setMaxDownloads(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-colors shadow-sm flex items-center justify-center space-x-1.5"
                >
                  <LinkIcon className="w-3.5 h-3.5" />
                  <span>Générer un nouveau lien sécurisé</span>
                </button>
              </div>
            </form>

            {linkCreatedSuccess && (
              <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center space-x-2 animate-in fade-in">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Nouveau lien de partage généré avec succès !</span>
              </div>
            )}

            {/* Active links list */}
            <div className="space-y-2 pt-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Liens actifs pour ce document ({docShares.filter(s => s.shareType === 'SECURE_LINK').length})
              </span>

              <div className="space-y-2 max-h-48 overflow-y-auto">
                {docShares.filter(s => s.shareType === 'SECURE_LINK').map((s) => {
                  const isCopied = copiedToken === s.token;
                  return (
                    <div
                      key={s.id}
                      className={`p-3 rounded-xl border transition-all text-xs space-y-2 ${
                        s.isActive
                          ? 'bg-slate-950 border-slate-800'
                          : 'bg-slate-950/40 border-slate-850 opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2 truncate">
                          <LinkIcon className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                          <span className="font-mono text-slate-300 truncate max-w-[200px]">
                            .../s/{s.token}
                          </span>
                        </div>

                        <div className="flex items-center space-x-1 shrink-0">
                          {s.token && (
                            <button
                              onClick={() => handleCopyLink(s.token!)}
                              className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
                              title="Copier le lien"
                            >
                              {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          )}
                          {onOpenPublicSimulator && (
                            <button
                              onClick={() => onOpenPublicSimulator(s)}
                              className="px-2 py-0.5 rounded bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 text-[10px] font-medium flex items-center space-x-1"
                              title="Simuler la vue du visiteur externe"
                            >
                              <ExternalLink className="w-3 h-3" />
                              <span>Tester</span>
                            </button>
                          )}
                          {onToggleShare && (
                            <button
                              onClick={() => onToggleShare(s.id)}
                              className={`p-1 rounded ${
                                s.isActive ? 'text-emerald-400 hover:text-rose-400' : 'text-slate-500 hover:text-emerald-400'
                              }`}
                              title={s.isActive ? 'Désactiver le lien' : 'Réactiver le lien'}
                            >
                              <Power className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {onRevokeShare && (
                            <button
                              onClick={() => onRevokeShare(s.id)}
                              className="p-1 rounded text-slate-500 hover:text-rose-400"
                              title="Supprimer définitivement"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Badges: password, expiry, download count */}
                      <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                        {s.hasPassword && (
                          <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 flex items-center space-x-1">
                            <Lock className="w-2.5 h-2.5" />
                            <span>Mot de passe requis</span>
                          </span>
                        )}
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                          {s.downloadCount} / {s.maxDownloads ? `${s.maxDownloads} téléch.` : 'Illimité'}
                        </span>
                        {s.expiresAt ? (
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                            Expire : {new Date(s.expiresAt).toLocaleDateString('fr-FR')}
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                            Permanent
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: User-to-User Sharing */}
        {activeTab === 'user' && (
          <div className="space-y-4">
            <form onSubmit={handleCreateInternalShare} className="flex gap-2">
              <input
                type="email"
                required
                value={invitedEmail}
                onChange={(e) => setInvitedEmail(e.target.value)}
                placeholder="adresse@exemple.fr"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <select
                value={invitedRole}
                onChange={(e) => setInvitedRole(e.target.value as UserRole)}
                className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none"
              >
                <option value="VIEWER">Lecteur</option>
                <option value="EDITOR">Éditeur</option>
                <option value="GUEST">Invité</option>
              </select>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-colors shrink-0"
              >
                Partager
              </button>
            </form>

            <div className="space-y-2 pt-2">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Utilisateurs ayant accès ({docShares.filter(s => s.shareType === 'INTERNAL_USER').length})
              </span>

              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {docShares.filter(s => s.shareType === 'INTERNAL_USER').map((s) => (
                  <div
                    key={s.id}
                    className="p-2.5 rounded-xl bg-slate-950 border border-slate-800/80 flex items-center justify-between text-xs"
                  >
                    <span className="text-slate-300 truncate max-w-[220px]">
                      {s.recipientEmail}
                    </span>
                    <div className="flex items-center space-x-2">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-semibold text-slate-400">
                        {s.role === 'VIEWER' ? 'Lecture seule' : s.role === 'EDITOR' ? 'Modification' : 'Invité'}
                      </span>
                      {onRevokeShare && (
                        <button
                          onClick={() => onRevokeShare(s.id)}
                          className="text-slate-500 hover:text-rose-400 p-1"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                {docShares.filter(s => s.shareType === 'INTERNAL_USER').length === 0 && (
                  <div className="text-center py-6 text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                    Aucun utilisateur direct invité pour ce document.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-between items-center pt-2 border-t border-slate-800">
          <div className="text-[11px] text-slate-500 flex items-center space-x-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Clé MinIO non exposée • Chiffrement de bout en bout</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs transition-colors"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
