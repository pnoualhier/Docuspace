import React from 'react';
import { 
  X, 
  History, 
  RotateCcw, 
  CheckCircle2, 
  FileText, 
  HardDrive, 
  Layers 
} from 'lucide-react';
import { DocumentItem, DocumentVersion } from '../types';
import { formatBytes } from '../services/crypto';

interface VersionsModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  onRestoreVersion: (doc: DocumentItem, version: DocumentVersion) => void;
}

export const VersionsModal: React.FC<VersionsModalProps> = ({
  document,
  onClose,
  onRestoreVersion,
}) => {
  if (!document) return null;

  const totalVersionBytes = document.versions.reduce((acc, v) => acc + v.sizeBytes, 0);

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
              <History className="w-5 h-5" />
            </div>
            <div>
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

        {/* Quota Impact */}
        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2 text-slate-300">
            <HardDrive className="w-4 h-4 text-purple-400" />
            <span>Stockage cumulé des versions</span>
          </div>
          <span className="font-mono font-semibold text-purple-300">
            {formatBytes(totalVersionBytes || document.sizeBytes)}
          </span>
        </div>

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

                  {!isCurrent && (
                    <button
                      onClick={() => onRestoreVersion(document, ver)}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-purple-600 hover:text-white text-slate-300 font-medium text-xs flex items-center space-x-1.5 transition-colors shrink-0"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Rétablir</span>
                    </button>
                  )}
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
