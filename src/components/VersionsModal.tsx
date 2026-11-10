import React, { useState, useRef } from 'react';
import { 
  X, 
  History, 
  RotateCcw, 
  CheckCircle2, 
  FileText, 
  HardDrive, 
  Layers,
  UploadCloud,
  Plus,
  Trash2,
  ShieldCheck,
  Loader2,
  AlertTriangle
} from 'lucide-react';
import { DocumentItem, DocumentVersion, Plan } from '../types';
import { formatBytes, calculateSHA256 } from '../services/crypto';

interface VersionsModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  onRestoreVersion: (doc: DocumentItem, version: DocumentVersion) => void;
  onCreateVersion?: (doc: DocumentItem, newVersion: DocumentVersion) => void;
  onPurgeVersion?: (doc: DocumentItem, versionId: string) => void;
}

export const VersionsModal: React.FC<VersionsModalProps> = ({
  document,
  onClose,
  onRestoreVersion,
  onCreateVersion,
  onPurgeVersion,
}) => {
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [revisionComment, setRevisionComment] = useState('');
  const [selectedRevisionFile, setSelectedRevisionFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processStep, setProcessStep] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!document) return null;

  const totalVersionBytes = document.versions.reduce((acc, v) => acc + v.sizeBytes, 0);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedRevisionFile(e.target.files[0]);
      setErrorMsg(null);
    }
  };

  const handleUploadNewVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRevisionFile || !onCreateVersion) return;

    setIsProcessing(true);
    setErrorMsg(null);

    try {
      setProcessStep("Calcul de l'empreinte SHA-256 de la nouvelle version...");
      const sha256 = await calculateSHA256(selectedRevisionFile);

      setProcessStep("Analyse antivirus ClamAV (Fail-Closed)...");
      await new Promise(r => setTimeout(r, 500));

      setProcessStep("Stockage S3 MinIO & synchronisation...");
      await new Promise(r => setTimeout(r, 400));

      const nextVersionNum = Math.max(...document.versions.map(v => v.versionNumber), 0) + 1;
      const newVersionId = `ver-${crypto.randomUUID()}`;
      const ext = document.extension || 'bin';
      const storageKey = `tenants/${document.tenantId}/${document.id}_v${nextVersionNum}.${ext}`;

      const newVer: DocumentVersion = {
        id: newVersionId,
        documentId: document.id,
        versionNumber: nextVersionNum,
        storageKey: storageKey,
        sizeBytes: selectedRevisionFile.size,
        mimeType: selectedRevisionFile.type || document.mimeType,
        sha256Hash: sha256,
        changeSummary: revisionComment.trim() || `Révision v${nextVersionNum}`,
        createdAt: new Date().toISOString()
      };

      onCreateVersion(document, newVer);
      setShowUploadForm(false);
      setSelectedRevisionFile(null);
      setRevisionComment('');
    } catch (err: any) {
      setErrorMsg(err.message || "Erreur lors de l'enregistrement de la révision.");
    } finally {
      setIsProcessing(false);
      setProcessStep('');
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5 truncate">
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
              <History className="w-5 h-5" />
            </div>
            <div className="truncate">
              <h3 className="text-sm font-bold text-white">Historique des versions</h3>
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

        {/* Quota & Add Version Banner */}
        <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2 text-slate-300">
            <HardDrive className="w-4 h-4 text-purple-400" />
            <div>
              <span className="block font-medium">Stockage cumulé des révisions</span>
              <span className="text-[10px] text-slate-500">{document.versions.length} version(s) conservée(s)</span>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <span className="font-mono font-semibold text-purple-300">
              {formatBytes(totalVersionBytes || document.sizeBytes)}
            </span>
            {onCreateVersion && (
              <button
                onClick={() => setShowUploadForm(!showUploadForm)}
                className="px-2.5 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-medium text-[11px] flex items-center space-x-1 transition-colors"
              >
                <Plus className="w-3 h-3" />
                <span>Nouvelle version</span>
              </button>
            )}
          </div>
        </div>

        {/* Upload New Version Form */}
        {showUploadForm && (
          <form onSubmit={handleUploadNewVersion} className="p-3.5 rounded-xl bg-slate-950/80 border border-purple-500/30 space-y-3 animate-in fade-in text-xs">
            <div className="flex items-center justify-between">
              <span className="font-bold text-purple-300 text-[11px] uppercase tracking-wider">
                Ajouter une nouvelle version
              </span>
              <button
                type="button"
                onClick={() => setShowUploadForm(false)}
                className="text-slate-500 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              required
              onChange={handleFileChange}
              className="hidden"
            />

            <div
              onClick={() => fileInputRef.current?.click()}
              className="p-3 rounded-lg border border-dashed border-slate-700 hover:border-purple-500 bg-slate-900/60 text-center cursor-pointer transition-colors"
            >
              <span className="text-slate-300 font-medium">
                {selectedRevisionFile ? selectedRevisionFile.name : "Cliquez pour choisir le fichier de révision"}
              </span>
              {selectedRevisionFile && (
                <span className="block text-[10px] text-purple-400 font-mono mt-0.5">
                  {formatBytes(selectedRevisionFile.size)}
                </span>
              )}
            </div>

            <input
              type="text"
              required
              value={revisionComment}
              onChange={(e) => setRevisionComment(e.target.value)}
              placeholder="Commentaire de révision (ex: Mise à jour clauses, correction fautes...)"
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500"
            />

            {errorMsg && (
              <div className="text-rose-400 text-xs flex items-center space-x-1.5">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {isProcessing && (
              <div className="p-2 rounded-lg bg-slate-900 text-purple-300 flex items-center space-x-2 text-[11px] animate-pulse">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>{processStep}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={!selectedRevisionFile || isProcessing}
              className="w-full py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold text-xs transition-colors flex items-center justify-center space-x-1.5"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>Valider et enregistrer la révision</span>
            </button>
          </form>
        )}

        {/* Versions List */}
        <div className="space-y-3 max-h-72 overflow-y-auto">
          {document.versions.length > 0 ? (
            document.versions.map((ver, idx) => {
              const isCurrent = idx === 0;
              return (
                <div
                  key={ver.id}
                  className={`p-3.5 rounded-xl border transition-all flex items-center justify-between ${
                    isCurrent
                      ? 'bg-purple-950/20 border-purple-500/30 text-purple-200'
                      : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-xs text-white">
                        Version {ver.versionNumber}
                      </span>
                      {isCurrent && (
                        <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-semibold border border-purple-500/30">
                          Active actuelle
                        </span>
                      )}
                    </div>

                    <p className="text-[11px] text-slate-400">
                      {ver.changeSummary || 'Révision enregistrée'}
                    </p>

                    <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
                      <span>{formatBytes(ver.sizeBytes)}</span>
                      <span>•</span>
                      <span>{new Date(ver.createdAt).toLocaleString('fr-FR')}</span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {!isCurrent && (
                      <button
                        onClick={() => onRestoreVersion(document, ver)}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-purple-600 hover:text-white text-slate-300 font-medium text-xs flex items-center space-x-1 transition-colors shrink-0"
                        title="Restaurer cette version comme active"
                      >
                        <RotateCcw className="w-3 h-3" />
                        <span>Rétablir</span>
                      </button>
                    )}
                    {!isCurrent && onPurgeVersion && document.versions.length > 1 && (
                      <button
                        onClick={() => onPurgeVersion(document, ver.id)}
                        className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                        title="Purger cette version et récupérer le quota"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-4 rounded-xl bg-slate-950 text-center text-xs text-slate-400">
              Aucune révision antérieure conservée.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center pt-2 border-t border-slate-800 text-[11px] text-slate-500">
          <div className="flex items-center space-x-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Chaque révision possède son empreinte SHA-256 dédiée</span>
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
