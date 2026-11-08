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
  Lock 
} from 'lucide-react';
import { User, Tenant, DocumentItem, SessionInfo } from '../types';
import { INITIAL_SESSIONS } from '../services/mockData';

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
  const [activeTab, setActiveTab] = useState<'rgpd' | 'sessions' | 'security'>('rgpd');
  const [sessions, setSessions] = useState<SessionInfo[]>(INITIAL_SESSIONS);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteInput, setDeleteInput] = useState('');

  if (!isOpen) return null;

  const handleExportData = () => {
    const exportBundle = {
      exportDate: new Date().toISOString(),
      user: {
        id: currentUser.id,
        email: currentUser.email,
        fullName: currentUser.fullName,
        createdAt: currentUser.createdAt
      },
      activeTenant: {
        id: currentTenant.id,
        name: currentTenant.name,
        planId: currentTenant.planId,
        usedBytes: currentTenant.usedBytes,
      },
      documents: documents.map(d => ({
        id: d.id,
        originalName: d.originalName,
        mimeType: d.mimeType,
        sizeBytes: d.sizeBytes,
        sha256Hash: d.sha256Hash,
        createdAt: d.createdAt,
        updatedAt: d.updatedAt,
        status: d.status,
        antivirusStatus: d.antivirusStatus,
      }))
    };

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportBundle, null, 2));
    const dlAnchorElem = document.createElement('a');
    dlAnchorElem.setAttribute('href', dataStr);
    dlAnchorElem.setAttribute('download', `docuspace_export_${currentUser.id}.json`);
    dlAnchorElem.click();
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
              <h3 className="text-sm font-bold text-white">Paramètres & Conformité RGPD</h3>
              <p className="text-[11px] text-slate-400">
                Souveraineté des données, sessions actives et gestion de compte.
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
        <div className="flex border-b border-slate-800">
          <button
            onClick={() => setActiveTab('rgpd')}
            className={`pb-2.5 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'rgpd' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Données & Export RGPD
          </button>
          <button
            onClick={() => setActiveTab('sessions')}
            className={`pb-2.5 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'sessions' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Sessions actives ({sessions.length})
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`pb-2.5 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'security' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Zone de danger
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
                Vous pouvez télécharger à tout moment une copie intégrale de vos métadonnées, documents, versions et historiques de partage dans un format lisible par machine (JSON).
              </p>
              <div className="pt-2">
                <button
                  onClick={handleExportData}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center space-x-2 shadow-sm transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Télécharger mon archive personnelle (.JSON)</span>
                </button>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1 text-[11px] text-slate-400">
              <div className="font-semibold text-slate-300">Durée de conservation légale :</div>
              <p>• Les documents de la corbeille sont purgés automatiquement après 30 jours.</p>
              <p>• Les journaux de connexion sont conservés 12 mois conformément aux obligations légales de traçabilité.</p>
            </div>
          </div>
        )}

        {/* Tab 2: Active Sessions */}
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

        {/* Tab 3: Danger Zone */}
        {activeTab === 'security' && (
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 space-y-2">
              <h4 className="font-bold text-sm flex items-center space-x-2 text-rose-400">
                <AlertTriangle className="w-4 h-4" />
                <span>Suppression définitive du compte</span>
              </h4>
              <p className="text-[11px] text-rose-300/80 leading-relaxed">
                Cette action est irréversible. L'ensemble de vos espaces documentaires, fichiers MinIO, partages et identifiants seront définitivement purgés des bases de données.
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
                    Veuillez taper <strong className="text-white">SUPPRIMER</strong> pour confirmer :
                  </p>
                  <input
                    type="text"
                    value={deleteInput}
                    onChange={(e) => setDeleteInput(e.target.value)}
                    placeholder="SUPPRIMER"
                    className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-xs text-white"
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
                      className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-40"
                    >
                      Confirmer la suppression
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
