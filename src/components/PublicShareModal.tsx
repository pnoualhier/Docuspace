import React, { useState } from 'react';
import { 
  X, 
  Lock, 
  Unlock, 
  Download, 
  ShieldCheck, 
  AlertTriangle, 
  FileText, 
  CheckCircle2, 
  Clock, 
  HardDrive,
  Eye,
  KeyRound
} from 'lucide-react';
import { Share, DocumentItem } from '../types';
import { formatBytes } from '../services/crypto';

interface PublicShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  share: Share | null;
  document: DocumentItem | null;
  onDownloadIncrement: (shareId: string) => void;
}

export const PublicShareModal: React.FC<PublicShareModalProps> = ({
  isOpen,
  onClose,
  share,
  document,
  onDownloadIncrement,
}) => {
  const [passwordInput, setPasswordInput] = useState('');
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [isRateLimited, setIsRateLimited] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  if (!isOpen || !share) return null;

  const isPasswordProtected = share.hasPassword && !isUnlocked;
  const isExpired = share.expiresAt && new Date(share.expiresAt).getTime() < Date.now();
  const isLimitReached = share.maxDownloads !== undefined && share.downloadCount >= share.maxDownloads;
  const isRevoked = !share.isActive;

  const handleUnlock = (e: React.FormEvent) => {
    e.preventDefault();
    if (isRateLimited) return;

    if (share.password && passwordInput === share.password) {
      setIsUnlocked(true);
      setErrorMsg(null);
      setFailedAttempts(0);
    } else {
      const nextAttempts = failedAttempts + 1;
      setFailedAttempts(nextAttempts);
      if (nextAttempts >= 5) {
        setIsRateLimited(true);
        setErrorMsg("Accès temporairement verrouillé pour 15 minutes (5 tentatives incorrectes).");
      } else {
        setErrorMsg(`Mot de passe incorrect (${nextAttempts}/5 tentatives).`);
      }
    }
  };

  const handleDownload = () => {
    if (isLimitReached || isExpired || isRevoked) return;
    onDownloadIncrement(share.id);
    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 3000);
  };

  return (
    <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-6 shadow-2xl">
        {/* Header with Visitor Badge */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-sky-500/10 text-sky-400">
              <Eye className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white">Simulateur Visiteur Public</h3>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  Vue Recipient
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate max-w-[280px]">
                https://docuspace.io/s/{share.token}
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

        {/* State Banner: Revoked or Expired */}
        {isRevoked ? (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold">Lien révoqué par le propriétaire</div>
              <p className="text-[11px] text-rose-400/90 mt-1">
                L'accès à cette ressource a été suspendu. Aucun téléchargement ou consultation n'est autorisé.
              </p>
            </div>
          </div>
        ) : isExpired ? (
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start space-x-3">
            <Clock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold">Ce lien de partage a expiré</div>
              <p className="text-[11px] text-amber-400/90 mt-1">
                La date limite de validité est dépassée depuis le {new Date(share.expiresAt!).toLocaleDateString('fr-FR')}.
              </p>
            </div>
          </div>
        ) : isPasswordProtected ? (
          /* Password Challenge Form */
          <form onSubmit={handleUnlock} className="space-y-4 py-2">
            <div className="p-4 rounded-2xl bg-slate-950/70 border border-slate-800 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-blue-500/10 text-blue-400 mx-auto flex items-center justify-center">
                <Lock className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white">Ce document est protégé par mot de passe</h4>
                <p className="text-[11px] text-slate-400 mt-1">
                  Veuillez renseigner la clé d'accès fournie par l'expéditeur pour déverrouiller le fichier.
                </p>
              </div>

              {share.password && (
                <div className="text-[10px] text-slate-500 bg-slate-900/60 p-2 rounded-lg border border-slate-800/80 flex items-center justify-center space-x-1.5">
                  <KeyRound className="w-3.5 h-3.5 text-amber-400" />
                  <span>Mot de passe de démonstration : <strong className="text-slate-300 font-mono">{share.password}</strong></span>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <input
                type="password"
                required
                disabled={isRateLimited}
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                placeholder="Saisissez le mot de passe d'accès"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />

              {errorMsg && (
                <div className="text-rose-400 text-xs flex items-center space-x-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={isRateLimited || !passwordInput}
              className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-xs transition-colors flex items-center justify-center space-x-2"
            >
              <Unlock className="w-4 h-4" />
              <span>Déverrouiller le document</span>
            </button>
          </form>
        ) : (
          /* Unlocked Resource View */
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-3">
              <div className="flex items-center space-x-3">
                <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400">
                  <FileText className="w-6 h-6" />
                </div>
                <div className="truncate">
                  <h4 className="text-xs font-bold text-white truncate">
                    {share.documentName || document?.originalName || 'Document Sécurisé'}
                  </h4>
                  <div className="flex items-center space-x-2 text-[10px] text-slate-400 mt-0.5 font-mono">
                    <span>{formatBytes(document?.sizeBytes || 1245000)}</span>
                    <span>•</span>
                    <span className="truncate">{document?.mimeType || 'application/pdf'}</span>
                  </div>
                </div>
              </div>

              {/* Security badges */}
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/80 text-[10px]">
                <div className="flex items-center space-x-1.5 text-emerald-400">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Contrôle ClamAV certifié</span>
                </div>
                <div className="flex items-center space-x-1.5 text-slate-400 font-mono">
                  <span>SHA-256 : {document?.sha256Hash?.substring(0, 10) || '9f86d08188'}...</span>
                </div>
              </div>
            </div>

            {/* Quota & Expiry info */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Téléchargements</div>
                <div className="text-white font-bold mt-1">
                  {share.downloadCount} / {share.maxDownloads !== undefined ? share.maxDownloads : 'Illimité'}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Expiration</div>
                <div className="text-slate-300 font-medium mt-1 truncate">
                  {share.expiresAt ? new Date(share.expiresAt).toLocaleDateString('fr-FR') : 'Sans limite'}
                </div>
              </div>
            </div>

            {/* Limit Reached Warning */}
            {isLimitReached && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>Le nombre maximal de téléchargements autorisés ({share.maxDownloads}) a été atteint.</span>
              </div>
            )}

            {/* Download Button */}
            <button
              onClick={handleDownload}
              disabled={isLimitReached}
              className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-xs flex items-center justify-center space-x-2 transition-all shadow-md shadow-blue-500/20"
            >
              {downloadSuccess ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-300" />
                  <span>Téléchargement initié avec succès !</span>
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  <span>Télécharger le document sécurisé</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-between items-center pt-2 border-t border-slate-800 text-xs text-slate-500">
          <div className="flex items-center space-x-1.5">
            <Lock className="w-3.5 h-3.5 text-blue-400" />
            <span>DocuSpace Zero-Knowledge Storage</span>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
