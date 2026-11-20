import React, { useState } from 'react';
import {
  X,
  CreditCard,
  AlertTriangle,
  Download,
  FileText,
  ArrowRight,
  Loader2,
  ExternalLink,
  CheckCircle2,
} from 'lucide-react';
import { Plan, Tenant, InvoiceItem } from '../types';
import { formatBytes } from '../services/crypto';
import { apiClient, ApiError } from '../services/api';

interface BillingCheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetPlan: Plan | null;
  plans: Plan[];
  currentTenant: Tenant;
  invoices: InvoiceItem[];
}

export const BillingCheckoutModal: React.FC<BillingCheckoutModalProps> = ({
  isOpen,
  onClose,
  targetPlan,
  plans,
  currentTenant,
  invoices,
}) => {
  const [activeTab, setActiveTab] = useState<'checkout' | 'invoices'>('checkout');
  const [billingInterval, setBillingInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [checkoutSession, setCheckoutSession] = useState<{
    session_id: string;
    url: string;
    plan_id: string;
    billing_interval: string;
    amount_eur: number;
    status: string;
  } | null>(null);

  if (!isOpen || !targetPlan) return null;

  const currentPlanObj = plans.find((p) => p.id === currentTenant.planId);
  const isDowngrade =
    targetPlan.maxStorageBytes < (currentPlanObj?.maxStorageBytes ?? 0);
  const willExceedQuota =
    isDowngrade && currentTenant.usedBytes > targetPlan.maxStorageBytes;

  const yearlyTotal =
    typeof targetPlan.priceYearly === 'number' && targetPlan.priceYearly > 0
      ? targetPlan.priceYearly
      : targetPlan.priceMonthly * 10;

  const price =
    billingInterval === 'yearly'
      ? yearlyTotal.toFixed(2)
      : targetPlan.priceMonthly.toFixed(2);

  const handleStartCheckout = async () => {
    setIsProcessing(true);
    setErrorMsg(null);
    setCheckoutSession(null);
    try {
      const session = await apiClient.billing.checkout(currentTenant.id, {
        plan_id: targetPlan.id,
        billing_interval: billingInterval,
        success_url: window.location.href,
        cancel_url: window.location.href,
      });
      setCheckoutSession(session);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError
          ? err.detail
          : 'Impossible de créer la session Stripe Checkout.'
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownloadInvoice = (inv: InvoiceItem) => {
    const receiptPayload = JSON.stringify(
      {
        eventId: inv.id,
        eventType: inv.eventType,
        planId: inv.planId,
        planName: inv.planName,
        amountEur: inv.amountEur,
        status: inv.status,
        issuedAt: inv.createdAt,
        tenantId: currentTenant.id,
      },
      null,
      2
    );
    const blob = new Blob([receiptPayload], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement('a');
    link.href = url;
    link.download = `docuspace_billing_${inv.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Souscription & Facturation Stripe</h3>
              <p className="text-[11px] text-slate-400">
                Création de session Stripe Checkout et historique réel PostgreSQL.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer la facturation"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab switch */}
        <div className="px-5 pt-3 pb-0 border-b border-slate-800 flex items-center space-x-4 text-xs font-medium">
          <button
            type="button"
            onClick={() => setActiveTab('checkout')}
            className={`pb-2.5 transition-colors border-b-2 ${
              activeTab === 'checkout'
                ? 'border-purple-500 text-white font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Session de paiement Stripe
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('invoices')}
            className={`pb-2.5 transition-colors border-b-2 ${
              activeTab === 'invoices'
                ? 'border-purple-500 text-white font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Historique de facturation ({invoices.length})
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {activeTab === 'checkout' ? (
            <>
              <div className="p-4 rounded-xl bg-slate-950 border border-purple-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-white text-sm">{targetPlan.name}</span>
                    <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-semibold border border-purple-500/30">
                      {formatBytes(targetPlan.maxStorageBytes)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Jusqu'à {targetPlan.maxMembers} membre(s) • ClamAV • Historique {targetPlan.maxVersionsPerFile} versions
                  </p>
                </div>

                <div className="text-right shrink-0">
                  <div className="text-2xl font-extrabold text-white">
                    {targetPlan.priceMonthly === 0 ? '0€' : `${price}€`}
                    <span className="text-xs font-normal text-slate-400">
                      {targetPlan.priceMonthly > 0
                        ? billingInterval === 'yearly'
                          ? ' / an'
                          : ' / mois'
                        : ''}
                    </span>
                  </div>
                </div>
              </div>

              {targetPlan.priceMonthly > 0 && (
                <div className="flex items-center justify-center p-1 bg-slate-950 border border-slate-800 rounded-xl max-w-xs mx-auto text-xs">
                  <button
                    type="button"
                    onClick={() => setBillingInterval('monthly')}
                    className={`flex-1 py-1.5 rounded-lg font-medium transition-colors ${
                      billingInterval === 'monthly'
                        ? 'bg-purple-600 text-white font-bold'
                        : 'text-slate-400'
                    }`}
                  >
                    Facturation mensuelle
                  </button>
                  <button
                    type="button"
                    onClick={() => setBillingInterval('yearly')}
                    className={`flex-1 py-1.5 rounded-lg font-medium transition-colors ${
                      billingInterval === 'yearly'
                        ? 'bg-purple-600 text-white font-bold'
                        : 'text-slate-400'
                    }`}
                  >
                    Annuelle (-17%)
                  </button>
                </div>
              )}

              {willExceedQuota && (
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start space-x-3 text-xs text-amber-200">
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <strong className="block text-amber-300 font-semibold">
                      Avertissement de dépassement de quota :
                    </strong>
                    <p className="text-[11px] leading-relaxed">
                      Votre consommation actuelle ({formatBytes(currentTenant.usedBytes)}) dépasse la limite du forfait sélectionné ({formatBytes(targetPlan.maxStorageBytes)}).
                      L'espace passerait en lecture seule en cas de rétrogradation effective.
                    </p>
                  </div>
                </div>
              )}

              {errorMsg && (
                <div role="alert" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                  {errorMsg}
                </div>
              )}

              {checkoutSession && (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-3 text-xs">
                  <div className="flex items-center space-x-2 text-emerald-300 font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Session Stripe Checkout créée ({checkoutSession.session_id})</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    Finalisez le paiement sur Stripe Checkout. Le changement de forfait et de quota sera appliqué automatiquement après réception et vérification HMAC du webhook Stripe côté serveur.
                  </p>
                  <a
                    href={checkoutSession.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs transition-colors"
                  >
                    <span>Ouvrir la page de paiement Stripe</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              )}

              {targetPlan.priceMonthly > 0 ? (
                <div className="space-y-3">
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Aucune coordonnée bancaire n'est collectée directement dans l'application : le paiement est délégué à Stripe Checkout.
                  </p>
                  <button
                    type="button"
                    onClick={handleStartCheckout}
                    disabled={isProcessing}
                    className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-bold text-xs shadow-md transition-colors flex items-center justify-center space-x-2"
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Création de la session Stripe...</span>
                      </>
                    ) : (
                      <>
                        <span>Passer au paiement Stripe ({price}€)</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 space-y-2">
                  <p className="font-semibold text-white">Offre Gratuite (FREE)</p>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Le passage vers l'offre Gratuite s'effectue automatiquement lors de la résiliation de votre abonnement payant via Stripe (événement webhook <code className="text-slate-300">customer.subscription.deleted</code>).
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-3">
              {invoices.length > 0 ? (
                invoices.map((inv) => (
                  <div
                    key={inv.id}
                    className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="p-2 rounded-lg bg-slate-900 text-purple-400">
                        <FileText className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="font-semibold text-white">{inv.planName}</div>
                        <div className="text-[10px] text-slate-500">
                          {inv.eventType} • {inv.createdAt ? new Date(inv.createdAt).toLocaleDateString('fr-FR') : '—'}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      <span className="font-mono font-bold text-slate-200">{inv.amountEur.toFixed(2)}€</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {inv.status}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDownloadInvoice(inv)}
                        className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                        title="Télécharger le justificatif JSON"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-800 rounded-xl">
                  Aucun événement de facturation ou facture enregistré pour cet espace.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
