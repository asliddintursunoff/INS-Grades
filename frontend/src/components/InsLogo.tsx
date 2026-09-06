import React from 'react';

interface InsLogoProps {
  size?: 'sm' | 'md' | 'lg';
  showSubtitle?: boolean;
}

export const InsLogo: React.FC<InsLogoProps> = ({ size = 'md', showSubtitle = true }) => {
  const iconSizes = {
    sm: 'w-7 h-7',
    md: 'w-9 h-9 sm:w-10 sm:h-10',
    lg: 'w-12 h-12',
  };

  const titleSizes = {
    sm: 'text-sm font-bold',
    md: 'text-base sm:text-lg font-black',
    lg: 'text-xl sm:text-2xl font-black',
  };

  return (
    <div className="flex items-center gap-2.5">
      {/* Custom Ins Grades Monogram Badge */}
      <div
        className={`${iconSizes[size]} rounded-xl bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 text-white flex items-center justify-center shadow-xs border border-blue-400/30 shrink-0 relative overflow-hidden`}
      >
        {/* Subtle decorative glow */}
        <div className="absolute inset-0 bg-radial from-white/20 to-transparent opacity-60 pointer-events-none" />
        
        {/* Monogram */}
        <div className="flex flex-col items-center justify-center leading-none">
          <span className="font-black tracking-tighter text-[13px] sm:text-[15px] text-white">
            INS
          </span>
          <span className="text-[7px] font-bold text-sky-200 tracking-widest uppercase mt-[1px]">
            GRADES
          </span>
        </div>
      </div>

      <div className="flex flex-col">
        <h1 className={`${titleSizes[size]} tracking-tight text-slate-900 leading-none`}>
          INS grades
        </h1>
      </div>
    </div>
  );
};
