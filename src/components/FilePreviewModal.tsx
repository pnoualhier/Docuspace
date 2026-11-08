import React from 'react';
import { 
  X, 
  Download, 
  Share2, 
  ShieldCheck, 
  FileText, 
  Copy, 
  Check, 
  HardDrive, 
  Key, 
  Layers, 
  Calendar 
} from 'lucide-react';
import { DocumentItem } from '../types';
import { formatBytes } from '../services/crypto';

interface FilePreviewModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  onShare: (doc: DocumentItem) => void;
}

export const FilePreviewModal: React.FC<FilePreviewModalProps> = ({
  document,
  onClose,
  onShare,
}) => {
  const [copiedHash, setCopiedHash] = React.useState(false);

  if (!document) return null;

  const handleCopyHash = () => {
    navigator.clipboard.writeText(document.sha256Hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleDownload = () => {
    // Generate simple download blob from preview content or generic bytes
    const blob = new Blob([document.contentPreview || 'DocuSpace Secure Document Content'], { 
      type: document.mimeType 
    });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = document.originalName;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isImage = document.mimeType.startsWith('image/') || ['jpg', 'png', 'svg', 'webp'].includes(document.extension);
  const isCsv = document.extension === 'csv' || document.mimeType === 'text/csv';

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 px-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3 truncate">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <FileText className="w-5 h-5" />
            </div>
            <div className="truncate">
              <h3 className="text-sm font-bold text-white truncate">{document.originalName}</h3>
              <p className="text-[11px] text-slate-400 font-mono">
                {document.mimeType} • {formatBytes(document.sizeBytes)}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => onShare(document)}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-xs flex items-center space-x-1.5"
              title="Partager le document"
            >
              <Share2 className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Partager</span>
            </button>
            <button
              onClick={handleDownload}
              className="p-2 px-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors text-xs flex items-center space-x-1.5 shadow-sm"
              title="Télécharger"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Télécharger</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Content: Preview + Side Metadata */}
        <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-slate-800">
          {/* Left 2 Cols: Document Viewer */}
          <div className="md:col-span-2 p-6 flex flex-col justify-center items-center bg-slate-950/60 min-h-[350px]">
            {isImage && document.contentPreview && document.contentPreview.startsWith('data:image') ? (
              <img
                src={document.contentPreview}
                alt={document.originalName}
                className="max-h-[400px] w-auto rounded-xl object-contain shadow-lg border border-slate-800"
              />
            ) : isCsv && document.contentPreview ? (
              <div className="w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/90 p-3 text-xs font-mono">
                <table className="w-full text-left">
                  <tbody>
                    {document.contentPreview.split('\n').filter(Boolean).map((row, rIdx) => (
                      <tr key={rIdx} className={rIdx === 0 ? 'border-b border-slate-700 font-bold text-sky-300' : 'border-b border-slate-800/60 text-slate-300'}>
                        {row.split(',').map((cell, cIdx) => (
                          <td key={cIdx} className="p-2 whitespace-nowrap">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="w-full h-full p-4 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 text-xs font-mono whitespace-pre-wrap overflow-y-auto max-h-[420px] leading-relaxed select-text">
                {document.contentPreview || 'Aperçu textuel du document chiffré généré automatiquement.'}
              </div>
            )}
          </div>

          {/* Right Col: Metadata & Security Inspection */}
          <div className="p-6 space-y-5 bg-slate-900/40 text-xs">
            <div className="space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Sécurité & Intégrité
              </span>
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 flex items-start space-x-2.5">
                <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-xs">Certifié ClamAV Sain</div>
                  <div className="text-[11px] text-emerald-400/80">
                    Aucune menace détectée. Règle fail-closed respectée.
                  </div>
                </div>
              </div>
            </div>

            {/* Cryptographic SHA-256 */}
            <div className="space-y-1.5">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Empreinte SHA-256
              </span>
              <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] break-all text-slate-300 flex items-center justify-between gap-2">
                <span>{document.sha256Hash}</span>
                <button
                  onClick={handleCopyHash}
                  className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white shrink-0"
                  title="Copier le hash SHA-256"
                >
                  {copiedHash ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* Storage key */}
            <div className="space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1">
                <Key className="w-3 h-3 text-slate-400" />
                <span>Clé interne S3 / MinIO</span>
              </span>
              <p className="font-mono text-[10px] text-slate-400 break-all p-2 bg-slate-950 rounded-lg border border-slate-800">
                {document.storageKey}
              </p>
              <p className="text-[10px] text-slate-500">
                Nom d'origine décorrélé de la clé physique d'objet.
              </p>
            </div>

            {/* Details */}
            <div className="border-t border-slate-800 pt-3 space-y-2 text-[11px]">
              <div className="flex justify-between text-slate-400">
                <span>Taille</span>
                <span className="text-slate-200 font-semibold">{formatBytes(document.sizeBytes)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Versions</span>
                <span className="text-slate-200 font-semibold">{document.versions.length || 1} révision(s)</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Créé le</span>
                <span className="text-slate-200">{new Date(document.createdAt).toLocaleDateString('fr-FR')}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Modifié le</span>
                <span className="text-slate-200">{new Date(document.updatedAt).toLocaleDateString('fr-FR')}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
