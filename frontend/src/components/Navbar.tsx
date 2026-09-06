import React from 'react';
import { Student } from '../types';
import { InsLogo } from './InsLogo';
import { useLanguage } from '../i18n';

interface NavbarProps {
  currentStudent: Student | null;
  onOpenPremium?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentStudent, onOpenPremium }) => {
  const { language, setLanguage, t } = useLanguage();
  const isPremium = currentStudent?.is_premium || currentStudent?.plan === 'premium';

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-2xs w-full max-w-full overflow-hidden">
      <div className="max-w-5xl mx-auto px-2.5 py-2 sm:px-4 sm:py-3 w-full">
        <div className="flex items-center justify-between gap-1.5 sm:gap-2.5 w-full">
          {/* Left: Logo & Language Selector */}
          <div className="flex items-center gap-2 sm:gap-3">
            <InsLogo size="md" showSubtitle={false} />

            {/* Language Switcher */}
            <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200/80">
              {(['en', 'uz', 'ru'] as const).map((lang) => (
                <button
                  key={lang}
                  onClick={() => setLanguage(lang)}
                  className={`px-1.5 py-0.5 text-[10px] sm:text-[11px] font-bold rounded-md transition-all uppercase ${
                    language === lang
                      ? 'bg-white text-blue-700 shadow-2xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {lang}
                </button>
              ))}
            </div>
          </div>

          {/* Right side: Free vs Premium Status Badge */}
          {currentStudent && (
            <div className="flex items-center gap-1.5 sm:gap-2.5">
              {isPremium ? (
                <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gradient-to-r from-amber-400 via-amber-300 to-yellow-400 text-slate-950 text-[11px] sm:text-xs font-black shadow-xs border border-amber-300 shrink-0">
                  <span>PREMIUM</span>
                  <span>⭐</span>
                </div>
              ) : (
                <button
                  onClick={onOpenPremium}
                  className="inline-flex items-center gap-1 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full bg-slate-100 hover:bg-amber-50 text-slate-700 hover:text-amber-800 text-[11px] sm:text-xs font-bold border border-slate-200 hover:border-amber-300 transition-all shadow-2xs shrink-0"
                  title="Click to view Premium benefits"
                >
                  <span className="font-extrabold text-slate-800">{t('plan_free')}</span>
                  <span className="text-[10px] text-amber-700 bg-amber-100 px-1 py-0.2 rounded font-semibold ml-0.5">
                    {t('upgrade')} ⭐
                  </span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
