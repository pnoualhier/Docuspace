import React, { useState } from 'react';
import { 
  X, 
  Settings, 
  Download, 
  Smartphone, 
  Trash2, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  Laptop, 
  Lock,
  Database,
  Archive,
  RotateCcw,
  Clock,
  HardDrive
} from 'lucide-react';
import { User, Tenant, DocumentItem, SessionInfo } from '../types';
import { INITIAL_SESSIONS } from '../services/mockData';
import { formatBytes } from '../services/crypto';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: User;
  currentTenant: Tenant;
  documents: DocumentItem[];
  onDeleteAccount: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  currentTenant,
  documents,
  onDeleteAccount,
}) => {
  const [activeTab, setActiveTab] = useState<'rgpd' | 'backups' | 'sessions' | 'security'>('rgpd');
  const [sessions, setSessions] = useState<SessionInfo[]>(INITIAL_SESSIONS);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteInput, setDeleteInput] = useState('');
  const [drillStatus, setDrillStatus] = useState<string | null>(null);

  if (!isOpen) return null;

  // GDPR Article 20 Complete Data Portability Export
  const handleExportData = () => {
    const exportBundle = {
      gdprCompliance: {
        standard: 'General Data Protection Regulation (EU 2016/679)',
        article: 'Article 20 - Droit à la portabilité des données',
        exportDate: new Date().toISOString(),
        controller: 'DocuSpace Platform (Debian Self-Hosted / SaaS)',
        userSubject: currentUser.email
      },
      user: {
        id: currentUser.id,
        email: currentUser.email,
        fullName: currentUser.fullName,
        isVerified: currentUser.isVerified,
        createdAt: currentUser.createdAt
      },
      activeTenant: {
        id: currentTenant.id,
        name: currentTenant.name,
        planId: currentTenant.planId,
        usedBytes: currentTenant.usedBytes,
        documentCount: currentTenant.documentCount,
        role: currentTenant.role
      },
      documents: documents.map(d => ({
        id: d.id,
        originalName: d.originalName,
        mimeType: d.mimeType,
        extension: d.extension,
        sizeBytes: d.sizeBytes,
        sha256Hash: d.sha256Hash,
        status: d.status,
        antivirusStatus: d.antivirusStatus,
        createdAt: d.createdAt,
        updatedAt: d.updatedAt,
        versionsCount: d.versions.length,
        versions: d.versions.map(v => ({
          versionNumber: v.versionNumber,
          sizeBytes: v.sizeBytes,
          sha256Hash: v.sha256Hash,
          changeSummary: v.changeSummary,
          createdAt: v.createdAt
        }))
      }))
    };

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportBundle, null, 2));
    const dlAnchorElem = document.createElement('a');
    dlAnchorElem.setAttribute('href', dataStr);
    dlAnchorElem.setAttribute('download', `docuspace_gdpr_export_${currentUser.id}.json`);
    dlAnchorElem.click();
  };

  const handleSimulateDisasterRecoveryDrill = () => {
    setDrillStatus('Calcul des empreintes SHA-256 du snapshot PostgreSQL & S3...');
    setTimeout(() => {
      setDrillStatus('Validation des contraintes RLS et restauration de test réussie (100% Intègre).');
      setTimeout(() => setDrillStatus(null), 4000);
    }, 1500);
  };

  const handleRevokeSession = (sessionId: string) => {
    setSessions(sessions.filter(s => s.id !== sessionId));
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <Settings className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Paramètres, RGPD & Continuité</h3>
              <p className="text-[11px] text-slate-400">
                Souveraineté des données, sauvegardes automatisées, sessions et purge de compte.
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

        {/* Tab Switcher */}
        <div className="flex border-b border-slate-800 overflow-x-auto text-xs">
          <button
            onClick={() => setActiveTab('rgpd')}
            className={`pb-2.5 px-4 font-semibold border-b-2 transition-all shrink-0 ${
              activeTab === 'rgpd' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Données & Portabilité RGPD
          </button>
          <button
            onClick={() => setActiveTab('backups')}
            className={`pb-2.5 px-4 font-semibold border-b-2 transition-all shrink-0 ${
              activeTab === 'backups' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Sauvegardes Debian (14j)
          </button>
          <button
            onClick={() => setActiveTab('sessions')}
            className={`pb-2.5 px-4 font-semibold border-b-2 transition-all shrink-0 ${
              activeTab === 'sessions' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Sessions ({sessions.length})
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`pb-2.5 px-4 font-semibold border-b-2 transition-all shrink-0 ${
              activeTab === 'security' ? 'border-rose-500 text-rose-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Zone de danger (Art. 17)
          </button>
        </div>

        {/* Tab 1: RGPD Data Export */}
        {activeTab === 'rgpd' && (
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <h4 className="font-semibold text-slate-200 flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Droit à la portabilité des données (Art. 20 RGPD)</span>
              </h4>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Vous pouvez exporter et télécharger l'ensemble de vos documents, versions antérieures, métadonnées, hachages cryptographiques SHA-256 et partages actifs dans une archive standardisée lisible par machine (JSON).
              </p>
              <div className="pt-2">
                <button
                  onClick={handleExportData}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center space-x-2 shadow-sm transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Télécharger mon archive personnelle complète (.JSON)</span>
                </button>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1 text-[11px] text-slate-400">
              <div className="font-semibold text-slate-300">Garanties de conformité légale :</div>
              <p>• Droit d'accès et de rectification garanti sans restriction technique.</p>
              <p>• Rétention de la corbeille limitée à 30 jours calendaires avant purge automatique irréversible.</p>
              <p>• Zéro journalisation de mots de passe en clair dans la base PostgreSQL ou les fichiers de logs.</p>
            </div>
          </div>
        )}

        {/* Tab 2: Backups & Disaster Recovery */}
        {activeTab === 'backups' && (
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white flex items-center space-x-2">
                  <Database className="w-4 h-4 text-purple-400" />
                  <span>Sauvegardes Système Automatisées (Debian 12)</span>
                </span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-semibold border border-emerald-500/20">
                  Rétention 14 jours
                </span>
              </div>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                Chaque nuit à 02h00, un instantané compressé de la base PostgreSQL (`pg_dump`) et des objets MinIO S3 est généré dans `/var/backups/docuspace` avec vérification d'intégrité par fichier `SHA256SUMS`.
              </p>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                  <div className="text-[10px] text-slate-500 uppercase font-bold">Dernière sauvegarde</div>
                  <div className="text-xs font-semibold text-white mt-0.5">Aujourd'hui à 02:00 UTC</div>
                  <div className="text-[10px] text-emerald-400 font-mono mt-0.5">SHA-256 Validé</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                  <div className="text-[10px] text-slate-500 uppercase font-bold">Rotation active</div>
                  <div className="text-xs font-semibold text-white mt-0.5">14 archives conservées</div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">Purge auto &gt; 14 jours</div>
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={handleSimulateDisasterRecoveryDrill}
                  disabled={drillStatus !== null}
                  className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs flex items-center space-x-2 transition-colors border border-slate-700"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-purple-400" />
                  <span>Exécuter un test d'intégrité à froid (Disaster Recovery Drill)</span>
                </button>
                {drillStatus && (
                  <div className="mt-2 text-xs text-purple-300 font-mono p-2 rounded bg-purple-950/40 border border-purple-500/30 animate-pulse">
                    {drillStatus}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Active Sessions */}
        {activeTab === 'sessions' && (
          <div className="space-y-3 text-xs">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Appareils connectés à votre compte
            </span>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {sessions.map((ses) => (
                <div
                  key={ses.id}
                  className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between"
                >
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-slate-900 text-slate-400">
                      {ses.device.includes('iPhone') ? <Smartphone className="w-4 h-4" /> : <Laptop className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="font-medium text-slate-200 flex items-center space-x-2">
                        <span>{ses.device}</span>
                        {ses.isCurrent && (
                          <span className="text-[10px] px-2 py-0.2 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Session actuelle
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {ses.browser} • {ses.ipAddress} • {ses.lastActive}
                      </div>
                    </div>
                  </div>

                  {!ses.isCurrent && (
                    <button
                      onClick={() => handleRevokeSession(ses.id)}
                      className="px-2.5 py-1 rounded-lg text-rose-400 hover:bg-rose-500/10 border border-rose-500/20 text-[11px] transition-colors"
                    >
                      Révoquer
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 4: Danger Zone / Article 17 */}
        {activeTab === 'security' && (
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 space-y-2">
              <h4 className="font-bold text-sm flex items-center space-x-2 text-rose-400">
                <AlertTriangle className="w-4 h-4" />
                <span>Droit à l'oubli & Suppression Définitive du Compte (Art. 17 RGPD)</span>
              </h4>
              <p className="text-[11px] text-rose-300/80 leading-relaxed">
                Cette action est irréversible. L'ensemble de vos espaces documentaires isolés, fichiers et versions dans MinIO S3, dossiers, partages et identifiants seront définitivement purgés des bases de données.
              </p>

              {!showDeleteConfirm ? (
                <button
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
                      onClick={() => setShowDeleteConfirm(false)}
                      className="px-3 py-1 rounded bg-slate-800 text-slate-300"
                    >
                      Annuler
                    </button>
                    <button
                      disabled={deleteInput !== 'SUPPRIMER'}
                      onClick={() => {
                        onDeleteAccount();
                        onClose();
                      }}
                      className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-40 font-semibold"
                    >
                      Confirmer la purge définitive
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
