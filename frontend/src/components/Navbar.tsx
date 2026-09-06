import React from 'react';
import { User, CheckCircle } from 'lucide-react';
import { Student } from '../types';
import { InsLogo } from './InsLogo';

interface NavbarProps {
  currentStudent: Student | null;
  onOpenPremium?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentStudent, onOpenPremium }) => {
  const isPremium = currentStudent?.is_premium || currentStudent?.plan === 'premium';

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-2xs w-full max-w-full overflow-hidden">
      <div className="max-w-5xl mx-auto px-3.5 py-2.5 sm:px-4 sm:py-3 w-full">
        <div className="flex items-center justify-between gap-2.5 w-full">
          {/* Logo & Title */}
          <div className="flex items-center gap-2">
            <InsLogo size="md" showSubtitle={false} />
          </div>

          {/* Right side: Free vs Premium Status Badge */}
          {currentStudent && (
            <div className="flex items-center gap-2 sm:gap-3">
              {isPremium ? (
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-gradient-to-r from-amber-400 via-amber-300 to-yellow-400 text-slate-950 text-xs font-black shadow-xs border border-amber-300">
                  <span>PREMIUM</span>
                  <span>⭐</span>
                </div>
              ) : (
                <button
                  onClick={onOpenPremium}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 hover:bg-amber-50 text-slate-700 hover:text-amber-800 text-xs font-bold border border-slate-200 hover:border-amber-300 transition-all shadow-2xs"
                  title="Click to view Premium benefits"
                >
                  <span className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Plan:</span>
                  <span className="font-extrabold text-slate-800">FREE</span>
                  <span className="text-[10px] text-amber-600 bg-amber-100/80 px-1.5 py-0.2 rounded font-semibold ml-0.5">
                    Upgrade ⭐
                  </span>
                </button>
              )}

              {/* Student Name */}
              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/80 rounded-xl px-2.5 py-1 text-xs">
                <div className="w-6 h-6 rounded-full bg-blue-600/10 text-blue-700 flex items-center justify-center font-bold text-[10px] shrink-0">
                  {currentStudent.full_name
                    ? currentStudent.full_name
                        .split(' ')
                        .map((n) => n[0])
                        .join('')
                        .slice(0, 2)
                        .toUpperCase()
                    : <User className="w-3.5 h-3.5" />}
                </div>
                <span className="font-bold text-slate-800 truncate max-w-[120px] sm:max-w-[160px] text-[11px] sm:text-xs">
                  {currentStudent.full_name.split(' ')[0]}
                </span>
                <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0" title="Verified Student" />
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
