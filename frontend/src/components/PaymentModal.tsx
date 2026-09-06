import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  X, 
  Copy, 
  Check, 
  Clock, 
  Sparkles, 
  AlertCircle, 
  RefreshCw,
  HelpCircle,
  ShieldCheck,
  CreditCard,
  Wifi
} from 'lucide-react';
import { apiCall } from '../api';
import { useLanguage } from '../i18n';
import { PremiumCelebration } from './PremiumCelebration';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  studentId: string;
  onPaymentSuccess?: () => void;
}

interface PaymentData {
  transaction_id: string;
  base_amount: number;
  salt: number;
  total_amount: number;
  formatted_amount: string;
  card_number: string;
  card_holder: string;
  expires_at: string;
  seconds_remaining: number;
  status: 'pending' | 'completed' | 'expired' | 'cancelled';
}

export const PaymentModal: React.FC<PaymentModalProps> = ({
  isOpen,
  onClose,
  studentId,
  onPaymentSuccess,
}) => {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paymentData, setPaymentData] = useState<PaymentData | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(300);
  const [paymentStatus, setPaymentStatus] = useState<'initiating' | 'pending' | 'completed' | 'expired'>('initiating');
  const [copiedAmount, setCopiedAmount] = useState(false);
  const [copiedCard, setCopiedCard] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<any>(null);
  const pollingRef = useRef<any>(null);

  // Initialize Payment Transaction
  const startPayment = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPaymentStatus('initiating');

    try {
      const res = await apiCall<PaymentData & { success: boolean; error?: string }>(
        '/api/payments/create/',
        'POST',
        { student_id: studentId }
      );

      if (res && res.transaction_id) {
        setPaymentData(res);
        setSecondsRemaining(res.seconds_remaining || 300);
        setPaymentStatus('pending');
      } else {
        setError(res.error || 'Failed to create payment transaction.');
      }
    } catch (err: any) {
      setError(err.message || 'Error connecting to payment server.');
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => {
    if (isOpen) {
      startPayment();
    } else {
      // Cleanup on modal close
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      if (timerRef.current) clearInterval(timerRef.current);
      if (pollingRef.current) clearInterval(pollingRef.current);
    }
  }, [isOpen, startPayment]);

  // Status checker function
  const checkStatus = useCallback(async (txId: string) => {
    try {
      const res = await apiCall<{ status: string; seconds_remaining: number; is_premium: boolean }>(
        `/api/payments/${txId}/status/`
      );
      if (res.status === 'completed') {
        setPaymentStatus('completed');
        if (onPaymentSuccess) onPaymentSuccess();
      } else if (res.status === 'expired') {
        setPaymentStatus('expired');
      }
    } catch (e) {
      console.warn('Status poll error:', e);
    }
  }, [onPaymentSuccess]);

  // WebSocket connection & Polling setup when pending
  useEffect(() => {
    if (!paymentData || paymentStatus !== 'pending') return;

    const txId = paymentData.transaction_id;

    // 1. Establish WebSocket connection
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/payments/${txId}/`;
      
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.status === 'completed') {
            setPaymentStatus('completed');
            if (onPaymentSuccess) onPaymentSuccess();
          } else if (data.status === 'expired') {
            setPaymentStatus('expired');
          }
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };

      ws.onerror = () => {
        console.log('WebSocket connection fallback to polling.');
      };
    } catch (err) {
      console.log('WebSocket not supported or failed to connect:', err);
    }

    // 2. Fallback polling every 2.5 seconds
    pollingRef.current = setInterval(() => {
      checkStatus(txId);
    }, 2500);

    // 3. Immediate check on Window Focus / App return (when user switches back from Click/Payme)
    const handleFocus = () => {
      checkStatus(txId);
    };
    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleFocus);

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleFocus);
    };
  }, [paymentData, paymentStatus, checkStatus, onPaymentSuccess]);

  // 1-Second Countdown Timer
  useEffect(() => {
    if (paymentStatus !== 'pending') {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    timerRef.current = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          setPaymentStatus('expired');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [paymentStatus]);

  if (!isOpen) return null;

  const copyToClipboard = (text: string, type: 'amount' | 'card') => {
    navigator.clipboard.writeText(text);
    if (type === 'amount') {
      setCopiedAmount(true);
      setTimeout(() => setCopiedAmount(false), 2000);
    } else {
      setCopiedCard(true);
      setTimeout(() => setCopiedCard(false), 2000);
    }
  };

  const formatTimer = (totalSec: number) => {
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <>
      {/* If payment succeeded, display full celebratory animation */}
      {paymentStatus === 'completed' && (
        <PremiumCelebration
          isOpen={true}
          onClose={() => {
            if (onPaymentSuccess) onPaymentSuccess();
            onClose();
          }}
        />
      )}

      {/* Main Payment Step-by-Step Guide Modal */}
      {paymentStatus !== 'completed' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/75 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl max-w-md w-full p-5 sm:p-6 shadow-2xl border border-slate-200 space-y-4 max-h-[92vh] overflow-y-auto">
            
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 text-white shadow-md shadow-amber-500/20 flex items-center justify-center font-bold">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-slate-900 tracking-tight">
                    {t('pay_title')}
                  </h3>
                  <div className="text-xs text-slate-500 font-medium">
                    {t('pay_subtitle')}
                  </div>
                </div>
              </div>

              <button
                onClick={onClose}
                className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* State 1: Initiating / Loading */}
            {loading && (
              <div className="py-14 text-center space-y-3">
                <RefreshCw className="w-9 h-9 text-blue-600 animate-spin mx-auto" />
                <p className="text-xs font-semibold text-slate-600">
                  {t('pay_initiating')}
                </p>
              </div>
            )}

            {/* State 2: Error creating transaction */}
            {error && !loading && (
              <div className="py-6 text-center space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto border border-rose-200">
                  <AlertCircle className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-bold text-slate-900">{t('pay_error_title')}</h4>
                  <p className="text-xs text-slate-600">{error}</p>
                </div>
                <button
                  onClick={startPayment}
                  className="px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-bold shadow-xs hover:bg-blue-700 transition-all"
                >
                  {t('pay_try_again')}
                </button>
              </div>
            )}

            {/* State 3: Active Pending Payment - Polished Guide */}
            {!loading && !error && paymentData && paymentStatus === 'pending' && (
              <div className="space-y-4">
                
                {/* Countdown & Security Bar */}
                <div className="flex items-center justify-between p-2.5 rounded-xl bg-amber-50 border border-amber-200/80 text-amber-950 text-xs">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-amber-600 animate-pulse shrink-0" />
                    <span className="font-semibold text-xs">{t('pay_expires_in')}</span>
                  </div>
                  <span className="font-mono text-xs font-black text-amber-950 bg-amber-200/80 px-2.5 py-0.5 rounded-md border border-amber-300">
                    {formatTimer(secondsRemaining)}
                  </span>
                </div>

                {/* 1. Realistic Bank Card Graphic */}
                <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-white p-4 sm:p-5 shadow-xl border border-slate-700/60">
                  {/* Decorative card glow circles */}
                  <div className="absolute -right-8 -bottom-8 w-32 h-32 bg-blue-500/15 rounded-full blur-xl pointer-events-none" />
                  <div className="absolute -left-6 -top-6 w-28 h-28 bg-amber-500/10 rounded-full blur-xl pointer-events-none" />

                  {/* Top row: Chip, contactless waves, brand */}
                  <div className="flex items-center justify-between relative z-10 mb-4">
                    <div className="flex items-center gap-2">
                      {/* EMV Chip graphic */}
                      <div className="w-9 h-7 rounded-md bg-gradient-to-br from-amber-200 via-amber-400 to-amber-300 border border-amber-500/60 shadow-xs flex items-center justify-center p-0.5">
                        <div className="w-full h-full border border-amber-600/40 rounded-xs grid grid-cols-2 gap-0.5 opacity-80" />
                      </div>
                      <Wifi className="w-4 h-4 text-slate-300 rotate-90" />
                    </div>
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-200 bg-white/10 px-2 py-0.5 rounded-md backdrop-blur-xs border border-white/15">
                      {t('pay_card_type')}
                    </span>
                  </div>

                  {/* Card Number & Copy */}
                  <div className="relative z-10 space-y-1 mb-3.5">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      {t('pay_card_number')}
                    </span>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-base sm:text-lg font-mono font-bold tracking-widest text-white select-all">
                        {paymentData.card_number}
                      </span>
                      <button
                        onClick={() => copyToClipboard(paymentData.card_number.replace(/\s+/g, ''), 'card')}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shrink-0 shadow-sm ${
                          copiedCard 
                            ? 'bg-emerald-500 text-white' 
                            : 'bg-white/15 hover:bg-white/25 text-white backdrop-blur-xs border border-white/20 active:scale-95'
                        }`}
                      >
                        {copiedCard ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copiedCard ? t('pay_copied') : t('pay_copy')}</span>
                      </button>
                    </div>
                  </div>

                  {/* Card Holder */}
                  <div className="relative z-10 flex items-center justify-between pt-1 border-t border-white/10 text-xs">
                    <div>
                      <span className="text-[9px] uppercase tracking-wider text-slate-400 block font-semibold">
                        {t('pay_card_holder')}
                      </span>
                      <span className="font-mono font-bold text-slate-200 uppercase text-xs">
                        {paymentData.card_holder || 'TURSUNOV ASLIDDIN'}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] text-emerald-400 font-semibold bg-emerald-950/60 px-2 py-0.5 rounded-md border border-emerald-500/30">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>{t('pay_salt_badge')}</span>
                    </div>
                  </div>
                </div>

                {/* 2. EXACT Amount Box & Strict Red Warning */}
                <div className="bg-gradient-to-br from-amber-500/10 via-amber-500/5 to-transparent border-2 border-amber-500/30 rounded-2xl p-3.5 sm:p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                      {t('pay_exact_amount')}
                    </span>
                    <span className="text-[10px] font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full border border-amber-300">
                      Aniqlik muhim ⚡
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-2 bg-white border border-amber-300 rounded-xl p-3 shadow-xs">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight font-mono">
                        {paymentData.formatted_amount}
                      </span>
                      <span className="text-xs font-extrabold text-slate-500">UZS</span>
                    </div>

                    <button
                      onClick={() => copyToClipboard(String(paymentData.total_amount), 'amount')}
                      className={`px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shrink-0 shadow-sm ${
                        copiedAmount 
                          ? 'bg-emerald-600 text-white' 
                          : 'bg-amber-500 hover:bg-amber-600 text-white active:scale-95'
                      }`}
                    >
                      {copiedAmount ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      <span>{copiedAmount ? t('pay_copied') : t('pay_copy')}</span>
                    </button>
                  </div>

                  {/* Red strict warning notice */}
                  <div className="p-3 rounded-xl bg-rose-50 border-2 border-rose-300 text-xs text-rose-950 font-bold leading-relaxed shadow-xs flex items-start gap-2">
                    <span className="text-base shrink-0 leading-none">❗️</span>
                    <div>{t('pay_step2_warning')}</div>
                  </div>
                </div>

                {/* 3. Salt Explanation Box ("Nega 10 000 emas, 10 101 so'm?") */}
                <div className="bg-indigo-50/70 border border-indigo-200/90 rounded-2xl p-3.5 space-y-1.5">
                  <div className="flex items-center gap-2 text-indigo-950 font-bold text-xs">
                    <HelpCircle className="w-4 h-4 text-indigo-600 shrink-0" />
                    <span>{t('pay_salt_why_title', { amount: paymentData.formatted_amount })}</span>
                  </div>
                  <p className="text-[11px] text-indigo-900/80 leading-relaxed font-medium pl-6">
                    {t('pay_salt_why_desc', { 
                      salt: paymentData.salt, 
                      amount: paymentData.formatted_amount 
                    })}
                  </p>
                </div>

                {/* 4. Simple 3-Step Navigation */}
                <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3 text-xs text-slate-700 space-y-2">
                  <div className="font-bold text-slate-800 flex items-center gap-1.5">
                    <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center">i</span>
                    <span>Qanday to'lash mumkin?</span>
                  </div>
                  <ol className="space-y-1.5 text-[11px] text-slate-600 pl-6 list-decimal font-medium">
                    <li>Karta raqami va aniq summani nusxalang</li>
                    <li>Click, Payme, Uzum yoki boshqa ilovada o'tkazma qiling</li>
                    <li>Shu oynaga qayting — hisobingiz 2-3 soniyada avtomatik Premium bo'ladi!</li>
                  </ol>
                </div>

                {/* Live Waiting Pulse */}
                <div className="flex items-center justify-center gap-2.5 py-1 text-xs text-slate-500">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-600"></span>
                  </span>
                  <span className="font-bold text-slate-700 animate-pulse text-xs">
                    {t('pay_waiting')}
                  </span>
                </div>

                {/* Action Buttons */}
                <div className="pt-1">
                  <button
                    onClick={onClose}
                    className="w-full py-2.5 px-4 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all"
                  >
                    {t('pay_cancel')}
                  </button>
                </div>
              </div>
            )}

            {/* State 5: Expired */}
            {paymentStatus === 'expired' && (
              <div className="py-6 text-center space-y-4">
                <div className="w-14 h-14 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto border border-amber-200">
                  <Clock className="w-7 h-7" />
                </div>

                <div className="space-y-1.5">
                  <h4 className="text-sm font-black text-slate-900">
                    {t('pay_timeout')}
                  </h4>
                  <p className="text-xs text-slate-500 leading-relaxed max-w-xs mx-auto">
                    {t('pay_timeout_desc')}
                  </p>
                </div>

                <div className="pt-2 space-y-2">
                  <button
                    onClick={startPayment}
                    className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-all shadow-xs"
                  >
                    {t('pay_try_again')}
                  </button>
                  <button
                    onClick={onClose}
                    className="w-full py-2.5 px-4 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all"
                  >
                    {t('premium_close')}
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      )}
    </>
  );
};
