import React from 'react';
import { User, CheckCircle } from 'lucide-react';
import { Student } from '../types';
import { InsLogo } from './InsLogo';

interface NavbarProps {
  currentStudent: Student | null;
}

export const Navbar: React.FC<NavbarProps> = ({ currentStudent }) => {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-2xs w-full max-w-full overflow-hidden">
      <div className="max-w-5xl mx-auto px-3.5 py-2.5 sm:px-4 sm:py-3 w-full">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5 w-full">
          {/* Logo, Title & Powered By */}
          <div className="flex items-center justify-between w-full sm:w-auto">
            <InsLogo size="md" showSubtitle={true} />
            
            {/* On mobile: compact group tag */}
            {currentStudent && (
              <div className="sm:hidden flex items-center gap-1.5">
                <span className="bg-blue-50 text-blue-700 text-[11px] font-bold px-2 py-0.5 rounded-md border border-blue-200">
                  {currentStudent.group_name}
                </span>
              </div>
            )}
          </div>

          {/* Right side: Showing ONLY our authenticated student profile */}
          {currentStudent && (
            <div className="flex items-center gap-2.5 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs w-full sm:w-auto justify-between sm:justify-start">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full bg-blue-600/10 border border-blue-200 text-blue-700 flex items-center justify-center font-bold text-xs shrink-0">
                  {currentStudent.full_name
                    ? currentStudent.full_name
                        .split(' ')
                        .map((n) => n[0])
                        .join('')
                        .slice(0, 2)
                        .toUpperCase()
                    : <User className="w-4 h-4" />}
                </div>
                <div className="flex flex-col min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-slate-900 leading-tight truncate">
                      {currentStudent.full_name}
                    </span>
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0" title="Verified Profile" />
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500 truncate">
                    <span className="font-mono text-slate-600">ID: {currentStudent.student_id}</span>
                    <span>•</span>
                    <span className="text-blue-600 font-semibold">{currentStudent.group_name}</span>
                    <span>•</span>
                    <span className="text-slate-500 font-medium">Year {currentStudent.year_of_study || 2}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
