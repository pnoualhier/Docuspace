import React, { useState, useMemo, useEffect } from 'react';
import {
  X,
  Download,
  Share2,
  ShieldCheck,
  ShieldAlert,
  Clock,
  FileText,
  Copy,
  Check,
  Key,
  Search,
  FileSpreadsheet,
  FileCode,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { DocumentItem, DocumentPreviewData } from '../types';
import { formatBytes } from '../services/crypto';
import { apiClient, ApiError } from '../services/api';

interface FilePreviewModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  onShare: (doc: DocumentItem) => void;
  onRequestDownload?: (doc: DocumentItem) => Promise<string | null>;
}

export const FilePreviewModal: React.FC<FilePreviewModalProps> = ({
  document,
  onClose,
  onShare,
  onRequestDownload,
}) => {
  const [preview, setPreview] = useState<DocumentPreviewData | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState(false);
  const [tableSearch, setTableSearch] = useState('');
  const [copiedCode, setCopiedCode] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const loadPreview = async () => {
      if (!document) {
        setPreview(null);
        setPreviewError(null);
        return;
      }
      setIsLoadingPreview(true);
      setPreviewError(null);
      setDownloadError(null);
      setTableSearch('');
      try {
        const res = await apiClient.documents.getPreview(document.tenantId, document.id);
        if (!cancelled) {
          setPreview({
            documentId: res.document_id,
            originalName: res.original_name,
            mimeType: res.mime_type,
            extension: res.extension,
            sizeBytes: res.size_bytes,
            mode: res.mode,
            textContent: res.text_content,
            htmlContent: res.html_content,
            svgContent: res.svg_content,
            csvData: res.csv_data,
            downloadUrl: res.download_url,
            message: res.message,
          });
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setPreview(null);
          setPreviewError(
            err instanceof ApiError
              ? err.detail
              : "Impossible de charger l'aperçu du document."
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingPreview(false);
        }
      }
    };

    void loadPreview();
    return () => {
      cancelled = true;
    };
  }, [document]);

  const filteredCsvRows = useMemo(() => {
    if (!preview?.csvData) return [];
    if (!tableSearch.trim()) return preview.csvData.rows;
    const q = tableSearch.toLowerCase();
    return preview.csvData.rows.filter((row) =>
      row.some((cell) => cell.toLowerCase().includes(q))
    );
  }, [preview, tableSearch]);

  if (!document) return null;

  const handleCopyHash = () => {
    navigator.clipboard.writeText(document.sha256Hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleDownload = async () => {
    setDownloadError(null);
    setIsDownloading(true);
    try {
      const presignedUrl = onRequestDownload
        ? await onRequestDownload(document)
        : (await apiClient.storage.getDownloadUrl(document.tenantId, document.id)).download_url;

      if (!presignedUrl) {
        setDownloadError('Aucune URL de téléchargement disponible.');
        return;
      }

      const a = window.document.createElement('a');
      a.href = presignedUrl;
      a.download = document.originalName;
      a.rel = 'noopener noreferrer';
      a.click();
    } catch (err: unknown) {
      setDownloadError(
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : 'Téléchargement refusé par la politique de sécurité.'
      );
    } finally {
      setIsDownloading(false);
    }
  };

  const isPdf = document.extension === 'pdf' || document.mimeType === 'application/pdf';
  const isImage =
    document.mimeType.startsWith('image/') ||
    ['jpg', 'jpeg', 'png', 'svg', 'webp', 'gif'].includes(document.extension.toLowerCase());
  const isCsv = preview?.mode === 'csv' || document.extension === 'csv';
  const isCode = ['py', 'ts', 'tsx', 'js', 'json', 'sh', 'sql', 'html', 'css', 'xml'].includes(
    document.extension.toLowerCase()
  );

  const renderAntivirusStatusBox = () => {
    switch (document.antivirusStatus) {
      case 'CLEAN':
        return (
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 flex items-start space-x-2.5">
            <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-xs">ClamAV : Sain</div>
              <div className="text-[11px] text-emerald-400/80">
                {document.antivirusDetails || 'Analyse antivirus validée.'}
              </div>
            </div>
          </div>
        );
      case 'PENDING':
        return (
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 flex items-start space-x-2.5">
            <Clock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-xs">ClamAV : Analyse en attente</div>
              <div className="text-[11px] text-amber-300/80">
                Téléchargement et aperçu bloqués par la politique Fail-Closed tant que le scan n'est pas terminé.
              </div>
            </div>
          </div>
        );
      default:
        return (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start space-x-2.5">
            <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-xs">
                ClamAV : {document.antivirusStatus === 'INFECTED' ? 'Menace détectée (Quarantaine)' : 'Erreur de scan'}
              </div>
              <div className="text-[11px] text-rose-300/80">
                {document.antivirusDetails || 'Accès bloqué par la politique de sécurité.'}
              </div>
            </div>
          </div>
        );
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in duration-150"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 px-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3 truncate">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              {isCsv ? (
                <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
              ) : isCode ? (
                <FileCode className="w-5 h-5 text-violet-400" />
              ) : (
                <FileText className="w-5 h-5 text-sky-400" />
              )}
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
              type="button"
              onClick={() => onShare(document)}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-xs flex items-center space-x-1.5"
              title="Partager le document"
            >
              <Share2 className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Partager</span>
            </button>
            <button
              type="button"
              onClick={() => void handleDownload()}
              disabled={isDownloading}
              className="p-2 px-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-medium transition-colors text-xs flex items-center space-x-1.5 shadow-sm whitespace-nowrap"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{isDownloading ? 'Préparation...' : 'Télécharger'}</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Fermer l'aperçu"
              className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {downloadError && (
          <div role="alert" className="mx-6 mt-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            {downloadError}
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-slate-800">
          {/* Main Viewer */}
          <div className="lg:col-span-2 flex flex-col bg-slate-950/70 overflow-hidden">
            <div className="p-2.5 px-4 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between text-xs text-slate-300">
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                {preview?.mode === 'csv'
                  ? 'Aperçu Tabulaire'
                  : preview?.mode === 'markdown'
                    ? 'Aperçu Markdown'
                    : preview?.mode === 'svg'
                      ? 'Aperçu SVG Assaini'
                      : preview?.mode === 'text'
                        ? 'Aperçu Texte'
                        : preview?.mode === 'binary_url'
                          ? 'Aperçu Binaire Signé'
                          : 'Aperçu Document'}
              </span>

              {preview?.mode === 'csv' && preview.csvData && (
                <div className="flex items-center space-x-1 px-2 py-0.5 rounded-lg bg-slate-950 border border-slate-800 text-xs">
                  <Search className="w-3 h-3 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Filtrer les cellules..."
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                    className="bg-transparent text-slate-200 text-xs focus:outline-none w-36"
                  />
                </div>
              )}

              {preview?.textContent && (
                <button
                  type="button"
                  onClick={() => handleCopyText(preview.textContent!)}
                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] flex items-center space-x-1"
                >
                  {copiedCode ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedCode ? 'Copié' : 'Copier le texte'}</span>
                </button>
              )}
            </div>

            <div className="flex-1 p-6 overflow-auto min-h-[420px] flex justify-center items-start">
              {isLoadingPreview ? (
                <div className="self-center text-center space-y-2 text-xs text-slate-400">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-400 mx-auto" />
                  <span>Récupération sécurisée du contenu depuis MinIO...</span>
                </div>
              ) : previewError ? (
                <div role="alert" className="self-center max-w-md p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{previewError}</span>
                </div>
              ) : !preview ? (
                <div className="self-center text-xs text-slate-400">
                  Aperçu indisponible.
                </div>
              ) : preview.mode === 'svg' && preview.svgContent ? (
                <img
                  src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(preview.svgContent)}`}
                  alt={document.originalName}
                  className="max-h-[450px] w-auto rounded-xl object-contain bg-white p-4 shadow-xl border border-slate-800"
                />
              ) : preview.mode === 'binary_url' && preview.downloadUrl ? (
                isImage ? (
                  <img
                    src={preview.downloadUrl}
                    alt={document.originalName}
                    className="max-h-[450px] w-auto rounded-xl object-contain shadow-xl border border-slate-800"
                  />
                ) : isPdf ? (
                  <iframe
                    src={preview.downloadUrl}
                    title={document.originalName}
                    className="w-full h-[460px] rounded-xl bg-white border border-slate-800"
                  />
                ) : (
                  <div className="self-center text-center space-y-3 max-w-sm">
                    <p className="text-xs text-slate-300">
                      Ce document binaire peut être téléchargé via son URL présignée sécurisée.
                    </p>
                    <button
                      type="button"
                      onClick={() => void handleDownload()}
                      className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
                    >
                      Télécharger le fichier
                    </button>
                  </div>
                )
              ) : preview.mode === 'csv' && preview.csvData ? (
                <div className="w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/90 shadow-md">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 border-b border-slate-800 text-sky-400 font-semibold font-mono uppercase text-[10px]">
                      <tr>
                        {preview.csvData.headers.map((header, hIdx) => (
                          <th key={hIdx} className="p-3 border-r border-slate-800/80 last:border-r-0">
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono text-slate-200">
                      {filteredCsvRows.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-800/50 transition-colors">
                          {row.map((cell, cIdx) => (
                            <td key={cIdx} className="p-2.5 border-r border-slate-800/40 last:border-r-0 whitespace-nowrap">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : preview.mode === 'markdown' ? (
                <div className="w-full h-full p-5 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 text-xs overflow-y-auto max-h-[460px] leading-relaxed select-text">
                  {preview.htmlContent ? (
                    <div
                      className="prose prose-invert prose-xs max-w-none"
                      dangerouslySetInnerHTML={{ __html: preview.htmlContent }}
                    />
                  ) : (
                    <pre className="whitespace-pre-wrap font-mono">{preview.textContent || ''}</pre>
                  )}
                </div>
              ) : preview.mode === 'text' ? (
                <div className="w-full rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs overflow-x-auto shadow-md max-h-[460px] overflow-y-auto">
                  {isCode ? (
                    <div className="space-y-1">
                      {(preview.textContent || '').split('\n').map((line, idx) => (
                        <div key={idx} className="flex space-x-4 hover:bg-slate-900/50 px-2 rounded">
                          <span className="text-slate-600 select-none w-8 text-right font-mono text-[11px]">
                            {idx + 1}
                          </span>
                          <span className="text-sky-300 whitespace-pre">{line}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <pre className="text-slate-200 whitespace-pre-wrap leading-relaxed select-text">
                      {preview.textContent || ''}
                    </pre>
                  )}
                </div>
              ) : (
                <div className="self-center max-w-md text-center space-y-3 p-6 rounded-2xl bg-slate-900/80 border border-slate-800">
                  <FileText className="w-8 h-8 text-slate-500 mx-auto" />
                  <p className="text-xs font-semibold text-white">Aperçu direct non disponible</p>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {preview.message ||
                      'Ce format binaire ne peut pas être rendu directement dans le navigateur. Téléchargez le document pour le consulter.'}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Metadata & Security Info */}
          <div className="p-6 space-y-5 bg-slate-900/40 text-xs">
            <div className="space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Sécurité & Intégrité
              </span>
              {renderAntivirusStatusBox()}
            </div>

            <div className="space-y-1.5">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Empreinte SHA-256
              </span>
              <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] break-all text-slate-300 flex items-center justify-between gap-2">
                <span>{document.sha256Hash}</span>
                <button
                  type="button"
                  onClick={handleCopyHash}
                  className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white shrink-0"
                  title="Copier le hash SHA-256"
                >
                  {copiedHash ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1">
                <Key className="w-3 h-3 text-slate-400" />
                <span>Stockage MinIO / S3</span>
              </span>
              <p className="text-[10px] text-slate-400 p-2 bg-slate-950 rounded-lg border border-slate-800">
                {document.storageKey || 'Clé interne opaque isolée côté serveur'}
              </p>
            </div>

            <div className="border-t border-slate-800 pt-3 space-y-2 text-[11px]">
              <div className="flex justify-between text-slate-400">
                <span>Taille</span>
                <span className="text-slate-200 font-semibold">{formatBytes(document.sizeBytes)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Statut document</span>
                <span className="text-slate-200 font-semibold">{document.status}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Date d'import</span>
                <span className="text-slate-200">{new Date(document.createdAt).toLocaleDateString('fr-FR')}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Dernière mise à jour</span>
                <span className="text-slate-200">{new Date(document.updatedAt).toLocaleDateString('fr-FR')}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
