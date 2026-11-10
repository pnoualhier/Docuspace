import React, { useState, useMemo } from 'react';
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
  Calendar,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight,
  Search,
  FileSpreadsheet,
  FileCode,
  FileCheck,
  FileType
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
  const [copiedHash, setCopiedHash] = useState(false);
  const [pdfPage, setPdfPage] = useState(1);
  const [pdfZoom, setPdfZoom] = useState(100);
  const [tableSearch, setTableSearch] = useState('');
  const [copiedCode, setCopiedCode] = useState(false);

  if (!document) return null;

  const handleCopyHash = () => {
    navigator.clipboard.writeText(document.sha256Hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleCopyCode = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleDownload = () => {
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
  const isPdf = document.extension === 'pdf' || document.mimeType === 'application/pdf';
  const isCsv = document.extension === 'csv' || document.mimeType === 'text/csv' || document.extension === 'xlsx';
  const isCode = ['py', 'ts', 'tsx', 'js', 'json', 'sh', 'sql', 'html', 'css', 'xml'].includes(document.extension);
  const isMarkdown = document.extension === 'md' || document.mimeType === 'text/markdown';
  const isOfficeDoc = ['docx', 'pptx', 'odt', 'ods'].includes(document.extension);

  // Parse CSV rows if tabular
  const csvData = useMemo(() => {
    if (!isCsv || !document.contentPreview) return null;
    const lines = document.contentPreview.split('\n').filter(Boolean);
    const delimiter = lines[0].includes(';') && !lines[0].includes(',') ? ';' : ',';
    const rows = lines.map(line => line.split(delimiter).map(cell => cell.trim()));
    const headers = rows[0] || [];
    let dataRows = rows.slice(1);

    if (tableSearch.trim()) {
      const q = tableSearch.toLowerCase();
      dataRows = dataRows.filter(r => r.some(cell => cell.toLowerCase().includes(q)));
    }

    return { headers, rows: dataRows };
  }, [isCsv, document.contentPreview, tableSearch]);

  return (
    <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 px-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3 truncate">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              {isPdf ? (
                <FileText className="w-5 h-5 text-rose-400" />
              ) : isCsv ? (
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
                {document.mimeType} • {formatBytes(document.sizeBytes)} • {document.versions.length} version(s)
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

        {/* Modal Body: Multi-Format Viewer + Side Security Panel */}
        <div className="flex-1 overflow-y-auto grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-slate-800">
          {/* Main Viewer (Left 2 columns) */}
          <div className="lg:col-span-2 flex flex-col bg-slate-950/70 overflow-hidden">
            {/* Viewer Controls Toolbar */}
            <div className="p-2.5 px-4 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between text-xs text-slate-300">
              <div className="flex items-center space-x-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {isPdf ? 'Visionneuse PDF.js' : isCsv ? 'Visionneuse Tableur' : isCode ? 'Éditeur de Code' : isMarkdown ? 'Aperçu Markdown' : 'Aperçu Document'}
                </span>
                {isOfficeDoc && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                    LibreOffice Headless 7.6
                  </span>
                )}
              </div>

              {/* PDF Toolbar Controls */}
              {isPdf && (
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setPdfPage(p => Math.max(1, p - 1))}
                    disabled={pdfPage <= 1}
                    className="p-1 rounded hover:bg-slate-800 text-slate-400 disabled:opacity-40"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </button>
                  <span className="text-[11px] font-mono">Page {pdfPage} / 3</span>
                  <button
                    onClick={() => setPdfPage(p => Math.min(3, p + 1))}
                    disabled={pdfPage >= 3}
                    className="p-1 rounded hover:bg-slate-800 text-slate-400 disabled:opacity-40"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                  <div className="h-3 w-px bg-slate-700 mx-1" />
                  <button
                    onClick={() => setPdfZoom(z => Math.max(75, z - 25))}
                    className="p-1 rounded hover:bg-slate-800 text-slate-400"
                    title="Zoom arrière"
                  >
                    <ZoomOut className="w-3.5 h-3.5" />
                  </button>
                  <span className="text-[11px] font-mono">{pdfZoom}%</span>
                  <button
                    onClick={() => setPdfZoom(z => Math.min(150, z + 25))}
                    className="p-1 rounded hover:bg-slate-800 text-slate-400"
                    title="Zoom avant"
                  >
                    <ZoomIn className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Table search control */}
              {isCsv && (
                <div className="flex items-center space-x-1 px-2 py-0.5 rounded-lg bg-slate-950 border border-slate-800 text-xs">
                  <Search className="w-3 h-3 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Filtrer les cellules..."
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                    className="bg-transparent text-slate-200 text-xs focus:outline-none w-32"
                  />
                </div>
              )}

              {/* Code copy button */}
              {isCode && document.contentPreview && (
                <button
                  onClick={() => handleCopyCode(document.contentPreview!)}
                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] flex items-center space-x-1"
                >
                  {copiedCode ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedCode ? 'Copié' : 'Copier le code'}</span>
                </button>
              )}
            </div>

            {/* Viewer Display Body */}
            <div className="flex-1 p-6 overflow-auto min-h-[420px] flex justify-center items-start">
              {isImage && document.contentPreview && document.contentPreview.startsWith('data:image') ? (
                <img
                  src={document.contentPreview}
                  alt={document.originalName}
                  className="max-h-[450px] w-auto rounded-xl object-contain shadow-xl border border-slate-800"
                />
              ) : isPdf ? (
                /* Simulated Paged PDF Page */
                <div 
                  className="bg-white text-slate-900 rounded-xl shadow-2xl p-8 max-w-xl w-full min-h-[500px] font-serif transition-transform select-text border border-slate-300"
                  style={{ transform: `scale(${pdfZoom / 100})`, transformOrigin: 'top center' }}
                >
                  <div className="border-b-2 border-slate-900 pb-3 mb-6 flex justify-between items-start">
                    <div>
                      <h2 className="text-base font-bold uppercase tracking-wider text-slate-900">
                        RÉPUBLIQUE FRANÇAISE
                      </h2>
                      <p className="text-xs text-slate-600 font-sans mt-0.5">
                        Document officiel certifié • Page {pdfPage} sur 3
                      </p>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-1 rounded bg-slate-100 border border-slate-300">
                      DocuSpace PDF/A-1b
                    </span>
                  </div>

                  <div className="space-y-4 text-xs font-sans leading-relaxed text-slate-800">
                    <p className="font-semibold text-slate-900">
                      Réf : {document.originalName}
                    </p>
                    <p className="whitespace-pre-wrap">
                      {document.contentPreview || "Contenu officiel du document PDF certifié."}
                    </p>
                    <div className="pt-8 text-[10px] text-slate-500 font-mono border-t border-slate-200 flex justify-between">
                      <span>Empreinte SHA-256 : {document.sha256Hash.substring(0, 16)}...</span>
                      <span>Certifié ClamAV Daemon</span>
                    </div>
                  </div>
                </div>
              ) : isCsv && csvData ? (
                /* Interactive Tabular Spreadsheet */
                <div className="w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/90 shadow-md">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 border-b border-slate-800 text-sky-400 font-semibold font-mono uppercase text-[10px]">
                      <tr>
                        {csvData.headers.map((header, hIdx) => (
                          <th key={hIdx} className="p-3 border-r border-slate-800/80 last:border-r-0">
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono text-slate-200">
                      {csvData.rows.map((row, rIdx) => (
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
              ) : isCode && document.contentPreview ? (
                /* Formatted Code with Line Numbers */
                <div className="w-full rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs overflow-x-auto shadow-md">
                  <div className="space-y-1">
                    {document.contentPreview.split('\n').map((line, idx) => (
                      <div key={idx} className="flex space-x-4 hover:bg-slate-900/50 px-2 rounded">
                        <span className="text-slate-600 select-none w-8 text-right font-mono text-[11px]">
                          {idx + 1}
                        </span>
                        <span className="text-sky-300 whitespace-pre">
                          {line}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                /* Formatted Plain Text / Markdown */
                <div className="w-full h-full p-5 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 text-xs font-mono whitespace-pre-wrap overflow-y-auto max-h-[460px] leading-relaxed select-text shadow-sm">
                  {document.contentPreview || 'Aperçu textuel du document chiffré généré automatiquement.'}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Metadata, Versions & Security Info */}
          <div className="p-6 space-y-5 bg-slate-900/40 text-xs">
            {/* ClamAV Antivirus Verification Badge */}
            <div className="space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Sécurité & Intégrité
              </span>
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 flex items-start space-x-2.5">
                <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-xs">Certifié ClamAV Sain</div>
                  <div className="text-[11px] text-emerald-400/80">
                    {document.antivirusDetails || "Aucune menace détectée. Règle fail-closed respectée."}
                  </div>
                </div>
              </div>
            </div>

            {/* Cryptographic SHA-256 Fingerprint */}
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

            {/* Isolated S3 Storage Key */}
            <div className="space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1">
                <Key className="w-3 h-3 text-slate-400" />
                <span>Clé interne MinIO / S3</span>
              </span>
              <p className="font-mono text-[10px] text-slate-400 break-all p-2 bg-slate-950 rounded-lg border border-slate-800">
                {document.storageKey}
              </p>
              <p className="text-[10px] text-slate-500">
                Nom d'origine décorrélé de la clé physique d'objet pour une sécurité optimale.
              </p>
            </div>

            {/* Metadata Summary */}
            <div className="border-t border-slate-800 pt-3 space-y-2 text-[11px]">
              <div className="flex justify-between text-slate-400">
                <span>Taille</span>
                <span className="text-slate-200 font-semibold">{formatBytes(document.sizeBytes)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Révisions</span>
                <span className="text-slate-200 font-semibold">{document.versions.length || 1} version(s)</span>
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
