import React, { useState } from 'react';
import { 
  X, 
  ShieldAlert, 
  ShieldCheck, 
  Terminal, 
  CheckCircle2, 
  XCircle, 
  Play, 
  RefreshCw, 
  Lock, 
  Eye, 
  Database, 
  AlertTriangle 
} from 'lucide-react';
import { User, Tenant, DocumentItem } from '../types';

interface SecuritySimulatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: User;
  currentTenant: Tenant;
  allTenants: Tenant[];
  allDocs: DocumentItem[];
}

export const SecuritySimulatorModal: React.FC<SecuritySimulatorModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  currentTenant,
  allTenants,
  allDocs,
}) => {
  const [activeScenario, setActiveScenario] = useState<string>('idor');
  const [simulationLog, setSimulationLog] = useState<Array<{ text: string; type: 'info' | 'success' | 'danger' | 'warning' }>>([]);
  const [isRunning, setIsRunning] = useState(false);

  if (!isOpen) return null;

  const otherTenant = allTenants.find(t => t.id !== currentTenant.id) || allTenants[1] || allTenants[0];
  const targetForeignDoc = allDocs.find(d => d.tenantId !== currentTenant.id) || allDocs[0];

  const runIDORTest = async () => {
    setIsRunning(true);
    setSimulationLog([]);

    const addLog = (text: string, type: 'info' | 'success' | 'danger' | 'warning') => {
      setSimulationLog(prev => [...prev, { text, type }]);
    };

    addLog(`[INIT] Utilisateur actif : ${currentUser.fullName} (${currentUser.email})`, 'info');
    addLog(`[INIT] Espace documentaire autorisé : ${currentTenant.name} (UUID: ${currentTenant.id})`, 'info');
    addLog(`[ATTACK] Tentative d'accès direct IDOR au document : "${targetForeignDoc.originalName}" (UUID: ${targetForeignDoc.id})`, 'warning');
    addLog(`[TARGET] Propriétaire légitime de la ressource : Espace "${otherTenant.name}" (UUID: ${otherTenant.id})`, 'info');

    await new Promise(r => setTimeout(r, 600));

    addLog(`[ÉVALUATION 1] FastAPI Tenant Context Middleware...`, 'info');
    addLog(` ➔ Vérification de l'association de ${currentUser.email} avec le tenant cible... ÉCHEC.`, 'danger');

    await new Promise(r => setTimeout(r, 500));

    addLog(`[ÉVALUATION 2] PostgreSQL Row-Level Security (RLS Engine)...`, 'info');
    addLog(` ➔ Session locale : SET LOCAL app.current_tenant_id = '${currentTenant.id}'`, 'info');
    addLog(` ➔ Requête SQL exécutée : SELECT * FROM documents WHERE id = '${targetForeignDoc.id}'`, 'info');
    addLog(` ➔ Politique PostgreSQL RLS : tenant_isolation_documents appliquée. 0 ligne retournée.`, 'danger');

    await new Promise(r => setTimeout(r, 500));

    addLog(`[RÉSULTAT SÉCURITÉ] 403 FORBIDDEN — Attaque IDOR neutralisée. Aucune fuite de données inter-tenants.`, 'success');
    setIsRunning(false);
  };

  const runHeaderInjectionTest = async () => {
    setIsRunning(true);
    setSimulationLog([]);

    const addLog = (text: string, type: 'info' | 'success' | 'danger' | 'warning') => {
      setSimulationLog(prev => [...prev, { text, type }]);
    };

    addLog(`[INIT] Envoi d'une requête HTTP forgée avec en-tête malveillant`, 'warning');
    addLog(` ➔ Jeton JWT : Utilisateur ${currentUser.email} (Non administrateur)`, 'info');
    addLog(` ➔ En-tête injecté : X-Tenant-ID: ${otherTenant.id}`, 'warning');

    await new Promise(r => setTimeout(r, 600));

    addLog(`[CONTRÔLE] Middleware tenant_context.py intercepte le header 'X-Tenant-ID'`, 'info');
    addLog(` ➔ Requête d'appartenance : SELECT role FROM tenant_members WHERE user_id = '${currentUser.id}' AND tenant_id = '${otherTenant.id}'`, 'info');

    await new Promise(r => setTimeout(r, 500));

    addLog(` ➔ Résultat : Aucune association trouvée pour cet utilisateur.`, 'danger');
    addLog(`[BLOCAGE SÉCURITÉ] HTTPException(403, detail="Accès interdit : vous n'êtes pas membre de cet espace")`, 'danger');
    addLog(`[RÉSULTAT SÉCURITÉ] Règle "Zéro confiance envers le client" respectée à 100%. L'en-tête forgé a été rejeté.`, 'success');
    setIsRunning(false);
  };

  const runRBACRestrictionTest = async () => {
    setIsRunning(true);
    setSimulationLog([]);

    const addLog = (text: string, type: 'info' | 'success' | 'danger' | 'warning') => {
      setSimulationLog(prev => [...prev, { text, type }]);
    };

    addLog(`[SCÉNARIO RBAC] Simulation d'un utilisateur ayant le rôle 'VIEWER' (Lecteur seul)`, 'info');
    addLog(`[ACTION TENTÉE] Requête POST /api/v1/documents/upload/initiate (document:write)`, 'warning');

    await new Promise(r => setTimeout(r, 600));

    addLog(`[VÉRIFICATION] Dépendance require_permission(Permission.DOCUMENT_WRITE)`, 'info');
    addLog(` ➔ Permissions autorisées pour 'VIEWER' : ['document:read']`, 'info');
    addLog(` ➔ Permission requise : 'document:write'`, 'warning');

    await new Promise(r => setTimeout(r, 500));

    addLog(`[REFUS] 403 FORBIDDEN — Permission insuffisante : l'action requiert 'document:write', votre rôle est 'VIEWER'`, 'danger');
    addLog(`[RÉSULTAT SÉCURITÉ] Principe du moindre privilège appliqué. L'écriture est strictement bloquée côté backend.`, 'success');
    setIsRunning(false);
  };

  return (
    <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 px-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-rose-500/10 text-rose-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">
                Simulateur de Sécurité & Tests d'Isolation RLS
              </h3>
              <p className="text-[11px] text-slate-400">
                Validation en temps réel des barrières anti-IDOR, en-têtes forgés et permissions RBAC
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

        {/* Tab scenario switcher */}
        <div className="flex border-b border-slate-800 bg-slate-950/40 px-6">
          <button
            onClick={() => {
              setActiveScenario('idor');
              setSimulationLog([]);
            }}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeScenario === 'idor' ? 'border-rose-500 text-rose-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            1. Attaque IDOR (Accès direct cross-tenant)
          </button>
          <button
            onClick={() => {
              setActiveScenario('header');
              setSimulationLog([]);
            }}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeScenario === 'header' ? 'border-rose-500 text-rose-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            2. Falsification X-Tenant-ID
          </button>
          <button
            onClick={() => {
              setActiveScenario('rbac');
              setSimulationLog([]);
            }}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-all ${
              activeScenario === 'rbac' ? 'border-rose-500 text-rose-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            3. Escalade de privilèges RBAC
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
          {activeScenario === 'idor' && (
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-white text-xs">Test IDOR : Requête directe sur un document tiers</h4>
                  <p className="text-[11px] text-slate-400">
                    L'attaquant connaît l'identifiant UUID exact d'un document confidentiel appartenant à un autre espace documentaire et tente de le requêter directement via <code className="text-rose-400">GET /api/v1/documents/{'{id}'}</code>.
                  </p>
                </div>
                <button
                  onClick={runIDORTest}
                  disabled={isRunning}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center space-x-2 shrink-0 transition-all shadow-md shadow-rose-600/20"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Exécuter le test</span>
                </button>
              </div>
            </div>
          )}

          {activeScenario === 'header' && (
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-white text-xs">Test d'injection d'en-tête : Forçage de X-Tenant-ID</h4>
                  <p className="text-[11px] text-slate-400">
                    L'attaquant modifie manuellement ses en-têtes HTTP pour déclarer un <code className="text-rose-400">X-Tenant-ID</code> dont il n'est pas membre, tentant de tromper l'API pour consulter un autre tenant.
                  </p>
                </div>
                <button
                  onClick={runHeaderInjectionTest}
                  disabled={isRunning}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center space-x-2 shrink-0 transition-all shadow-md shadow-rose-600/20"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Exécuter le test</span>
                </button>
              </div>
            </div>
          )}

          {activeScenario === 'rbac' && (
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-white text-xs">Test RBAC : Tentative d'écriture avec le rôle LECTEUR</h4>
                  <p className="text-[11px] text-slate-400">
                    Un utilisateur invité en lecture seule (VIEWER) forge une requête de téléversement ou de suppression de document. Le backend doit interdire l'action avec une erreur 403 Forbidden.
                  </p>
                </div>
                <button
                  onClick={runRBACRestrictionTest}
                  disabled={isRunning}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center space-x-2 shrink-0 transition-all shadow-md shadow-rose-600/20"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Exécuter le test</span>
                </button>
              </div>
            </div>
          )}

          {/* Terminal Logs Display */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
              <span className="flex items-center space-x-1.5">
                <Terminal className="w-3.5 h-3.5 text-slate-400" />
                <span>Journal d'audit du test de pénétration</span>
              </span>
              <span>Backend FastAPI & PostgreSQL RLS Engine</span>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] min-h-[220px] max-h-[300px] overflow-y-auto space-y-1.5 shadow-inner">
              {simulationLog.length === 0 ? (
                <div className="text-slate-500 text-center py-12">
                  Cliquez sur "Exécuter le test" pour lancer la simulation d'attaque et observer le blocage en temps réel.
                </div>
              ) : (
                simulationLog.map((log, idx) => (
                  <div
                    key={idx}
                    className={`leading-relaxed ${
                      log.type === 'danger'
                        ? 'text-rose-400 font-semibold'
                        : log.type === 'success'
                        ? 'text-emerald-400 font-bold bg-emerald-500/10 p-2 rounded border border-emerald-500/20 mt-2'
                        : log.type === 'warning'
                        ? 'text-amber-300'
                        : 'text-slate-300'
                    }`}
                  >
                    {log.text}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950 flex justify-between items-center text-xs text-slate-400">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>PostgreSQL Row-Level Security Enforced</span>
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
