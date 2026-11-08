import React, { useState } from 'react';
import { 
  X, 
  Server, 
  Database, 
  ShieldCheck, 
  Code, 
  Terminal, 
  Layers, 
  Copy, 
  Check, 
  CheckCircle2, 
  FileText 
} from 'lucide-react';

interface ArchitectureModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ArchitectureModal: React.FC<ArchitectureModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'stack' | 'api' | 'sql' | 'docker'>('stack');
  const [copiedCmd, setCopiedCmd] = useState(false);

  if (!isOpen) return null;

  const debianCommands = `# 1. Préparation de la machine Debian 12
sudo apt update && sudo apt install -y curl docker.io docker-compose-plugin
sudo systemctl enable --now docker

# 2. Cloner et configurer DocuSpace
git clone https://github.com/docuspace/docuspace.git /opt/docuspace
cd /opt/docuspace
cp .env.example .env

# 3. Démarrage des conteneurs
docker compose up -d --build

# 4. Application des migrations Alembic (PostgreSQL RLS)
docker compose exec backend alembic upgrade head`;

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(debianCommands);
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const apiEndpoints = [
    { method: 'POST', path: '/api/v1/auth/register', desc: 'Inscription & création atomique de l’espace personnel', tag: 'Auth' },
    { method: 'POST', path: '/api/v1/auth/login', desc: 'Authentification Argon2id & cookies HttpOnly sécurisés', tag: 'Auth' },
    { method: 'POST', path: '/api/v1/auth/logout', desc: 'Révocation de session et purge des cookies', tag: 'Auth' },
    { method: 'GET',  path: '/api/v1/auth/me', desc: 'Profil authentifié avec validation de jeton JWT', tag: 'Auth' },
    { method: 'GET',  path: '/api/v1/tenants/current', desc: 'Quota de stockage & état de l’espace actif', tag: 'Tenants' },
    { method: 'GET',  path: '/api/v1/tenants/my-tenants', desc: 'Liste des espaces multi-tenants autorisés', tag: 'Tenants' },
    { method: 'GET',  path: '/api/v1/documents/folders', desc: 'Navigation arborescente isolée par tenant', tag: 'Documents' },
    { method: 'POST', path: '/api/v1/documents/folders', desc: 'Création de sous-dossier avec contrôle de cycles', tag: 'Documents' },
    { method: 'GET',  path: '/api/v1/documents/documents', desc: 'Filtres, tri et pagination des métadonnées', tag: 'Documents' },
    { method: 'GET',  path: '/api/v1/health', desc: 'Sonde de santé PostgreSQL, MinIO et ClamAV', tag: 'Système' },
  ];

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 px-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">
                Architecture DocuSpace — Monolithe Modulaire Multi-Tenant
              </h3>
              <p className="text-[11px] text-slate-400">
                Phase 1 : Docker Compose, FastAPI, PostgreSQL RLS, MinIO S3 & ClamAV
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

        {/* Tab switcher */}
        <div className="flex border-b border-slate-800 bg-slate-950/40 px-6">
          <button
            onClick={() => setActiveTab('stack')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'stack' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Stack & Principes
          </button>
          <button
            onClick={() => setActiveTab('api')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'api' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Endpoints REST API v1
          </button>
          <button
            onClick={() => setActiveTab('sql')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'sql' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Schéma PostgreSQL & RLS
          </button>
          <button
            onClick={() => setActiveTab('docker')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'docker' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Déploiement Debian & Docker
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 text-xs">
          {activeTab === 'stack' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                  <div className="flex items-center space-x-2 text-indigo-400 font-bold">
                    <Layers className="w-4 h-4" />
                    <span>Modèle Monolithe Modulaire</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed text-[11px]">
                    Séparation stricte des couches : API FastAPI, Pydantic v2 pour la validation, SQLAlchemy 2 (asyncpg) pour la persistance, et interface abstraite StorageProvider prête pour MinIO et AWS S3.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                  <div className="flex items-center space-x-2 text-emerald-400 font-bold">
                    <ShieldCheck className="w-4 h-4" />
                    <span>Isolation Multi-Tenant & RLS</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed text-[11px]">
                    Double barrière de sécurité : validation de l'appartenance de l'utilisateur au tenant côté backend, couplée aux politiques <strong>Row-Level Security</strong> de PostgreSQL injectées dans chaque transaction.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                  <div className="flex items-center space-x-2 text-sky-400 font-bold">
                    <Server className="w-4 h-4" />
                    <span>Sécurité Antivirus Fail-Closed</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed text-[11px]">
                    Intégration ClamAV en flux continu. Aucun fichier n'est téléchargeable sans validation préalable. Détection réelle des signatures MIME pour contrer les faux types d'extension.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                  <div className="flex items-center space-x-2 text-purple-400 font-bold">
                    <Database className="w-4 h-4" />
                    <span>Gestion des Quotas Transactionnels</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed text-[11px]">
                    Réservation atomique des octets avant streaming pour empêcher tout dépassement de quota lors d'uploads simultanés. Forfaits configurables (500 Mo, 20 Go, 100 Go).
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400 space-y-1">
                <span className="font-semibold text-white">Arborescence complète générée :</span>
                <p className="font-mono text-[10px] text-slate-300">
                  docuspace/ (backend/app/api/v1/routes, models, schemas, core, migrations, infrastructure/docker, nginx, scripts/init, backup, restore, docs/)
                </p>
              </div>
            </div>
          )}

          {activeTab === 'api' && (
            <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-950">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                  <tr>
                    <th className="p-3 pl-4">Méthode</th>
                    <th className="p-3">Chemin Endpoint</th>
                    <th className="p-3">Description Fonctionnelle</th>
                    <th className="p-3">Module</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {apiEndpoints.map((ep, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/60">
                      <td className="p-3 pl-4 font-bold text-sky-400">{ep.method}</td>
                      <td className="p-3 text-slate-200">{ep.path}</td>
                      <td className="p-3 text-slate-400 font-sans">{ep.desc}</td>
                      <td className="p-3 text-indigo-400">{ep.tag}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'sql' && (
            <div className="space-y-4">
              <p className="text-slate-300 text-xs">
                Politiques de Row-Level Security (RLS) PostgreSQL appliquées dans <code className="text-blue-400 font-mono">scripts/init/init_db.sql</code> et migrations Alembic :
              </p>
              <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-emerald-300 overflow-x-auto leading-relaxed">
{`-- Activation RLS sur les tables sensibles
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE storage_usage ENABLE ROW LEVEL SECURITY;

-- Politique d'isolation stricte par tenant
CREATE POLICY tenant_isolation_documents ON documents
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID 
        OR current_setting('app.is_superuser', true) = 'true'
    );`}
              </pre>
            </div>
          )}

          {activeTab === 'docker' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">
                  Commandes de lancement sur Debian 12 (Bookworm)
                </span>
                <button
                  onClick={handleCopyCmd}
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center space-x-1.5 transition-colors"
                >
                  {copiedCmd ? <Check className="w-3.5 h-3.5 text-emerald-300" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedCmd ? 'Copié !' : 'Copier les commandes'}</span>
                </button>
              </div>

              <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-sky-300 overflow-x-auto leading-relaxed">
                {debianCommands}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950 flex justify-end">
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
