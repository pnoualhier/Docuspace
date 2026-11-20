import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  Lock,
  Download,
  FileText,
  Clock,
  AlertTriangle,
  Loader2,
  ArrowLeft,
  CheckCircle2,
} from 'lucide-react';
import { apiClient, ApiError, ApiPublicShareDetails } from '../services/api';
import { PublicShareDetails } from '../types';
import { formatBytes } from '../services/crypto';

interface PublicShareViewProps {
  token: string;
  onExitPublicView?: () => void;
}

const mapPublicShare = (d: ApiPublicShareDetails): PublicShareDetails => ({
  token: d.token,
  resourceType: d.resource_type,
  resourceName: d.resource_name,
  mimeType: d.mime_type,
  extension: d.extension,
  sizeBytes: d.size_bytes,
  sha256Hash: d.sha256_hash,
  hasPassword: d.has_password,
  isPasswordRequired: d.is_password_required,
  expiresAt: d.expires_at,
  downloadCount: d.download_count,
  maxDownloads: d.max_downloads,
  canDownload: d.can_download,
  isActive: d.is_active,
});

export const PublicShareView: React.FC<PublicShareViewProps> = ({
  token,
  onExitPublicView,
}) => {
  const [details, setDetails] = useState<PublicShareDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [unlockedPassword, setUnlockedPassword] = useState<string | undefined>(undefined);
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [isUnlocking, setIsUnlocking] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadSuccessMsg, setDownloadSuccessMsg] = useState<string | null>(null);

  const loadShareInfo = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.shares.getPublic(token);
      const mapped = mapPublicShare(res);
      setDetails(mapped);
      if (!mapped.isPasswordRequired) {
        setIsUnlocked(true);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMsg(err.detail);
      } else {
        setErrorMsg('Impossible de charger ce lien de partage public.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadShareInfo();
  }, [loadShareInfo]);

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) return;
    setIsUnlocking(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.shares.accessPublic(token, password);
      setDetails(mapPublicShare(res));
      setUnlockedPassword(password);
      setIsUnlocked(true);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMsg(err.detail);
      } else {
        setErrorMsg('Échec de la vérification du mot de passe.');
      }
    } finally {
      setIsUnlocking(false);
    }
  };

  const handleDownload = async () => {
    if (!details) return;
    setIsDownloading(true);
    setErrorMsg(null);
    setDownloadSuccessMsg(null);
    try {
      const res = await apiClient.shares.downloadPublic(token, unlockedPassword);
      setDetails((prev) =>
        prev
          ? {
              ...prev,
              downloadCount: res.download_count,
              maxDownloads: res.max_downloads,
              canDownload:
                res.max_downloads === null ||
                res.max_downloads === undefined ||
                res.download_count < res.max_downloads,
            }
          : prev
      );
      const a = window.document.createElement('a');
      a.href = res.download_url;
      a.download = res.filename;
      a.rel = 'noopener noreferrer';
      a.click();
      setDownloadSuccessMsg(`Téléchargement lancé pour "${res.filename}".`);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMsg(err.detail);
      } else {
        setErrorMsg('Le téléchargement du document a échoué.');
      }
    } finally {
      setIsDownloading(false);
    }
  };

  const quotaReached =
    details !== null &&
    details.maxDownloads !== null &&
    details.maxDownloads !== undefined &&
    details.downloadCount >= details.maxDownloads;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-3xl p-8 space-y-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-sky-400 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-base font-extrabold text-white">DocuSpace — Partage sécurisé</h1>
              <p className="text-[11px] text-slate-400">Accès externe contrôlé</p>
            </div>
          </div>

          {onExitPublicView && (
            <button
              type="button"
              onClick={onExitPublicView}
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center space-x-1.5 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Accueil</span>
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="py-12 text-center space-y-3">
            <Loader2 className="w-7 h-7 animate-spin text-blue-400 mx-auto" />
            <p className="text-xs text-slate-400">Vérification du lien de partage auprès du serveur...</p>
          </div>
        ) : !details ? (
          <div role="alert" className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/30 space-y-2 text-center">
            <AlertTriangle className="w-7 h-7 text-rose-400 mx-auto" />
            <h2 className="text-sm font-bold text-white">Lien indisponible</h2>
            <p className="text-xs text-rose-200">{errorMsg || 'Ce lien est introuvable, expiré ou révoqué.'}</p>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center space-x-3">
                <div className="p-2.5 rounded-xl bg-blue-500/10 text-blue-400">
                  <FileText className="w-5 h-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="text-sm font-bold text-white truncate">{details.resourceName}</h2>
                  <p className="text-[11px] text-slate-400 font-mono">
                    {details.mimeType || 'application/octet-stream'}
                    {typeof details.sizeBytes === 'number' && details.sizeBytes > 0
                      ? ` • ${formatBytes(details.sizeBytes)}`
                      : ''}
                  </p>
                </div>
              </div>

              {details.sha256Hash && (
                <div className="pt-2 border-t border-slate-800/80 text-[10px] font-mono text-slate-400 break-all">
                  SHA-256 : {details.sha256Hash}
                </div>
              )}

              <div className="flex flex-wrap gap-2 pt-1 text-[10px]">
                <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                  Téléchargements : {details.downloadCount} / {details.maxDownloads ?? 'Illimité'}
                </span>
                {details.expiresAt && (
                  <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300 inline-flex items-center space-x-1">
                    <Clock className="w-3 h-3 text-slate-400" />
                    <span>Expire le {new Date(details.expiresAt).toLocaleString('fr-FR')}</span>
                  </span>
                )}
              </div>
            </div>

            {errorMsg && (
              <div role="alert" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{errorMsg}</span>
              </div>
            )}

            {downloadSuccessMsg && (
              <div role="status" className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{downloadSuccessMsg}</span>
              </div>
            )}

            {!isUnlocked && details.isPasswordRequired ? (
              <form onSubmit={handleUnlock} className="space-y-3">
                <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-200 text-xs flex items-center space-x-2">
                  <Lock className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>Ce document est protégé par mot de passe.</span>
                </div>
                <div>
                  <label htmlFor="public-share-password" className="block text-xs font-semibold text-slate-300 mb-1">
                    Mot de passe du partage
                  </label>
                  <input
                    id="public-share-password"
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Saisir le mot de passe"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isUnlocking}
                  className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-semibold text-xs flex items-center justify-center space-x-2"
                >
                  {isUnlocking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-3.5 h-3.5" />}
                  <span>{isUnlocking ? 'Vérification...' : 'Déverrouiller le partage'}</span>
                </button>
              </form>
            ) : details.resourceType === 'DOCUMENT' ? (
              <button
                type="button"
                onClick={handleDownload}
                disabled={isDownloading || quotaReached || !details.canDownload}
                className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-xs flex items-center justify-center space-x-2 shadow-lg shadow-blue-600/20"
              >
                {isDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                <span>
                  {quotaReached || !details.canDownload
                    ? 'Quota de téléchargements atteint'
                    : isDownloading
                      ? 'Génération du lien signé...'
                      : 'Télécharger le document sécurisé'}
                </span>
              </button>
            ) : (
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400">
                Ce lien pointe vers un dossier partagé ({details.resourceName}).
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
