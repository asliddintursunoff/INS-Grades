import React from 'react';
import { BookOpen } from 'lucide-react';
import { useLanguage } from '../i18n';

export const HomeworkTab: React.FC = () => {
  const { t } = useLanguage();

  return (
    <div className="max-w-md mx-auto py-12 px-4 text-center">
      <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-xs space-y-4">
        <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto border border-blue-100">
          <BookOpen className="w-7 h-7" />
        </div>

        <div className="space-y-2">
          <h2 className="text-lg font-extrabold text-slate-900">
            {t('homework_title')}
          </h2>
          <p className="text-sm font-medium text-slate-600 leading-relaxed max-w-xs mx-auto">
            {t('homework_msg')}
          </p>
        </div>
      </div>
    </div>
  );
};
