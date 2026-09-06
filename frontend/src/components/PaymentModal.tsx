import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  X, 
  Copy, 
  Check, 
  Clock, 
  Sparkles, 
  AlertCircle, 
  RefreshCw
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl max-w-sm w-full p-5 sm:p-6 shadow-2xl border border-slate-100 space-y-4 max-h-[92vh] overflow-y-auto">
            
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-amber-500 text-white flex items-center justify-center shadow-xs">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900">
                    {t('pay_title')}
                  </h3>
                  <p className="text-[11px] text-slate-500 font-medium">
                    {t('pay_subtitle')}
                  </p>
                </div>
              </div>

              <button
                onClick={onClose}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* State 1: Initiating / Loading */}
            {loading && (
              <div className="py-10 text-center space-y-2">
                <RefreshCw className="w-8 h-8 text-blue-600 animate-spin mx-auto" />
                <p className="text-xs font-semibold text-slate-600">
                  {t('pay_initiating')}
                </p>
              </div>
            )}

            {/* State 2: Error creating transaction */}
            {error && !loading && (
              <div className="py-6 text-center space-y-3">
                <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto border border-rose-200">
                  <AlertCircle className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-slate-900">{t('pay_error_title')}</h4>
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

            {/* State 3: Active Pending Payment - Clear 3 Steps */}
            {!loading && !error && paymentData && paymentStatus === 'pending' && (
              <div className="space-y-3.5">
                
                {/* Step 1: Card Number */}
                <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-3.5 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">
                      {t('pay_step1_title')}
                    </span>
                    <span className="text-[11px] text-slate-500 font-medium">
                      {t('pay_card_holder_label')} <strong className="text-slate-700">{paymentData.card_holder || 'Asliddin Tursunov'}</strong>
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-2 bg-white border border-slate-200 rounded-xl p-2.5">
                    <span className="text-base font-mono font-black text-slate-900 tracking-wider select-all">
                      {paymentData.card_number}
                    </span>
                    <button
                      onClick={() => copyToClipboard(paymentData.card_number.replace(/\s+/g, ''), 'card')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 shrink-0 ${
                        copiedCard 
                          ? 'bg-emerald-600 text-white' 
                          : 'bg-slate-900 hover:bg-slate-800 text-white active:scale-95'
                      }`}
                    >
                      {copiedCard ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedCard ? t('pay_copied') : t('pay_copy')}</span>
                    </button>
                  </div>

                  <p className="text-[11px] text-slate-500 leading-normal">
                    {t('pay_step1_desc')}
                  </p>
                </div>

                {/* Step 2: Payment Amount */}
                <div className="bg-amber-50/70 border border-amber-200/80 rounded-2xl p-3.5 space-y-2.5">
                  <span className="text-xs font-bold text-slate-900 block">
                    {t('pay_step2_title')}
                  </span>

                  <div className="flex items-center justify-between gap-2 bg-white border border-amber-300 rounded-xl p-2.5 shadow-xs">
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-black text-slate-900 font-mono">
                        {paymentData.formatted_amount}
                      </span>
                      <span className="text-xs font-bold text-slate-500">UZS</span>
                    </div>

                    <button
                      onClick={() => copyToClipboard(String(paymentData.total_amount), 'amount')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 shrink-0 ${
                        copiedAmount 
                          ? 'bg-emerald-600 text-white' 
                          : 'bg-amber-500 hover:bg-amber-600 text-white active:scale-95'
                      }`}
                    >
                      {copiedAmount ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedAmount ? t('pay_copied') : t('pay_copy')}</span>
                    </button>
                  </div>

                  {/* Red Warning & Explanation */}
                  <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 font-semibold leading-relaxed">
                    {t('pay_amount_warning')}
                  </div>
                </div>

                {/* Step 3: Return Here */}
                <div className="bg-emerald-50/60 border border-emerald-200/70 rounded-2xl p-3 text-xs space-y-1">
                  <span className="font-bold text-emerald-950 block">
                    {t('pay_step3_title')}
                  </span>
                  <p className="text-[11px] text-emerald-900/80 leading-normal">
                    {t('pay_step3_desc')}
                  </p>
                </div>

                {/* Live Waiting & Timer Bar */}
                <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
                    </span>
                    <span className="font-semibold text-slate-700 text-[11px]">
                      {t('pay_waiting')}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 font-mono text-xs font-bold text-slate-600">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>{formatTimer(secondsRemaining)}</span>
                  </div>
                </div>

                {/* Cancel Action */}
                <button
                  onClick={onClose}
                  className="w-full py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-semibold transition-all"
                >
                  {t('pay_cancel')}
                </button>
              </div>
            )}

            {/* State 4: Expired */}
            {paymentStatus === 'expired' && (
              <div className="py-6 text-center space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto border border-amber-200">
                  <Clock className="w-6 h-6" />
                </div>

                <div className="space-y-1">
                  <h4 className="text-sm font-bold text-slate-900">
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
