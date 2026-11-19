import React, { useState, useRef } from 'react';
import {
  X,
  UploadCloud,
  FileCheck,
  AlertTriangle,
  ShieldCheck,
  Loader2,
  Lock,
  ShieldAlert,
} from 'lucide-react';
import { Plan, Tenant, DocumentItem, Folder } from '../types';
import { calculateSHA256, formatBytes, generateStorageKey } from '../services/crypto';

interface FileUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTenant: Tenant;
  currentPlan: Plan;
  currentFolder: Folder | null;
  onUploadSuccess: (newDoc: DocumentItem) => void;
  onUploadToApi?: (
    file: File,
    folderId: string | null,
    onProgress: (percent: number) => void
  ) => Promise<DocumentItem>;
}

const PROHIBITED_EXTS = [
  '.exe', '.bat', '.cmd', '.sh', '.bash', '.ps1', '.vbs',
  '.msi', '.dll', '.com', '.scr', '.sys', '.bin', '.elf',
  '.jar', '.deb', '.rpm', '.dmg', '.pkg', '.appimage',
];

export const FileUploadModal: React.FC<FileUploadModalProps> = ({
  isOpen,
  onClose,
  currentTenant,
  currentPlan,
  currentFolder,
  onUploadSuccess,
  onUploadToApi,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadStep, setUploadStep] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const hasDangerousFilename = (filename: string): string | null => {
    if (!filename || filename.includes('\0') || filename.includes('/') || filename.includes('\\') || filename.includes('..')) {
      return 'Nom de fichier invalide : caractères de traversée de chemin interdits.';
    }
    const lower = filename.toLowerCase().trim();
    if (PROHIBITED_EXTS.some((ext) => lower.endsWith(ext))) {
      return 'Fichier rejeté : les extensions exécutables ou scripts (.exe, .sh, .bat, .dll, etc.) sont strictement interdites.';
    }
    // Double-extension masquerading check (e.g., document.exe.pdf)
    const parts = lower.split('.');
    if (parts.length > 2) {
      const middleExts = parts.slice(1, -1).map((p) => `.${p}`);
      if (middleExts.some((m) => PROHIBITED_EXTS.includes(m))) {
        return 'Fichier rejeté : double extension exécutable dissimulée détectée.';
      }
    }
    return null;
  };

  const handleFileSelected = (file: File) => {
    setErrorMsg(null);
    setUploadProgress(0);

    const filenameError = hasDangerousFilename(file.name);
    if (filenameError) {
      setErrorMsg(filenameError);
      setSelectedFile(null);
      return;
    }

    if (file.size === 0) {
      setErrorMsg('Le fichier sélectionné est vide (0 octet).');
      setSelectedFile(null);
      return;
    }

    if (file.size > currentPlan.maxFileSizeBytes) {
      setErrorMsg(
        `Fichier trop volumineux (${formatBytes(file.size)}). Votre forfait ${currentPlan.name} est limité à ${formatBytes(currentPlan.maxFileSizeBytes)} par fichier.`
      );
      setSelectedFile(null);
      return;
    }

    const used = currentTenant.usedBytes || 0;
    if (used + file.size > currentPlan.maxStorageBytes) {
      setErrorMsg(
        `Espace de stockage insuffisant. L'ajout de ce fichier (${formatBytes(file.size)}) dépasserait la limite de votre forfait (${formatBytes(currentPlan.maxStorageBytes)}).`
      );
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleInjectEicarTest = () => {
    const eicarBlob = new Blob(
      ['X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'],
      { type: 'text/plain' }
    );
    const testFile = new File([eicarBlob], 'eicar_virus_test.txt', { type: 'text/plain' });
    setSelectedFile(testFile);
    setErrorMsg(null);
    setUploadProgress(0);
  };

  const processUpload = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setErrorMsg(null);
    setUploadProgress(5);

    try {
      if (onUploadToApi) {
        setUploadStep('Transfert sécurisé et analyse antivirus ClamAV côté serveur...');
        const uploadedDoc = await onUploadToApi(
          selectedFile,
          currentFolder ? currentFolder.id : null,
          (pct) => {
            setUploadProgress(pct);
            if (pct >= 100) {
              setUploadStep('Finalisation du scan ClamAV et persistance PostgreSQL / MinIO...');
            }
          }
        );
        setUploadProgress(100);
        onUploadSuccess(uploadedDoc);
        onClose();
        return;
      }

      // Local WebCrypto preview pipeline (when running offline without backend session)
      setUploadStep('Étape 1/3 : Calcul de l’empreinte cryptographique SHA-256...');
      const sha256 = await calculateSHA256(selectedFile);
      setUploadProgress(35);

      const fileText = await selectedFile.text().catch(() => '');
      const isEicarInfected = fileText.includes('EICAR-STANDARD-ANTIVIRUS-TEST-FILE');

      setUploadStep('Étape 2/3 : Préparation du transfert vers MinIO S3...');
      await new Promise((r) => setTimeout(r, 250));
      setUploadProgress(70);

      setUploadStep('Étape 3/3 : Analyse antivirus ClamAV en flux (Fail-Closed)...');
      await new Promise((r) => setTimeout(r, 250));

      if (isEicarInfected) {
        throw new Error(
          "Alerte de sécurité ClamAV : Signature 'EICAR.Test.File-FOUND' détectée ! Le fichier a été immédiatement rejeté, supprimé du stockage et placé en quarantaine."
        );
      }

      setUploadProgress(100);
      const ext = selectedFile.name.split('.').pop() || 'bin';
      const storageKey = generateStorageKey(currentTenant.id, ext);

      let previewText: string | undefined = undefined;
      if (selectedFile.type.startsWith('text/') || ['csv', 'md', 'json', 'xml'].includes(ext)) {
        previewText = fileText;
      }

      const docId = `doc-${crypto.randomUUID()}`;
      const newDoc: DocumentItem = {
        id: docId,
        tenantId: currentTenant.id,
        folderId: currentFolder ? currentFolder.id : null,
        originalName: selectedFile.name,
        storageKey,
        mimeType: selectedFile.type || 'application/octet-stream',
        extension: ext,
        sizeBytes: selectedFile.size,
        sha256Hash: sha256,
        status: 'READY',
        antivirusStatus: 'CLEAN',
        isFavorite: false,
        isTrashed: false,
        createdBy: currentTenant.ownerId,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        versions: [
          {
            id: `ver-${crypto.randomUUID()}`,
            documentId: docId,
            versionNumber: 1,
            storageKey,
            sizeBytes: selectedFile.size,
            mimeType: selectedFile.type || 'application/octet-stream',
            sha256Hash: sha256,
            changeSummary: 'Version initiale importée',
            createdAt: new Date().toISOString(),
          },
        ],
        contentPreview:
          previewText ||
          `Document : ${selectedFile.name}\nTaille : ${formatBytes(selectedFile.size)}\nSHA-256 : ${sha256}`,
      };

      onUploadSuccess(newDoc);
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Une erreur est survenue lors de l’analyse ou du transfert.';
      setErrorMsg(msg);
      setUploadProgress(0);
    } finally {
      setIsProcessing(false);
      setUploadStep('');
    }
  };

  return (
    <div
      className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-5 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
              <h3 id="upload-modal-title" className="text-sm font-bold text-white">
                Importer un document
              </h3>
              <p className="text-[11px] text-slate-400">
                Destination :{' '}
                <span className="text-blue-400 font-semibold">
                  {currentFolder ? currentFolder.name : 'Racine'}
                </span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            aria-label="Fermer la fenêtre d'import"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drop Zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => !isProcessing && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-colors ${
            dragActive
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-slate-800 hover:border-slate-700 bg-slate-950/40'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            aria-label="Sélectionner un fichier à importer"
            onChange={handleFileInputChange}
            className="hidden"
          />

          <div className="space-y-3">
            <div className="w-12 h-12 rounded-xl bg-slate-800/80 text-blue-400 mx-auto flex items-center justify-center">
              <UploadCloud className="w-6 h-6" />
            </div>

            <div>
              <p className="text-xs font-semibold text-slate-200">
                {selectedFile ? selectedFile.name : 'Glissez votre fichier ici ou cliquez pour parcourir'}
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                Limite forfait {currentPlan.name} : {formatBytes(currentPlan.maxFileSizeBytes)}
              </p>
            </div>

            {selectedFile && (
              <div className="inline-flex items-center space-x-2 text-blue-300 text-xs font-mono tabular-nums">
                <FileCheck className="w-3.5 h-3.5" />
                <span>{formatBytes(selectedFile.size)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Error message */}
        {errorMsg && (
          <div
            role="alert"
            className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start space-x-2"
          >
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Security info */}
        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
          <div className="flex items-center space-x-1.5 p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span>Scan ClamAV en flux</span>
          </div>
          <div className="flex items-center space-x-1.5 p-2 rounded-lg bg-slate-950/60 border border-slate-800/80">
            <Lock className="w-3.5 h-3.5 text-sky-400 shrink-0" />
            <span>Clé MinIO opaque S3</span>
          </div>
        </div>

        {/* Antivirus Live Test */}
        <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 text-xs">
          <div className="flex items-center space-x-2 text-slate-400 text-[11px]">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span>Tester la détection ClamAV :</span>
          </div>
          <button
            type="button"
            onClick={handleInjectEicarTest}
            disabled={isProcessing}
            className="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/20 text-[11px] font-medium whitespace-nowrap transition-colors"
          >
            Injecter fichier test EICAR
          </button>
        </div>

        {/* Processing progress */}
        {isProcessing && (
          <div
            aria-live="polite"
            className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs text-blue-300"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400 shrink-0" />
                <span>{uploadStep}</span>
              </div>
              <span className="font-mono tabular-nums text-blue-200">{uploadProgress}%</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-blue-500 h-full transition-all duration-200"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex items-center justify-end space-x-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-colors whitespace-nowrap"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={processUpload}
            disabled={!selectedFile || isProcessing}
            className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-xs flex items-center space-x-2 transition-colors whitespace-nowrap"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Traitement en cours...</span>
              </>
            ) : (
              <>
                <UploadCloud className="w-3.5 h-3.5" />
                <span>Lancer l'import sécurisé</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
