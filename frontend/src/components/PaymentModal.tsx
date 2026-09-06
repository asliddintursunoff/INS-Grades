import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  X, 
  Copy, 
  Check, 
  Clock, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  CreditCard, 
  ShieldCheck, 
  RefreshCw,
  ArrowRight
} from 'lucide-react';
import { apiCall } from '../api';
import { useLanguage } from '../i18n';

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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl max-w-sm w-full p-5 sm:p-6 shadow-2xl border border-slate-200 space-y-4 max-h-[92vh] overflow-y-auto">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center font-bold">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-extrabold text-slate-900">
                {t('pay_title')}
              </h3>
              <div className="text-[11px] text-slate-500 font-medium">
                P2P Automated Verification
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* State 1: Initiating / Loading */}
        {loading && (
          <div className="py-12 text-center space-y-3">
            <RefreshCw className="w-8 h-8 text-blue-600 animate-spin mx-auto" />
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
              <h4 className="text-sm font-bold text-slate-900">Error</h4>
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

        {/* State 3: Active Pending Payment */}
        {!loading && !error && paymentData && paymentStatus === 'pending' && (
          <div className="space-y-4">
            
            {/* Countdown Banner */}
            <div className="flex items-center justify-between p-3 rounded-2xl bg-amber-50/80 border border-amber-200/80 text-amber-950 text-xs">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-600 animate-pulse shrink-0" />
                <span className="font-semibold">{t('pay_expires_in')}</span>
              </div>
              <span className="font-mono text-sm font-black text-amber-900 bg-amber-200/60 px-2 py-0.5 rounded-lg">
                {formatTimer(secondsRemaining)}
              </span>
            </div>

            {/* Exact Amount Card */}
            <div className="bg-gradient-to-br from-blue-50/70 to-indigo-50/40 border border-blue-200/80 rounded-2xl p-4 text-center space-y-2">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                {t('pay_exact_amount')}
              </span>
              <div className="flex items-center justify-center gap-2">
                <span className="text-2xl font-black text-blue-700 tracking-tight">
                  {paymentData.formatted_amount}
                </span>
                <span className="text-xs font-bold text-slate-600">UZS</span>
                
                <button
                  onClick={() => copyToClipboard(String(paymentData.total_amount), 'amount')}
                  className="p-1.5 rounded-lg bg-white hover:bg-blue-100 text-blue-700 border border-blue-200 transition-colors shadow-2xs"
                  title="Copy amount"
                >
                  {copiedAmount ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Salt Note Warning */}
              <div className="text-[10.5px] text-slate-600 font-medium leading-relaxed bg-white/80 p-2.5 rounded-xl border border-blue-100 text-left">
                ⚠️ <strong>{t('pay_salt_note')}</strong>
              </div>
            </div>

            {/* Card Details Card */}
            <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3.5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">
                    {t('pay_card_number')}
                  </span>
                  <span className="text-sm font-black text-slate-800 font-mono tracking-wider">
                    {paymentData.card_number}
                  </span>
                </div>

                <button
                  onClick={() => copyToClipboard(paymentData.card_number.replace(/\s+/g, ''), 'card')}
                  className="px-2.5 py-1.5 rounded-xl bg-white hover:bg-slate-200 text-slate-700 border border-slate-200 text-xs font-bold transition-colors flex items-center gap-1 shadow-2xs"
                >
                  {copiedCard ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedCard ? t('pay_copied') : 'Copy'}</span>
                </button>
              </div>

              <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">{t('pay_card_holder')}:</span>
                <span className="font-bold text-slate-800">{paymentData.card_holder}</span>
              </div>
            </div>

            {/* Live Waiting Pulse */}
            <div className="flex items-center justify-center gap-2 py-1 text-xs text-slate-500">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-600"></span>
              </span>
              <span className="font-semibold text-slate-600 animate-pulse">
                {t('pay_waiting')}
              </span>
            </div>

            {/* Action Buttons */}
            <div className="pt-1 flex items-center gap-2">
              <button
                onClick={onClose}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all"
              >
                {t('pay_cancel')}
              </button>
            </div>
          </div>
        )}

        {/* State 4: Completed Success */}
        {paymentStatus === 'completed' && (
          <div className="py-6 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto border border-emerald-200 animate-in zoom-in-50 duration-300">
              <CheckCircle2 className="w-9 h-9" />
            </div>

            <div className="space-y-1.5">
              <h4 className="text-base font-black text-slate-900">
                {t('pay_success')}
              </h4>
              <p className="text-xs text-slate-600 leading-relaxed max-w-xs mx-auto">
                {t('pay_success_desc')}
              </p>
            </div>

            <div className="pt-2">
              <button
                onClick={onClose}
                className="w-full py-3 px-4 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-black shadow-xs flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
              >
                <span>Davom etish</span>
                <ArrowRight className="w-4 h-4" />
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
  );
};
