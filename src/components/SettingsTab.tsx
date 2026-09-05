import React, { useState, useEffect } from 'react';
import { Bell, BellOff, Clock, ShieldCheck, UserCheck, Send, CheckCircle2, Lock } from 'lucide-react';
import { Student, NotificationSettings } from '../types';
import { apiCall } from '../api';

interface SettingsTabProps {
  student: Student;
  botUsername: string;
}

export const SettingsTab: React.FC<SettingsTabProps> = ({ student, botUsername }) => {
  const [settings, setSettings] = useState<NotificationSettings>({ enabled: true, minutes_before: 30 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiCall<NotificationSettings>(`/api/students/${student.student_id}/notification-settings/`)
      .then((res) => {
        setSettings({
          enabled: res.enabled !== undefined ? res.enabled : true,
          minutes_before: res.minutes_before || 30,
        });
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [student.student_id]);

  const updateSettings = async (newSettings: Partial<NotificationSettings>) => {
    const updated = { ...settings, ...newSettings };
    setSettings(updated);
    setSaving(true);
    try {
      await apiCall(`/api/students/${student.student_id}/notification-settings/`, 'PATCH', updated);
      setSavedMessage('Notification settings saved successfully!');
      setTimeout(() => setSavedMessage(null), 2500);
    } catch (err: any) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const minutesOptions = [5, 10, 15, 30, 45, 60];

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      {/* Settings Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-5">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Bell className="w-5 h-5 text-blue-600" />
            Telegram Notification Settings
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            The university bot will automatically dispatch class reminder notifications to your linked Telegram account before each lecture starts.
          </p>
        </div>

        {savedMessage && (
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{savedMessage}</span>
          </div>
        )}

        {/* Toggle Notification */}
        <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 border border-slate-200">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${settings.enabled ? 'bg-blue-100 text-blue-700' : 'bg-slate-200 text-slate-400'}`}>
              {settings.enabled ? <Bell className="w-5 h-5" /> : <BellOff className="w-5 h-5" />}
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900">
                Receive Class Reminders
              </div>
              <div className="text-xs text-slate-500">
                {settings.enabled ? 'Active: Telegram bot sends automated class alerts' : 'Disabled: Alerts are muted'}
              </div>
            </div>
          </div>

          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={settings.enabled}
              onChange={(e) => updateSettings({ enabled: e.target.checked })}
              className="sr-only peer"
              disabled={loading || saving}
            />
            <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>

        {/* Minutes Selector */}
        {settings.enabled && (
          <div className="space-y-2 pt-2">
            <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-blue-600" />
              <span>Reminder Timing (Minutes Before Class):</span>
            </label>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {minutesOptions.map((min) => (
                <button
                  key={min}
                  type="button"
                  onClick={() => updateSettings({ minutes_before: min })}
                  className={`py-2 px-3 rounded-xl text-xs font-semibold border transition-all ${
                    settings.minutes_before === min
                      ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {min} min
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Telegram Account Connection Status Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <Send className="w-4 h-4 text-blue-600" />
          Telegram Account Link
        </h3>

        {student.telegram_id ? (
          <div className="p-3.5 rounded-xl bg-emerald-50/70 border border-emerald-200 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2.5">
              <UserCheck className="w-5 h-5 text-emerald-600 shrink-0" />
              <div>
                <div className="font-bold text-emerald-900">
                  Account Linked: @{student.telegram_username || student.telegram_id}
                </div>
                <div className="text-[11px] text-emerald-700">
                  Telegram ID: {student.telegram_id}
                </div>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded-md bg-emerald-200/60 text-emerald-900 font-bold text-[11px]">
              Connected
            </span>
          </div>
        ) : (
          <div className="p-3.5 rounded-xl bg-amber-50/70 border border-amber-200 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <div className="font-bold text-amber-900">Telegram Link Status</div>
              <span className="px-2.5 py-1 rounded-md bg-amber-200/60 text-amber-900 font-bold text-[11px]">
                Pending Link
              </span>
            </div>
            <div className="text-[11px] text-amber-800">
              When starting the bot, send your Student ID: <strong>{student.student_id}</strong>.
              If your ID is not found in the database, contact administrator: <strong>@asliddin_tursunoff</strong>.
            </div>
          </div>
        )}
      </div>

      {/* Read-Only Profile Information Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Lock className="w-4 h-4 text-slate-400" />
            Official Academic Profile (Read Only)
          </h3>
          <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
            Verified Registrar Record
          </span>
        </div>

        <p className="text-xs text-slate-500">
          Personal information, student ID, and primary academic group are managed centrally by the university registrar and cannot be modified directly in the student portal.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
            <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">
              Student ID
            </span>
            <span className="text-xs font-bold text-slate-800 mt-0.5 block font-mono">
              {student.student_id}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
            <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">
              Full Name
            </span>
            <span className="text-xs font-bold text-slate-800 mt-0.5 block">
              {student.full_name}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
            <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">
              Primary Academic Group
            </span>
            <span className="text-xs font-bold text-slate-800 mt-0.5 block">
              {student.group_name}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
            <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">
              Academic Standing
            </span>
            <span className="text-xs font-bold text-slate-800 mt-0.5 block">
              Year {student.year_of_study || 2} Student
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
