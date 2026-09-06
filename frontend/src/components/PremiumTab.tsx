import React, { useState } from 'react';
import { Sparkles, Check, ArrowRight } from 'lucide-react';
import { Student } from '../types';
import { apiCall } from '../api';
import { useLanguage } from '../i18n';
import { PaymentModal } from './PaymentModal';

interface PremiumTabProps {
  student: Student;
  onPremiumUpdated?: () => void;
}

export const PremiumTab: React.FC<PremiumTabProps> = ({ student, onPremiumUpdated }) => {
  const { t } = useLanguage();
  const isPremium = student.is_premium || student.plan === 'premium';
  const [loading, setLoading] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);

  const handleToggleDemo = async (activate: boolean) => {
    setLoading(true);
    try {
      await apiCall(
        `/api/students/${student.student_id}/premium/`,
        'POST',
        {
          action: activate ? 'activate' : 'deactivate',
          duration_days: 30,
        }
      );
      if (onPremiumUpdated) onPremiumUpdated();
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto py-6 px-3">
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center font-bold">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-slate-900 leading-tight">
                {t('premium_title')}
              </h2>
              <div className="text-xs text-slate-500 font-medium">
                {isPremium ? (
                  <span className="text-emerald-600 font-bold">✓ {t('premium_active')}</span>
                ) : (
                  <span>Free Plan</span>
                )}
              </div>
            </div>
          </div>

          <div className="text-right">
            <div className="text-base font-black text-slate-900">
              {t('premium_price')}
            </div>
            <div className="text-[11px] text-slate-400 font-normal">
              {t('premium_period')}
            </div>
          </div>
        </div>

        {/* 3 Simple Features */}
        <div className="space-y-3 py-1">
          <div className="flex items-start gap-3">
            <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3.5 h-3.5" />
            </div>
            <p className="text-xs font-semibold text-slate-700 leading-snug">
              {t('premium_feat1')}
            </p>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3.5 h-3.5" />
            </div>
            <p className="text-xs font-semibold text-slate-700 leading-snug">
              {t('premium_feat2')}
            </p>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3.5 h-3.5" />
            </div>
            <p className="text-xs font-semibold text-slate-700 leading-snug">
              {t('premium_feat3')}
            </p>
          </div>
        </div>

        {/* Action Button */}
        <div className="pt-2 space-y-3">
          <button
            onClick={() => setShowPaymentModal(true)}
            className="w-full py-3 px-4 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-xs flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
          >
            <span>{t('premium_btn')}</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
            <a
              href="https://t.me/asliddin_tursunoff"
              target="_blank"
              rel="noreferrer"
              className="text-slate-500 hover:text-blue-600 transition-colors"
            >
              Savollar bormi? @asliddin_tursunoff
            </a>

            {/* Test switcher */}
            <button
              onClick={() => handleToggleDemo(!isPremium)}
              disabled={loading}
              className="text-slate-400 hover:text-slate-700 underline transition-colors"
            >
              {loading
                ? '...'
                : isPremium
                ? t('premium_demo_free')
                : t('premium_demo_prem')}
            </button>
          </div>
        </div>
      </div>

      {/* Live P2P Payment Verification Modal */}
      <PaymentModal
        isOpen={showPaymentModal}
        onClose={() => setShowPaymentModal(false)}
        studentId={student.student_id}
        onPaymentSuccess={() => {
          if (onPremiumUpdated) onPremiumUpdated();
        }}
      />
    </div>
  );
};
