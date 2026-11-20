import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  Settings,
  Download,
  Smartphone,
  ShieldCheck,
  AlertTriangle,
  Laptop,
  Loader2,
  LogOut,
} from 'lucide-react';
import { User, Tenant, SessionInfo } from '../types';
import { apiClient, ApiError } from '../services/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: User;
  currentTenant: Tenant;
  onDeleteAccount: () => Promise<void> | void;
  onAllSessionsRevoked?: () => void;
}

const parseUserAgent = (ua: string | null): { device: string; browser: string; isMobile: boolean } => {
  if (!ua) {
    return { device: 'Appareil inconnu', browser: 'Navigateur inconnu', isMobile: false };
  }
  const isMobile = /iPhone|Android|Mobile|iPad/i.test(ua);
  const device = /iPhone/i.test(ua)
    ? 'iPhone'
    : /iPad/i.test(ua)
      ? 'iPad'
      : /Android/i.test(ua)
        ? 'Android'
        : /Mac OS X|Macintosh/i.test(ua)
          ? 'macOS'
          : /Windows/i.test(ua)
            ? 'Windows'
            : /Linux/i.test(ua)
              ? 'Linux'
              : 'Poste de travail';
  const browser = /Firefox/i.test(ua)
    ? 'Firefox'
    : /Edg\//i.test(ua)
      ? 'Edge'
      : /Chrome/i.test(ua)
        ? 'Chrome'
        : /Safari/i.test(ua)
          ? 'Safari'
          : 'Client HTTP';
  return { device, browser, isMobile };
};

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  onDeleteAccount,
  onAllSessionsRevoked,
}) => {
  const [activeTab, setActiveTab] = useState<'rgpd' | 'sessions' | 'security'>('rgpd');
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteInput, setDeleteInput] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    setErrorMsg(null);
    try {
      const apiSessions = await apiClient.auth.sessions();
      setSessions(
        apiSessions.map((s) => ({
          id: s.id,
          userAgent: s.user_agent,
          ipAddress: s.ip_address,
          isRevoked: s.is_revoked,
          isCurrent: s.is_current,
          expiresAt: s.expires_at,
          createdAt: s.created_at,
          lastActiveAt: s.last_active_at,
        }))
      );
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : 'Impossible de charger les sessions actives.'
      );
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      void loadSessions();
    }
  }, [isOpen, loadSessions]);

  if (!isOpen) return null;

  const handleExportData = async () => {
    setIsExporting(true);
    setErrorMsg(null);
    try {
      const blob = await apiClient.gdpr.exportData();
      const url = URL.createObjectURL(blob);
      const dlAnchorElem = window.document.createElement('a');
      dlAnchorElem.href = url;
      dlAnchorElem.download = `docuspace_gdpr_export_${currentUser.id}.json`;
      dlAnchorElem.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : "Erreur lors de l'export RGPD côté serveur."
      );
    } finally {
      setIsExporting(false);
    }
  };

  const handleRevokeSession = async (sessionId: string) => {
    setErrorMsg(null);
    try {
      await apiClient.auth.revokeSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : 'Impossible de révoquer cette session.'
      );
    }
  };

  const handleRevokeAllSessions = async () => {
    setErrorMsg(null);
    try {
      await apiClient.auth.revokeAllSessions();
      setSessions([]);
      if (onAllSessionsRevoked) {
        onAllSessionsRevoked();
      }
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : 'Impossible de révoquer toutes les sessions.'
      );
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <Settings className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Paramètres, RGPD & Sessions</h3>
              <p className="text-[11px] text-slate-400">
                Souveraineté des données, révocation de sessions et suppression du compte.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer les paramètres"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-slate-800 overflow-x-auto text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('rgpd')}
            className={`pb-2.5 px-4 font-semibold border-b-2 transition-all shrink-0 ${
              activeTab === 'rgpd'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Données & Portabilité RGPD
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('sessions')}
            className={`pb-2.5 px-4 font-semibold border-b-2 transition-all shrink-0 ${
              activeTab === 'sessions'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Sessions ({sessions.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('security')}
            className={`pb-2.5 px-4 font-semibold border-b-2 transition-all shrink-0 ${
              activeTab === 'security'
                ? 'border-rose-500 text-rose-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Zone de danger (Art. 17)
          </button>
        </div>

        {errorMsg && (
          <div role="alert" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Tab 1: RGPD Data Export */}
        {activeTab === 'rgpd' && (
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <h4 className="font-semibold text-slate-200 flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Droit à la portabilité des données (Art. 20 RGPD)</span>
              </h4>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Téléchargez l'export complet généré par le serveur PostgreSQL contenant votre profil, vos espaces, documents, versions, partages et journaux d'audit.
              </p>
              <div className="pt-2">
                <button
                  type="button"
                  disabled={isExporting}
                  onClick={handleExportData}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-semibold text-xs flex items-center space-x-2 shadow-sm transition-colors"
                >
                  {isExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                  <span>
                    {isExporting
                      ? 'Génération de l’export...'
                      : 'Télécharger mon archive personnelle complète (.JSON)'}
                  </span>
                </button>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1 text-[11px] text-slate-400">
              <div className="font-semibold text-slate-300">Garanties de conformité :</div>
              <p>• Droit d'accès, de portabilité et d'effacement exécutés côté serveur.</p>
              <p>• Rétention de la corbeille limitée à 30 jours avant purge.</p>
              <p>• Hachage Argon2id des mots de passe et empreintes SHA-256 des jetons.</p>
            </div>
          </div>
        )}

        {/* Tab 2: Active Sessions */}
        {activeTab === 'sessions' && (
          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Appareils connectés à votre compte
              </span>
              {sessions.length > 0 && (
                <button
                  type="button"
                  onClick={handleRevokeAllSessions}
                  className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/20 text-[11px] flex items-center space-x-1 transition-colors"
                >
                  <LogOut className="w-3 h-3" />
                  <span>Révoquer toutes les sessions</span>
                </button>
              )}
            </div>

            {isLoadingSessions ? (
              <div className="py-8 text-center text-slate-400 flex items-center justify-center space-x-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                <span>Chargement des sessions...</span>
              </div>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {sessions.map((ses) => {
                  const ua = parseUserAgent(ses.userAgent);
                  return (
                    <div
                      key={ses.id}
                      className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between"
                    >
                      <div className="flex items-center space-x-3">
                        <div className="p-2 rounded-lg bg-slate-900 text-slate-400">
                          {ua.isMobile ? <Smartphone className="w-4 h-4" /> : <Laptop className="w-4 h-4" />}
                        </div>
                        <div>
                          <div className="font-medium text-slate-200 flex items-center space-x-2">
                            <span>
                              {ua.device} — {ua.browser}
                            </span>
                            {ses.isCurrent && (
                              <span className="text-[10px] px-2 py-0.2 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                Session actuelle
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">
                            IP : {ses.ipAddress || 'Inconnue'} • Dernière activité :{' '}
                            {new Date(ses.lastActiveAt).toLocaleString('fr-FR')}
                          </div>
                        </div>
                      </div>

                      {!ses.isCurrent && (
                        <button
                          type="button"
                          onClick={() => handleRevokeSession(ses.id)}
                          className="px-2.5 py-1 rounded-lg text-rose-400 hover:bg-rose-500/10 border border-rose-500/20 text-[11px] transition-colors"
                        >
                          Révoquer
                        </button>
                      )}
                    </div>
                  );
                })}
                {sessions.length === 0 && (
                  <div className="py-6 text-center text-slate-500 border border-dashed border-slate-800 rounded-xl">
                    Aucune session active trouvée.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Danger Zone / Article 17 */}
        {activeTab === 'security' && (
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 space-y-2">
              <h4 className="font-bold text-sm flex items-center space-x-2 text-rose-400">
                <AlertTriangle className="w-4 h-4" />
                <span>Droit à l'oubli & Suppression Définitive du Compte (Art. 17 RGPD)</span>
              </h4>
              <p className="text-[11px] text-rose-300/80 leading-relaxed">
                Cette action est irréversible. L'ensemble de vos espaces documentaires isolés, fichiers et versions dans MinIO S3, dossiers, partages et identifiants seront définitivement purgés.
              </p>

              {!showDeleteConfirm ? (
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="mt-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs transition-colors"
                >
                  Demander la suppression de mon compte
                </button>
              ) : (
                <div className="p-3 rounded-lg bg-slate-950 border border-rose-500/30 space-y-2 mt-2">
                  <p className="text-[11px] text-slate-300">
                    Veuillez taper <strong className="text-white">SUPPRIMER</strong> pour confirmer la suppression définitive :
                  </p>
                  <input
                    type="text"
                    value={deleteInput}
                    onChange={(e) => setDeleteInput(e.target.value)}
                    placeholder="SUPPRIMER"
                    className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-rose-500"
                  />
                  <div className="flex justify-end space-x-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setShowDeleteConfirm(false)}
                      className="px-3 py-1 rounded bg-slate-800 text-slate-300"
                    >
                      Annuler
                    </button>
                    <button
                      type="button"
                      disabled={deleteInput !== 'SUPPRIMER' || isDeleting}
                      onClick={async () => {
                        setIsDeleting(true);
                        try {
                          await onDeleteAccount();
                          onClose();
                        } finally {
                          setIsDeleting(false);
                        }
                      }}
                      className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-40 font-semibold"
                    >
                      {isDeleting ? 'Suppression...' : 'Confirmer la purge définitive'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-slate-800">
          <button
            type="button"
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
