import React, { useState } from 'react';
import { Sparkles, Check, ArrowRight } from 'lucide-react';
import { Student } from '../types';
import { useLanguage } from '../i18n';
import { formatDateDDMMYYYY } from '../utils/date';
import { PaymentModal } from './PaymentModal';

interface PremiumTabProps {
  student: Student;
  onPremiumUpdated?: () => void;
}

export const PremiumTab: React.FC<PremiumTabProps> = ({ student, onPremiumUpdated }) => {
  const { t } = useLanguage();
  const isPremium = student.is_premium || student.plan === 'premium';
  const [showPaymentModal, setShowPaymentModal] = useState(false);

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
                  <span>{t('plan_free')}</span>
                )}
              </div>
            </div>
          </div>

          <div className="text-right">
            {isPremium ? (
              <div className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-gradient-to-r from-amber-400 to-yellow-400 text-slate-950 text-xs font-black shadow-2xs border border-amber-300">
                <span>PREMIUM</span>
                <span>⭐</span>
              </div>
            ) : (
              <>
                <div className="text-base font-black text-slate-900">
                  {t('premium_price')}
                </div>
                <div className="text-[11px] text-slate-400 font-normal">
                  {t('premium_period')}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Active Premium Banner if already subscribed */}
        {isPremium && (
          <div className="p-3.5 rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200 text-left space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-800 font-bold text-xs">
              <Check className="w-4 h-4 text-emerald-600" />
              <span>{t('premium_active_title')}</span>
            </div>
            <p className="text-[11px] text-emerald-700 leading-relaxed">
              {t('premium_active_desc')}
            </p>
            {student.premium_expires_at && (
              <div className="text-[11px] font-bold text-emerald-900 pt-1">
                {t('premium_expires_label')} {formatDateDDMMYYYY(student.premium_expires_at)}
              </div>
            )}
          </div>
        )}

        {/* 5 Persuasive Features */}
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

          <div className="flex items-start gap-3">
            <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3.5 h-3.5" />
            </div>
            <p className="text-xs font-semibold text-slate-700 leading-snug">
              {t('premium_feat4')}
            </p>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3.5 h-3.5" />
            </div>
            <p className="text-xs font-semibold text-slate-700 leading-snug">
              {t('premium_feat5')}
            </p>
          </div>
        </div>

        {/* Action Button */}
        <div className="pt-2 space-y-3">
          {isPremium ? (
            <button
              onClick={() => setShowPaymentModal(true)}
              className="w-full py-2.5 px-4 rounded-2xl bg-amber-50 hover:bg-amber-100 border border-amber-300 text-amber-900 font-bold text-xs shadow-2xs flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
            >
              <span>{t('premium_extend_btn')}</span>
              <ArrowRight className="w-4 h-4 text-amber-700" />
            </button>
          ) : (
            <button
              onClick={() => setShowPaymentModal(true)}
              className="w-full py-3 px-4 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-xs flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
            >
              <span>{t('premium_btn')}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          )}

          <div className="text-center text-[11px] text-slate-400 pt-1">
            <a
              href="https://t.me/asliddin_tursunoff"
              target="_blank"
              rel="noreferrer"
              className="text-slate-500 hover:text-blue-600 transition-colors"
            >
              {t('contact_support')}
            </a>
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
