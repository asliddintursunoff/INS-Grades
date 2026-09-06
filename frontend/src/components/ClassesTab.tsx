import React, { useState, useEffect, useCallback } from 'react';
import { 
  BookOpen, 
  Trash2, 
  RotateCcw, 
  User, 
  MapPin, 
  CheckCircle, 
  AlertTriangle, 
  PlusCircle, 
  RefreshCw,
  X,
  Layers,
  GraduationCap
} from 'lucide-react';
import { StudentClass } from '../types';
import { apiCall } from '../api';
import { RetakeCourseModal } from './RetakeCourseModal';
import { useLanguage } from '../i18n';

interface ClassesTabProps {
  studentId: string;
  onClassesUpdated?: () => void;
  isPremium?: boolean;
  onRequirePremium?: (featureName: string) => void;
}

export const ClassesTab: React.FC<ClassesTabProps> = ({
  studentId,
  onClassesUpdated,
  isPremium = false,
  onRequirePremium,
}) => {
  const { t } = useLanguage();
  const [classes, setClasses] = useState<StudentClass[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Drop confirmation dialog state (replaces blocked window.confirm)
  const [dropConfirmClass, setDropConfirmClass] = useState<StudentClass | null>(null);

  // Retake modal state
  const [showRetakeModal, setShowRetakeModal] = useState(false);

  const fetchClasses = useCallback(() => {
    setLoading(true);
    apiCall<{ classes: StudentClass[] }>(`/api/students/${studentId}/classes/`)
      .then((res) => {
        setClasses(res.classes || []);
      })
      .catch((err) => {
        console.error(err);
        setNotification({ type: 'error', message: 'Failed to load courses list.' });
      })
      .finally(() => setLoading(false));
  }, [studentId]);

  useEffect(() => {
    fetchClasses();
  }, [fetchClasses]);

  const handleConfirmDrop = async () => {
    if (!dropConfirmClass) return;

    const classToDrop = dropConfirmClass;
    setActionLoadingId(classToDrop.class_id);
    setDropConfirmClass(null);

    try {
      const res = await apiCall<{ success: boolean; message: string }>(
        `/api/students/${studentId}/drop/`,
        'POST',
        { class_id: classToDrop.class_id }
      );

      setNotification({
        type: 'success',
        message: `${classToDrop.subject_full} (${classToDrop.subject_short}) was dropped successfully.`,
      });
      fetchClasses();
      if (onClassesUpdated) onClassesUpdated();
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Failed to drop course.',
      });
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleQuickRetake = async (c: StudentClass) => {
    setActionLoadingId(c.class_id);
    try {
      const res = await apiCall<{ success: boolean; message: string }>(
        `/api/students/${studentId}/retake/`,
        'POST',
        { class_id: c.class_id }
      );

      setNotification({
        type: 'success',
        message: `${c.subject_full} (${c.subject_short}) re-enrolled successfully.`,
      });
      fetchClasses();
      if (onClassesUpdated) onClassesUpdated();
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Failed to re-enroll course.',
      });
    } finally {
      setActionLoadingId(null);
    }
  };

  const activeClasses = classes.filter((c) => c.status === 'active');
  const droppedClasses = classes.filter((c) => c.status === 'dropped');

  return (
    <div className="space-y-4">
      {/* Top Banner & Retake Button */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-600" />
            {t('enrolled_courses_title')}
          </h2>
          <p className="text-xs text-slate-500 mt-1 max-w-xl leading-relaxed">
            {t('enrolled_courses_desc')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (!isPremium && onRequirePremium) {
                onRequirePremium(t('premium_only_retake'));
              } else {
                setShowRetakeModal(true);
              }
            }}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-all shadow-xs shrink-0"
          >
            <RotateCcw className="w-4 h-4" />
            <span>+ {t('add_retake')}</span>
          </button>
        </div>
      </div>

      {/* Notification toast */}
      {notification && (
        <div
          className={`p-3.5 rounded-xl border text-xs flex items-center justify-between shadow-2xs transition-all ${
            notification.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {notification.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-slate-400 hover:text-slate-700 font-bold ml-3"
          >
            ✕
          </button>
        </div>
      )}

      {/* Active Classes */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-500 px-1 font-medium">
          <span className="font-bold text-slate-700">{t('currently_enrolled')}</span>
          <span className="bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded-full font-semibold">
            {activeClasses.length} {t('courses_count')}
          </span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-slate-400">
            {t('loading_courses')}
          </div>
        ) : activeClasses.length === 0 ? (
          <div className="bg-white border border-dashed border-slate-300 rounded-2xl p-8 text-center space-y-3">
            <BookOpen className="w-8 h-8 text-slate-300 mx-auto" />
            <div className="text-xs text-slate-500">
              {t('no_active_courses')}
            </div>
            <button
              onClick={() => setShowRetakeModal(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-50 text-blue-700 font-bold text-xs hover:bg-blue-100 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              {t('register_retake')}
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {activeClasses.map((c) => (
              <div
                key={c.class_id}
                className="bg-white border border-slate-200 hover:border-slate-300 rounded-2xl p-4 flex flex-col justify-between shadow-xs transition-all"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 border border-blue-200">
                        {c.subject_short}
                      </span>
                      <h3 className="text-sm font-bold text-slate-900 leading-tight">
                        {c.subject_full}
                      </h3>
                    </div>

                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
                      {t('active_badge')}
                    </span>
                  </div>

                  <div className="text-xs text-slate-600 mb-3.5 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>
                      {t('professor_label')} <strong className="text-slate-800">{c.professor}</strong>
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-3 border-t border-slate-100 flex items-center justify-end">
                  <button
                    disabled={actionLoadingId === c.class_id}
                    onClick={() => {
                      if (!isPremium && onRequirePremium) {
                        onRequirePremium(t('premium_only_drop'));
                      } else {
                        setDropConfirmClass(c);
                      }
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold transition-colors disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>
                      {actionLoadingId === c.class_id ? 'Processing...' : t('drop_course')}
                    </span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Dropped Classes Section */}
      {droppedClasses.length > 0 && (
        <div className="space-y-3 pt-4">
          <div className="flex items-center justify-between text-xs font-bold text-slate-600 px-1">
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
              <span>{t('retake_courses')}:</span>
            </div>
            <span className="text-slate-400 font-normal">
              {droppedClasses.length} {t('dropped_badge').toLowerCase()}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {droppedClasses.map((c) => (
              <div
                key={c.class_id}
                className="bg-slate-50/80 border border-slate-200 rounded-2xl p-4 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold px-2 py-0.5 rounded-lg bg-slate-200 text-slate-700">
                        {c.subject_short}
                      </span>
                      <h3 className="text-sm font-semibold text-slate-600 line-through">
                        {c.subject_full}
                      </h3>
                    </div>

                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-200 text-slate-600 shrink-0">
                      {t('dropped_badge')}
                    </span>
                  </div>

                  <div className="text-xs text-slate-500 mb-3 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>{t('professor_label')} {c.professor}</span>
                  </div>
                </div>

                <div className="pt-2.5 border-t border-slate-200/60 flex items-center justify-end">
                  <button
                    disabled={actionLoadingId === c.class_id}
                    onClick={() => {
                      if (!isPremium && onRequirePremium) {
                        onRequirePremium(t('premium_only_retake'));
                      } else {
                        handleQuickRetake(c);
                      }
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors disabled:opacity-50 shadow-2xs"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>
                      {actionLoadingId === c.class_id ? '...' : t('reenroll_course')}
                    </span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Confirmation Dialog for Dropping Course */}
      {dropConfirmClass && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900">
                  {t('drop_confirm_title')}
                </h4>
                <p className="text-xs text-slate-500">
                  {dropConfirmClass.subject_full} ({dropConfirmClass.subject_short})
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              {t('drop_confirm_desc')}
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setDropConfirmClass(null)}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
              >
                {t('cancel_btn')}
              </button>
              <button
                onClick={handleConfirmDrop}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 transition-colors shadow-xs"
              >
                {t('confirm_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Retake Modal Wizard */}
      <RetakeCourseModal
        studentId={studentId}
        isOpen={showRetakeModal}
        onClose={() => setShowRetakeModal(false)}
        onSuccess={() => {
          fetchClasses();
          if (onClassesUpdated) onClassesUpdated();
        }}
      />
    </div>
  );
};
